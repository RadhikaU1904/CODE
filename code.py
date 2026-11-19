path = "PASTE TODAY'S DATABRICKS PDF PATH"

with open(path, "rb") as f:
    data = f.read()

df = (spark.createDataFrame([(bytearray(data),)], "content binary")
      .selectExpr("to_json(ai_parse_document(content, map('version','2.0'))) AS parsed"))

out = df.first()["parsed"]
print("Characters read:", len(out))

# quick check: are today's known numbers in the output?
for v in ["$739.6M", "$21.0M", "10.5M", "$51.3M", "894.4K", "161.8K", "$718.7M", "438.5K"]:
    print(v, "FOUND" if v in out else "not found")

print(out[:5000])