def sql_of(d):
    return d.get("query") or " ".join(d.get("queryLines", []))

# 1) show the SQL of the first two datasets
for d in spec["datasets"][:2]:
    print("=====", d.get("displayName"), "=====")
    print(sql_of(d))
    print()

# 2) try running the first one (Net Sales)
df = spark.sql(sql_of(spec["datasets"][0]))
print("Rows:", df.count(), "| Columns:", df.columns)
display(df)