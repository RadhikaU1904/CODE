L = pages[3].splitlines()
i = next(n for n, l in enumerate(L) if "Order Ready" in l)
for n in range(max(0, i - 4), min(len(L), i + 14)):
    print(n, repr(L[n]))