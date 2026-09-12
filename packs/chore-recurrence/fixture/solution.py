from datetime import date


def next_due(start: date, rule: str, after: date, holidays):
    """Return the next due date strictly after `after` for a chore.

    rule is one of:
      'daily:N'            every N days from start
      'weekly:N:MO,WE'     every N weeks from start, on those weekdays
      'monthly:N:D'        every N months from start, on day-of-month D
    A due date landing on a date in `holidays` (a set of date) rolls FORWARD
    to the next day that is not a holiday.
    """
    raise NotImplementedError
