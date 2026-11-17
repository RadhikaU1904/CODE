import pdfplumber

path = "PASTE DATABRICKS PDF PATH"

with pdfplumber.open(path) as pdf:
    for p, page in enumerate(pdf.pages[:5], 1):
        print(f"\n===== DATABRICKS PAGE {p} =====")
        print(page.extract_text())