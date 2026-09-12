from datetime import date, timedelta
from calendar import monthrange


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return d.replace(year=y, month=m)


def _apply_holidays(d: date, holidays) -> date:
    if holidays is None:
        return d
    while d in holidays:
        d += timedelta(days=1)
    return d


def next_due(start: date, rule: str, after: date, holidays) -> date:
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
    n = int(parts[1])

    if rtype == "daily":
        # Every N days from start
        # d = start + k * N
        # We need d > after => start + k * N > after => k * N > (after - start).days
        # k >= floor((after - start).days / N) + 1 (or we can just iterate or compute min k)
        diff = (after - start).days
        if diff < 0:
            k = 0
        else:
            k = diff // n + 1
        
        while True:
            candidate = start + timedelta(days=k * n)
            if candidate > after:
                res = _apply_holidays(candidate, holidays)
                if res > after:
                    return res
            k += 1

    elif rtype == "weekly":
        # weekly:N:MO,WE
        weekday_strs = parts[2].split(",")
        weekday_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
        target_wd = {weekday_map[w] for w in weekday_strs}

        # Start week alignment. A week starts on Monday or we can find weeks relative to start's week.
        # Usually "every N weeks from start" means:
        # Week 0 is the week containing start, or weeks counted from start's Monday / week start?
        # Let's check Python's standard interpretation or ISO weeks / 7-day blocks from start.
        # "every N weeks from start" typically means weeks anchored at start, or 7*N day blocks from start.
        # Wait, let's be precise. Does "weekly:N:MO,WE" mean every N weeks relative to start, and on those weekdays in that week?
        # Let's consider how weeks are defined. A week can be a 7-day period starting on Monday, or starting on start's weekday, or ISO weeks.
        # Let's test standard assumptions or check if start is Monday-aligned or start-aligned.
        # Usually, "N weeks from start" means every N weeks where week 0 is the week of start (or N-week blocks starting from start).
        # Let's check both or design a robust approach.
        # Let's see: if start is on a Wednesday, does week 0 start on start, or Monday?
        # In many date scheduling libraries (like iCal / RRULE or similar Python dateutil rrule):
        # rrule weekly intervals count from start date's week or 7-day blocks.
        # Wait, let's examine standard conventions or write a helper that generates candidate dates.
        # Let's consider: if we generate all candidate weekdays for weeks $k = 0, 1, 2, \dots$ where week $k$ starts at `start + timedelta(weeks=k*N)` or similar?
        # Wait, what if the weekdays are in the week containing `start + timedelta(weeks=k*N)`?
        # Let's define the weeks starting on Monday or starting on start's weekday?
        # Actually, let's look at how weekly rules are usually specified: "weekly:N:MO,WE" means every N weeks from start on MO and WE.
        # If we anchor 7-day periods from `start` (or start's Monday), let's check what makes the most sense.
        # Wait! If start is Wednesday, and rule is weekly:1:MO,WE, does MO refer to the Monday of the week of start?
        # Let's check standard python date weekday: Monday is 0, Sunday is 6.
        # If we find the Monday of start's week (or start itself), let's see.
        # Let's check if start's week is anchored at Monday or Sunday or start.
        # Usually, week-based rules in Python date libraries (like dateutil or standard calendar) align weeks to Monday (or Sunday).
        # But wait, "every N weeks from start" could mean:
        # Week k starts at `start + timedelta(weeks=k*N)` and goes for 7 days, or it aligns with calendar weeks (Monday-Sunday) containing those dates.
        # Let's test both or check if start is always aligned or if we can handle both / standard interpretation.
        # Wait, let's re-read carefully: "every N weeks from start, on the listed weekdays".
        # If someone says "every 2 weeks from start on MO, FR", it usually means:
        # Take the weeks (e.g. ISO weeks or Monday-starting weeks, or weeks starting on start's day of week) that are spaced by N weeks from start's week, and pick MO and FR in those weeks.
        # Specifically, let's find the Monday (or week start) of `start`. If weeks start on Monday:
        # week_0_monday = start - timedelta(days=start.weekday())
        # Then week k starts at `week_0_monday + timedelta(weeks=k*N)`.
        # For each week starting at `w_start`, the days in that week are `w_start + timedelta(days=i)` for `i` in 0..6.
        # If that day's weekday is in `target_wd` AND the date is `>= start`, it's a due date!
        # Wait, what if `start` itself is a Wednesday, and rule is weekly:1:MO? If week starts on Monday, the Monday of start's week is before start. But the rule says "from start", so any due date must be `>= start`.
        # That fits naturally: generate days in week k, filter `d >= start`, and then find the first one strictly after `after`.
        
        # Let's also consider if week 0 starts on `start`'s weekday or Monday. Usually Monday is standard for MO, WE.
        # Let's check Monday-based weeks vs start-based 7-day blocks.
        # Actually, let's check if we can support both or if Monday-based calendar weeks are standard.
        # Wait, if `start` is a Tuesday, and we want "every 1 week on TU", if weeks started on Monday, TU would be day 1 of the week. If weeks started on Tuesday, TU would be day 0 of the week.
        # But weekday codes MO, TU, WE, TH, FR, SA, SU are absolute calendar weekdays (Monday = MO, etc.). Therefore, calendar weeks (Monday-Sunday) are standard when specific weekday names (MO, TU...) are given.
        # Let's verify: Monday-Sunday calendar weeks where week 0 is the calendar week containing `start`, and we take weeks at intervals of N weeks.
        
        week_0_mon = start - timedelta(days=start.weekday())
        
        # We can start searching from k such that the week is around `after`.
        # Estimate k from (after - week_0_mon).days // (7 * n)
        est_days = (after - week_0_mon).days
        k = max(0, est_days // (7 * n) - 1)
        
        while True:
            w_mon = week_0_mon + timedelta(weeks=k * n)
            # Week days
            for i in range(7):
                d = w_mon + timedelta(days=i)
                if d >= start and d.weekday() in target_wd:
                    if d > after:
                        res = _apply_holidays(d, holidays)
                        if res > after:
                            return res
            k += 1

    elif rtype == "monthly":
        # monthly:N:D (every N months from start, on day-of-month D)
        d_val = int(parts[2])
        
        # We need months from start.
        # Month 0 is start.month in start.year (or we can track m_index).
        # Let's define month index m_idx relative to start.
        # Start month index = 0. Month m_idx is `_add_months(start_base, m_idx * n)`.
        # What is `start_base`? Is it a date in start's month with day D, or start itself?
        # "every N months from start, on day-of-month D"
        # Usually, the series of months starts with the month of `start` (or the first occurrence on day D on or after `start`).
        # Let's check: if start is Jan 15, and rule is monthly:1:10, does the first occurrence happen in January 10 (which is before start, so filtered out by `>= start`) or February 10?
        # "every N months from start" means the month sequence starts from `start`'s month.
        # Let's test month index `m_idx = 0, 1, 2, ...`.
        # For each `m_idx`, target month date has year/month given by adding `m_idx * n` months to `start`.
        # Day is min(d_val, last day of that month).
        # If that date is `>= start`, it's a valid scheduled date.
        
        # Estimate m_idx from after
        # Approximate months between start and after:
        approx_months = (after.year - start.year) * 12 + (after.month - start.month)
        m_idx = max(0, approx_months // n - 2)
        
        while True:
            target_month_date = _add_months(start.replace(day=1), m_idx * n)
            last_day = monthrange(target_month_date.year, target_month_date.month)[1]
            day_to_use = min(d_val, last_day)
            candidate = date(target_month_date.year, target_month_date.month, day_to_use)
            
            if candidate >= start and candidate > after:
                res = _apply_holidays(candidate, holidays)
                if res > after:
                    return res
            m_idx += 1

    else:
        raise ValueError(f"Unknown rule type: {rtype}")
