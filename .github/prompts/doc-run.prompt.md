---
description: Documentation kit - document a module from its source code (flows, business rules, outputs), checked step by step
agent: agent
---
# Document a module

You are the controller. A Python tool decides every step and does all the exact work itself. You only carry out
what it prints. Do not read source code or documentation files yourself: that is the agents' work, so that your
context stays small and every agent starts clean.

## Loop

1. In the terminal, from the workspace root, run:
   `python .github/doc-kit/tools/doc.py next`
2. Read the one line it prints:
   - `TASK <agent>: <text>`: start a sub-agent with the custom agent `<agent>`, and give it `<text>` exactly as
     printed, nothing added. Wait until it finishes. Then go to 1.
   - `STOP: <text>`: stop. Tell the person `<text>` exactly. It is something only a person can do.
   - `FINISHED: <text>`: stop. Tell the person where the document is and whether it is DRAFT or FINAL,
     then run `python .github/doc-kit/tools/doc.py status` and show its table.

## Rules

- Keep looping until STOP or FINISHED. Do not stop to summarise, and do not ask whether to continue.
- Never decide a step yourself and never skip one. The tool keeps the state and counts the attempts.
- Never edit any file yourself.
- If an agent fails or writes nothing, go to 1: the tool gives the same task again and gives up on a unit after
  3 attempts. If the same task fails twice in a row without writing anything, stop and report it.
- If this editor cannot start sub-agents: do each task yourself by reading its step file, and stop after 3 tasks
  with "Run /doc-run again in a new chat to continue." The tool continues where you stopped.
- The input and output folders are `doc-input` and `doc-output`. If the person named other folders, add
  `--input <folder> --output <folder>` before `next` in every command.
