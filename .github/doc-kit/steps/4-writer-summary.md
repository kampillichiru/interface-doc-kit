# Write the business summary

First read `0-rules.md` in this folder and follow it.

The summary opens the document. Its reader knows **nothing** of this business: a new analyst, a tester, someone
from another team. After reading it they must be able to tell the whole story of the module in their own words.

You do **not** read the source code. Every flow, output and concept has already been documented and checked by a
second reader. You build the summary from those checked files only, so it says nothing they do not say.

## Input

- `<output>/discovery.md`: the flows, and section 8, **How the document will explain it**. Follow that plan: its
  readers, its reading order, its main example, its terms and its cases.
- The flow files in `<output>/flows/`, the output files in `<output>/outputs/`, the concept pages in
  `<output>/concepts/` when there are any, and the data check reports in `<output>/data-check/` when present.
- `<input>/business/`, `<input>/glossary.csv`, `<input>/sme-answers.md`, `<input>/test-data/` when present.
- If the task names a problems file, a verify file or a reader file: fix every point in it. A reader file lists what
  a newcomer could not follow: rewrite those parts in plainer words and change no fact, id or value.

**Do not open the source code.** If the checked files do not settle something, it is a question for the SME.

## What to do

1. **In one paragraph.** At most 120 words: what the module is for, who uses it, what starts its work and what it
   produces. Take the purpose from `module.md` and `business/`.
2. **Who and what is involved.** One row per person, team, system or file the process involves, with its role.
3. **The process from start to end.** One row per business step, in the plan's reading order, about 6 to 15 rows.
   Tell it as a story a newcomer can follow: what happens, then what happens next. Every flow appears.
   **Based on** names the rule and scenario ids each row rests on (`F01-BR03`, `F01-SC1`).
4. **A worked example.** The plan's main example, followed from the first step to the last, with real numbers.
   Use the numbers of the flows' examples or of the test data. Work every amount out again from the rules.
5. **What can go wrong.** One row per other case: every rejection, error, alternate path and code value with
   different behaviour. The tool checks that **every scenario of every flow** is named somewhere in the summary.
6. **Words to know.** Every code and abbreviation you used (COD, SKU, PENDING_PAYMENT), and every term of the plan's
   "Terms to explain first", with its meaning **copied from the input folder**. A term without a meaning there is
   a question, not a row.
7. **Questions for the SME**: what the checked files leave open that a newcomer would ask.
8. Write `<output>/summary.md` with the template `../templates/summary.md`.
9. Run `python .github/doc-kit/tools/doc.py check SUMMARY` and fix every problem until it prints `OK`.
10. Reply with one line: the number of process steps, cases under What can go wrong, and words to know.

## Write for a newcomer

- Short sentences, one fact each, at most 25 words. Explain a word the first time you use it.
- Business words only: "the order is refused when an item is out of stock", never code or Java names. The tool
  rejects Java names, method calls and code operators.
- Say what a value means, not only what it is: "status CONFIRMED (paid, or cash on delivery; ready to ship)".
- Ids only in Based on. No "may", "probably", "seems": a fact is in a checked file, or it is a question.
