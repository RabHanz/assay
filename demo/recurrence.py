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
    
    parts = rule.split(':')
    type = parts[0]
    
    def apply_holiday_roll(d):
        while d in holidays:
            d += timedelta(days=1)
        return d

    if type == 'daily':
        n = int(parts[1])
        # Find the first occurrence after 'after'
        days_diff = (after - start).days
        # k*n > days_diff => k > days_diff / n
        if days_diff < 0:
            k = 0
        else:
            k = (days_diff // n) + 1
        
        cand = start + timedelta(days=k * n)
        return apply_holiday_roll(cand)

    elif type == 'weekly':
        n = int(parts[1])
        weekdays = parts[2].split(',')
        weekday_map = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}
        target_weekdays = sorted([weekday_map[wd] for wd in weekdays])
        
        # We need to check weeks. A week starts from 'start'.
        # Let's just generate candidates in order.
        # This might be inefficient if 'after' is very far, but it's simple.
        
        # Optimization: start checking from a reasonable point.
        # Weeks since start:
        days_since_start = (after - start).days
        week_num = max(0, days_since_start // 7)
        
        while True:
            # Check weeks starting from week_num
            for w in range(week_num, week_num + 1000000): # Safety break or just loop
                if w % n == 0:
                    week_start = start + timedelta(weeks=w)
                    for wd in target_weekdays:
                        # Day in this week
                        day_in_week = week_start + timedelta(days=(wd - week_start.weekday()))
                        if day_in_week > after:
                            return apply_holiday_roll(day_in_week)
            week_num += 1

    elif type == 'monthly':
        n = int(parts[1])
        d = int(parts[2])
        
        # Generate candidates: start + k*n months
        # For each candidate month, day is min(d, last_day_of_month)
        
        months_since_start = (after.year - start.year) * 12 + (after.month - start.month)
        k = max(0, (months_since_start // n))
        
        while True:
            # Current month candidate
            year = start.year + (start.month - 1 + k * n) // 12
            month = (start.month - 1 + k * n) % 12 + 1
            
            last_day = calendar.monthrange(year, month)[1]
            day = min(d, last_day)
            cand = date(year, month, day)
            
            if cand > after:
                return apply_holiday_roll(cand)
            k += 1
