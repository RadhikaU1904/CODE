import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

DBX_PDF = "PASTE THE NOV 17 DATABRICKS PDF PATH"

ocr = RapidOCR()
pdf = pdfium.PdfDocument(DBX_PDF)
for pg in range(len(pdf) - 1):                 # skip the glossary page
    img = pdf[pg].render(scale=3).to_numpy()
    result, _ = ocr(img)
    items = sorted((sum(p[1] for p in b) / 4, sum(p[0] for p in b) / 4, t, s) for b, t, s in result)
    lines, cur, last = [], [], None
    for y, x, t, s in items:
        if last is not None and y - last > 25:
            lines.append(cur); cur = []
        cur.append((x, t, s)); last = y
    lines.append(cur)
    print(f"\n===== PAGE {pg+1} | lowest confidence {min(s for _, _, _, s in items):.2f} =====")
    for ln in lines:
        print(" | ".join(t for x, t, s in sorted(ln)))