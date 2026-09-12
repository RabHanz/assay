"""What this candidate's code actually DOES with three real bills, in pounds and pence.

Outside the workspace, workspace importable, never copied in — the same isolation as the check.
The last column is the one that carries it: the shares added back up. A split that loses a
penny prints £99.99 under a £100.00 bill, and nobody needs a rule explained to see it.
"""
import json

BILLS = [
    ("Dinner", "100.00", 3),
    ("Coffees", "0.10", 3),
    ("Rent", "1234.56", 3),
]
EXPECTED = {
    "Dinner": ["£33.33", "£33.33", "£33.34", "£100.00"],
    "Coffees": ["£0.03", "£0.03", "£0.04", "£0.10"],
    "Rent": ["£411.52", "£411.52", "£411.52", "£1234.56"],
}
WHY = {
    "Dinner": "a hundred pounds three ways does not divide evenly, so one share carries the extra penny",
    "Coffees": "ten pence three ways: two threes and a four, and the four goes last",
    "Rent": "this one divides evenly, so every share is the same",
}

try:
    from solution import split_bill
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {str(e)[:120]}"}))
    raise SystemExit(0)


def pence(s: str) -> int:
    whole, _, frac = str(s).partition(".")
    return int(whole) * 100 + int((frac + "00")[:2])


rows = []
for name, total, ways in BILLS:
    try:
        shares = [str(x) for x in split_bill(total, ways)]
        cells = [f"£{s}" for s in shares[:ways]]
        while len(cells) < ways:
            cells.append("—")
        added = sum(pence(s) for s in shares)
        cells.append(f"£{added // 100}.{added % 100:02d}")
    except Exception as e:
        cells = [f"— {type(e).__name__}"] + ["—"] * ways
    rows.append({"label": name, "note": f"£{total} · {ways} ways", "cells": cells,
                 "expected": EXPECTED[name], "why": WHY[name]})

print(json.dumps({
    "title": "Three bills, split three ways, and what the shares add back up to",
    "subtitle": "the last column must equal the bill, to the penny",
    "columns": ["share 1", "share 2", "share 3", "adds up to"],
    "rows": rows,
}))
