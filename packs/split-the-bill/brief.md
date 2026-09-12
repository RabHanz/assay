The file `solution.py` in your workspace contains `split_bill`, which is not implemented.

Implement it exactly as its docstring specifies:

- `total` is a bill in pounds as a string with two decimals, for example `"100.00"`.
- `ways` is how many people share it, an integer of at least 1.
- Return a list of `ways` strings, each a share in pounds with exactly two decimals.
- The shares must add up to `total` exactly, to the penny. `"100.00"` split three ways is
  `["33.33", "33.33", "33.34"]`, never three lots of `"33.33"`, which loses a penny.
- No share may differ from any other by more than one penny.
- When the split is uneven, the smaller shares come first and the larger ones last.

Do not use floating-point arithmetic on the money; work in pence.

Read the file first, then write the complete corrected file with `write_file`, then call `done`.
Standard library only.
