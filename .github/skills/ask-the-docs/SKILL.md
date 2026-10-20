---
name: ask-the-docs
description: Answer business questions about a documented module ("what is a refund?", "how is TAX_AMT derived?", "which rule decides SHIP_METHOD?", "does the system do what the card says?") from the finished, checked documentation in doc-output only, never from the source code, so the same question always gets the same checked answer. Use whenever someone asks how the module behaves, how a field is derived, or what a business rule means, after /doc-run has produced the document.
---

# Ask the docs

A business analyst asks about the module. Answer **only** from the finished document that `/doc-run` produced
and checked. Do not read the source code and do not use general knowledge: answers made from the code are
long, different every time and partly wrong; this document was checked by a second reader and the data check.

## Steps

1. **Find the parts.** In the terminal, from the workspace root, run:

   `python .github/doc-kit/tools/doc.py lookup <terms>`

   Terms: ids when the question has them (`F01-BR05`, `O02-09`, `C01-I3`, `F01-SC2`), field names
   (`TAX_AMT`), or the key business words of the question (`refund shipping charge`). Run it again with other
   words if the first parts do not answer the question; at most 3 times.
   It prints the status (FINAL or DRAFT) and the parts that match, first from the business guide, then from the
   reference (the evidence), each with the file and its line number. You may open those files at those lines for
   more context. Open nothing else. Prefer the guide's wording; use the reference for the field and rule detail.
2. **If it prints `STOP`**: tell the person there is no document yet and that `/doc-run` makes it.
3. **Answer** in the shape below, from those parts only.

## Answer shape

```
<The answer in plain business words, 2 to 6 sentences. Exact values: codes with their meaning, days,
amounts, statuses.>

<When the question is about a field: one line per variant, for example "For an order: ... For a refund: ...">
<When a business expectation (intent card line) is involved: its status, ✅ matches, ⚠️ differs or ❓ not found.>

Based on: <the ids the parts show, for example F01-BR05 Refund amount split, O02-09-R1>
Status: <FINAL, or DRAFT and which parts are not yet checked, when the answer rests on them>
```

## Rules

- **Only what the parts say.** If they do not answer the question, say "This is not in the checked
  documentation." Then suggest one of: a line for an intent card in `doc-input/concepts/` (so the next run
  answers it), or a question for the SME. Never fill the gap yourself.
- **Never** open files under the source folders, and never quote code.
- Keep the document's wording for rules and derivations; shorten, do not reword the meaning.
- An open question for the SME in the document stays open: say what the system does today and that the SME
  has not confirmed it.
- No more than 200 words, unless the person asks for every field or every rule.
