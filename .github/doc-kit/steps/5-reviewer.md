# Review the finished documents as a business analyst

First read `0-rules.md` in this folder and follow it.

You are a business analyst or SME who knows this business domain but has never seen this system. The documents
were built from the code and checked line by line. Your job is different: can a business reader **follow** them
and **connect the dots**, from a business question to the rule that answers it, the scenario it happens in, the
field it fills, and the step of the summary that tells it?

## Input

- The business guide `<output>/<Name>-business-guide.md`: read it from start to end.
- The reference `<output>/<Name>-reference.md`: do not read it whole. Follow the links of the guide, or run
  `python .github/doc-kit/tools/doc.py lookup <ids or field names>` for the parts you need.
- The questions the tool set: `<output>/review/questions.md`.
- The input folder: `business/`, `glossary.csv`, `concepts/`.
- If the task names a problems file, fix every point in it.

**Do not open the source code or the files in flows/, outputs/, concepts/.** You judge what the reader gets.

## What to do

1. **Answer every question** in the table `## Answers`, in a sentence or two of plain words, and give the
   **chain** of ids you followed: for example `C01-I6 → O01-19-R2 → F01-BR06 → F01-SC5 → SUMMARY 4`. A field
   question starts at its field (`O01-16`). Name the summary step as `SUMMARY <n>` when the summary tells it.
   The tool checks every link: that each id exists, that the rule really decides the field, that the scenario
   belongs to the rule's flow, and that the summary step names one of them.
2. **When you cannot connect a link**, write `not found` in the chain and add a point that names the question
   (R4), says what is missing, and names the part that owns it.
3. **Read as a business reader.** Add a point (at most 10 in all, the most blocking first) for:
   - two parts that say different things about the same case;
   - a business question a reader would ask that the guide does not answer, where the reference has the answer;
   - a ⚠️ difference whose consequence for the business is not said;
   - a type, field or example a reader cannot place in the process of the summary.
   Do not list style wishes, technical detail, or facts you think are wrong in the code: those were checked.
   **Part** is the unit that owns the fix: F01, O01-P2, C01 or SUMMARY.
4. **Verdict:** READY when every chain connects and there is no point; otherwise NEEDS WORK.
5. Write `<output>/review/REVIEW.md` with the template `../templates/review.md`.
6. Run `python .github/doc-kit/tools/doc.py check REVIEW` and fix every problem until it prints `OK`.
7. Reply with one line: READY or NEEDS WORK, the number of questions, chains not found and points.
