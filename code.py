# Databricks notebook source
# MAGIC %md
# MAGIC # Power BI PDF vs Databricks dashboard PDF
# MAGIC Reads both PDFs and compares the tables and KPI cards. Charts and maps are not compared.
# MAGIC It only reads the two PDF files. It does not touch any data.

# COMMAND ----------
# MAGIC %pip install pdfplumber pypdfium2 rapidocr-onnxruntime openpyxl

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: the two PDFs
# MAGIC Download both PDFs at the same time of day, then put their paths here.

# COMMAND ----------
PBI_PDF = "PASTE POWER BI PDF PATH"
DBX_PDF = "PASTE DATABRICKS DASHBOARD PDF PATH"
REPORT = "H&W Weekly Trade Report"
OUT_DIR = "."                     # folder for the Excel, chart and email text ("." = this notebook's folder)
TIMEZONE = "America/Chicago"

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
GLUED = re.compile(r"^(.*[A-Za-z)%])((?:-\$?|\$)\d[\d,]*\.?\d*[KMB%]?|\d[\d,]*\.\d+[KMB%]?)$")
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
                elif len(vals) >= 3:
                    out.append({"page": p, "name": "", "key": "", "vals": vals})
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
        if nx and r["key"] and nx["page"] == r["page"] and nx["key"] == r["key"] and len(r["vals"]) <= 2 and len(nx["vals"]) >= 6:
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
SYM = "▲▼↑↓△Δ"
UNITV = r"-?\$?\d[\d,]*\.?\d*[KMB%]"
def _multi(tok):
    """one word -> list of values inside it ('-0.7%0.5%' -> two values), or None if it is not only values"""
    s = tok.replace("−", "-").replace("–", "-").strip(SYM)
    if not s: return []
    out = []
    for part in re.split(r"(?<=[\dKMB%])(?=[-$])", s):
        if VALO.fullmatch(part): out.append(part)
        elif re.fullmatch(rf"(?:{UNITV})+(?:-?\$?\d[\d,]*\.?\d*)?", part):
            out += re.findall(rf"{UNITV}|-?\$?\d[\d,]*\.?\d*$", part)
        else: return None
    return [v for v in out if v]
def split_piece(t):
    """one piece of text read from the picture -> [('val', x) / ('name', x), ...] in reading order"""
    toks = t.split()
    a, pre = 0, []
    while a < len(toks) and _multi(toks[a]) is not None: pre += _multi(toks[a]); a += 1
    b, suf = len(toks), []
    while b > a and _multi(toks[b - 1]) is not None: suf = _multi(toks[b - 1]) + suf; b -= 1
    name = " ".join(toks[a:b])
    while name and suf and re.fullmatch(r"\d{1,2}", suf[0]): name += suf.pop(0)        # 'GLP 1' stays a name
    g = GLUED.match(name.replace(" ", "").replace("−", "-").replace("–", "-")) if name else None
    if g and _multi(g.group(2)): name, suf = g.group(1), _multi(g.group(2)) + suf
    return [("val", v) for v in pre] + ([("name", name)] if name else []) + [("val", v) for v in suf]
def ocr_value(t):
    p = split_piece(t)
    return p[0][1] if len(p) == 1 and p[0][0] == "val" else None
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
                for kind, x in split_piece(t):
                    if kind == "val":
                        if cur: cur["vals"].append(x); cur["conf"].append(s)
                        continue
                    k = raw(x)
                    if not k or any(w in k for w in IGNORE_TEXT): continue
                    cur = {"page": p, "name": x, "key": k, "vals": [], "conf": []}; out.append(cur)
    return [r for r in out if r["vals"]]
def dbx_kpis(lines):
    start = next((i for i, ln in enumerate(lines) if any(raw(t) == "hwmerchsales" for t, s in ln)), None)
    if start is None: return None
    vl = [[(x, s) for t, s in ln for kind, x in split_piece(t) if kind == "val"] for ln in lines[start + 1:start + 7]]
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
                found_by_values = False
                if d is None and best is not None:
                    cand = [(sum(num(a) == num(b) for a, b in zip(r["vals"][:n], best[2])), j) for j, r in enumerate(dbx_rows)
                            if j not in used_d and r["page"] == dp and len(r["vals"]) >= n]
                    if cand and max(cand)[0] >= max(3, -(-n * 6 // 10)):
                        dc = [(0, 0, max(cand)[1])]; d = dbx_rows[dc[0][2]]; found_by_values = "Databricks"
                if d and best is None:
                    for j, r in enumerate(pbi_rows):
                        if j in used_p or r["page"] != pp: continue
                        pv = [v for v in r["vals"] if v != "NA"] if present else r["vals"]
                        for o in range(len(pv) - n + 1):
                            sc = sum(num(a) == num(b) for a, b in zip(d["vals"], pv[o:o + n]))
                            if sc >= max(3, -(-n * 6 // 10)) and (best is None or sc > best[0][0]): best = ((sc, 0), j, pv[o:o + n]); found_by_values = True
                if d: used_d.add(min(dc)[2])
                if best: used_p.add(best[1])
                for q, ci in enumerate(idx):
                    dv, pv = (d["vals"][q] if d else ""), (best[2][q] if best else "")
                    if d and best:
                        st, note = verdict(dv, pv, d["conf"][q])
                        emit(table, label, cols[ci], dv, pv, st, note or ((f"Row name is unreadable in the {found_by_values if isinstance(found_by_values, str) else 'Power BI'} PDF; row found by its values." if found_by_values else "")))
                    else: emit(table, label, cols[ci], dv, pv, CHECK, "Row not readable in the " + ("Databricks" if not d else "Power BI") + " PDF.")
            else:   # geo: 7 business units x 2 columns, different order in the two reports
                dc = [(-dbx_name_ok(r["key"], names), j) for j, r in enumerate(dbx_rows) if j not in used_d and r["page"] == dp and dbx_name_ok(r["key"], names) and len(r["vals"]) >= 14]
                d = dbx_rows[min(dc)[1]] if dc else None
                pc = [(j, r) for j, r in enumerate(pbi_rows) if j not in used_p and r["page"] == pp and pbi_kind(r["key"], names) and len(r["vals"]) >= 12]
                def geo_score(r):
                    if not d: return 0
                    mm = max(0, 14 - len(r["vals"]))
                    return sum(num(d["vals"][BU_DBX.index(BU_PBI[q // 2]) * 2 + q % 2]) == num(r["vals"][q - mm]) for q in range(mm, 14))
                pj, p = max(pc, key=lambda x: geo_score(x[1])) if pc else (None, None)
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
# MAGIC ## Step 5: read the Databricks PDF as a picture, two times
# MAGIC The numbers in this PDF are pictures. Each page is read at two zoom levels. A number is trusted only if both reads agree.

# COMMAND ----------
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
doc = pdfium.PdfDocument(DBX_PDF)
reads = {}
for scale in (3, 4):
    lines = []
    for i in range(len(doc)):
        result, _ = ocr(doc[i].render(scale=scale).to_numpy())
        lines.append(ocr_lines(result, gap=25 * scale / 3))
    reads[scale] = lines
    print(f"Read at zoom {scale}: {sum(len(l) for pg in lines for l in pg)} pieces of text on {len(lines)} pages")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: compare
# MAGIC Both reads are compared with Power BI. If the two reads give a different Databricks number, the cell goes to **Check manually**.

# COMMAND ----------
def merge_reads(r1, r2):
    out = r1.copy()
    for i in range(len(out)):
        a, b = r1.at[i, "Databricks"], r2.at[i, "Databricks"]
        if num(a) != num(b):
            if not a and b:  out.loc[i] = r2.loc[i]                       # only the second read found the row
            elif a and b:    out.at[i, "Match?"] = CHECK; out.at[i, "Note"] = f"The two reads of the Databricks PDF disagree ({a} / {b})."
    return out
res = merge_reads(*[compare(dbx_rows_from_lines(reads[s]), reads[s][0], pbi_rows, pbi_pages) for s in (3, 4)])

import os, datetime as dt
from zoneinfo import ZoneInfo
now = dt.datetime.now(ZoneInfo(TIMEZONE)); TODAY = now.strftime("%Y-%m-%d")
TAB_NAMES = {1: "Executive Summary", 2: "Sales & Volume", 3: "Category & Operations", 4: "Geography", 5: "Rx Delivery"}   # Databricks PDF page -> tab
res["tab"] = res["table"].map({t[0]: TAB_NAMES[t[1]] for t in TABLES})
m = re.search(r"Last Updated\s*:?\s*([0-9/]+\s+[0-9:]+\s*[AP]M)", " ".join(pbi_pages)); PBI_TIME = m.group(1) if m else "not found in the PDF"
wk = next((t for ln in reads[3][0] for t, s in ln if "WEEKSHOWN" in t.upper().replace(" ", "")), "")
WEEK = re.sub(r"(?i)week\s*shown\s*:?\s*", "", wk).strip() or "week not read"
ORDER = ["Match", "Match – style only", "No match", CHECK]
n = res["Match?"].value_counts().reindex(ORDER, fill_value=0)
total, read = len(res), len(res) - n[CHECK]
PCT = (n["Match"] + n["Match – style only"]) / max(read, 1) * 100
print("Power BI last updated:", PBI_TIME, "| Week on the Databricks PDF:", WEEK)
print(f"{PCT:.1f}% the same (of the {read} cells read on both sides)  |  " + "  |  ".join(f"{k}: {v}" for k, v in n.items()))
by_tab = res.groupby("tab")["Match?"].value_counts().unstack(fill_value=0).reindex(index=list(TAB_NAMES.values()), columns=ORDER, fill_value=0)
display(spark.createDataFrame(by_tab.reset_index()))
display(spark.createDataFrame(res[res["Match?"] != "Match"].astype(str)))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 7: make the Excel

# COMMAND ----------
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
FILL = {"Match": "C6E0B4", "Match – style only": "FFE699", "No match": "F8CBAD", CHECK: "D9D9D9"}
FIX = {"Match": "No", "Match – style only": "No", "No match": "Investigate", CHECK: "Check manually"}
wb = Workbook(); ws = wb.active; ws.title = "Summary"
ws["A1"] = f"{REPORT}: Power BI PDF vs Databricks PDF (automated, tables and KPI cards)"; ws["A1"].font = Font(bold=True, size=14)
for i, (a, b) in enumerate([("Week", WEEK), ("Power BI last updated", PBI_TIME), ("Run on", now.strftime("%Y-%m-%d %I:%M %p")), ("Databricks side", "read from the PDF as a picture (OCR), two reads")], 2):
    ws.cell(i, 1, a); ws.cell(i, 2, b)
for j, h in enumerate(["Tab", "Compared"] + ORDER + ["Same number (of cells read)"], 1):
    c = ws.cell(7, j, h); c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3864")
for i, (tab, r) in enumerate(list(by_tab.iterrows()) + [("All tabs", n)], 8):
    vals = [tab, int(r.sum())] + [int(r[k]) for k in ORDER] + [(r["Match"] + r["Match – style only"]) / max(r.sum() - r[CHECK], 1)]
    for j, v in enumerate(vals, 1): ws.cell(i, j, v)
    ws.cell(i, len(vals)).number_format = "0.0%"
for col, w in zip("ABCDEFG", [34, 30, 12, 20, 12, 16, 28]): ws.column_dimensions[col].width = w
for tab in TAB_NAMES.values():
    sh = wb.create_sheet(tab)
    sh.append(["Metric / KPI", "Where it is", "Databricks value", "Power BI value", "Match?", "Fix needed?", "Comments"])
    for c in sh[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3864")
    for r in res[res["tab"] == tab].to_dict("records"):
        sh.append([f"{r['row']} – {r['column']}", r["table"], r["Databricks"], r["Power BI"], r["Match?"], FIX[r["Match?"]], r["Note"]])
        sh.cell(sh.max_row, 5).fill = PatternFill("solid", fgColor=FILL[r["Match?"]])
    for col, w in zip("ABCDEFG", [58, 28, 18, 18, 20, 16, 70]): sh.column_dimensions[col].width = w
    sh.freeze_panes = "A2"; sh.auto_filter.ref = f"A1:G{sh.max_row}"
XLSX = os.path.join(OUT_DIR, f"Validation_auto_{TODAY}.xlsx"); wb.save(XLSX); print("Excel saved:", XLSX)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 8: make the chart

# COMMAND ----------
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
COL = ["#2E9E5B", "#E8A93B", "#D64545", "#9AA0A6"]; INK, MUTED = "#1A1A1A", "#6B7280"
fig = plt.figure(figsize=(15, 7.6)); fig.patch.set_facecolor("white")
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.25], left=0.02, right=0.97, top=0.74, bottom=0.30, wspace=0.12)
ax = fig.add_subplot(gs[0, 0])
ax.pie([v for v in n if v], colors=[c for c, v in zip(COL, n) if v], startangle=90, counterclock=False, wedgeprops=dict(width=0.34, edgecolor="white", linewidth=3))
ax.text(0, 0, f"{PCT:.1f}%", ha="center", va="center", fontsize=38, fontweight="bold", color=INK)
ax.set_title("Overall (all tabs)", fontsize=15, fontweight="bold", color=INK, pad=10)
ax.text(0, -1.20, f"{n['Match']} match · {n['Match – style only']} style only · {n['No match']} no match · {n[CHECK]} to check", ha="center", va="top", fontsize=12, color=MUTED)
ax.text(0, -1.38, f"{total} numbers compared", ha="center", va="top", fontsize=11, color=MUTED)
bx = fig.add_subplot(gs[0, 1])
for xi, (tab, r) in enumerate(by_tab.iterrows()):
    tot, bottom = max(r.sum(), 1), 0
    for k, c in zip(ORDER, COL):
        h = r[k] / tot * 100
        if h > 0: bx.bar(xi, h, bottom=bottom, color=c, width=0.6, edgecolor="white", linewidth=2)
        bottom += h
    bx.text(xi, 102, f"{(r['Match'] + r['Match – style only']) / max(tot - r[CHECK], 1) * 100:.1f}%", ha="center", va="bottom", fontsize=14, fontweight="bold", color=INK)
    bx.text(xi, -4, tab.replace(" & ", " &\n"), ha="center", va="top", fontsize=12, color=INK)
    bx.text(xi, -17, f"{r['Match']} match\n{r['Match – style only']} style only\n{r['No match']} no match\n{r[CHECK]} to check", ha="center", va="top", fontsize=9.5, color=MUTED, linespacing=1.4)
bx.set_xlim(-0.6, len(by_tab) - 0.4); bx.set_ylim(0, 100); bx.axis("off")
bx.set_title("By tab", fontsize=15, fontweight="bold", color=INK, pad=34)
fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(COL, ORDER)], loc="lower right", bbox_to_anchor=(0.99, 0.015), frameon=False, fontsize=12, labelcolor=INK, ncol=4)
fig.text(0.03, 0.93, f"{REPORT} (Power BI vs Databricks)", fontsize=20, fontweight="bold", color=INK)
fig.text(0.03, 0.875, f"As of {now.strftime('%b %d, %Y %I:%M %p')}  ·  {WEEK}  ·  Power BI updated {PBI_TIME}", fontsize=11, color=MUTED)
fig.text(0.03, 0.03, "Automated PDF vs PDF check of tables and KPI cards. Charts and maps are not included.", fontsize=10, color=MUTED)
PNG = os.path.join(OUT_DIR, f"Validation_chart_{TODAY}.png"); plt.savefig(PNG, dpi=140); plt.show(); print("Chart saved:", PNG)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 9: the email text
# MAGIC Copy this into your email, paste the chart, and attach the Excel.

# COMMAND ----------
L = [f"Subject: {REPORT} Validation | Power BI vs Databricks | {WEEK} ({now.strftime('%b %d, %Y')})", "", "Hi Team,", "",
     f"Attached is the automated PDF vs PDF validation of the {REPORT} as of {now.strftime('%b %d, %Y')}. Power BI last updated: {PBI_TIME}.", "",
     f"Overall, {PCT:.1f}% of metrics are aligned, with {total} metrics compared (tables and KPI cards):", "",
     f"- {n['Match']} Matches", f"- {n['Match – style only']} Style/formatting differences only", f"- {n['No match']} Mismatches", f"- {n[CHECK]} to check manually", ""]
mm = res[res["Match?"] == "No match"].to_dict("records")
L += (["Mismatches:"] + [f"- {r['tab']}: {r['row']} – {r['column']} ({r['Databricks']} vs {r['Power BI']})" for r in mm]) if mm else ["No mismatches today."]
L += ["", "The attached Excel has the detailed results by tab.", "", "Thanks,"]
EMAIL = "\n".join(L); print(EMAIL)
_ = open(os.path.join(OUT_DIR, f"Validation_email_{TODAY}.txt"), "w", encoding="utf-8").write(EMAIL)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 10: why is a row in "Check manually"?
# MAGIC For each row the code could not read, this prints what the picture-reader saw near it. Send a photo of this if any row is still in Check manually.

# COMMAND ----------
todo = res[res["Match?"] == CHECK].drop_duplicates(["table", "row"])
print("Rows still in Check manually:", len(todo))
PAGE = {t[0]: t[1] for t in TABLES}
for r in todo.to_dict("records"):
    pg, key = PAGE[r["table"]], raw(r["row"])[:5]
    want = {num(v) for v in res[(res["table"] == r["table"]) & (res["row"] == r["row"])]["Power BI"] if v}
    print(f"\n=== {r['table']} / {r['row']} (Databricks PDF page {pg}) ===")
    for ln in reads[3][pg - 1]:
        if any(key in raw(t) or num(t.replace(" ", "")) in want for t, s in ln):
            print("   ", " | ".join(f"{t} [{s:.2f}]" for t, s in ln))