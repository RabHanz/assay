from datetime import date, timedelta
import calendar


def next_due(start: date, rule: str, after: date, holidays):
    """Return the next due date strictly after `after` for a chore.

    rule is one of:
      'daily:N'            every N days from start
      'weekly:N:MO,WE'     every N weeks from start, on those weekdays
      'monthly:N:D'        every N months from start, on day-of-month D
    A due date landing on a date in `holidays` (a set of date) rolls FORWARD
    to the next day that is not a holiday.
    """
    # Helper to roll forward over holidays
    def roll_forward(d: date) -> date:
        while d in holidays:
            d += timedelta(days=1)
        return d

    parts = rule.split(':')
    if parts[0] == 'daily':
        # rule format: daily:N
        if len(parts) != 2:
            raise ValueError(f"Invalid daily rule: {rule}")
        N = int(parts[1])
        if N <= 0:
            raise ValueError("N must be positive for daily rule")
        # If start is after 'after', candidate is start
        if start > after:
            candidate = start
        else:
            diff = (after - start).days
            k = diff // N + 1
            candidate = start + timedelta(days=k * N)
        return roll_forward(candidate)

    if parts[0] == 'weekly':
        # rule format: weekly:N:MO,WE
        if len(parts) != 3:
            raise ValueError(f"Invalid weekly rule: {rule}")
        N = int(parts[1])
        if N <= 0:
            raise ValueError("N must be positive for weekly rule")
        weekdays_str = parts[2]
        weekday_map = {
            'MO': 0,
            'TU': 1,
            'WE': 2,
            'TH': 3,
            'FR': 4,
            'SA': 5,
            'SU': 6,
        }
        try:
            weekdays = sorted({weekday_map[w.strip()] for w in weekdays_str.split(',')})
        except KeyError as e:
            raise ValueError(f"Invalid weekday code in rule: {e}")

        # Compute week offset candidate
        if after < start:
            week_offset_start = 0
        else:
            diff_days = (after - start).days
            week_offset_start = diff_days // 7
        # Find the next week offset that is a multiple of N
        if week_offset_start % N == 0:
            week_offset = week_offset_start
        else:
            week_offset = week_offset_start + (N - week_offset_start % N)

        while True:
            # For this week offset, compute candidate dates
            base = start + timedelta(weeks=week_offset)
            # base is the date that is start + week_offset weeks
            # We need to find dates in this week that match weekdays
            candidates = []
            for w in weekdays:
                # Compute delta days from base.weekday() to target weekday w
                delta = (w - base.weekday()) % 7
                candidate = base + timedelta(days=delta)
                if candidate > after:
                    candidates.append(candidate)
            if candidates:
                candidate = min(candidates)
                return roll_forward(candidate)
            # No candidate in this week after 'after', move to next cycle
            week_offset += N

    if parts[0] == 'monthly':
        # rule format: monthly:N:D
        if len(parts) != 3:
            raise ValueError(f"Invalid monthly rule: {rule}")
        N = int(parts[1])
        if N <= 0:
            raise ValueError("N must be positive for monthly rule")
        D = int(parts[2])
        if not (1 <= D <= 31):
            raise ValueError("Day-of-month D must be between 1 and 31")

        def month_offset_to_date(offset: int) -> date:
            # Compute year and month for start + offset months
            year = start.year + (start.month - 1 + offset) // 12
            month = (start.month - 1 + offset) % 12 + 1
            # Determine last day of month
            last_day = calendar.monthrange(year, month)[1]
            day = min(D, last_day)
            return date(year, month, day)

        if after < start:
            month_offset_start = 0
        else:
            # Compute months difference between start and after
            months_diff = (after.year - start.year) * 12 + (after.month - start.month)
            month_offset_start = months_diff
        # Find the next month offset that is a multiple of N
        if month_offset_start % N == 0:
            month_offset = month_offset_start
        else:
            month_offset = month_offset_start + (N - month_offset_start % N)

        while True:
            candidate = month_offset_to_date(month_offset)
            if candidate > after:
                return roll_forward(candidate)
            month_offset += N

    raise ValueError(f"Unknown rule type: {parts[0]}")
