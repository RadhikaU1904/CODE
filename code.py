# %pip install openpyxl   <- run this first in its own cell if you get 'No module named openpyxl'
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ---- change only these 3 lines each day ----
path  = "/Workspace/Users/your.name/Dashboard_vs_PowerBI_W43_Nov25_2026.xlsx"   # right-click the file > Copy path
as_of = "Nov 25, 2026, 11:35 AM"
week  = "Week 43 WTD (Nov 21 – Nov 24, 2026 · 4 of 7 days)"

tabs = ["Executive Summary", "Sales & Volume", "Category & Operations", "Geography", "Rx Delivery"]
labels = ["Match", "Match – style only", "No match"]
colors = ["#2E9E5B", "#E8A93B", "#D64545"]          # green, amber, red
INK, MUTED = "#1A1A1A", "#6B7280"

def count(df):
    c = df["Match?"].value_counts()
    return [int(c.get(k, 0)) for k in labels]

per_tab = {t: count(pd.read_excel(path, sheet_name=t)) for t in tabs}
overall = [sum(v[i] for v in per_tab.values()) for i in range(3)]
total = sum(overall)
same = (overall[0] + overall[1]) / total * 100

fig = plt.figure(figsize=(15, 7.6))
fig.patch.set_facecolor("white")
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.25], left=0.02, right=0.97, top=0.74, bottom=0.30, wspace=0.12)

# ---- left: pie (donut) for overall ----
ax = fig.add_subplot(gs[0, 0])
ax.pie(overall, colors=colors, startangle=90, counterclock=False,
       wedgeprops=dict(width=0.34, edgecolor="white", linewidth=3))
ax.text(0, 0, f"{same:.1f}%", ha="center", va="center", fontsize=38, fontweight="bold", color=INK)
ax.set_title("Overall (all tabs)", fontsize=15, fontweight="bold", color=INK, pad=10)
ax.text(0, -1.20, f"{overall[0]} match · {overall[1]} style only · {overall[2]} no match",
        ha="center", va="top", fontsize=12, color=MUTED)
ax.text(0, -1.38, f"{total} numbers compared", ha="center", va="top", fontsize=11, color=MUTED)

# ---- right: one vertical bar graph for all tabs ----
bx = fig.add_subplot(gs[0, 1])
for xi, t in enumerate(tabs):
    v = per_tab[t]; n = sum(v); bottom = 0
    for val, col in zip(v, colors):
        h = val / n * 100
        if h > 0:
            bx.bar(xi, h, bottom=bottom, color=col, width=0.6, edgecolor="white", linewidth=2)
        bottom += h
    bx.text(xi, 102, f"{(v[0] + v[1]) / n * 100:.1f}%", ha="center", va="bottom",
            fontsize=14, fontweight="bold", color=INK)
    bx.text(xi, -4, t.replace(" & ", " &\n"), ha="center", va="top", fontsize=12, color=INK)
    bx.text(xi, -17, f"{v[0]} match\n{v[1]} style only\n{v[2]} no match",
            ha="center", va="top", fontsize=9.5, color=MUTED, linespacing=1.4)
bx.set_xlim(-0.6, len(tabs) - 0.4); bx.set_ylim(0, 100); bx.axis("off")
bx.set_title("By tab", fontsize=15, fontweight="bold", color=INK, pad=34)

fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(colors, labels)], loc="upper right",
           bbox_to_anchor=(0.99, 0.905), frameon=False, fontsize=12, labelcolor=INK, ncol=3)
fig.text(0.03, 0.93, "Health and Wellness Weekly Trade Report (Power BI vs Databricks)", fontsize=20, fontweight="bold", color=INK)
fig.text(0.03, 0.875, f"As of {as_of}  ·  {week}", fontsize=13, color=MUTED)
fig.text(0.03, 0.03, "Style only = same number, different look ($ sign or Δ).  "
         f"{overall[2]} numbers differ today; details are in the Excel.", fontsize=10, color=MUTED)
out = path.rsplit("/", 1)[0] + "/Validation_Chart.png"      # saved next to the Excel
plt.savefig(out, dpi=140)
print("Saved:", out)
plt.show()