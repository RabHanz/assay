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
    while d in holidays:
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
    kind = parts[0]

    if kind == "daily":
        n = int(parts[1])
        # Find k such that start + k*n > after
        # start + k*n > after <=> k*n > after - start <=> k >= (after - start).days // n + 1
        diff = (after - start).days
        if diff < 0:
            k = 0
        else:
            k = diff // n + 1
        
        while True:
            cand = start + timedelta(days=k * n)
            resolved = _resolve_holiday(cand, holidays)
            if resolved > after:
                return resolved
            k += 1

    elif kind == "weekly":
        n = int(parts[1])
        weekdays_str = parts[2]
        weekday_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_wd = {weekday_map[w] for w in weekdays_str.split(",")}

        # We can align to weeks from start.
        # Week 0 starts on start - timedelta(days=start.weekday()) or similar?
        # Wait, how are weekly:N:MO,WE defined?
        # "every N weeks from start, on the listed weekdays"
        # Usually, weeks are anchored relative to start's week, or start itself.
        # Let's anchor weeks relative to start's Monday (or start's week start).
        # Specifically, start_monday = start - timedelta(days=start.weekday())
        # Week i starts at start_monday + timedelta(weeks=i*n).
        # Within week i, we check all weekdays in target_wd.
        # If multiple weekdays match, we take them in chronological order.
        # Let's check how week blocks work.
        
        start_monday = start - timedelta(days=start.weekday())
        
        # Estimate week index k so that start_monday + weeks(k*n) is around after.
        # Let's find an initial k based on (after - start_monday).days // 7
        approx_weeks = (after - start_monday).days // 7
        k = max(0, approx_weeks // n - 1)

        while True:
            week_start = start_monday + timedelta(weeks=k * n)
            # generate candidate dates in this week
            week_cands = []
            for wd in sorted(target_wd):
                cand = week_start + timedelta(days=wd)
                # Should we consider cands >= start? Or just any candidate after after?
                # The rule says "every N weeks from start, on the listed weekdays". 
                # Does it include days before start if they fall in the same week? 
                # Usually schedule starts from start, or week containing start. But let's check if cand >= start or if after can be before start.
                # If cand > after, we check it.
                resolved = _resolve_holiday(cand, holidays)
                if resolved > after:
                    week_cands.append(resolved)
            
            if week_cands:
                # filter out those not >= start if start is strict? But rule says "every N weeks from start". 
                # Wait, if start is Wednesday, and rule is weekly:1:MO,WE, does MO of that week (which is before start) count?
                # Usually schedule occurrences start at or after start, or at least we should filter cand >= start? 
                # Wait! Let's check if `cand >= start` is required. "every N weeks from start, on the listed weekdays".
                # If start is Wednesday, Monday of that week is before start. Is Monday due? 
                # Let's be careful: `cand >= start` is standard for "from start". But wait, what if `after` is before `start`? 
                # "Return the next due date strictly after `after`." If `after` is way in the past, and start is today, do we return dates before start? 
                # No, "from start" means starting from start. Let's filter `cand >= start`.
                valid_week_cands = [c for c in week_cands if c >= start]
                if valid_week_cands:
                    return min(valid_week_cands)
            k += 1

    elif kind == "monthly":
        n = int(parts[1])
        d_day = int(parts[2])

        # Monthly:N:D
        # "every N months from start, on day-of-month D"
        # How are months counted from start?
        # Month 0 is start's month (or we can anchor by month index from start's year/month).
        # Let's compute month offset relative to start.
        # start has year, month, day.
        start_month_idx = start.year * 12 + start.month - 1
        after_month_idx = after.year * 12 + after.month - 1
        
        diff_months = after_month_idx - start_month_idx
        if diff_months < 0:
            k = 0
        else:
            k = max(0, diff_months // n - 1)

        while True:
            target_month_idx = start_month_idx + k * n
            year = target_month_idx // 12
            month = target_month_idx % 12 + 1
            
            _, last_day = monthrange(year, month)
            day = min(d_day, last_day)
            cand = date(year, month, day)

            resolved = _resolve_holiday(cand, holidays)
            if resolved >= start and resolved > after:
                return resolved
            k += 1

    raise ValueError(f"Unknown rule: {rule}")
