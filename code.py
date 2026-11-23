from pypdf import PdfReader

DBX_PDF = "PASTE DATABRICKS DASHBOARD PDF PATH"
r = PdfReader(DBX_PDF)
root = r.trailer["/Root"]
print("Has accessibility tags:", "/StructTreeRoot" in root)

pg = r.pages[0]
annots = [a.get_object() for a in (pg.get("/Annots") or [])]
print("Links on page 1:", len(annots))
for a in annots[:12]:
    info = {k: str(a[k])[:90] for k in ("/Contents", "/T", "/Alt", "/TU") if k in a}
    uri = str(a["/A"].get("/URI"))[:150] if "/A" in a else ""
    print(info, "| goes to:", uri)

xo = pg["/Resources"].get("/XObject", {})
print("Pictures on page 1:", sum(1 for k in xo if xo[k].get_object().get("/Subtype") == "/Image"))
print("Fonts on page 1:", list(pg["/Resources"].get("/Font", {}).keys()))

found, todo, seen = [], [root.get("/StructTreeRoot")], 0
while todo and seen < 20000:
    o = todo.pop(); seen += 1
    try: o = o.get_object()
    except Exception: pass
    if isinstance(o, dict):
        for k in ("/Alt", "/ActualText"):
            if k in o: found.append(str(o[k])[:60])
        todo += [o[k] for k in ("/K",) if k in o]
    elif isinstance(o, list):
        todo += list(o)
print("Hidden text pieces found:", len(found)); print(found[:40])