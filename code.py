PBI_PDF = "PASTE TODAY'S POWER BI PDF PATH"

# 1) how Databricks stores the KPI cards
kpi = spark.sql("""
  SELECT row_order, row_label, col_sort, col_key, geo_name, cell_text
  FROM `wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display
  WHERE week_choice = 'Latest' AND visual_id = 'p6_kpi_cards'
  ORDER BY row_order, col_sort
""")
print("KPI cells:", kpi.count())
display(kpi)

# 2) how the Power BI PDF writes the Executive Summary page
import pdfplumber
with pdfplumber.open(PBI_PDF) as pdf:
    print("Pages:", len(pdf.pages))
    print(pdf.pages[5].dedupe_chars().extract_text()[:2500])