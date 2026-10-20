<!-- doc-kit:start -->
# Documentation kit

When a task mentions `/doc-run`, the `doc-input` or `doc-output` folders, or an agent named `doc-*`, read
`.github/doc-kit/steps/0-rules.md` first and follow it: never guess, quote the code for every statement, take
business meaning only from `doc-input`, write only the file your step names.

When someone asks how a documented module behaves, how a field is derived or what a business rule means, use the
skill `ask-the-docs` (`.github/skills/ask-the-docs/SKILL.md`): answer from the finished document in `doc-output`,
not from the source code.
<!-- doc-kit:end -->
