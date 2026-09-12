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
    freq_type = parts[0]
    
    if freq_type == "daily":
        n = int(parts[1])
        diff = (after - start).days
        if diff < 0:
            k = 0
        else:
            k = diff // n
            while (start + timedelta(days=k * n)) <= after:
                k += 1
        
        while True:
            cand = start + timedelta(days=k * n)
            resolved = _resolve_holiday(cand, holidays)
            if resolved > after:
                return resolved
            k += 1

    elif freq_type == "weekly":
        n = int(parts[1])
        weekdays_str = parts[2]
        weekday_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_wd = {weekday_map[w] for w in weekdays_str.split(",")}
        
        start_monday = start - timedelta(days=start.weekday())
        
        after_monday = after - timedelta(days=after.weekday())
        weeks_diff = (after_monday - start_monday).days // 7
        k = max(0, weeks_diff // n - 2)
        
        while True:
            week_start = start_monday + timedelta(weeks=k * n)
            for wd in sorted(target_wd):
                cand = week_start + timedelta(days=wd)
                if cand >= start:
                    resolved = _resolve_holiday(cand, holidays)
                    if resolved > after:
                        return resolved
            k += 1

    elif freq_type == "monthly":
        n = int(parts[1])
        day_d = int(parts[2])
        
        months_approx = (after.year - start.year) * 12 + (after.month - start.month)
        k = max(0, months_approx // n - 2)
        
        while True:
            target_year = start.year + (start.month - 1 + k * n) // 12
            target_month = (start.month - 1 + k * n) % 12 + 1
            _, last_d = monthrange(target_year, target_month)
            d_val = min(day_d, last_d)
            cand = date(target_year, target_month, d_val)
            
            if cand >= start:
                resolved = _resolve_holiday(cand, holidays)
                if resolved > after:
                    return resolved
            k += 1

    raise ValueError(f"Unknown rule: {rule}")
