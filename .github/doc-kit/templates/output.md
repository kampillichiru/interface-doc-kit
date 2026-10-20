# O01. <Output name> (fields <first>-<last>)

## 01. <FIELD_NAME> (positions <start>-<end>)

**Record:** <Only when the spec has a record column: the record type, for example D.>
**Meaning:** <What the value means to the business, at most 30 words.>
**Kind:** <Common | Variant by event | Variant by order type | ...>
**Source:** <TABLE.COLUMN | fixed value "X" | calculated | run date>
**When missing:** <Exactly what is written when there is no value.>

### Requirements

| ID | Requirement | Business rule |
|---|---|---|
| O01-01-R1 | <The FIELD shall be ..., at most 45 words, one behaviour.> | <F01-BR05> |
| O01-01-R2 | <The FIELD shall be padded on the right with spaces to 10 characters.> | format |

<!-- Business rule: the flow rule this requirement carries out (F01-BR05; several: F01-BR05, F01-BR06),
     `format` when it only lays the value out, `none` when no flow rule decides it (then add a question). -->

### Decision table

<!-- Only for a variant field. Delete this section for a common field. -->

| <Event> | <Order type> | Value written | Requirement |
|---|---|---|---|
| | | | O01-01-R.. |

### Examples

| # | Flow | Input | Written | Requirement |
|---|---|---|---|---|
| 1 | <F01, the flow and its variant> | <COLUMN = a value from the test data> | `<exact characters, · for a space>` | O01-01-R1 |

### Evidence

| Hop | File:line | Code |
|---|---|---|
| Writer | <path/File.java:27> | `<exact code>` |
| SQL | <path/queries.xml:7> | `<exact code>` |

<!-- Repeat the ## section for every field of this unit, in spec order. -->

## Questions for the SME

| # | Question | What the system does today |
|---|---|---|
| 1 | <Question> | <Behaviour today> |

<!-- Write "None." when there are none. -->
