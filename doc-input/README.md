# doc-input: what the team knows

The agents use only the source code and this folder. What is not here is not guessed: it comes back as a
question for the SME.

| Item | Needed | What goes in it |
|---|---|---|
| `module.md` | Yes | Name, business domain, purpose, source folders, data check yes or no, test database |
| `business/` | Strongly advised | Any business context you have, as `.md`, `.txt` or `.csv` files, or at the end of `business/README.md` below its marked line. A table of codes and terms with their meanings feeds the glossary |
| `concepts/` | For a business question | One intent card per question (refund, order fulfilment): what the business expects; the run says line by line what the system does |
| `outputs/` | When an output has a layout | One `.csv` per output file or table with a specification |
| `glossary.csv` | Optional | Business terms and code values with their meaning |
| `test-data/` | For the data check | Expected and actual files per output (the run tells you when) |
| `sme-answers.md` | Later | Answers to the open questions (see that file for how to apply them) |

Use test data only. Never put real customer data, passwords or keys here.
