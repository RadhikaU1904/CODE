# 1) how Databricks stores the KPI cards
kpi = dbx[dbx["visual_id"] == "p6_kpi_cards"].sort_values(["row_label", "col_sort"])
print("KPI cells:", len(kpi))
display(spark.createDataFrame(kpi[["row_label", "col_key", "geo_name", "cell_text"]].astype(str)))

# 2) how the Power BI PDF writes the Executive Summary page
print(pages[5][:2500])