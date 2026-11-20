display(spark.sql("""
SELECT visual_id, row_label, col_key, cell_text,
       COUNT(*) OVER (PARTITION BY visual_id, row_label, col_key) AS copies
FROM `wmt-hnw-pharmacy-catalog-prod`.trade_deck.v_slide_cells_display
WHERE week_choice = 'Latest'
  AND row_label IN ('Order Ready Session', 'Add to Cart', 'Central Fill Scripts')
ORDER BY row_label, col_key
"""))