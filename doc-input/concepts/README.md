# concepts: the business questions, with what the business expects

One file per business question, for example `refund.md`, `order-cancellation.md`, `gift-card.md`. When this
folder has cards, the run documents **only** what these concepts need: their flows, their outputs field by
field, and one business page per concept, in plain words, at the start of the document.

Write the card **before** the run, as the business understands it today. It does not need to be right or
complete: the run answers each line with what the system really does.

- ✅ **Matches**: the system does it.
- ⚠️ **Differs**: the system does something else, or only in some cases. This is the most useful result.
- ❓ **Not found in the code**: nothing in these flows does it (maybe another system does).

Copy this shape. The tool reads the title and the table under `## What the business expects`.

```markdown
# Concept: Order refund

**Asked by:** Business analysis team
**Question:** What happens when a customer returns items of an order? How is each field of the refund
record derived?
**Outputs to explain:** REFUND_TXN, ORDER_TXN

## What the business expects

| # | The business expects |
|---|---|
| I1 | A refund gives back the price of the returned items and their tax; the shipping charge is kept. |
| I2 | An order can be refunded only within 30 days of delivery. |
| I3 | The refund record holds one line for the returned items and one for their tax. |
```

Tips:

- One expectation per line, in business words, with the numbers you know (days, amounts, statuses).
- Put the outputs you want explained field by field in `outputs/` as a spec (a table needs no positions).
