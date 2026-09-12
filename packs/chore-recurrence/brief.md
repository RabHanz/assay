The file `solution.py` in your workspace contains a function `next_due` that is not implemented.

Implement it exactly as its docstring specifies:

- `rule` is one of `daily:N` (every N days from `start`), `weekly:N:MO,WE` (every N weeks from
  `start`, on the listed weekdays; weekday codes are MO TU WE TH FR SA SU), or `monthly:N:D`
  (every N months from `start`, on day-of-month D).
- Return the next due date strictly after `after`.
- A due date that lands on a date in `holidays` (a set of `date`) rolls FORWARD to the next day
  that is not a holiday.
- If day-of-month D does not exist in a month (for example 31 in February), the due date is the
  last day of that month.
- `after` may be far in the future; return the next occurrence after it, not merely the next step
  after `start`.

Read the file first, then write the complete corrected file with `write_file`, then call `done`.
Standard library only.
