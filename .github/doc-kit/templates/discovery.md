# Discovery: <MODULE>

**Status:** DRAFT

<!-- A person checks this file, then changes the Status line to REVIEWED. Only then does the run continue. -->

## 1. Purpose

<Two to four sentences, from module.md and business/ only.>

## 2. Flows

| ID | Flow | Trigger | Entry point | Varies by | Outputs |
|---|---|---|---|---|---|
| F01 | <business name> | <what starts it> | <path/File.java:12> | <event, order type, or -> | <O01, O02> |

## 3. Outputs

| ID | Output | Kind | Written at | Spec |
|---|---|---|---|---|
| O01 | <file, table or message name> | <file / table / message / response> | <path/File.java:37> | <outputs/NAME.csv or none> |

<!-- Every table the code changes is an output: name the table in the Output column. -->

## 4. Variant dimensions

| Dimension | Values in the code | Where (file:line) | Meaning comes from |
|---|---|---|---|
| <Event> | <P, PR> | <path:line> | <business/codes.md, or "not given: Q1"> |

## 5. Not documented

| Entry point | Reason |
|---|---|
| | |

<!-- Write "None." when every entry point belongs to a flow. -->

## 6. Concepts

| ID | Concept | Card | Flows | Outputs |
|---|---|---|---|---|
| C01 | <name on the card> | <concepts/refund.md> | <F01, F02> | <O01, O02> |

<!-- One row per intent card in the input folder's concepts/. Write "None." when there are no cards. -->

## 7. Questions

| # | Question | What the system does today |
|---|---|---|
| | | |

<!-- Write "None." when there are none. -->

## 8. How the document will explain it

| Item | Plan |
|---|---|
| Readers | <Who will read it and what they already know, from business/; else "Business analysts new to the domain"> |
| Reading order | <Every flow id in the order a newcomer should read them, following the business process: F01, F03, F02> |
| Main example | <One case followed through the whole business summary, with real numbers: "a SILVER customer orders 2 shirts and pays online; the order is shipped the next night"> |
| Terms to explain first | <The words a newcomer needs before anything else, separated by commas: COD, tier, SKU> |
| Cases to show | <The cases the summary must show besides the main example: payment failed, cash on delivery, out of stock> |

<!-- The person reviews this plan with the rest of the file. The business summary follows it, and the flows appear
in the document in this reading order. -->

## 9. Data the code depends on

| Table or procedure | What it decides | Content |
|---|---|---|
| <ORDER_STATUS_PARAM> | <Which statuses can be shipped> | <business/order-status-param.csv, input, or Q3> |

<!-- Every table the documented flows only read, and every stored procedure they call that is not in the source
folders: rules can live in their rows. Content is `input` (the records the flow processes), a file in the input
folder with its exported rows, or the number of a question asking for it. The tool checks every one. Write
"None." when there are none. -->

## 10. Large flows kept whole

| Flow | Why |
|---|---|

<!-- Only for a flow the tool says is too large that you keep whole, with the reason. Write "None." otherwise. -->

