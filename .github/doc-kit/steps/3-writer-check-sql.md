# Write the data check SQL for one output

First read `0-rules.md` in this folder and follow it.

If the documentation is right, a second implementation written **only from the documentation** produces the same
output as the legacy system. You write that second implementation as one SQL query. A person runs it on the test
database, and the tool compares its result with the real output, field by field.

## Input

- The output named in your task (for example `O01`): its unit files in `<output>/outputs/`, its specification,
  and the flows that write it in `<output>/flows/` (for which records are selected, and their order).
- **Do not read the source code.** The SQL must come from the documentation alone; that is what makes it a check.
  If the documentation is not clear enough for part of the SQL, write your best reading and add a comment
  `-- GAP: <what is unclear>`.

## What to do

1. One `SELECT` in the SQL of the test database named in `<input>/module.md` (`Test database`; Oracle when
   empty) that returns one column, `RECORD`: the complete expected output line for every record the
   documentation says is written, in the documented order.
   When the spec has a `record` column, return every line of the file in file order: header, details, trailer
   (a `UNION ALL` with a sort key). Counts and totals in a header or trailer are computed over the details the
   documentation says are written.
2. Each field follows its requirements. A **positional** output (the spec has positions): `RPAD(NVL(x, ' '), n, ' ')`
   for left-aligned text, `LPAD(..., n, '0')` for zero-padded numbers, `CASE` for each decision table,
   `TO_CHAR(d, 'YYYYMMDD')` for dates. A **table or message** (the spec has no positions): the fields in spec
   order joined with `|`, amounts with 2 decimals (`1500.00`), an empty string when there is no value. Rows of a
   table are compared without regard to order.
   Put the requirement ids in a comment on each field.
3. The selection rules of the flow become the WHERE clause, with comments naming the rule ids.
   Use `:run_date` for the run date. The SQL runs on the test database **as it was before the run**: compute
   what the run will write from the data that was there (pending requests, stock levels, earlier orders).
4. Write `<output>/data-check/<OUTPUT>.sql`.
5. Reply with one line: the output, the number of fields, the number of GAP comments.
