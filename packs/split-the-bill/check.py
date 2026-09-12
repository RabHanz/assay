"""Hidden check for split-the-bill. Runs OUTSIDE the workspace; the workspace is on PYTHONPATH."""
import json

try:
    from solution import split_bill
except Exception as e:
    print(json.dumps({"passed": False, "failures": [["import", f"EXC {type(e).__name__}: {str(e)[:120]}"]], "total": 7, "passed_count": 0}))
    raise SystemExit(0)

cases = [
    (("100.00", 3), ["33.33", "33.33", "33.34"]),
    (("0.10", 3), ["0.03", "0.03", "0.04"]),
    (("200.00", 4), ["50.00", "50.00", "50.00", "50.00"]),
    (("99.99", 2), ["49.99", "50.00"]),
    (("1.00", 7), ["0.14", "0.14", "0.14", "0.14", "0.14", "0.15", "0.15"]),
    (("12.34", 1), ["12.34"]),
    (("1234.56", 3), ["411.52", "411.52", "411.52"]),
]
bad = []
for args, want in cases:
    try:
        got = split_bill(*args)
        got = [str(x) for x in got]
    except Exception as e:
        bad.append([f"{args[0]} split {args[1]} ways", f"EXC {type(e).__name__}"])
        continue
    if got != want:
        bad.append([f"{args[0]} split {args[1]} ways", f"{got} want {want}"])
print(json.dumps({"passed": not bad, "failures": bad, "total": len(cases), "passed_count": len(cases) - len(bad)}))
