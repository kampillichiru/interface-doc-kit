# Verify one unit (independent second reader)

First read `0-rules.md` in this folder and follow it.

You did not write the file you check. Your job is to find what is wrong with it. The tool has already checked
the form (every quote is at its line, ids, the flow graph, lengths), so spend your effort on the **meaning**.

## Input

- The unit named in your task, its row in `<output>/discovery.md`, the source code, the input folder. For a flow
  or an output, start with `python .github/doc-kit/tools/doc.py context <UNIT>`: the code places to read.
- The unit file `<output>/flows/<UNIT>.md`, `<output>/outputs/<UNIT>.md`, `<output>/concepts/<UNIT>.md` or, for
  `SUMMARY`, `<output>/summary.md`. **Do not open it before step 2.**

## What to do

1. **Your own reading first.** From the code alone, write in section 1 of your file, as short bullets: for a
   flow, its decisions and ends; for an output, each field's source and rules. Write it before you open the unit
   file, so that its reasoning cannot steer yours.
   **An output unit:** your task names up to 3 fields for a spot check. Trace each one from the code yourself
   (writer, every hop, the business rule that decides it) and write it under `## Spot check`. The tool compares
   your rules with the unit file's: when they differ, read the code again and decide which is wrong.
2. **Compare.** Open the unit file and check each rule, step, scenario, requirement, decision row and example:
   - Does the code really do that, in every case? Look for `>` versus `>=`, the default branch, null and empty
     values, rounding, the order of checks.
   - Work out every example again from the code.
   - Is anything in the code missing from the file: a condition, a branch, a value, an error path?
   - **An output unit:** does each requirement name the right business rule in `Business rule`? The rule must
     really decide that value in the code (the split rule for the amounts, the refund rule for copied values).
     A wrong or missing link is a FAIL point: the business reader follows it.
   - Is any business meaning not backed by the input folder?
   **A concept unit** (`C01`, file `<output>/concepts/<UNIT>.md`) is built from the checked flow and output files,
   not from the code. In step 1, write your own reading of each line of its card: from the code, does the
   system do it, and where? Then check:
   - Every `✅ Matches`: does the system do it in **every** case the card covers? A single exception (one
     order type, one status) makes it `⚠️ Differs`.
   - Every `❓ Not found in the code`: search the code for it. If the code does it, the page is wrong.
   - Every `⚠️ Differs`: is the difference stated exactly, with a case?
   - Every row of Fields this question changes and the Worked examples: work each example out again from the
     rules (the split, every amount, every value in the file).
   - Is any business meaning not backed by the input folder? Is there code in the text?
   **A flow unit:** is anything under `## Decision lines not in a rule` really a business decision? Then it is a
   FAIL point: it must be a rule.
   **The summary** (`SUMMARY`) is built from the checked flow, output and concept files, not from the code. In
   step 1, write your own short story of the module from the flow files. Then check:
   - Every row of the process, the worked example and What can go wrong: do the rules it is based on say that,
     in every case? Work every amount of the worked example out again from the rules.
   - Is any flow, rejection or case of the flows missing, or told in a way that changes its meaning?
   - Does every meaning under Words to know come from the input folder, in substance?
   **What makes a FAIL point.** A statement in the file that is wrong, or a business behaviour that is missing:
   a branch, a rejection, a value or a condition that changes what a business reader or a rebuilding team would
   do. Technical detail that changes no business result (logging, connection failures, a rounding case the data
   cannot produce) is not a FAIL point: list it under `## 4. Notes` in your file instead.

   **On a re-check** (your verify file already exists): read it first. Check that every earlier point is fixed,
   then check the rest as usual. Do not hold back a point you see now, but do not raise again what is fixed.
3. **Verdict:** PASS when everything agrees and nothing is missing; otherwise FAIL, with a numbered list of what
   must change. Each point names the id, says what is wrong, and cites `path:line`.
4. Write `<output>/verify/<UNIT>.md` with the template `../templates/verify.md`.
5. Reply with one line: the unit, PASS or FAIL, the number of points.
