# Databricks notebook source
# Stage 2 (version 3): Power BI PDF  vs  Databricks dashboard data.
# Compares tables and KPI cards. Charts and maps are not compared.
# Read-only: it only runs SELECT on the view and reads the PDF.
# Run "%pip install pdfplumber" in a cell above this one first.

# COMMAND ----------
PBI_PDF = "PASTE TODAY'S POWER BI PDF PATH"
VIEW = "`wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display"

# COMMAND ----------
import re
from collections import Counter
import pandas as pd

VAL = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"
ROW = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%$-]*?)\s+((?:{VAL}(?:\s+|$)){{2,}})$")
SKIP = ("trend", "map", "momentum", "kpi")              # charts and maps are not compared; KPI cards have their own reader
ALIAS = {"pharmacyadj": "pharmacy", "rxscriptsadj": "rxadjscriptssold",          # Power BI name -> Databricks name
         "rxdeliveryorderreadysession": "orderreadysession", "rxdeliveryaddtocart": "addtocart",
         "rxdeliveryplacedorders": "placedorders", "mixedbasketdelivered": "mixedbasket"}
GEO = {"T": 0, "E": 1, "F": 2, "M": 3, "B": 4, "A": 5, "O": 6}                   # Power BI column order
CHECK = "Check manually"

def raw(s):    return re.sub(r"[^a-z0-9]", "", str(s).lower())
def clean(v):  return re.sub(r"\s+", " ", str(v or "")).strip()
def num(v):    return re.sub(r"[^0-9.$%KMB-]", "", str(v))
def digits(v): return "".join(ch for ch in str(v) if ch in "0123456789.-")

def status(d, p):
    if d == p: return "Match"
    return "Match – style only" if num(d) == num(p) else "No match"

def unshuffle(s):
    """'--$$330055..77MM' -> '-$305.7M' (the PDF sometimes prints a value twice on top of itself)"""
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
    out = []
    for p, text in enumerate(pages, 1):
        for line in (text or "").splitlines():
            m = ROW.search(preclean(line).strip())
            if m:
                out.append({"page": p, "name": m.group(1).strip(), "key": raw(m.group(1)),
                            "vals": [clean(v) for v in re.findall(VAL, m.group(2))]})
    merged, i = [], 0                      # a Total line followed by its BU line (same name) is one table row
    while i < len(out):
        r, nx = out[i], out[i + 1] if i + 1 < len(out) else None
        if nx and nx["page"] == r["page"] and nx["key"] == r["key"] and len(r["vals"]) <= 2 and len(nx["vals"]) >= 6:
            merged.append({**r, "vals": r["vals"] + nx["vals"]}); i += 2
        else:
            merged.append(r); i += 1
    return merged

def subseq(a, b):
    it = iter(b); return all(ch in it for ch in a)

def match_kind(k, label):
    t = raw(label); t = ALIAS.get(t, t)
    for c in {t} | {s for s, d in ALIAS.items() if d == t}:
        if k == c: return "exact"
    for c in {t} | {s for s, d in ALIAS.items() if d == t}:
        if sorted(k) == sorted(c * 2): return "doubled"                              # FramFreasmes = Frames + Frames
        if k.startswith(c) and any(ch.isdigit() for ch in k[len(c):]): return "jumble"   # label + value on top of each other
        if len(c) >= 8 and k.endswith(c): return "suffix"                            # chart legend text before the name
        if len(c) < len(k) <= 2 * len(c) and k[:3] == c[:3] and k[-5:] == c[-5:] and subseq(c, k): return "fuzzy"
    return None

def pbi_kpis(pages, page=6):
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

def compare_kpis(cards, dbx):
    k = dbx[(dbx["visual_id"].str.contains("kpi")) & (~dbx["col_key"].str.startswith("Trend"))]
    order = {r: i for i, r in enumerate(k.sort_values("row_order")["row_label"].drop_duplicates())}
    out = []
    for r in k.sort_values(["row_order", "col_sort"]).itertuples():
        field, txt = r.col_key.split("|")[-1].replace("pts ", ""), clean(r.cell_text)
        if txt in ("", "NA"): continue
        i = order[r.row_label]
        pv = cards[i].get(field, "") if i < len(cards) else ""
        out.append({"visual_id": r.visual_id, "row": r.row_label, "geo": r.geo_name, "column": r.col_key, "Databricks": txt,
                    "Power BI": pv, "Match?": status(txt, pv) if pv else CHECK, "Note": "" if pv else "Card value not found in the PDF."})
    return out

def compare(pbi_rows, dbx, cards=()):
    results = compare_kpis(list(cards), dbx)
    d = dbx[~dbx["visual_id"].str.contains("|".join(SKIP))].copy()
    d["page"] = d["visual_id"].str.extract(r"^p(\d+)_")[0].astype(int)
    d["g"] = d["geo_name"].fillna("Total").str[0].str.upper().map(GEO).fillna(9)
    d["m"] = d["col_key"].str.split("|").str[-1]
    d["cell_text"] = d["cell_text"].map(clean)
    cells_of = lambda o: [(r.geo_name, r.col_key, r.cell_text) for r in o.itertuples() if r.cell_text not in ("", "NA")]
    used, groups = set(), []
    for (vis, rlabel), grp in d.groupby(["visual_id", "row_label"], sort=False):          # pass 1: match rows by name
        page, best = int(grp["page"].iloc[0]), None
        orders = [grp.sort_values(["g", "col_sort"]), grp.sort_values(["g", "m", "col_sort"])]
        for o in orders:
            cells = cells_of(o); want = [c[2] for c in cells]
            for i, pr in enumerate(pbi_rows):
                if i in used or pr["page"] != page: continue
                kind = match_kind(pr["key"], rlabel)
                if not kind: continue
                got, m = [v for v in pr["vals"] if v != "NA"], 0
                if kind == "jumble" and len(want) - len(got) in (1, 2): m = len(want) - len(got)
                elif len(got) < len(want): continue
                score = sum(num(a) == num(b) for a, b in zip(want[m:], got))
                if kind == "exact" and not (score > 0 or len(got) == len(want)): continue
                if kind != "exact" and score * 2 < len(want) - m: continue
                rank = score - (0 if kind == "exact" else 0.5)
                if best is None or rank > best["rank"]: best = dict(rank=rank, got=got, i=i, cells=cells, m=m)
        if best: used.add(best["i"])
        groups.append((vis, rlabel, page, cells_of(orders[0]), best))
    for vis, rlabel, page, cells, best in groups:
        def emit(j, pv, st, note=""):
            results.append({"visual_id": vis, "row": rlabel, "geo": cells[j][0], "column": cells[j][1],
                            "Databricks": cells[j][2], "Power BI": pv, "Match?": st, "Note": note})
        if best:
            cells, m = best["cells"], best["m"]
            sig, exp = digits(pbi_rows[best["i"]]["name"]), "".join(digits(c[2]) for c in cells[:m])
            for j in range(len(cells)):
                if j < m:
                    emit(j, digits(cells[j][2]) if sig == exp else sig, "Match" if sig == exp else CHECK,
                         "Value sits on top of the row label in the PDF; compared on digits only.")
                else: emit(j, best["got"][j - m], status(cells[j][2], best["got"][j - m]))
            continue
        want, hit = [num(c[2]) for c in cells], None                                      # pass 2: find the row by its values
        for k in (0, 1):
            if hit or len(want) - k < 3: continue
            for i, pr in enumerate(pbi_rows):
                if i in used or pr["page"] != page: continue
                g = [num(v) for v in pr["vals"] if v != "NA"]
                if any(g[s:s + len(want) - k] == want[k:] for s in range(len(g) - len(want) + k + 1)):
                    hit = (k, i); used.add(i); break
        for j in range(len(cells)):
            if hit and j >= hit[0]: emit(j, cells[j][2], "Match", "Row name is unreadable in the PDF; row found by its values.")
            else: emit(j, "", CHECK, "Not readable in the PDF (text overlaps)." if hit else "Row not found in the PDF, or its values differ and its name is unreadable.")
    return pd.DataFrame(results)

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

n = res["Match?"].value_counts()
same = n.get("Match", 0) + n.get("Match – style only", 0)
checked = len(res) - n.get(CHECK, 0)
print("Power BI table rows read from PDF:", len(pbi_rows), "| KPI cards read:", len(cards))
print("Databricks cells:", len(res))
print(n.to_string())
print(f"Of the {checked} cells the code could read on both sides, {same / max(checked, 1) * 100:.1f}% are the same.")
display(spark.createDataFrame(res.groupby(["visual_id", "Match?"]).size().reset_index(name="cells")))
display(spark.createDataFrame(res[res["Match?"] != "Match"].astype(str)))

# COMMAND ----------
# For the next fix: raw text of the Power BI Rx Delivery page (funnel area)
print(pages[3][:2500])