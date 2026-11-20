# Databricks notebook source
# MAGIC %md
# MAGIC # Power BI PDF vs Databricks dashboard PDF
# MAGIC Reads both PDFs and compares the tables and KPI cards. Charts and maps are not compared.
# MAGIC It only reads the two PDF files. It does not touch any data.

# COMMAND ----------
# MAGIC %pip install pdfplumber pypdfium2 rapidocr-onnxruntime

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: the two PDFs
# MAGIC Download both PDFs at the same time of day, then put their paths here.

# COMMAND ----------
PBI_PDF = "PASTE POWER BI PDF PATH"
DBX_PDF = "PASTE DATABRICKS DASHBOARD PDF PATH"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: report settings
# MAGIC Which tables to compare, on which page of each PDF, and the row names. For another report, only this cell changes.

# COMMAND ----------
import re, difflib
from collections import Counter
import pandas as pd

# ---------------- CONFIG: the only part that changes for another report ----------------
BU_DBX = ["Total", "A/I", "B", "E", "F", "M", "O"]          # column order in the Databricks PDF
BU_PBI = ["Total", "E", "F", "M", "B", "A/I", "O"]          # column order in the Power BI PDF
W6 = ["Actual (Week)", "vs Plan (Week)", "Comp % (Week)", "Actual (MTD)", "vs Plan (MTD)", "Comp % (MTD)"]
L6 = ["Actual (Week)", "vs LY (Week)", "Actual (MTD)", "vs LY (MTD)", "Actual (YTD)", "vs LY (YTD)"]
C5 = ["Merch $", "vs Plan", "vs LY", "Script/Units vs LY", "AUR vs LY"]
C15 = [f"{c} ({p})" for p in ("Week", "MTD", "YTD") for c in C5]
M4 = ["Week", "WoW %", "YTD", "YoY %"]
# (table, Databricks page, Power BI page, kind, columns, value types, rows)   row = "Name|other name@columns present"
TABLES = [
 ("KPI cards", 1, 6, "kpi", None, None, ["H&W Merch Sales", "Vision Merch Sales", "Pharmacy Adj. Scripts", "Rx Delivery GMV", "Rx Delivery Penetration"]),
 ("Scorecard", 1, 6, "plain", ["Comp % (Week)", "Comp % (MTD)", "Comp % (QTD)", "vs Plan (Week)", "vs Plan (MTD)", "vs Plan (QTD)"], None,
  ["H&W Total", "Excl. Rx AUR Deflation@0,1,2", "Pharmacy", "Vision", "Pharmacy Adj.Scripts", "Vision Units@0,1,2"]),
 ("Pharmacy Category (Exec)", 1, 6, "plain", C5, None, ["Total", "Generic", "Brand excl.GLP1", "GLP1"]),
 ("Net Sales", 2, 1, "plain", W6, "$$%$$%", ["Health & Wellness", "Excl. Rx AUR Deflation@0,2,3,5", "Pharmacy", "Vision"]),
 ("Script Sold", 2, 1, "plain", W6, "nn%nn%", ["Pharmacy|Pharmacy (Adj)", "Vision Units|Vision (Units)@0,2,3,5"]),
 ("Traffic", 2, 1, "plain", L6, "n%n%n%", ["Pharmacy", "Vision"]),
 ("Digital Pharmacy", 2, 1, "plain", L6, None, ["New Rx Accounts|Rx Accounts"]),
 ("Rx Delivery (S&V)", 2, 1, "plain", L6, None, ["New RxD Patient", "Rx Delivered Orders", "% RxD Penetration", "GMV Delivered"]),
 ("Pharmacy Category", 3, 2, "plain", C15, None, ["Total", "Generic", "Brand excl.GLP1", "GLP1"]),
 ("Vision Category", 3, 2, "plain", C15, None, ["Merch Total", "Frames", "Lenses", "Contact", "Other", "Warranty"]),
 ("Pharmacy Operations", 3, 2, "plain", ["Actual", "vs Plan", "vs LY", "vs LW"], None, ["Immunizations", "Central Fill Scripts", "Store Wage per Script (PPE)"]),
 ("Vision Operations", 3, 2, "plain", ["Actual", "vs LY", "vs LW"], None, ["AOD Exams", "Exam Conversions", "Warranty Conversion %"]),
 ("Geography Scorecard", 4, 3, "geo", ["Actual", "vs LY"], None,
  ["Rx Merch Sales ($)", "Rx Adj Scripts Sold|Rx Scripts (Adj)", "Rx Visits", "Rx NPS", "% RxD Penetration", "Vision Merch Sales ($)", "Vision Units", "Vision Visits", "Vision NPS"]),
 ("RxD Metrics", 5, 4, "plain", M4, None, ["RxD Scripts Count", "RxD Scripts per Order", "% RxD Penetration", "GMV Delivered", "Average Basket Size", "New RxD Patient", "Repeat RxD Patient"]),
 ("Rx Delivery Funnel", 5, 4, "plain", M4, None, ["Order Ready Session|Rx Delivery Order Ready Session", "Add to Cart|Rx Delivery Add to Cart", "Placed Orders|Rx Delivery Placed Orders", "Delivered Orders"]),
 ("Rx Delivery by Geography", 5, 4, "geo", ["Total", "WoW %"], None,
  ["Orders Delivered", "Orders Cancelled", "Cold Chain Orders", "RxD Scripts Count", "% RxD Penetration", "% Mixed Basket|% Mixed Basket (Delivered)", "Perfect Order Rate"]),
]
IGNORE_TEXT = ("beingvalidated", "previousstage")       # words inside a Databricks row that are not a row name
LOW_CONF = 0.90                                          # below this, a difference is "Check manually", not "No match"
CHECK = "Check manually"


# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: reading and comparing rules
# MAGIC This cell only defines the rules. Nothing runs yet.

# COMMAND ----------
# ---------------- small tools ----------------
VAL = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"
ROW = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%$-]*?)\s+((?:{VAL}(?:\s+|$)){{2,}})$")
VALO = re.compile(r"-?\$?\d[\d,]*\.?\d*[KMB%]?|NA")
def raw(s):    return re.sub(r"[^a-z0-9]", "", str(s).lower())
def clean(v):  return re.sub(r"\s+", " ", str(v or "")).strip()
def num(v):    return re.sub(r"[^0-9.$%KMB-]", "", str(v))
def digits(v): return "".join(ch for ch in str(v) if ch in "0123456789.-")
def type_ok(vals, types):
    if not types: return True
    for v, t in zip(vals, types):
        if v == "NA": continue
        if t == "$" and "$" not in v: return False
        if t == "%" and not v.endswith("%"): return False
        if t == "n" and ("$" in v or v.endswith("%")): return False
    return True
def spec(row):
    names, _, cols = row.partition("@")
    return names.split("|"), ([int(c) for c in cols.split(",")] if cols else None)

# ---------------- Power BI PDF (text) ----------------
def unshuffle(s):
    if len(s) < 6 or len(s) % 2 or any(c % 2 for c in Counter(s).values()): return None
    def go(i, pend, t):
        if i == len(s): return t if not pend else None
        if pend and pend[0] == s[i]:
            r = go(i + 1, pend[1:], t)
            if r is not None: return r
        return go(i + 1, pend + s[i], t + s[i]) if len(t) < len(s) // 2 else None
    return go(0, "", "")
def preclean(line):
    toks = [(unshuffle(t) or t) if any(c.isdigit() for c in t) else t for t in line.split(" ")]
    line = re.sub(r"(\d\.)\s+(\d)", r"\1\2", " ".join(toks))
    return re.sub(r"(\d) %(?=\s+[-$\d]|\s*$)", r"\1%", line)
def pbi_rows_from_text(pages):
    out, only_vals = [], re.compile(rf"(?:{VAL}\s*)+")
    for p, text in enumerate(pages, 1):
        names = []
        for n, line in enumerate((text or "").splitlines()):
            line = preclean(line).strip()
            if only_vals.fullmatch(line):
                vals = [clean(v) for v in re.findall(VAL, line)]
                owner = next((x for x in reversed(names) if n - x[0] <= 3 and not x[2]), None)
                if len(vals) >= 3 and owner:
                    owner[2] = True
                    out.append({"page": p, "name": owner[1], "key": raw(owner[1]), "vals": vals})
                continue
            m = ROW.search(line)
            if m:
                out.append({"page": p, "name": m.group(1).strip(), "key": raw(m.group(1)), "vals": [clean(v) for v in re.findall(VAL, m.group(2))]})
                names.append([n, m.group(1).strip(), False])
            elif line and len(line) <= 40 and not re.search(r"\d", line):
                names.append([n, line, False])
    merged, i = [], 0
    while i < len(out):
        r, nx = out[i], out[i + 1] if i + 1 < len(out) else None
        if nx and nx["page"] == r["page"] and nx["key"] == r["key"] and len(r["vals"]) <= 2 and len(nx["vals"]) >= 6:
            merged.append({**r, "vals": r["vals"] + nx["vals"]}); i += 2
        else:
            merged.append(r); i += 1
    return merged
def subseq(a, b):
    it = iter(b); return all(ch in it for ch in a)
def pbi_kind(k, names):
    cs = [raw(n) for n in names]
    if k in cs: return "exact"
    for c in cs:
        if sorted(k) == sorted(c * 2): return "doubled"
        if k.startswith(c) and any(ch.isdigit() for ch in k[len(c):]): return "jumble"
        if len(c) >= 8 and k.endswith(c): return "suffix"
        if len(c) < len(k) <= 2 * len(c) and k[:3] == c[:3] and k[-5:] == c[-5:] and subseq(c, k): return "fuzzy"
    return None
def pbi_kpis(pages, page):
    lines = (pages[page - 1] or "").splitlines()
    start = next((i for i, l in enumerate(lines) if "MERCH SALES" in l and l.upper() == l), None)
    if start is None: return []
    cards = [{"Actual": clean(a)} for a in re.findall(VAL, lines[start + 1])]
    for l in lines[start + 2:start + 8]:
        pairs = re.findall(rf"({VAL})\s+vs\s+(LY|Plan|LW)", l)
        if pairs:
            for k, (v, lab) in enumerate(pairs):
                if k // 2 < len(cards): cards[k // 2]["vs " + lab] = clean(v)
            break
        one = re.findall(VAL, l)
        if len(one) == 1 and cards: cards[0]["Excl. Rx AUR Deflation"] = clean(one[0])
    return cards

# ---------------- Databricks PDF (read as a picture, OCR) ----------------
def ocr_value(t):
    s = t.replace(" ", "").replace("−", "-").replace("–", "-").lstrip("▲▼↑↓△").rstrip("△Δ▲")
    return s if VALO.fullmatch(s) else None
def ocr_lines(result, gap=25):
    """OCR result of one page -> lines of (text, confidence), top to bottom, left to right"""
    items = sorted((sum(p[1] for p in b) / 4, sum(p[0] for p in b) / 4, t, float(s)) for b, t, s in (result or []))
    lines, cur, last = [], [], None
    for y, x, t, s in items:
        if last is not None and y - last > gap:
            lines.append(cur); cur = []
        cur.append((x, t, s)); last = y
    if cur: lines.append(cur)
    return [[(t, s) for x, t, s in sorted(ln)] for ln in lines]
def dbx_rows_from_lines(pages_lines):
    out = []
    for p, lines in enumerate(pages_lines, 1):
        for ln in lines:
            cur = None
            for t, s in ln:
                v = ocr_value(t)
                if v is not None:
                    if cur: cur["vals"].append(v); cur["conf"].append(s)
                    continue
                k = raw(t)
                if not k or any(w in k for w in IGNORE_TEXT): continue
                cur = {"page": p, "name": t, "key": k, "vals": [], "conf": []}; out.append(cur)
    return [r for r in out if r["vals"]]
def dbx_kpis(lines):
    start = next((i for i, ln in enumerate(lines) if any(raw(t) == "hwmerchsales" for t, s in ln)), None)
    if start is None: return None
    vl = [[(ocr_value(t), s) for t, s in ln if ocr_value(t) is not None] for ln in lines[start + 1:start + 7]]
    a = next((v for v in vl if len(v) >= 5), None)
    b = next((v for v in vl if len(v) >= 10 and v is not a), None)
    if not a or not b or len(a) != 6: return None
    act, b = [a[0], a[2], a[3], a[4], a[5]], b[-10:]
    cards = []
    for i in range(5):
        c = {"Actual": act[i], ("vs LY"): b[2 * i], ("vs Plan" if i < 3 else "vs LW"): b[2 * i + 1]}
        if i == 0: c["Excl. Rx AUR Deflation"] = a[1]
        cards.append(c)
    return cards

# ---------------- compare ----------------
def verdict(d, p, conf=1.0):
    if num(d) == num(p): return ("Match – style only" if p.endswith("pts") else "Match"), ""
    if conf < LOW_CONF: return CHECK, f"Databricks value was read from the picture with low confidence ({conf:.2f})."
    return "No match", ""
def dbx_name_ok(k, names):
    cs = [raw(n) for n in names]
    if k in cs: return 2
    return 1 if any(difflib.SequenceMatcher(None, k, c).ratio() >= 0.88 for c in cs) else 0

def compare(dbx_rows, dbx_page1_lines, pbi_rows, pbi_pages):
    res, used_d, used_p = [], set(), set()
    def emit(t, r, c, d, p, st, note=""): res.append({"table": t, "row": r, "column": c, "Databricks": d, "Power BI": p, "Match?": st, "Note": note})
    for table, dp, pp, kind, cols, types, rows in TABLES:
        if kind == "kpi":
            dc, pc = dbx_kpis(dbx_page1_lines), pbi_kpis(pbi_pages, pp)
            for i, r in enumerate(rows):
                fields = ["Actual"] + (["Excl. Rx AUR Deflation"] if i == 0 else []) + ["vs LY", "vs Plan" if i < 3 else "vs LW"]
                for f in fields:
                    d = dc[i].get(f) if dc else None; p = pc[i].get(f) if i < len(pc) else None
                    if not d or not p: emit(table, r, f, d[0] if d else "", p or "", CHECK, "KPI card could not be read on one side.")
                    else: emit(table, r, f, d[0], p, *verdict(d[0], p, d[1]))
            continue
        for row in rows:
            names, present = spec(row); label = names[0]
            if kind == "plain":
                idx = present or list(range(len(cols))); n = len(idx); ty = [types[i] for i in idx] if types else None
                dc = [(-dbx_name_ok(r["key"], names), len(r["vals"]), j) for j, r in enumerate(dbx_rows) if j not in used_d and r["page"] == dp
                      and dbx_name_ok(r["key"], names) and len(r["vals"]) >= n and type_ok(r["vals"][:n], ty)]
                d = dbx_rows[min(dc)[2]] if dc else None
                best = None
                for j, r in enumerate(pbi_rows):
                    if j in used_p or r["page"] != pp or not pbi_kind(r["key"], names): continue
                    pv = [v for v in r["vals"] if v != "NA"] if present else r["vals"]
                    if len(pv) < n or not type_ok(pv[:n], ty): continue
                    sc = sum(num(a) == num(b) for a, b in zip(d["vals"], pv[:n])) if d else 0
                    if best is None or (sc, -len(pv)) > best[0]: best = ((sc, -len(pv)), j, pv[:n])
                if d: used_d.add(min(dc)[2])
                if best: used_p.add(best[1])
                for q, ci in enumerate(idx):
                    dv, pv = (d["vals"][q] if d else ""), (best[2][q] if best else "")
                    if d and best: emit(table, label, cols[ci], dv, pv, *verdict(dv, pv, d["conf"][q]))
                    else: emit(table, label, cols[ci], dv, pv, CHECK, "Row not readable in the " + ("Databricks" if not d else "Power BI") + " PDF.")
            else:   # geo: 7 business units x 2 columns, different order in the two reports
                dc = [(-dbx_name_ok(r["key"], names), j) for j, r in enumerate(dbx_rows) if j not in used_d and r["page"] == dp and dbx_name_ok(r["key"], names) and len(r["vals"]) >= 14]
                d = dbx_rows[min(dc)[1]] if dc else None
                pc = [(j, r) for j, r in enumerate(pbi_rows) if j not in used_p and r["page"] == pp and pbi_kind(r["key"], names) and len(r["vals"]) >= 12]
                pj, p = pc[0] if pc else (None, None)
                if d: used_d.add(min(dc)[1])
                if p: used_p.add(pj)
                m = max(0, 14 - len(p["vals"])) if p else 0          # Total cells sitting on top of the row name in the Power BI PDF
                for q in range(14):
                    bu, col = BU_PBI[q // 2], cols[q % 2]
                    di = BU_DBX.index(bu) * 2 + q % 2
                    dv = d["vals"][di] if d else ""
                    cname = f"{bu} · {col}"
                    if not d or not p: emit(table, label, cname, dv, "", CHECK, "Row not readable in the " + ("Databricks" if not d else "Power BI") + " PDF."); continue
                    if q < m:
                        want = "".join(digits(d["vals"][BU_DBX.index("Total") * 2 + z]) for z in range(m)).replace("-", "")
                        ok = digits(p["name"]).replace("-", "") == want
                        emit(table, label, cname, dv, digits(dv) if ok else digits(p["name"]), "Match" if ok else CHECK, "Total sits on top of the row name in the Power BI PDF; compared on digits only.")
                    else:
                        pv = p["vals"][q - m]; emit(table, label, cname, dv, pv, *verdict(dv, pv, d["conf"][di]))
    return pd.DataFrame(res)

print("Rules are ready.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: read the Power BI PDF (as text)

# COMMAND ----------
import pdfplumber
with pdfplumber.open(PBI_PDF) as pdf:
    pbi_pages = [(p.dedupe_chars().extract_text() or "") for p in pdf.pages]
pbi_rows = pbi_rows_from_text(pbi_pages)
print("Power BI pages:", len(pbi_pages), "| table rows read:", len(pbi_rows))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: read the Databricks PDF (as a picture)
# MAGIC The numbers in this PDF are pictures, so each page is read like eyes would read it. This takes a few minutes.

# COMMAND ----------
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
doc = pdfium.PdfDocument(DBX_PDF)
dbx_lines = []
for i in range(len(doc)):
    result, _ = ocr(doc[i].render(scale=3).to_numpy())
    dbx_lines.append(ocr_lines(result))
    print(f"Databricks page {i+1}: {sum(len(l) for l in dbx_lines[-1])} pieces of text read")
dbx_rows = dbx_rows_from_lines(dbx_lines)
print("Databricks table rows read:", len(dbx_rows))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: compare

# COMMAND ----------
res = compare(dbx_rows, dbx_lines[0], pbi_rows, pbi_pages)
n = res["Match?"].value_counts()
same = n.get("Match", 0) + n.get("Match – style only", 0)
read = len(res) - n.get(CHECK, 0)
print("Cells compared:", len(res))
print(n.to_string())
print(f"Of the {read} cells read on both sides, {same / max(read, 1) * 100:.1f}% are the same.")
display(spark.createDataFrame(res.groupby(["table", "Match?"]).size().reset_index(name="cells")))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 7: the differences

# COMMAND ----------
display(spark.createDataFrame(res[res["Match?"] != "Match"].astype(str)))