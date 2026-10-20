# Explain one flow

First read `0-rules.md` in this folder and follow it.

## Input

- The unit named in your task (for example `F01`) and its row in `<output>/discovery.md`.
- **Start with the context pack:** run `python .github/doc-kit/tools/doc.py context <UNIT>`. It gives only what
  this flow needs: the methods and SQL it reaches with their lines, its settings, every decision line (if, else
  if, switch, ternary, catch, throw, comparisons; WHERE, AND, CASE in SQL) and the code values compared there,
  with their meanings from the input folder. Open `<output>/inventory.md` only for what the pack does not show.
- The input folder: `module.md`, `business/`, `glossary.csv`, `sme-answers.md`.
- If the task names a problems file, a verify file or a data check report: fix every point in it.
- If the task names a reader file (`<output>/reader/<UNIT>.md`): a reader new to the domain could not follow the
  points it lists. Rewrite those parts in plainer words: explain the word, add the missing step, split the
  sentence, finish the example. Change no fact, id, value or evidence.

## What to do

1. **Read the flow** from its entry point to every way it can end. Start from the list under "What each entry
   point reaches" in the inventory: it names the methods and SQL of this flow, with their lines. It can miss
   calls through interfaces or reflection, so follow the code where the list stops. Read every SQL the flow runs
   (by id in XML, by constant name, or built in the method) and every configuration value it reads.
   A call that leaves the module: name it, do not guess what it does.

   Legacy JDBC code, things to look for:
   - SQL built with `+` or `append`: each condition added under an `if` is a business rule with that condition.
     The inventory shows the joined text with constants filled in; read the code for which parts apply when.
   - `rs.getString(3)`: the third column of the SELECT, counted in the SQL itself.
   - `con.commit()` / `rollback()` and `try / catch`: they decide what is saved when something fails. An error
     that is caught and only logged is an end of the flow ("error logged, nothing more happens").
   - A stored procedure call (`{call PKG.PROC(?)}`): read the procedure in the SQL files when it is there; its
     IF / UPDATE / INSERT statements are rules of this flow.
   - Numbers and characters compared with `==` (`status == 9`, `flag == 'Y'`) are codes, as much as strings.
2. **Business rules.** One rule is one business decision or calculation. Selection conditions (which records are
   processed: SQL WHERE, Java skips) are rules too. For each rule: the rule in plain words, when it applies, the
   origin of every value (input, database TABLE.COLUMN, fixed value, calculated, configuration, system date),
   one example with real numbers, and the reason with its basis.
3. **Steps.** The flow as a short list of business steps, about 12: start, steps, decisions, ends. One box is
   one business step, not one line of code; a loop is one step ("For each order: ..."). Every way the flow
   can end is its own end step, including rejections and errors. Link each step to its rules.
4. **Scenarios.** One complete path from start to an end, with its outcome. Write enough scenarios that every
   arrow is followed by at least one. One is `main`; others are `alternate` or `exception`. When the flow varies
   by a code, give a scenario for each value with different behaviour, and one for the values the code does not
   name (they take the default path). Never leave out a scenario to keep the file short.
5. **Evidence.** One row per rule at least: the `path:line` and the exact code that shows it.
   **Every decision line** of the context pack (also `doc.py conditions <UNIT>`) must be covered: cited in the Evidence of the rule it belongs
   to (a citation of at most 15 lines), or listed under `## Decision lines not in a rule` with the reason
   (it decides an output field: name the output and field; or it is technical, like finding a record by its
   key). A line that changes what a business reader would see is a rule, never "not in a rule".
   **Every call the tool could not follow** (an interface, a parent class, reflection; listed in the context
   pack) must be followed: read the code it reaches and cite it in the rule it belongs to, or list the call under
   `## Calls not followed by the tool` with where it leads (a class, another system, or a question). The tool
   checks it.
   **Every code value** it lists (GOLD, COD, CANCELLED) must appear in a rule, step or scenario that says what
   happens for it, unless its line is listed under Decision lines not in a rule. The tool checks both.
6. **Questions** for the SME: what the code does but does not explain.
7. Write `<output>/flows/<UNIT>.md` with the template `../templates/flow.md`.
8. Run `python .github/doc-kit/tools/doc.py check <UNIT>` and fix every problem until it prints `OK`.
9. Reply with one line: the number of steps, scenarios, rules and questions.

## Keep it short

| What | Limit |
|---|---|
| Step text | 12 words |
| `**Rule:**` | 45 words, one decision |
| Steps | about 12 per flow; above 15 means two flows or too much detail |
| Scenarios | No limit: every path and every code value with different behaviour. Above 20, the flow probably holds two flows: say so in a question |
| Questions | 3 per rule, each one sentence |

Output field details (what goes in each position of a file) do not belong here: they go in the output step.
Here, write "Writes <the file> (output O01)".
