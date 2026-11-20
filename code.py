%pip install rapidocr-onnxruntime


import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

DBX_PDF = "/Workspace/Users/radhika.uppanapalli@walmart.com/H&W Weekly Trade Report (trade_deck)- V2 2026-11-20 21_11.pdf"

ocr = RapidOCR()
pdf = pdfium.PdfDocument(DBX_PDF)
found = []
for i in range(len(pdf) - 1):          # skip the last page (glossary)
    img = pdf[i].render(scale=3).to_numpy()
    result, _ = ocr(img)
    words = [r[1] for r in (result or [])]
    print(f"page {i+1}: {len(words)} pieces of text read")
    found += words

for v in ["$910.0M", "$26.3M", "12.9M", "$79.9M", "$883.8M", "195.1K", "539.9K", "339.8K"]:
    print(v, "FOUND" if any(v in w for w in found) else "not found")
print("Funnel check:", [w for w in found if w in ("1.2M", "1.4M", "338.4K", "417.0K")])
print(found[:100])