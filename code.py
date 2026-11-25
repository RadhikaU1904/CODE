# Databricks notebook source
# MAGIC %md
# MAGIC # Test: read the Power BI PDF as a picture (OCR), no manual list
# MAGIC Same idea as pdf_extract_any, but the page is read like a photo. Only reads the PDF and saves one Excel in your folder.

# COMMAND ----------

# MAGIC %pip install pypdfium2 rapidocr-onnxruntime openpyxl

# COMMAND ----------

# STEP 1 - the only thing you change
PDF_PATH = "/Workspace/Users/your.name/powerbi.pdf"
OUT_DIR  = "."

# COMMAND ----------

# STEP 2 - rules (nothing to change)
import re, datetime
import pandas as pd
ONE = r"-?\$?\d[\d,]*\.?\d*[KMB%]?|NA"                       # one number: $402.4M, -9.8%, 1,775, NA
NUMS = re.compile(rf"(?:{ONE})(?:\s*(?:Δ|△|pts))?")
def split_piece(t):
    """one piece of text from the picture -> ('name', text) or ('vals', [numbers])"""
    t = t.replace("−", "-").replace("–", "-").strip(" ▲▼↑↓")
    t = re.sub(r"(-?\d+\.\d+)\s?[AΔ△∆±]+(?=\s|$)", r"\1 Δ", t)       # the picture reads the Δ sign as 'A' or '±': '2.9A', '3.5 ±' -> '2.9 Δ'
    t = re.sub(r"(\d[KMB%]?)\s?[^\w\s$%.,()\-Δ]+(?=\s|$)", r"\1", t)       # any other stray symbol right after a number is dropped            # the picture often reads the Δ sign as 'A': '2.9A' -> '2.9 Δ'
    if not t: return None
    if re.fullmatch(rf"(?:(?:{ONE})\s*(?:Δ|△|pts)?\s*)+", t): return ("vals", [m.strip() for m in NUMS.findall(t)])
    m = re.match(rf"^(.*?[A-Za-z)%$])\s+((?:(?:{ONE})\s*(?:Δ|△|pts)?\s*)+)$", t)       # 'Pharmacy $406.3M -$1.9M' read as one piece
    if m and any(c.isdigit() for c in m.group(2)): return ("both", m.group(1).strip(), [x.strip() for x in NUMS.findall(m.group(2))])
    return ("name", t)
def to_lines(result, gap=None):
    """group pieces into lines: a piece joins a line only if it sits at the same height as that line's first piece
       (half a text-height apart at most), so two table rows that are close together are never glued into one.
       Then a line that has only numbers (no name) is joined to the closest line just above or below that has a name,
       if their numbers sit in different columns - this catches numbers printed a little higher or lower than their name."""
    items = []
    for b, t, s in (result or []):
        ys, xs = [p[1] for p in b], [p[0] for p in b]
        items.append((sum(ys) / 4, sum(xs) / 4, max(ys) - min(ys), max(xs) - min(xs), t, float(s)))
    items.sort()
    lines = []                                   # each line: [anchor_y, height, [(x, width, t, s)]]
    for y, x, h, w, t, s in items:
        if lines and abs(y - lines[-1][0]) <= 0.5 * max(h, lines[-1][1]):
            lines[-1][2].append((x, w, t, s))
        else:
            lines.append([y, h, [(x, w, t, s)]])
    has_name = lambda ln: any((split_piece(t) or ("vals",))[0] != "vals" for x, w, t, s in ln[2])
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not has_name(ln):
            best = None
            for j in (i - 1, i + 1):
                if 0 <= j < len(lines) and has_name(lines[j]):
                    d = abs(lines[j][0] - ln[0])
                    free = all(abs(x - x2) > 0.6 * ln[1] * 4 for x, _, _, _ in ln[2] for x2, _, _, _ in lines[j][2])
                    if d <= 1.2 * max(ln[1], lines[j][1]) and free and (best is None or d < best[1]): best = (j, d)
            if best:
                lines[best[0]][2] += ln[2]; lines.pop(i)
                if best[0] < i: continue
                continue
        i += 1
    return [sorted(ln[2]) for ln in lines]
def rows_from_lines(lines, page):
    """lines -> rows. Every number keeps its position (x, width) so we can check which table column it sits under."""
    rows = []
    for n, ln in enumerate(lines, 1):
        cur = None
        for x, w, t, s in ln:
            p = split_piece(t)
            if p is None: continue
            if p[0] == "name":
                cur = {"Page": page, "Line": n, "Name": p[1], "vals": [], "pos": [], "conf": []}; rows.append(cur); continue
            vals = p[2] if p[0] == "both" else p[1]
            if p[0] == "both":
                cur = {"Page": page, "Line": n, "Name": p[1], "vals": [], "pos": [], "conf": []}; rows.append(cur)
                pos = [None] * len(vals)                                   # numbers glued to a name: position unknown, always kept
            else:
                if cur is None:
                    cur = {"Page": page, "Line": n, "Name": "", "vals": [], "pos": [], "conf": []}; rows.append(cur)
                m = len(vals); left = x - w / 2                            # several numbers in one piece: share its width
                pos = [(left + w * (2 * k + 1) / (2 * m), w / m) for k in range(m)]
            cur["vals"] += vals; cur["pos"] += pos; cur["conf"] += [s] * len(vals)
    return rows

def header_lines(lines):
    """lines with only words (a table header like 'Week  MTD  QTD' or 'Actual  vs LY'): line number -> [(x, width, text)]"""
    out = {}
    for n, ln in enumerate(lines, 1):
        words, ok = [], True
        for x, w, t, s in ln:
            p = split_piece(t)
            if p is None: continue
            if p[0] == "name": words.append((x, w, p[1]))
            elif p[0] == "vals" and all(re.fullmatch(r"\d{1,2}", v) for v in p[1]): continue    # 'Week 43': a week number in a header is fine
            else: ok = False; break
        if ok and len(words) >= 2: out[n] = words
    return out

def use_headers(rows, lines):
    """For each row, find the table header above it: the nearest line of words whose words sit right above the row's numbers.
       Numbers that sit outside that header's columns (for example chart labels printed next to the table) are left out,
       and every kept number gets its column name. A row with no header found keeps all its numbers."""
    heads = header_lines(lines)
    def above(h, v):                                   # header word h sits above number v
        return abs(h[0] - v[0]) <= (h[1] + v[1]) / 2 + 0.25 * max(h[1], v[1])
    for r in rows:
        r["Columns"], r["Left out"] = "", ""
        known = [(p, k) for k, p in enumerate(r["pos"]) if p]
        if len(known) < 2: continue
        found = None
        for m in range(r["Line"] - 1, max(0, r["Line"] - 30), -1):
            if m in heads:
                hit = [h for h in heads[m] if any(above(h, p) for p, k in known)]
                if len(hit) >= 2: found = sorted(hit); break
        if not found: continue
        gaps = [b[0] - a[0] for a, b in zip(found, found[1:])]
        g = sorted(gaps)[len(gaps) // 2]                                   # usual space between two columns
        groups, cur = [], [found[0]]                                       # split the header words where a big gap starts
        for h, gap in zip(found[1:], gaps):
            if gap > 2.2 * g: groups.append(cur); cur = []
            cur.append(h)
        groups.append(cur)
        best = max(groups, key=lambda grp: sum(any(above(h, p) for h in grp) for p, k in known))
        if len(best) < 2: continue
        lo = min(h[0] - h[1] / 2 for h in best) - 0.5 * g
        hi = max(h[0] + h[1] / 2 for h in best) + 0.5 * g
        keep, cols, out = [], [], []
        for k, (v, p) in enumerate(zip(r["vals"], r["pos"])):
            if p and not (lo <= p[0] <= hi): out.append(v); continue
            keep.append(k)
            cols.append(min(best, key=lambda h: abs(h[0] - p[0]))[2] if p else "?")
        r["Left out"] = " ".join(out)
        r["Columns"] = " | ".join(cols)
        for key in ("vals", "pos", "conf"): r[key] = [r[key][k] for k in keep]
    return rows

# COMMAND ----------

# STEP 3 - read every page as a picture
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
ocr, doc, SCALE = RapidOCR(), pdfium.PdfDocument(PDF_PATH), 3
rows, all_lines = [], []
for i in range(len(doc)):
    img = doc[i].render(scale=SCALE).to_numpy()
    try: result = ocr(img, use_cls=False)[0]
    except TypeError: result = ocr(img)[0]
    lines = to_lines(result)
    all_lines.append(lines); rows += use_headers(rows_from_lines(lines, i + 1), lines)
width = max((len(r["vals"]) for r in rows), default=0)
for r in rows:
    v, c = r.pop("vals"), r.pop("conf"); r.pop("pos")
    r["How many"] = len(v); r["Lowest confidence"] = round(min(c), 2) if c else None
    one_letter = bool(r["Name"]) and re.fullmatch(r"[A-Za-z]\s?\d*", r["Name"].strip()) is not None    # map labels like 'R 52' or 'R56' are not metrics
    r["Kind"] = "Table row" if r["Name"] and len(v) >= 2 and not one_letter else ("Text only" if not v else "Other number")
    for k in range(width): r[f"Value {k+1}"] = v[k] if k < len(v) else ""
df = pd.DataFrame(rows)
metrics = df[df["Kind"] == "Table row"]
print(f"Pages read: {len(doc)}   |   table rows: {len(metrics)}  with {int(metrics['How many'].sum())} numbers   |   other numbers: {int(df[df['Kind']=='Other number']['How many'].sum())}")
print(f"rows where numbers outside the table columns were left out: {(metrics['Left out'] != '').sum()}")
print(metrics.groupby("Page").agg(Rows=("Name", "size"), Numbers=("How many", "sum")).to_string())

# COMMAND ----------

# STEP 4 - look at one page (change the number)
SHOW_PAGE = 1
display(metrics[metrics["Page"] == SHOW_PAGE])

# COMMAND ----------

# STEP 5 - the names that were jumbled in text mode: how does the picture read them?
for word in ["Total", "Deflation", "Lenses", "New Rx", "Rx Merch", "Rx Visits", "Vision NPS", "Vision Units"]:
    hit = metrics[metrics["Name"].str.replace(" ", "").str.contains(word.replace(" ", ""), case=False, regex=False)]
    print(f"--- {word}: {len(hit)} row(s)")
    for _, r in hit.iterrows():
        print(f"   page {r['Page']}: {r['Name']!r}  ->  {r['Value 1']}, {r['Value 2']}  ({r['How many']} numbers)")
        if r["Columns"]: print(f"        columns: {r['Columns']}")
        if r["Left out"]: print(f"        left out: {r['Left out']}")

# COMMAND ----------

# STEP 6 - save
out = f"{OUT_DIR}/PDF_extract_OCR_{datetime.date.today().isoformat()}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    metrics.to_excel(xl, sheet_name="Table rows", index=False)
    df[df["Kind"] != "Table row"].to_excel(xl, sheet_name="Everything else", index=False)
print("Saved:", out)