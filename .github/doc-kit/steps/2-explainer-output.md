# Trace the fields of one output

First read `0-rules.md` in this folder and follow it.

This step runs only for outputs that have a specification in `<input>/outputs/`. It says, field by field, where
each value comes from and every rule applied on the way.

## Input

- The unit named in your task (`O01`, or `O01-P2` for the second part of a long output) and the field range
  the task gives ("Fields 1-12 of the spec"). Document exactly those fields.
- **Start with the context pack:** run `python .github/doc-kit/tools/doc.py context <UNIT>`. It gives your fields
  from the spec, the business rules of every flow (the flows that write the output first: a value can come from
  an earlier flow through an intermediate file), and the lines where the code writes. Then read those flow files
  in `<output>/flows/`. Open `<output>/inventory.md` only for what the pack does not show.
- The input folder: `business/`, `glossary.csv`, `sme-answers.md`, `test-data/` if present.
- If the task names a problems file, a verify file or a data check report: fix every point in it.

## What to do

For each field of your unit, in spec order:

1. **Start at the output.** Find the code that puts a value at this field's place: for a fixed-position file the
   writer call at its positions, for a table the column in the INSERT or UPDATE, for a message the property.
   For a positional file, add up the lengths of the writer calls before it to confirm the positions.
   When the spec has a `record` column (header, detail and trailer layouts), find the writer of that record
   type and write its code on the line **Record:**; positions start again at 1 in each record type. A header or
   trailer field is often a count, total, date or sequence number: say over which records it is counted or summed.
2. **Go back one hop at a time** until you reach a database column, a fixed value, the run date or a
   calculation: writer → intermediate file (read and write) → every place the value is set in Java (all of
   them, with the condition of each) → result-set read (for `rs.getString(3)` count the SELECT items carefully)
   → SQL item → table and column.
   A value written with `String.format` takes its width, alignment and decimals from the pattern (`%-12s` is
   left-aligned text of 12, `%12.2f` a right-aligned number of 12 with 2 decimals): count each one.
3. **Requirements.** Each rule on the way is one requirement: SQL (NVL, CASE, DECODE, functions), Java (if,
   ternary, defaults, rounding, sign, format), writer (padding, cutting). In the order the system applies them.
4. **Link each requirement to its business rule.** In the column `Business rule`, name the rule of the flow file
   that decides this value (`F01-BR05`; several when several decide it: `F01-BR05, F01-BR06`). This is what lets
   a business reader go from a rule ("Refund amount split") to every field it fills, and back. Write:
   - the rule id, when a flow rule decides the value (a split, a code, a date, a copy from the original);
   - `format` when the requirement only lays the value out (padding, cutting, date or number format);
   - `none` when no flow rule decides it, and add a question for the SME: the flow is missing a rule.
   The tool checks that every id is a rule in the flow files, that every field names at least one rule (or is
   layout only), and, with the last part of an output, that every rule saying "Writes ... (output O01)" is
   named by at least one field.
5. **Common or variant.** If the value depends on a code (event, order type), the field is variant: add a
   decision table with one row per value from the input folder (rows may be grouped when the value is the same).
6. **Examples.** Use values from `test-data/` when present. Work out the exact characters written and show
   spaces as `·`; the tool checks the length.
7. **Evidence.** One row per hop, with the exact code.
8. Write `<output>/outputs/<UNIT>.md` with the template `../templates/output.md`.
9. Run `python .github/doc-kit/tools/doc.py check <UNIT>` and fix every problem until it prints `OK`.
10. Reply with one line: the number of fields, variant fields and questions.
