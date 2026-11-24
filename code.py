# Databricks notebook source
# MAGIC %md
# MAGIC # PDF extractor - no manual list
# MAGIC Give one PDF path. The code reads every page and pulls out **every name and its numbers**.
# MAGIC Nothing about the report is typed by hand. It only reads the PDF and saves one Excel in your own folder.

# COMMAND ----------

# MAGIC %pip install pdfplumber openpyxl

# COMMAND ----------

# STEP 1 - the only thing you change: the PDF path
PDF_PATH = "/Workspace/Users/your.name/powerbi.pdf"
OUT_DIR  = "."

# COMMAND ----------

# STEP 2 - the rules (same for every report, nothing to change)
import re, datetime
from collections import Counter
import pandas as pd, pdfplumber

VAL  = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"          # what a number looks like: $402.4M, -9.8%, 5.6M, 1,775, NA
ROW  = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%$:'+-]*?)\s+((?:{VAL}(?:\s+|$))+)$")   # name, then numbers
ONLY = re.compile(rf"(?:{VAL}\s*)+")                                   # a line that is only numbers
DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}:\d{2}")

def clean(v): return re.sub(r"\s+", " ", str(v or "")).strip()

def unshuffle(s):
    """Power BI sometimes prints the same text twice on top of itself ('FramFreasmes'). This gives back 'Frames'."""
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
    line = re.sub(r"(\d\.)\s+(\d)", r"\1\2", " ".join(toks))          # '12. 1%' -> '12.1%'
    return re.sub(r"(\d) %(?=\s+[-$\d]|\s*$)", r"\1%", line)           # '11.4 %' -> '11.4%'

def fix_name(name):
    """returns (name, note). If the name was printed twice on top of itself, un-double it. If it still looks broken, say so."""
    fixed = unshuffle(name.replace(" ", ""))
    if fixed and len(fixed) >= 3: return fixed, "name was doubled in the PDF, fixed"
    def bad(tok):
        parts = [w for w in re.split(r"[./()-]+", tok) if w]
        return any(re.search(r"[a-z][A-Z]", w) and not w.startswith("Rx") for w in parts) \
               or any(re.search(r"[a-z]\d|\d[a-z]|\$\d|\d\$", w) for w in parts)
    toks = name.split()
    first_bad = next((i for i, t in enumerate(toks) if bad(t)), None)
    odd = first_bad is not None
    if odd and first_bad >= 2:          # 'Rx Merch Sales ($) R$x4 M06e...' -> keep the clean start
        if first_bad >= 3 and toks[first_bad - 1] == toks[0]: first_bad -= 1     # the second copy of the name had started
        return " ".join(toks[:first_bad]), "name was partly jumbled in the PDF, kept the clean part - the first number of this row may be missing"
    return name, ("name looks jumbled in the PDF - check" if odd else "")

def extract_page(text, page):
    """one page of text -> list of rows (name + numbers) and list of plain text lines"""
    rows, texts, last_text = [], [], None            # last_text = [line number, text] of the nearest line without numbers
    for n, line in enumerate((text or "").splitlines(), 1):
        line = preclean(clean(line))
        if not line: continue
        if DATE.search(line):                         # dates and times are text, not metrics
            texts.append({"Page": page, "Line": n, "Text": line}); continue
        if ONLY.fullmatch(line):                      # only numbers: the name is the text just above it
            vals  = [clean(v) for v in re.findall(VAL, line)]
            above = last_text[1] if last_text and n - last_text[0] <= 3 else ""
            rows.append({"Page": page, "Line": n, "Text above": above, "Name": "", "vals": vals,
                         "Note": "numbers only on this line - name is in 'Text above'" if above else "numbers with no name near them (may be a chart)"})
            continue
        pairs = re.findall(rf"({VAL})\s+(vs\s+\w+)", line)   # KPI card line: '0.6% vs LY -$9.8M vs Plan'
        if pairs and not re.sub(rf"{VAL}\s+vs\s+\w+", "", line).strip():
            rows.append({"Page": page, "Line": n, "Text above": last_text[1] if last_text else "", "Name": "",
                         "vals": [clean(v) for v, _ in pairs], "Note": "labels in order: " + " | ".join(clean(l) for _, l in pairs)})
            continue
        m = ROW.search(line)
        if m:
            name, note = fix_name(m.group(1).strip())
            before = line[:m.start()].strip()
            if before: note = (note + "; " if note else "") + f"extra text before the name: {before}"
            rows.append({"Page": page, "Line": n, "Text above": last_text[1] if last_text else "", "Name": name,
                         "vals": [clean(v) for v in re.findall(VAL, m.group(2))], "Note": note})
        else:
            texts.append({"Page": page, "Line": n, "Text": line})
            if len(line) <= 80: last_text = [n, line]
    return rows, texts

def extract_pdf(path):
    rows, texts, empty = [], [], []
    with pdfplumber.open(path) as pdf:
        for p, page in enumerate(pdf.pages, 1):
            text = page.dedupe_chars().extract_text() or ""
            if len(text.strip()) < 20: empty.append(p)
            r, t = extract_page(text, p); rows += r; texts += t
    width = max((len(r["vals"]) for r in rows), default=0)
    for r in rows:
        for i in range(width): r[f"Value {i+1}"] = r["vals"][i] if i < len(r["vals"]) else ""
        vals = r.pop("vals"); n = len(vals); r["How many"] = n
        ints = [int(v) for v in vals if re.fullmatch(r"\d{1,3}", v)]
        axis = len(ints) == n and n >= 3 and all(b - a == 1 for a, b in zip(ints, ints[1:]))      # 32 33 34 ... = chart axis
        label = n == 1 and len(ints) == 1 and bool(r["Name"])                                    # 'Week 43', 'R 53' = a label, not a metric
        short = bool(r["Name"]) and re.fullmatch(r"[A-Za-z]", r["Name"].split()[0]) is not None   # map labels 'R 54 ...'
        if axis or label or short: r["Name"], r["Text above"], r["Note"] = "", "", ""
        if r["Name"] and n >= 2:                         r["Kind"] = "Table row"
        elif r["Name"]:                                  r["Kind"] = "Name with one number"
        elif r["Text above"] and (n >= 3 or r["Note"].startswith("labels")): r["Kind"] = "Numbers under a heading"
        else:                                            r["Kind"] = "Loose number (chart label)"
        if r["Kind"] == "Loose number (chart label)":    r["Note"] = ""
    cols = ["Page", "Line", "Kind", "Text above", "Name", "How many"] + [f"Value {i+1}" for i in range(width)] + ["Note"]
    return pd.DataFrame(rows, columns=cols), pd.DataFrame(texts, columns=["Page", "Line", "Text"]), empty

# COMMAND ----------

# STEP 3 - read the PDF
rows, texts, empty = extract_pdf(PDF_PATH)
metrics = rows[rows["Kind"] != "Loose number (chart label)"]          # tables and KPI cards
loose   = rows[rows["Kind"] == "Loose number (chart label)"]          # chart labels, axis numbers
print(f"Metric rows (tables and cards): {len(metrics)}  with {int(metrics['How many'].sum())} numbers   |   loose chart numbers: {int(loose['How many'].sum())}   |   text lines: {len(texts)}")
if empty: print(f"NOTE: page(s) {empty} have almost no text (a picture or an empty page).")
print(rows.groupby(["Page", "Kind"]).agg(Rows=("Name", "size"), Numbers=("How many", "sum")).to_string())

# COMMAND ----------

# STEP 4 - look at one page: only the metric rows (change the number to see another page)
SHOW_PAGE = 1
pd.set_option("display.max_rows", 500, "display.max_columns", 50, "display.width", 250, "display.max_colwidth", 45)
display(metrics[metrics["Page"] == SHOW_PAGE].drop(columns=["Note"]))

# COMMAND ----------

# STEP 5 - metric rows the code is not sure about
display(metrics[metrics["Note"] != ""][["Page", "Line", "Kind", "Name", "Value 1", "Note"]])

# COMMAND ----------

# STEP 6 - save one Excel
TODAY = datetime.date.today().isoformat()
out = f"{OUT_DIR}/PDF_extract_{TODAY}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xl:
    metrics.to_excel(xl, sheet_name="Metrics - all pages", index=False)
    for p in sorted(metrics["Page"].unique()):
        metrics[metrics["Page"] == p].to_excel(xl, sheet_name=f"Page {p}", index=False)
    loose.to_excel(xl, sheet_name="Chart numbers", index=False)
    texts.to_excel(xl, sheet_name="Other text", index=False)
print("Saved:", out)