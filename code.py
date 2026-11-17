import pdfplumber, re
import pandas as pd

path = "PASTE THE SAME PDF PATH HERE"

VAL = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"
ROW = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%-]*?)\s+((?:{VAL}(?:\s+|$)){{2,}})$")

rows = []
with pdfplumber.open(path) as pdf:
    for p, page in enumerate(pdf.pages, 1):
        text = page.dedupe_chars().extract_text() or ""
        for line in text.splitlines():
            m = ROW.search(line.strip())
            if m:
                vals = re.findall(VAL, m.group(2))
                rows.append({"page": p, "row name": m.group(1).strip(),
                             "how many": len(vals), "numbers": " | ".join(vals)})

df = pd.DataFrame(rows)
print(df.groupby("page").size())
display(df)