"""What this candidate's code actually DOES, in a form anyone can read.

Runs outside the workspace with the workspace importable — the same isolation as `check.py`,
so nothing here is visible to a model. It prints one JSON object describing a household's
schedule as this candidate would compute it. The board shows those side by side; a wrong date
is then visible to someone who has never read a line of Python, which a diff never is.
"""
import json
from datetime import date

HOLIDAYS = {date(2026, 1, 2), date(2026, 1, 3), date(2026, 2, 2)}
TODAY = date(2026, 1, 28)
CHORES = [
    ("Bins out", date(2026, 1, 1), "weekly:1:MO"),
    ("Water the plants", date(2026, 1, 1), "daily:3"),
    ("Deep clean", date(2026, 1, 31), "monthly:1:31"),
    ("Piano practice", date(2026, 1, 5), "weekly:2:MO,WE"),
]

try:
    from solution import next_due
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {str(e)[:120]}"}))
    raise SystemExit(0)

rows = []
for name, start, rule in CHORES:
    cells, cursor = [], TODAY
    for _ in range(3):
        try:
            cursor = next_due(start, rule, cursor, HOLIDAYS)
            cells.append(cursor.strftime("%a %d %b"))
        except Exception as e:
            cells.append(f"— {type(e).__name__}")
            break
    while len(cells) < 3:
        cells.append("—")
    rows.append({"label": name, "note": rule, "cells": cells})

print(json.dumps({
    "title": "The next three times each chore comes round",
    "subtitle": f"as of {TODAY.strftime('%A %d %B %Y')}, skipping the household's holidays",
    "columns": ["next", "then", "after that"],
    "rows": rows,
}))
