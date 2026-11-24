img = doc[0].render(scale=SCALE).to_numpy()
res = ocr(img, use_cls=False)[0]
pieces = [(sum(p[1] for p in b)/4, sum(p[0] for p in b)/4, max(p[0] for p in b)-min(p[0] for p in b), t) for b, t, s in res]
y0 = next(y for y, x, w, t in pieces if "Total" in t.replace(" ", "") and "H" in t)
for y, x, w, t in sorted(p for p in pieces if abs(p[0] - y0) < 40):
    print(f"x={x:6.0f}  width={w:4.0f}  y={y:6.0f}  {t}")