# Verify: <UNIT>

## 1. My own reading (written before opening the unit file)

- <Decision, field source or rule, with path:line>

## Spot check

| Field | Source | Business rule |
|---|---|---|
| <TAX_AMT> | <ORDER_ITEM.TAX_AMT, rounded to 2 decimals> | <F01-BR05> |

<!-- Only for an output unit: the fields your task names, traced from the code before you open the unit file.
     The tool compares the business rules with the unit file's. Delete this section for other units. -->

## 2. Comparison

| Item | Verdict | Evidence |
|---|---|---|
| <F01-BR01 / F01-SC2 / O01-05-R1 / example 3> | AGREE / DISAGREE | <path:line, worked-out value> |
| Missing from the unit file | <what> | <path:line> |

## 3. Result

**Verdict:** PASS

<!-- For FAIL, list each point:
1. <id>: <what is wrong> (<path:line>). <What it should say.>
-->

## 4. Notes

<!-- Technical points that change no business result. Write "None." when there are none. -->
