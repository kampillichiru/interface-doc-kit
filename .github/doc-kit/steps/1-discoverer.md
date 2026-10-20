# Discover the flows and outputs

First read `0-rules.md` in this folder and follow it.

You decide **what will be documented**: the flows (each way work starts) and the outputs. A person reviews your
file before anything else runs, so make it easy to check.

## Input

- `<output>/inventory.md`, written by the tool: every source file, entry point, SQL, output and comparison
  with a fixed value. It is complete; you do not need to search for these yourself.
- `<input>/module.md`, every business context file the inventory lists (section Input folder),
  `<input>/glossary.csv`, `<input>/outputs/*.csv`, and the intent cards in `<input>/concepts/` when there are any.
- If the task names a problems file, fix every point in it.

## What to do

1. **Purpose.** In two to four sentences, what the module is for, taken from `module.md` and `business/` only.
   If they do not say, write "Not given by the team" and add a question.
2. **Flows.** Group the entry points into flows. A flow is one business way work starts: a nightly job, an
   endpoint a user calls, a timer, a listener. Use "What each entry point reaches" in the inventory: entry points
   that reach the same work are one flow (a startup listener that starts a timer task belongs to the task's
   flow, as its trigger). Read the code at each entry point to name it in business words. A stored procedure
   that Java calls is part of the calling flows; document it as its own flow only when several flows share it.
   Entry points that are only technical (a health check, a test main) go to "Not documented", with the reason.
   A flow marked **Large** in the inventory should be split by business step if it can be.
   **Every entry point of the inventory** must be in a flow or under "Not documented"; the tool checks it.
3. **Outputs.** List what the module produces: files written, tables changed (INSERT, UPDATE, DELETE, MERGE),
   messages sent, responses returned. For each one, give the specification file from `<input>/outputs/` if one
   matches (by name), otherwise `none`. **Every table the code changes** is an output, named in the Output
   column; the tool checks it against the SQL in the inventory.
4. **Variant dimensions.** From "Comparisons with codes" and "Constants and enums" in the inventory, list the
   codes that change behaviour (for example an order type, a status, an event). For each: the values found in
   the code, and where their meaning comes from: an input file, or "constant names only (inferred)", or
   "not given" (then ask). The same code can appear as a constant, as a plain number (`status == 9`) and inside
   SQL (`STATUS = 1`): list it once with all its places.
5. **Code tables.** If the inventory lists possible code tables and `business/` does not explain those codes,
   add one question asking the team to export them (for example `SELECT * FROM ORDER_STATUS_PARAM`) into `business/`.
6. **Concepts.** For each intent card in `<input>/concepts/`: one row (C01, C02, ...) with the card's file, the
   flows that carry the concept out (read the code at their entry points to be sure), and the outputs it writes.
   Name every flow the concept goes through, end to end: where the request comes in and every flow that changes
   the same records for it. When there are concepts, only their flows and outputs are documented in this run.
   Without cards, write "None." under Concepts.
7. **Questions** for the SME: everything above you could not settle.
8. **How the document will explain it.** The plan for a reader new to the domain, which the person reviews with
   the rest. Before you write it, read the business files again and ask: what must a newcomer learn first, and
   which one case shows the whole process best?
   - **Readers**: who will read it and what they already know (from `business/`); else "Business analysts new to
     the domain".
   - **Reading order**: every flow id, in the order the business process runs (an order is placed, then paid, then
     shipped), not the order of the code.
   - **Main example**: one case to follow through the whole summary, with real numbers, taken from `business/`
     when it gives one.
   - **Terms to explain first**: the codes and words a newcomer needs before anything else. Each one needs its
     meaning in the input folder, or a question (the tool checks it).
   - **Cases to show**: the other cases the summary must show (rejections, other payment methods, errors).
9. **Data the code depends on.** Run the tool check once: it lists every table the documented flows only read
   and every stored procedure they call that is not in the source folders. Rules can live in their rows (a
   mapping, a parameter table). For each: what it decides, and its content: `input` when it holds the records the
   flow processes, the file in the input folder where the team exported its rows, or a question asking for the
   export (for example `SELECT * FROM ORDER_STATUS_PARAM`).
10. **Large flows.** The tool names a flow that reaches more code than one agent reads well. Split it into
    flows by business step, or keep it whole and say why under `## 10. Large flows kept whole`.
11. Write `<output>/discovery.md` with the template `../templates/discovery.md`. Keep `Status: DRAFT`.
12. Run `python .github/doc-kit/tools/doc.py check discovery` and fix every problem until it prints `OK`.
13. Reply with one line: the number of flows, outputs, concepts and questions.
