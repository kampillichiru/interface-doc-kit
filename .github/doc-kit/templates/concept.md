# C01. <Concept name, as on the card>

## In short

<At most 150 words, plain words: what it is, what starts it and what it changes.>

## What the business expects and what the system does

| # | The business expects | The system does | Status | Based on |
|---|---|---|---|---|
| I1 | <copied from the card> | <What the documented rules say, at most 45 words.> | ✅ Matches | F01-BR03 |
| I2 | <copied from the card> | <How it differs, with a case.> | ⚠️ Differs | F01-BR04, O01-09-R2 |
| I3 | <copied from the card> | No documented rule does this. | ❓ Not found in the code | |

### Also in the system

| # | The system does | Based on |
|---|---|---|
| A1 | <A business behaviour the card does not mention.> | F01-BR01 |

## Types and how each works

| Type | Meaning | How the system handles it | Example | Based on |
|---|---|---|---|---|
| <`GOLD` code> | <Meaning copied from the input folder.> | <What the system does differently for it, at most 45 words.> | <One small case with numbers.> | F01-BR04 |

<!-- One row per code that changes what the system does (an event, a transaction or order type, a status).
     The tool checks that every code the flows compare with, and that has a meaning in the input, has a row. -->

## Fields this question changes

### O01 <Output name>

| Field | Business meaning | Derived as | Based on |
|---|---|---|---|
| `<FIELD>` | <What it means to the business.> | <How its value changes for this question, at most 45 words.> | O01-01-R1 |

<!-- One ### part per output of the concept that has a specification. Every variant field (its value changes by
     type, event or code) has a row; add another field only when this question needs it. Every field is described
     once, in the output section of the document: do not copy it here. -->

## Worked examples

### Example 1. <Case, for example: order paid by card and shipped>

**Source:** <Test run row R202610160001, or "constructed from F01-BR03">
**Before:** <The order: items, shipping, tax, status.>
**Event:** <What happened, with the amount and dates.>
**Split:** <How the amount was applied, by part.>
**After:** <The order now; status.>

**In the file:** <O01 line 2: the line of the real test file this example ends in>

| Field | Value | Based on |
|---|---|---|
| `<ORDER_NO>` | `<the exact characters of that field in that line, · for a space>` | O01-01-R1 |

<!-- Connects the dots: the record of the example, the rules, and the real line it becomes. The tool reads that
     line of doc-input/test-data/<output>/actual.* and checks every value. Show the fields that tell the story
     (the codes, the amount, the variant fields). When the real file is there, at least one example must have it. -->

## Questions for the SME

| # | Question | What the system does today |
|---|---|---|
| 1 | <Question> | <Behaviour today> |

<!-- Write "None." when there are none. -->
