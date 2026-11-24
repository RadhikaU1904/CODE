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
    t = re.sub(r"(-?\d+\.\d+)\s?[AΔ△](?=\s|$)", r"\1 Δ", t)            # the picture often reads the Δ sign as 'A': '2.9A' -> '2.9 Δ'
    if not t: return None
    if re.fullmatch(rf"(?:(?:{ONE})\s*(?:Δ|△|pts)?\s*)+", t): return ("vals", [m.strip() for m in NUMS.findall(t)])
    m = re.match(rf"^(.*?[A-Za-z)%$])\s+((?:(?:{ONE})\s*(?:Δ|△|pts)?\s*)+)$", t)       # 'Pharmacy $406.3M -$1.9M' read as one piece
    if m and any(c.isdigit() for c in m.group(2)): return ("both", m.group(1).strip(), [x.strip() for x in NUMS.findall(m.group(2))])
    return ("name", t)
def to_lines(result, gap=None):
    """group pieces into lines: a piece joins a line only if it sits at the same height as that line's first piece
       (half a text-height apart at most), so two table rows that are close together are never glued into one"""
    items = []
    for b, t, s in (result or []):
        ys, xs = [p[1] for p in b], [p[0] for p in b]
        items.append((sum(ys) / 4, sum(xs) / 4, max(ys) - min(ys), t, float(s)))
    items.sort()
    lines = []                                   # each line: [anchor_y, height, [(x, t, s)]]
    for y, x, h, t, s in items:
        if lines and abs(y - lines[-1][0]) <= 0.5 * max(h, lines[-1][1]):
            lines[-1][2].append((x, t, s))
        else:
            lines.append([y, h, [(x, t, s)]])
    return [[(t, s) for x, t, s in sorted(ln[2])] for ln in lines]
def rows_from_lines(lines, page):
    rows = []
    for n, ln in enumerate(lines, 1):
        cur = None
        for t, s in ln:
            p = split_piece(t)
            if p is None: continue
            if p[0] == "name":
                cur = {"Page": page, "Line": n, "Name": p[1], "vals": [], "conf": []}; rows.append(cur)
            elif p[0] == "both":
                cur = {"Page": page, "Line": n, "Name": p[1], "vals": list(p[2]), "conf": [s] * len(p[2])}; rows.append(cur)
            else:
                if cur is None: cur = {"Page": page, "Line": n, "Name": "", "vals": [], "conf": []}; rows.append(cur)
                cur["vals"] += p[1]; cur["conf"] += [s] * len(p[1])
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
    all_lines.append(lines); rows += rows_from_lines(lines, i + 1)
width = max((len(r["vals"]) for r in rows), default=0)
for r in rows:
    v, c = r.pop("vals"), r.pop("conf")
    r["How many"] = len(v); r["Lowest confidence"] = round(min(c), 2) if c else None
    r["Kind"] = "Table row" if r["Name"] and len(v) >= 2 else ("Text only" if not v else "Other number")
    for k in range(width): r[f"Value {k+1}"] = v[k] if k < len(v) else ""
df = pd.DataFrame(rows)
metrics = df[df["Kind"] == "Table row"]
print(f"Pages read: {len(doc)}   |   table rows: {len(metrics)}  with {int(metrics['How many'].sum())} numbers   |   other numbers: {int(df[df['Kind']=='Other number']['How many'].sum())}")
print(metrics.groupby("Page").agg(Rows=("Name", "size"), Numbers=("How many", "sum")).to_string())

# COMMAND ----------

# STEP 4 - look at one page (change the number)
SHOW_PAGE = 1
display(metrics[metrics["Page"] == SHOW_PAGE])

# COMMAND ----------

# STEP 5 - the names that were jumbled in text mode: how does the picture read them?
for word in ["Deflation", "Lenses", "New Rx", "Rx Merch", "Rx Visits", "Vision NPS"]:
    hit = metrics[metrics["Name"].str.replace(" ", "").str.contains(word.replace(" ", ""), case=False, regex=False)]
    print(f"--- {word}: {len(hit)} row(s)")
    for _, r in hit.iterrows(): print(f"   page {r['Page']}: {r['Name']!r}  ->  {r['Value 1']}, {r['Value 2']}  ({r['How many']} numbers)")

# COMMAND ----------

# STEP 6 - save
out = f"{OUT_DIR}/PDF_extract_OCR_{datetime.date.today().isoformat()}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    metrics.to_excel(xl, sheet_name="Table rows", index=False)
    df[df["Kind"] != "Table row"].to_excel(xl, sheet_name="Everything else", index=False)
print("Saved:", out)