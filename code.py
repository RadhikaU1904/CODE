# Databricks notebook source
# Stage 2: Power BI PDF  vs  Databricks dashboard data.
# Compares tables and KPI cards. Charts and maps are not compared.
# Run "%pip install pdfplumber" in a cell above this one first.

# COMMAND ----------
PBI_PDF = "PASTE TODAY'S POWER BI PDF PATH"
VIEW = "`wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display"

# COMMAND ----------
import re
import pandas as pd

VAL = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"
ROW = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%$-]*?)\s+((?:{VAL}(?:\s+|$)){{2,}})$")
SKIP = ("trend", "map", "momentum")                    # charts and maps are not compared
ALIAS = {"pharmacyadj": "pharmacy", "visionunits": "visionunits", "rxscriptsadj": "rxadjscriptssold",
         "rxdeliveryorderreadysession": "orderreadysession", "rxdeliveryaddtocart": "addtocart",
         "rxdeliveryplacedorders": "placedorders", "mixedbasketdelivered": "mixedbasket"}
GEO = {"T": 0, "E": 1, "F": 2, "M": 3, "B": 4, "A": 5, "O": 6}   # Power BI column order: Total, E, F, M, B, A, O

def norm(s):
    k = re.sub(r"[^a-z0-9]", "", str(s).lower())
    return ALIAS.get(k, k)

def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()

def pbi_rows_from_text(pages):
    """pages: list of page texts (page 1 first) -> list of dicts"""
    out = []
    for p, text in enumerate(pages, 1):
        for line in (text or "").splitlines():
            m = ROW.search(line.strip())
            if m:
                vals = [clean(v) for v in re.findall(VAL, m.group(2))]
                out.append({"page": p, "name": m.group(1).strip(), "key": norm(m.group(1)), "vals": vals})
    return out

def num(v):
    return re.sub(r"[^0-9.$%KMB-]", "", str(v))

def status(d, p):
    if d == p: return "Match"
    return "Match – style only" if num(d) == num(p) else "No match"

def pbi_kpis(pages, page=6):
    """KPI cards on the Power BI Executive Summary page -> list of dicts, one per card, left to right"""
    lines = (pages[page - 1] or "").splitlines()
    start = next((i for i, l in enumerate(lines) if "MERCH SALES" in l and l.upper() == l), None)
    if start is None:
        return []
    actual = [clean(v) for v in re.findall(VAL, lines[start + 1])]
    cards = [{"Actual": a} for a in actual]
    for l in lines[start + 2:start + 8]:
        pairs = re.findall(rf"({VAL})\s+vs\s+(LY|Plan|LW)", l)
        if pairs:
            for k, (v, lab) in enumerate(pairs):
                if k // 2 < len(cards): cards[k // 2]["vs " + lab] = clean(v)
            break
        one = re.findall(VAL, l)
        if len(one) == 1 and cards: cards[0]["Excl. Rx AUR Deflation"] = clean(one[0])
    return cards

def compare_kpis(cards, dbx):
    k = dbx[(dbx["visual_id"].str.contains("kpi")) & (~dbx["col_key"].str.startswith("Trend"))].copy()
    order = {r: i for i, r in enumerate(k.sort_values("row_order")["row_label"].drop_duplicates())}
    out = []
    for r in k.sort_values(["row_order", "col_sort"]).itertuples():
        field, txt = r.col_key.split("|")[-1], clean(r.cell_text)
        if txt in ("", "NA"): continue
        i = order[r.row_label]
        pv = cards[i].get(field, "") if i < len(cards) else ""
        out.append({"visual_id": r.visual_id, "row": r.row_label, "geo": r.geo_name, "column": r.col_key,
                    "Databricks": txt, "Power BI": pv, "Match?": status(txt, pv) if pv else "Not found in PDF"})
    return out

def compare(pbi_rows, dbx, cards=()):
    """dbx: pandas DataFrame of the Databricks cells for week_choice = 'Latest'"""
    kpi_results = compare_kpis(list(cards), dbx)
    dbx = dbx[~dbx["visual_id"].str.contains("|".join(SKIP + ("kpi",)))].copy()
    dbx["page"] = dbx["visual_id"].str.extract(r"^p(\d+)_")[0].astype(int)
    dbx["g"] = dbx["geo_name"].fillna("Total").str[0].str.upper().map(GEO).fillna(9)
    dbx["m"] = dbx["col_key"].str.split("|").str[-1]
    dbx["cell_text"] = dbx["cell_text"].map(clean)
    used, results = set(), []
    for (vis, rlabel), grp in dbx.groupby(["visual_id", "row_label"], sort=False):
        page, key, best = int(grp["page"].iloc[0]), norm(rlabel), None
        # two possible column orders: Week,MTD,.. per metric  or  metric by metric
        orders = [grp.sort_values(["g", "col_sort"]), grp.sort_values(["g", "m", "col_sort"])]
        for o in orders:
            cells = [(r.geo_name, r.col_key, r.cell_text) for r in o.itertuples() if r.cell_text not in ("", "NA")]
            want = [c[2] for c in cells]
            for i, pr in enumerate(pbi_rows):
                if i in used or pr["page"] != page or pr["key"] != key: continue
                got = [v for v in pr["vals"] if v != "NA"]
                if len(got) < len(want): continue
                score = sum(num(a) == num(b) for a, b in zip(want, got))
                if best is None or score > best[0]: best = (score, got, i, cells)
        if best: used.add(best[2])
        cells = best[3] if best else [(r.geo_name, r.col_key, r.cell_text) for r in orders[0].itertuples() if r.cell_text not in ("", "NA")]
        for j, (geo, col, txt) in enumerate(cells):
            pv = best[1][j] if best else ""
            results.append({"visual_id": vis, "row": rlabel, "geo": geo, "column": col, "Databricks": txt,
                            "Power BI": pv, "Match?": status(txt, pv) if best else "Not found in PDF"})
    return pd.DataFrame(kpi_results + results)

# COMMAND ----------
import pdfplumber

with pdfplumber.open(PBI_PDF) as pdf:
    pages = [(p.dedupe_chars().extract_text() or "") for p in pdf.pages]
pbi_rows = pbi_rows_from_text(pages)
cards = pbi_kpis(pages)

dbx = spark.sql(f"""
  SELECT visual_id, row_order, row_label, col_sort, col_key, geo_name, cell_text
  FROM {VIEW} WHERE week_choice = 'Latest'
""").toPandas()

res = compare(pbi_rows, dbx, cards)

print("Power BI table rows read from PDF:", len(pbi_rows), "| KPI cards read:", len(cards))
print("Databricks cells compared:", len(res))
print(res["Match?"].value_counts().to_string())
display(spark.createDataFrame(res.groupby(["visual_id", "Match?"]).size().reset_index(name="cells")))
display(spark.createDataFrame(res[res["Match?"] != "Match"].astype(str)))