dbx = spark.sql("""
  SELECT visual_id, row_order, row_label, col_sort, col_key,
         geo_id, geo_name, period_week_label, cell_text, metric_status
  FROM `wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display
  WHERE week_choice = 'Latest'
""")
print("Total cells:", dbx.count())
display(dbx.groupBy("visual_id").count().orderBy("visual_id"))
display(dbx.filter("visual_id = 'p1_net_sales'").orderBy("row_order", "col_sort"))