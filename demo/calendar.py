"""Print the next few due dates for a household's chores.

    python -m demo.calendar

Before a result is applied, `next_due` raises NotImplementedError and this prints what is
missing. After `assay room … --target . --target-path demo/recurrence.py` applies the chosen
artefact, the same command prints a calendar. That is the before/after a non-developer can see.
"""
from datetime import date, timedelta

from .recurrence import next_due

CHORES = [
    ("Bins out", date(2026, 1, 1), "weekly:1:MO", set()),
    ("Water the plants", date(2026, 1, 1), "daily:3", set()),
    ("Deep clean", date(2026, 1, 31), "monthly:1:31", set()),
    ("Piano practice", date(2026, 1, 5), "weekly:2:MO,WE", set()),
]
HOLIDAYS = {date(2026, 1, 2), date(2026, 1, 3), date(2026, 2, 2)}


def main() -> int:
    today = date(2026, 1, 28)
    print(f"Chores due after {today.isoformat()}\n")
    for name, start, rule, _ in CHORES:
        try:
            due = []
            cursor = today
            for _ in range(3):
                cursor = next_due(start, rule, cursor, HOLIDAYS)
                due.append(cursor)
            print(f"  {name:18} {rule:18} " + "  ".join(d.strftime("%a %d %b") for d in due))
        except NotImplementedError:
            print(f"  {name:18} {rule:18} (not implemented yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
