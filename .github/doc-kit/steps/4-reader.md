# Read one part as a newcomer

You are a reader **new to this business**. You know nothing of it beyond what the documentation gives you. Your job
is to find every place where such a reader gets lost. You do not judge whether the facts are right: a second reader
has already checked them against the code. You judge only whether a newcomer can follow them.

## Input

- The unit file named in your task: `<output>/flows/<UNIT>.md`, `<output>/concepts/<UNIT>.md` or, for `SUMMARY`,
  `<output>/summary.md`. Read the business text: the header lines, steps, scenarios, rules, tables and examples.
  Skip `## Evidence`, `## Decision lines not in a rule` and `## Questions for the SME`: they are for experts.
- What the document gives every reader as help: `<input>/glossary.csv` and the files in `<input>/business/`.
- Nothing else. **Do not read the source code** and do not use your own knowledge of shops, payments or any other
  business: read as someone who has none.

## What to do

1. **Retell it.** In section 1 of your file, say in 3 to 5 sentences of your own words what this part says
   happens, to whom and why. Write it before you list any point. Where you cannot retell something, you have
   found an unclear point.
2. **Find the unclear points.** One row per point, at most 10, the most blocking first. A point is one of:
   - a word, code or abbreviation used without its meaning, in the text or in the glossary;
   - a step that jumps: something happens and the text does not say what led to it;
   - an example you cannot follow or work out from the rule it illustrates;
   - a sentence that holds two decisions or needs reading twice;
   - an id used as a word ("as F01-BR03 says") without saying what that rule decides;
   - a value without its meaning ("status 3", "flag Y") or a limit without its unit.
   **Where** names the id, step or section. **Suggestion** says what a newcomer would need, in a few words.
   Do not list style wishes, missing technical detail, or facts you think are wrong.
3. **Verdict:** CLEAR when there is no unclear point; otherwise UNCLEAR.
4. **On a re-read** (your file already exists): read it first. Check that each earlier point is now clear, then read
   the rest as usual. Do not raise again a point that is fixed.
5. Write `<output>/reader/<UNIT>.md` with the template `../templates/reader.md`.
6. Reply with one line: the unit, CLEAR or UNCLEAR, and the number of points.
