bad = res[res["Match?"] != "Match"]
print(bad[bad.visual_id == "p4_rxd_funnel"][["row", "column", "Databricks", "Power BI", "Match?"]].to_string())

for v in ["p3_geography", "p4_rxd_geography", "p2_vision_category", "p1_digital", "p4_rxd_funnel"]:
    d = dbx[dbx.visual_id == v]
    print("\n", v, "\n rows:", list(d.row_label.unique()), "\n geos:", list(d.geo_name.astype(str).unique()))

for p in [1, 2, 3, 4]:
    print("\n--- Power BI page", p)
    for r in pbi_rows:
        if r["page"] == p:
            print(len(r["vals"]), "|", r["name"], "|", " ".join(r["vals"][:5]))

print(pages[2][:1500])