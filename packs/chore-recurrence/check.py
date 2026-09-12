"""Hidden check for chore-recurrence. Runs OUTSIDE the workspace; the workspace is on PYTHONPATH.

Prints one JSON object on its last line: passed, failures, total, passed_count.
The cases were written before any model saw the task and are never shown to a model.
"""
import json
from datetime import date

try:
    from solution import next_due
except Exception as e:  # import failure is a failure of the artefact, reported as such
    print(json.dumps({"passed": False, "failures": [["import", f"EXC {type(e).__name__}: {str(e)[:120]}"]], "total": 7, "passed_count": 0}))
    raise SystemExit(0)

H = {date(2026, 1, 2), date(2026, 1, 3)}
cases = [
    ((date(2026, 1, 1), "daily:3", date(2026, 1, 1), set()), date(2026, 1, 4)),
    ((date(2026, 1, 1), "daily:1", date(2026, 1, 1), H), date(2026, 1, 4)),
    ((date(2026, 1, 5), "weekly:1:MO,WE", date(2026, 1, 5), set()), date(2026, 1, 7)),
    ((date(2026, 1, 5), "weekly:2:MO,WE", date(2026, 1, 7), set()), date(2026, 1, 19)),
    ((date(2026, 1, 31), "monthly:1:31", date(2026, 1, 31), set()), date(2026, 2, 28)),
    ((date(2026, 11, 15), "monthly:3:15", date(2026, 11, 15), set()), date(2027, 2, 15)),
    ((date(2026, 1, 1), "daily:7", date(2026, 3, 1), set()), date(2026, 3, 5)),
]
bad = []
for args, want in cases:
    try:
        got = next_due(*args)
    except Exception as e:
        bad.append([f"{args[1]} after {args[2]}", f"EXC {type(e).__name__}"])
        continue
    if got != want:
        bad.append([f"{args[1]} after {args[2]}", f"{got} want {want}"])
print(json.dumps({"passed": not bad, "failures": bad, "total": len(cases), "passed_count": len(cases) - len(bad)}))
