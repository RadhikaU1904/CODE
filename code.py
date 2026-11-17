import pdfplumber, re

paths = {
    "POWER BI":   "PASTE POWER BI PDF PATH",
    "DATABRICKS": "PASTE DATABRICKS PDF PATH",
}

VAL = r"(?:-?\$?\d[\d,]*\.?\d*[KMB%]?(?:\s(?:Δ|pts))?|NA)"
ROW = re.compile(rf"((?:(?<!\d)% )?[A-Za-z][A-Za-z0-9 .&()/*%-]*?)\s+((?:{VAL}(?:\s+|$)){{2,}})$")

for name, path in paths.items():
    print(f"\n########## {name} ##########")
    with pdfplumber.open(path) as pdf:
        print("Pages:", len(pdf.pages))
        for p, page in enumerate(pdf.pages, 1):
            text = page.dedupe_chars().extract_text() or ""
            print(f"--- page {p}: {len(text)} characters ---")
            for line in text.splitlines():
                m = ROW.search(line.strip())
                if m:
                    print(f"p{p} | {m.group(1).strip()} | {' | '.join(re.findall(VAL, m.group(2)))}")