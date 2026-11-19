path = "PASTE YOUR DATABRICKS PDF PATH"   # the same /Workspace/... path as before

with open(path, "rb") as f:
    data = f.read()

df = (spark.createDataFrame([(bytearray(data),)], "content binary")
      .selectExpr("ai_parse_document(content, map('version','2.0')) AS parsed"))
display(df)