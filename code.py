# Databricks notebook source
# MAGIC %md
# MAGIC # Daily validation: Power BI vs Databricks dashboard
# MAGIC **Morning:** run Step 1 and Step 2 right after the dashboard refresh. **Any time later:** run the rest.
# MAGIC It only reads data. The only things it writes are small files in the output folder below.

# COMMAND ----------
# MAGIC %pip install pdfplumber openpyxl

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: settings
# MAGIC The only cell you change each day (the Power BI PDF path).

# COMMAND ----------
PBI_PDF = "PASTE TODAY'S POWER BI PDF PATH"
VIEW = "`wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display"
REPORT = "H&W Weekly Trade Report"
OUT_DIR = "."                     # folder for the saved copy, Excel, chart and email text ("." = this notebook's folder)
TIMEZONE = "America/Chicago"
TABS = {6: "Executive Summary", 1: "Sales & Volume", 2: "Category & Operations", 3: "Geography", 4: "Rx Delivery"}   # Power BI PDF page -> tab name

import os, re, datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd
now = dt.datetime.now(ZoneInfo(TIMEZONE))
TODAY = now.strftime("%Y-%m-%d")
SNAP = os.path.join(OUT_DIR, f"databricks_morning_copy_{TODAY}.csv")
print("Today:", TODAY, "| time now:", now.strftime("%I:%M %p"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: save the morning copy of the Databricks numbers
# MAGIC Run this **right after the dashboard's morning refresh**. It saves what the dashboard shows at that moment.
# MAGIC If today's copy is already saved, it keeps it and does not overwrite it.

# COMMAND ----------
OVERWRITE = False                 # set True only if you saved the copy at the wrong time and want to save it again
if os.path.exists(SNAP) and not OVERWRITE:
    print("Today's copy is already saved. Keeping it:", SNAP)
else:
    snap = spark.sql(f"""
      SELECT visual_id, row_order, row_label, col_sort, col_key, geo_name, period_week_label, cell_text
      FROM {VIEW} WHERE week_choice = 'Latest'
    """).toPandas()
    snap["saved_at"] = now.strftime("%Y-%m-%d %I:%M %p")
    snap.to_csv(SNAP, index=False)
    print(f"Saved {len(snap)} dashboard cells at {now.strftime('%I:%M %p')} ->", SNAP)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: rules for reading and comparing
# MAGIC This cell only defines the rules. Nothing runs yet.

# COMMAND ----------
import re
from collections import Counter

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
    out, only_vals = [], re.compile(rf"(?:{VAL}\s*)+")
    for p, text in enumerate(pages, 1):
        names = []                                   # [line number, name, already used by a values-only line]
        for n, line in enumerate((text or "").splitlines()):
            line = preclean(line).strip()
            if only_vals.fullmatch(line):            # a line of numbers only: its name is on a line just above (funnel)
                vals = [clean(v) for v in re.findall(VAL, line)]
                owner = next((x for x in reversed(names) if n - x[0] <= 3 and not x[2]), None)
                if len(vals) >= 3 and owner:
                    owner[2] = True
                    out.append({"page": p, "name": owner[1], "key": raw(owner[1]), "vals": vals})
                elif len(vals) >= 3:          # numbers with no readable name: keep them, a row can still be found by its values
                    out.append({"page": p, "name": "", "key": "", "vals": vals})
                continue
            m = ROW.search(line)
            if m:
                out.append({"page": p, "name": m.group(1).strip(), "key": raw(m.group(1)),
                            "vals": [clean(v) for v in re.findall(VAL, m.group(2))]})
                names.append([n, m.group(1).strip(), False])
            elif line and len(line) <= 40 and not re.search(r"\d", line):
                names.append([n, line, False])
    merged, i = [], 0                      # a Total line followed by its BU line (same name) is one table row
    while i < len(out):
        r, nx = out[i], out[i + 1] if i + 1 < len(out) else None
        if nx and r["key"] and nx["page"] == r["page"] and nx["key"] == r["key"] and len(r["vals"]) <= 2 and len(nx["vals"]) >= 6:
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

print("Rules are ready.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: read the Power BI PDF and the saved Databricks copy

# COMMAND ----------
import pdfplumber
with pdfplumber.open(PBI_PDF) as pdf:
    pages = [(p.dedupe_chars().extract_text() or "") for p in pdf.pages]
pbi_rows, cards = pbi_rows_from_text(pages), pbi_kpis(pages)
m = re.search(r"Last Updated\s*:?\s*([0-9/]+\s+[0-9:]+\s*[AP]M)", " ".join(pages))
PBI_TIME = m.group(1) if m else "not found in the PDF"

dbx = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
dbx["row_order"] = pd.to_numeric(dbx["row_order"]); dbx["col_sort"] = pd.to_numeric(dbx["col_sort"])
DBX_TIME = dbx["saved_at"].iloc[0]
WEEK = next((w for w in dbx["period_week_label"] if w), "")
print("Power BI last updated:", PBI_TIME)
print("Databricks copy saved:", DBX_TIME)
print("Week:", WEEK)
print("Power BI rows read:", len(pbi_rows), "| KPI cards:", len(cards), "| Databricks cells:", len(dbx))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: compare

# COMMAND ----------
res = compare(pbi_rows, dbx, cards)
res["tab"] = res["visual_id"].str.extract(r"^p(\d+)_")[0].astype(int).map(TABS)
ORDER = ["Match", "Match – style only", "No match", CHECK]
n = res["Match?"].value_counts().reindex(ORDER, fill_value=0)
total, same = len(res), n["Match"] + n["Match – style only"]
PCT = same / total * 100
print(f"{PCT:.1f}% the same  |  {total} compared  |  " + "  |  ".join(f"{k}: {v}" for k, v in n.items()))
by_tab = res.groupby("tab")["Match?"].value_counts().unstack(fill_value=0).reindex(index=list(TABS.values()), columns=ORDER, fill_value=0)
display(spark.createDataFrame(by_tab.reset_index()))
diffs = res[res["Match?"] != "Match"]
display(spark.createDataFrame(diffs.astype(str)))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: make the Excel

# COMMAND ----------
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
FILL = {"Match": "C6E0B4", "Match – style only": "FFE699", "No match": "F8CBAD", CHECK: "D9D9D9"}
FIX = {"Match": "No", "Match – style only": "No", "No match": "Investigate", CHECK: "Check manually"}
wb = Workbook(); ws = wb.active; ws.title = "Summary"
ws["A1"] = f"{REPORT}: Power BI vs Databricks (automated, tables and KPI cards)"; ws["A1"].font = Font(bold=True, size=14)
for i, (a, b) in enumerate([("Week", WEEK), ("Power BI last updated", PBI_TIME), ("Databricks copy saved", DBX_TIME), ("Run on", now.strftime("%Y-%m-%d %I:%M %p"))], 2):
    ws.cell(i, 1, a); ws.cell(i, 2, b)
head = ["Tab", "Compared"] + ORDER + ["Same number"]
for j, h in enumerate(head, 1):
    c = ws.cell(7, j, h); c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3864")
for i, (tab, r) in enumerate(list(by_tab.iterrows()) + [("All tabs", n)], 8):
    vals = [tab, int(r.sum())] + [int(r[k]) for k in ORDER] + [(r["Match"] + r["Match – style only"]) / max(r.sum(), 1)]
    for j, v in enumerate(vals, 1): ws.cell(i, j, v)
    ws.cell(i, len(vals)).number_format = "0.0%"
for col, w in zip("ABCDEFG", [34, 26, 12, 20, 12, 16, 14]): ws.column_dimensions[col].width = w
for tab in list(TABS.values()):
    sh = wb.create_sheet(tab); part = res[res["tab"] == tab]
    sh.append(["Metric / KPI", "Where it is", "Databricks value", "Power BI value", "Match?", "Fix needed?", "Comments"])
    for c in sh[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3864")
    for r in part.itertuples():
        geo = "" if str(r.geo) in ("Total", "", "nan", "None") else f" · {r.geo}"
        sh.append([f"{r.row} – {r.column.replace('|', ' ')}{geo}", r.visual_id, r.Databricks, getattr(r, "_6"), getattr(r, "_7"), FIX[getattr(r, "_7")], r.Note])
        sh.cell(sh.max_row, 5).fill = PatternFill("solid", fgColor=FILL[getattr(r, "_7")])
    for col, w in zip("ABCDEFG", [58, 24, 18, 18, 20, 16, 70]): sh.column_dimensions[col].width = w
    sh.freeze_panes = "A2"; sh.auto_filter.ref = f"A1:G{sh.max_row}"
XLSX = os.path.join(OUT_DIR, f"Validation_auto_{TODAY}.xlsx"); wb.save(XLSX); print("Excel saved:", XLSX)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 7: make the chart

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
    bx.text(xi, 102, f"{(r['Match'] + r['Match – style only']) / tot * 100:.1f}%", ha="center", va="bottom", fontsize=14, fontweight="bold", color=INK)
    bx.text(xi, -4, tab.replace(" & ", " &\n"), ha="center", va="top", fontsize=12, color=INK)
    bx.text(xi, -17, f"{r['Match']} match\n{r['Match – style only']} style only\n{r['No match']} no match", ha="center", va="top", fontsize=9.5, color=MUTED, linespacing=1.4)
bx.set_xlim(-0.6, len(by_tab) - 0.4); bx.set_ylim(0, 100); bx.axis("off")
bx.set_title("By tab", fontsize=15, fontweight="bold", color=INK, pad=34)
fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(COL, ORDER)], loc="upper right", bbox_to_anchor=(0.99, 0.905), frameon=False, fontsize=12, labelcolor=INK, ncol=4)
fig.text(0.03, 0.93, f"{REPORT} (Power BI vs Databricks)", fontsize=20, fontweight="bold", color=INK)
fig.text(0.03, 0.875, f"As of {now.strftime('%b %d, %Y')}  ·  {WEEK}  ·  Power BI updated {PBI_TIME}  ·  Databricks copy {DBX_TIME}", fontsize=11, color=MUTED)
fig.text(0.03, 0.03, "Automated check of tables and KPI cards. Charts and maps are not included.", fontsize=10, color=MUTED)
PNG = os.path.join(OUT_DIR, f"Validation_chart_{TODAY}.png"); plt.savefig(PNG, dpi=140); plt.show(); print("Chart saved:", PNG)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 8: the email text
# MAGIC Copy this into your email, paste the chart, and attach the Excel.

# COMMAND ----------
lines = [f"Subject: {REPORT} Validation | Power BI vs Databricks | {WEEK} ({now.strftime('%b %d, %Y')})", "", "Hi Team,", "",
         f"Attached is the automated validation comparing the {REPORT} in Power BI and Databricks as of {now.strftime('%b %d, %Y')}.",
         f"Power BI last updated: {PBI_TIME}. Databricks numbers saved: {DBX_TIME}.", "",
         f"Overall, {PCT:.1f}% of metrics are aligned, with {total} metrics compared (tables and KPI cards):", "",
         f"- {n['Match']} Matches", f"- {n['Match – style only']} Style/formatting differences only", f"- {n['No match']} Mismatches", f"- {n[CHECK]} to check manually", ""]
mm = res[res["Match?"] == "No match"]
if len(mm):
    lines.append("Mismatches:")
    for r in mm.itertuples():
        geo = "" if str(r.geo) in ("Total", "", "nan", "None") else f", {r.geo}"
        lines.append(f"- {r.tab}: {r.row} – {r.column.replace('|', ' ')}{geo} ({r.Databricks} vs {getattr(r, '_6')})")
else:
    lines.append("No mismatches today.")
lines += ["", "The attached Excel has the detailed results by tab.", "", "Thanks,"]
EMAIL = "\n".join(lines); print(EMAIL)
open(os.path.join(OUT_DIR, f"Validation_email_{TODAY}.txt"), "w", encoding="utf-8").write(EMAIL)