"""Hidden check for merge-windows. Runs OUTSIDE the workspace; the workspace is on PYTHONPATH."""
import json

try:
    from solution import merge_windows
except Exception as e:
    print(json.dumps({"passed": False, "failures": [["import", f"EXC {type(e).__name__}: {str(e)[:120]}"]], "total": 5, "passed_count": 0}))
    raise SystemExit(0)

cases = [
    ([[1, 3], [2, 6], [8, 10], [15, 18]], [[1, 6], [8, 10], [15, 18]]),
    ([[1, 4], [4, 5]], [[1, 5]]),
    ([], []),
    ([[5, 6], [1, 2]], [[1, 2], [5, 6]]),
    ([[1, 10], [2, 3], [4, 5]], [[1, 10]]),
]
bad = []
for inp, want in cases:
    try:
        got = [list(g) for g in merge_windows([list(x) for x in inp])]
    except Exception as e:
        bad.append([str(inp), f"EXC {type(e).__name__}"])
        continue
    if got != want:
        bad.append([str(inp), f"{got} want {want}"])
print(json.dumps({"passed": not bad, "failures": bad, "total": len(cases), "passed_count": len(cases) - len(bad)}))
