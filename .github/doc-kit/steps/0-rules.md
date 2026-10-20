# Rules for every step

You document what a legacy system does today, so that a business analyst can understand it and another team can
rebuild it. A wrong statement is worse than a missing one: someone will build it.

## Where facts come from

1. **The source code** in the source folders named in `<input>/module.md`.
2. **The input folder**: `module.md`, everything in `business/`, `glossary.csv`, `sme-answers.md`,
   the output specifications in `outputs/`, the intent cards in `concepts/`. In `business/README.md`, only the
   text below the line "Write your business context below this line." is business context; above it is the
   kit's guidance. The inventory lists the business files that count.

An intent card says what the business team **expects**; it is not a fact about the system. Never write that the
system does something because a card says so: the code decides, and the difference is the finding.

Nothing else: not your general knowledge of the business, not what a name suggests.

## Rules

1. **Never guess.** When the code and the input folder do not settle something, say what the code does and add
   a question for the SME. A question is a good result.
2. **Read the real lines** before you write about them. Names in old code are often wrong.
3. **Evidence for everything.** Every rule, step and field cites `path:line` or `path:start-end` and quotes the
   code exactly, copied from the file. The tool checks every quote against the file.
4. **Business meaning only from the input folder.** Codes (event, order type, status, shipping method) take their
   meaning from `business/`, `glossary.csv` or `sme-answers.md`. A code not described there: say what the code
   does with it, and ask. When the input folder and the code disagree, say both and ask.
   The name of a constant or enum (`STATUS_ON_HOLD = 3`, `ShipMethod.EXPRESS`) is a hint, not a fact: you may use
   it, but write it as "3 (named STATUS_ON_HOLD in the code)" and mark the meaning inferred, to be confirmed by
   the SME.
5. **The reason for a rule** is `stated` (name the comment, message or input file that says it), `inferred`
   (marked "to be confirmed by the SME") or `unknown` (write "Not known from the code" and ask).
6. **Describe what the code does**, even when it looks like a bug. Then ask.
7. **Plain words for the reader.** Rule text, steps, scenarios and examples are for a reader **new to the
   domain**: business words, no Java words ("the customer is not found", not "c == null"), short sentences, one
   fact each. File names, lines and code go in the Evidence tables only. The tool rejects Java names, method calls
   and code operators in the business text, and a reader agent that knows nothing of the business reads every
   flow, concept and the summary and sends back what it cannot follow.
8. **Every term has a meaning.** Every code and abbreviation you write in capitals (COD, PENDING_PAYMENT) must have
   its meaning in the input folder, or a question in your file asking for it. The tool checks it.
9. **Exact values** with their unit: codes, limits, days, rounding, formats, table and column names.
10. **Every variant.** When behaviour depends on a code (event, order type, status), say what happens for
   each value listed in the input folder, including values the code does not mention: they take the default path.
11. **Use your template exactly**: same headings, same table columns, same ids. The tool reads them.
12. **Write only the file your step names.** Never change source code or the input folder.
13. **Finish with the tool check**: run the command at the end of your step and fix every problem it lists,
    until it prints `OK`.
14. **No secrets, no real customer data.** Write "(secret, not shown)" for passwords, keys and tokens.

## Files of points to fix

Your task line may name a file of points: a problems file (the tool), a verify file (the second reader), a reader
file (the newcomer), the review file `review/REVIEW.md` (the business analyst) or `sme-answers.md` (the SME).
Fix every point in it that concerns your unit; in the review file, only the points whose **Part** is your unit;
in the SME answers, the answer your task names: it settles the question, so write what it says (stated:
sme-answers.md) and remove the question.

## Say each thing once

- **Questions.** Before you add a question, read the questions of the files you were given. If one already asks
  it, do not ask it again: the document lists each question once, with every part that raised it. The tool
  rejects a question another part already asks.
- **Facts.** A rule is stated in its flow, a field in its output section, a meaning in the glossary. Elsewhere,
  name the id (`F01-BR06`) in a few words instead of explaining it again.

## Ids

| Id | Meaning | Example |
|---|---|---|
| `F01` | A flow: one way work starts (a batch job, an endpoint, a listener) | F01 Nightly export of the day's orders |
| `F01-BR01` | Business rule 01 of flow F01 | F01-BR03 Direction by event |
| `F01-SC1` | Scenario 1 of flow F01 | F01-SC2 Request refused |
| `O01` | An output with a specification (a file, a table, a message) | O01 the export file |
| `O01-05-R2` | Requirement 2 of field 05 of output O01; it names the flow rule it carries out | O01-05-R2 → F01-BR05 |
| `C01` | A business concept: one question of the business team, with its intent card | C01 Order refund |
| `C01-I3` | Line I3 of the intent card of concept C01 | |
| `SUMMARY` | The business summary at the start of the document | |
