# Explain one business concept

First read `0-rules.md` in this folder and follow it.

A business analyst asked a question, for example "What is an order refund, and how is each field of the refund
record derived?". The business team wrote what they expect in an **intent card**. You answer it in plain words,
line by line: what the business expects, and what the system really does.

You do **not** read the source code. Every flow and output this concept needs has already been documented and
checked by a second reader (and by the data check when there is one). You build the business page from those
checked files only. That is what makes the page right, and the same each time it is written.

## Input

- The unit named in your task (`C01`), its row in `<output>/discovery.md` (section Concepts): its card, its
  flows and its outputs.
- The card in `<input>/concepts/`.
- The flow files and output files of this concept in `<output>/flows/` and `<output>/outputs/`, their verify
  files in `<output>/verify/`, and the data check reports in `<output>/data-check/` when present.
- The real rows of the test run in `<input>/test-data/<output id>/actual.*` when present.
- `<input>/business/`, `<input>/glossary.csv`, `<input>/sme-answers.md`, `<input>/outputs/*.csv`.
- If the task names a problems file or a verify file: fix every point in it.
- If the task names a reader file (`<output>/reader/<UNIT>.md`): a reader new to the domain could not follow the
  points it lists. Rewrite those parts in plainer words and change no fact, id or value.

**Do not open the source code.** If the checked files do not settle something, it is a question for the SME.

## What to do

1. **In short.** At most 150 words: what the concept is in business terms, what starts it, and what it changes.
2. **Each line of the card.** One row per card line (I1, I2, ...), in card order. Copy the card's text. Then:
   - **The system does**: what the documented rules say, in plain words, at most 45 words. Name exact values:
     codes with their meaning, days, amounts.
   - **Status**:
     - `✅ Matches`: the rules show the system does it, in every case the card covers.
     - `⚠️ Differs`: the system does something else, or only in some cases, or more than the card says. Say
       exactly how it differs, with a case (for example "a partial refund does not return the shipping charge").
     - `❓ Not found in the code`: no documented rule does it. It may be done by another system: add a question.
   - **Based on**: the rule, scenario and requirement ids that show it (`F01-BR03`, `F01-SC2`, `O01-05-R1`).
     The tool checks that each id exists. Not needed for `❓`.
3. **Types and how each works.** One row per code that changes what the system does for this concept: each
   event, transaction type, order type or status (for example a payment and its reversal, and each transaction
   code under them). Meaning copied from the input folder; how the system handles that type, in plain words; one
   small example with numbers; Based on its rule ids. Group codes that are handled the same way in one row
   ("`GOLD`, `SILVER`: ..."). The tool checks that every code the flows compare with, and that has a meaning in
   the input folder, has a row.
4. **Also in the system.** Up to 10 business behaviours of these flows that the card does not mention and a
   business reader must know: which records are selected, rejections, dates used, what happens on an error.
   Ids A1, A2, with Based on.
5. **Fields this question changes.** For each output of the concept with a specification: one row per field
   whose value changes by type, event or code (its **Kind:** is a variant; the tool checks that each one has a
   row), and any other field this question needs. Business meaning from `business/`, the glossary or the spec;
   Derived as in plain words, for each variant (for an order / for a refund); Based on the output's requirement
   ids. Do not copy the other fields: the document describes each field once, in its output section.
6. **Worked examples.** One example for each main case of the card, with real rows from the test run when
   they are there (say which reference). For each: the order before, the event (the tool checks the line **Event:**), how
   the amount is split, and the order after.
   **Follow it into the file.** When the real test file is in `<input>/test-data/<output id>/actual.*`, end each
   example that reaches it with `**In the file:** O01 line <n>` (the line of that file the example becomes) and a
   table `| Field | Value | Based on |`: the fields that tell the story, with the exact characters of that line
   (`·` for a space) and the requirement ids that set them. The tool reads the line and checks every value. This is
   how a reader connects a business case to the real record.
7. **Questions for the SME**: every `⚠️` that may be a defect, and every `❓`.
8. Write `<output>/concepts/<UNIT>.md` with the template `../templates/concept.md`.
9. Run `python .github/doc-kit/tools/doc.py check <UNIT>` and fix every problem until it prints `OK`.
10. Reply with one line: the unit, and the number of lines that match, differ and are not found.

## Write for a business analyst

- Business words only: "the refund is refused when the order is not delivered", never code or Java names. The tool
  rejects Java names, method calls and code operators on this page.
- Table and column names (`ORDER_TXN.TAX_AMT`) only in the Field column; ids only in Based on.
- One fact per sentence. No "may", "probably", "seems": a fact is in a checked file, or it is a question.
