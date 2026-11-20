import pypdfium2 as pdfium

DBX_PDF = "PASTE DATABRICKS DASHBOARD PDF PATH"

pdf = pdfium.PdfDocument(DBX_PDF)
text = ""
for i in range(len(pdf)):
    t = pdf[i].get_textpage().get_text_range()
    print(f"page {i+1}: {len(t)} letters")
    text += t

for v in ["$910.0M", "$26.3M", "12.9M", "$79.9M", "1.2M", "338.4K", "86.7K", "-16.2%"]:
    print(v, "FOUND" if v in text else "not found")