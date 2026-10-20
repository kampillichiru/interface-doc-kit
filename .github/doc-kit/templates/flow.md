# F01. <Flow name in business words>

**Trigger:** <What starts it, for example: the nightly batch, for one business date.>
**Purpose:** <Why it exists, at most 40 words.> (<stated: source | inferred, to be confirmed by the SME | unknown>)
**Entry point:** <path/File.java:12>
**Preconditions:** <What must be true before it runs, or "None found in the code".>
**Outputs:** <O01 the export file; or a table it changes>

## Steps

| Step | Kind | Text | Next | Rules |
|---|---|---|---|---|
| S1 | start | <Batch starts for a business date> | S2 | |
| S2 | step | <Select the day's paid orders> | S3 | F01-BR01 |
| S3 | decision | <Amount is zero?> | yes: E1; no: S4 | F01-BR02 |
| S4 | step | <Write the record> | E2 | F01-BR03 |
| E1 | end | <Order skipped> | | |
| E2 | end | <Record written> | | |

<!-- Kind is start, step, decision or end. Next is one step id; a decision has labelled branches: `yes: S4; no: E1`. -->

## Scenarios

| ID | Type | Scenario | Path | Outcome |
|---|---|---|---|---|
| F01-SC1 | main | <Normal case> | S1 S2 S3 S4 E2 | <What comes out> |
| F01-SC2 | exception | <Zero amount> | S1 S2 S3 E1 | <Nothing is written> |

<!-- Type is main, alternate or exception. -->

## Business rules

### F01-BR01. <Title, at most 10 words>

- **Rule:** <One decision in plain words, at most 45 words.>
- **Applies when:** <Conditions, or "Always".>
- **Values:** <Each value and its origin: Business date = run date given to the job; Status = <TABLE>.STATUS; Limit = fixed 1000.>
- **Example:** <Input with real numbers → result.>
- **Reason:** <The business reason> (<stated: source | inferred, to be confirmed by the SME | unknown>)

## Evidence

| Ref | File:line | Code |
|---|---|---|
| F01-BR01 | <path/File.xml:18-21> | `<exact code from those lines>` |

<!-- One row per quote; a rule may have several rows. Ref is the rule id. A citation covers at most 15 lines. -->

## Decision lines not in a rule

| File:line | Code | Why |
|---|---|---|
| <path/File.java:88> | `<exact code from that line>` | <Decides the field courier service of O01 (see the output); or: technical, finds the order by its number> |

<!-- Every decision line of `doc.py conditions <UNIT>` is cited in Evidence or listed here. Write "None." when every
line is in a rule. Never put a business decision here: it is a rule. -->

## Calls not followed by the tool

| File:line | Code | Where it leads |
|---|---|---|
| <path/File.java:52> | `<exact code of the call>` | <The class or system it reaches, or "not in this code: question 2"> |

<!-- Only for calls the context pack lists under "Calls the tool could not follow" that you did not follow into a
rule. A call you followed is covered by the Evidence of its rule. Write "None." when there are none. -->

## Questions for the SME

| # | Question | What the system does today |
|---|---|---|
| 1 | <Question> | <Behaviour today> |

<!-- Write "None." when there are none. -->
