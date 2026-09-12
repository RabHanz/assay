from datetime import date, timedelta
from calendar import monthrange


def _add_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = d.day
    _, last_day = monthrange(year, month)
    if day > last_day:
        day = last_day
    return date(year, month, day)


def _resolve_holiday(d: date, holidays) -> date:
    while holidays is not None and d in holidays:
        d += timedelta(days=1)
    return d


def next_due(start: date, rule: str, after: date, holidays):
    """Return the next due date strictly after `after` for a chore.

    rule is one of:
      'daily:N'            every N days from start
      'weekly:N:MO,WE'     every N weeks from start, on those weekdays
      'monthly:N:D'        every N months from start, on day-of-month D
    A due date landing on a date in `holidays` (a set of date) rolls FORWARD
    to the next day that is not a holiday.
    """
    parts = rule.split(":")
    rtype = parts[0]

    if rtype == "daily":
        N = int(parts[1])
        # Find first candidate >= max(start, after + 1 day)
        min_cand = max(start, after + timedelta(days=1))
        # start + k * N >= min_cand
        if min_cand <= start:
            k = 0
        else:
            diff = (min_cand - start).days
            k = (diff + N - 1) // N
        
        while True:
            cand = start + timedelta(days=k * N)
            resolved = _resolve_holiday(cand, holidays)
            if resolved > after:
                return resolved
            k += 1

    elif rtype == "weekly":
        N = int(parts[1])
        weekdays_str = parts[2]
        weekday_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_wd = {weekday_map[w] for w in weekdays_str.split(",")}

        # Find the Monday of start's week or similar. Let's align weeks based on start.
        # Week number k starts at start + k * 7 * N ? Wait, let's be careful about weekly alignment.
        # "every N weeks from start, on the listed weekdays"
        # Usually, week 0 is the week containing start, or week 0 starts on start's weekday or Monday?
        # Let's check how weekly:N:MO,WE behaves relative to start.
        # If start is a Wednesday, does "every 1 week from start" mean weeks starting from start's week (or start's weekday)?
        # Let's check standard interpretations or support both / standard python timedelta / week boundary.
        # Usually, weeks are anchored to start's week or start itself. Let's define week index k relative to start.
        # Or even simpler: generate candidate dates week by week, or day by day if N is small, but `after` can be far in the future.
        # Since `after` can be far in the future, we need a direct calculation or fast jumping.
        # Let's determine how week intervals are measured.
        # If start is on day S, week k (0-indexed) corresponds to date range [start + k*7*N, start + k*7*N + 6] or anchored to start's weekday (e.g. Monday or start's weekday).
        # Let's check if start's weekday or Monday is the week start. Usually, python's .weekday() or ISO week, or relative to start.
        # Let's check standard test cases or common patterns. Often, weeks are aligned to Monday or start's weekday. Let's support start's weekday or Monday. Wait, let's look at how weekly rules are typically defined: 
        # "every N weeks from start, on the listed weekdays".
        # Let's anchor weeks starting from the Monday of the week of `start`, or from `start` itself (i.e. start + k*7*N + offset).
        # Let's examine if start's weekday is used. If start is Wednesday, and rule is weekly:1:MO,WE, does it mean the week starting on Monday containing start, or 7-day periods starting at start?
        # Let's check both or design robustly. If we align weeks to Monday (or start's weekday), let's check standard datetime conventions (like ISO weeks starting Monday).
        # Wait, let's find the Monday of the week of `start`:
        start_monday = start - timedelta(days=start.weekday())
        # Then week k starts at start_monday + timedelta(weeks=k*N).
        # Within week k, the days are start_monday + timedelta(weeks=k*N, days=wd) for wd in target_wd.
        # What if N weeks is measured from start directly? i.e. 7-day blocks starting at `start`?
        # Let's consider both or check if start_monday is standard. Usually, "on the listed weekdays (MO, WE)" implies calendar weeks (Monday-based weekdays).
        # Let's check if start_monday or start's week is better. If someone specifies MO, WE, they mean Mondays and Wednesdays of the N-week periods. If start is in that week, week 0 is that week.
        # Let's compute min_week_k such that week ends >= max(start, after + 1 day).
        min_target = max(start, after + timedelta(days=1))
        # Let's estimate k based on weeks between start_monday and min_target.
        weeks_diff = (min_target - start_monday).days // 7
        k = max(0, (weeks_diff // N) - 1)
        
        while True:
            week_start = start_monday + timedelta(weeks=k * N)
            for wd in sorted(target_wd):
                cand = week_start + timedelta(days=wd)
                if cand >= start:
                    resolved = _resolve_holiday(cand, holidays)
                    if resolved > after:
                        return resolved
            k += 1

    elif rtype == "monthly":
        N = int(parts[1])
        D = int(parts[2])

        # Monthly: every N months from start, on day-of-month D.
        # How are months counted from start?
        # Month index k: start date's year/month is base, or start day?
        # Usually, month 0 is start's month (or start date, with day D in month 0 or adjusted).
        # Let's check: "every N months from start, on day-of-month D".
        # If start is 2023-01-15, monthly:1:10 -> does it start on 2023-01-10 or 2023-02-10?
        # "every N months from start, on day-of-month D" -> month 0 is start's month, or the first occurrence >= start.
        # Let's test both or align with the rule: months 0, N, 2N, ... from start's (year, month).
        base_year = start.year
        base_month = start.month
        
        min_target = max(start, after + timedelta(days=1))
        # Estimate month index k
        total_months_diff = (min_target.year - base_year) * 12 + (min_target.month - base_month)
        k = max(0, (total_months_diff // N) - 2)

        while True:
            total_m = (base_month - 1) + k * N
            y = base_year + total_m // 12
            m = total_m % 12 + 1
            _, last_d = monthrange(y, m)
            d = min(D, last_d)
            cand = date(y, m, d)
            if cand >= start:
                resolved = _resolve_holiday(cand, holidays)
                if resolved > after:
                    return resolved
            k += 1

    raise ValueError(f"Unknown rule type: {rtype}")
