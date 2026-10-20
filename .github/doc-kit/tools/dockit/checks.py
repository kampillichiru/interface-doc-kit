"""Checks on what an agent wrote. Problems come back as plain sentences the agent can act on."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import compare, concept, coverage, evidence, flowgraph, links, markdown, questions, scan, spec, terms
from .discovery import EXPLAIN_SECTION, Discovery
from .plan import Unit
from .project import Paths

MAX_RULE_WORDS = 45
MAX_MEANING_WORDS = 30
MAX_LISTED = 25  # problems of one kind listed in full; the rest are counted
VERDICT = re.compile(r"\*\*Verdict:\*\*\s*(PASS|FAIL)", re.I)
_POSITIONS = re.compile(r"\(\s*positions?\s+(\d+)(?:\s*[-–]\s*(\d+))?", re.I)


def unit_problems(unit: Unit, paths: Paths, discovery: Discovery) -> List[str]:
    path = paths.unit_file(unit.id)
    if not path.exists():
        return [f"{paths.rel(path)} does not exist."]
    text = path.read_text(encoding="utf-8")
    roots = tuple(paths.sources)
    if unit.kind == "flow":
        problems = _flow(unit, text, roots)
        return problems or _flow_coverage(unit, text, paths, discovery)
    if unit.kind == "concept":
        return _concept(unit, text, paths, discovery)
    if unit.kind == "summary":
        return _summary(text, paths, discovery)
    if unit.kind == "review":
        from . import review
        from .plan import Plan
        plan = Plan.load(paths) or Plan.build(discovery, paths, paths.discovery.stat().st_mtime)
        return review.problems(paths, discovery, plan)
    output = next(o for o in discovery.outputs if o.id == unit.output_id)
    all_fields = spec.load(paths.input / output.spec)
    rules = links.flow_rules(paths.out / "flows")
    problems = _output(unit, text, roots, unit.fields(all_fields), rules)
    problems += asked_before(text, paths, ("flows", "outputs"), paths.unit_file(unit.id))
    if not problems and unit.last_field >= len(all_fields):
        problems += _rule_coverage(unit, paths, all_fields, rules)
    return problems


def verdict(paths: Paths, unit_id: str) -> Optional[str]:
    path = paths.verify_file(unit_id)
    if not path.exists():
        return None
    found = VERDICT.search(path.read_text(encoding="utf-8"))
    return found.group(1).upper() if found else None


def discovery_problems(paths: Paths) -> List[str]:
    discovery = Discovery.load(paths.discovery)
    found = discovery.problems(paths.input)
    text = paths.discovery.read_text(encoding="utf-8")
    roots = tuple(paths.sources)
    for row in markdown.first_table(markdown.section(text, "Flows")):
        for ref in re.split(r"[;,]|<br>", row.get("Entry point", "")):
            ref = ref.strip("` ")
            if ref:
                _, problem = evidence.resolve(ref.split(":")[0], roots)
                if problem:
                    found.append(f"Flow {row.get('ID')}: {problem}.")
    if paths.inventory_json.exists():
        found += _coverage(scan.load(paths), text)
        found += _dependencies(paths, discovery, scan.load(paths), text)
        found += _large_flows(paths, discovery, text)
    found += _concept_coverage(paths, discovery)
    found += _terms_first(discovery, text, terms.input_text(paths.input))
    return found


def _terms_first(discovery: Discovery, text: str, known: str) -> List[str]:
    """A term the plan will explain first needs its meaning from the input folder, or a question."""
    questions = markdown.section(text, "Questions") or ""
    return [f"{EXPLAIN_SECTION}: the term `{t}` has no meaning in the input folder. Add a question asking what it "
            f"means." for t in discovery.terms_first if not terms.mentions(known, t) and not terms.mentions(questions, t)]


def _coverage(inventory: scan.Inventory, text: str) -> List[str]:
    """Nothing the scan found may be left out silently: every entry point is in a flow or under
    Not documented, and every table the code changes is listed as an output."""
    placed = " ".join(markdown.section(text, t) or "" for t in ("Flows", "Not documented"))
    problems = []
    for n, hit in enumerate(scan.unique(inventory.entry_points), 1):
        names = {Path(hit.file).name}
        if "->" in hit.text:  # a web.xml mapping: covered by the servlet class it points to
            names.add(hit.text.split("->")[-1].strip().split(".")[-1])
        if not any(name in placed for name in names):
            problems.append(f"Entry point EP{n:02d} ({hit.file}:{hit.line}, `{hit.text}`) is in no flow and not "
                            f"under Not documented. Add it to a flow, or say under Not documented why it is left out.")
    outputs = (markdown.section(text, "Outputs") or "").upper()
    for table in sorted(scan.tables_changed(inventory)):
        if not re.search(rf"\b{re.escape(table)}\b", outputs):
            problems.append(f"Table {table} is changed by the code (see the SQL in the inventory) but is not in the "
                            f"Outputs table. Every table the module changes is an output.")
    return problems


DEPENDS_SECTION = "Data the code depends on"
LARGE_SECTION = "Large flows kept whole"
_TABLES = re.compile(r"tables: ([^;]*)")
_QUESTION_REF = re.compile(r"^Q?(\d+)$", re.I)


def dependencies(paths: Paths, discovery: Discovery, inventory: scan.Inventory) -> List[str]:
    """What the documented flows read but the code does not hold: tables they only read (reference data,
    mappings, parameters: rules can live in their rows) and stored procedures they call that are not in the
    source folders."""
    sql_ids = set()
    for flow in (f for f in discovery.flows if discovery.in_scope(f.id)):
        for reach in coverage.reaches(paths, discovery, flow.id):
            sql_ids |= set(reach.sql)
    hits = [inventory.sql[int(q[1:]) - 1] for q in sorted(sql_ids) if 0 < int(q[1:]) <= len(inventory.sql)]
    changed = scan.tables_changed(inventory)
    read = {t.strip().split(".")[-1].upper() for h in hits if h.kind.upper().startswith("SELECT")
            for found in _TABLES.findall(h.text) for t in found.split(",") if t.strip()}
    defined = {h.text.split(".")[-1].strip('"').upper() for h in inventory.entry_points
               if re.match(r"(PROCEDURE|FUNCTION|PACKAGE)", h.kind.upper())}
    called = {h.text.split(";")[0].split(".")[-1].strip().upper() for h in hits if h.kind.upper().startswith("CALL")}
    return sorted(read - changed) + sorted(called - defined)


def _dependencies(paths: Paths, discovery: Discovery, inventory: scan.Inventory, text: str) -> List[str]:
    """Each dependency has a row that says what it decides and where its content is: `input` (the records the
    flow processes), a file in the input folder (exported rows), or the number of a question."""
    needed = dependencies(paths, discovery, inventory)
    rows = markdown.first_table(markdown.section(text, DEPENDS_SECTION))
    by_name = {r.get("Table or procedure", "").strip().strip("`").upper(): r for r in rows}
    asked = {m for r in markdown.first_table(markdown.section(text, "Questions"))
             for m in [re.sub(r"\D", "", r.get("#", ""))] if m}
    problems = []
    for name in needed:
        row = by_name.get(name)
        if row is None:
            problems.append(f"`{name}` is read by the documented flows but its rows are not in the code: rules can "
                            f"live in them. Give it a row under `## {DEPENDS_SECTION}`: what it decides, and its "
                            f"content (`input`, a file in the input folder, or a question number).")
            continue
        content = row.get("Content", "").strip().strip("`")
        ref = _QUESTION_REF.match(content)
        if content.lower().startswith("input"):
            continue
        if ref:
            if ref.group(1) not in asked:
                problems.append(f"{DEPENDS_SECTION} `{name}`: question {content} is not in the Questions table.")
        elif not content or not (paths.input / content).exists():
            problems.append(f"{DEPENDS_SECTION} `{name}`: the content `{content}` is not a file in the input "
                            f"folder. Export its rows there, or write `input` or a question number.")
        if not row.get("What it decides", "").strip():
            problems.append(f"{DEPENDS_SECTION} `{name}`: the column `What it decides` is empty.")
    return problems


def _large_flows(paths: Paths, discovery: Discovery, text: str) -> List[str]:
    """A flow that reaches more code than one agent reads well is split by business step, or kept whole with
    a reason the person reviews."""
    kept = {r.get("Flow", "").strip().split(" ")[0]: r.get("Why", "").strip()
            for r in markdown.first_table(markdown.section(text, LARGE_SECTION))}
    problems = []
    for flow in (f for f in discovery.flows if discovery.in_scope(f.id)):
        lines = sum(r.lines for r in coverage.reaches(paths, discovery, flow.id))
        if lines > scan.LARGE_FLOW_LINES and not kept.get(flow.id):
            problems.append(f"{flow.id} reaches about {lines} lines of code (more than {scan.LARGE_FLOW_LINES}). "
                            f"Split it by business step into several flows, or keep it whole and say why under "
                            f"`## {LARGE_SECTION}` (| Flow | Why |).")
    return problems


def _concept_coverage(paths: Paths, discovery: Discovery) -> List[str]:
    cards = concept.load_all(paths.input)
    problems = [p for card in cards for p in concept.problems(card)]
    listed = [c.card for c in discovery.concepts]
    for card in cards:
        if not any(c.endswith(card.file) or card.file.endswith(c) for c in listed if c):
            problems.append(f"The card {card.file} has no row in the Concepts table.")
    return problems


# Flows

def _flow(unit: Unit, text: str, roots: Tuple[Path, ...]) -> List[str]:
    problems = _required(text, ["Steps", "Scenarios", "Business rules", "Evidence", "Questions for the SME"])
    if problems:
        return problems
    if not markdown.labelled(text, "Trigger"):
        problems.append("The line **Trigger:** is missing.")
    rules = markdown.sections(markdown.section(text, "Business rules") or "", 3)
    rule_ids = set()
    for title, body in rules:
        rule_id = title.split(".")[0].strip()
        if not re.fullmatch(rf"{unit.id}-BR\d{{2}}", rule_id):
            problems.append(f"Rule heading `{title}` must start with an id like {unit.id}-BR01.")
            continue
        rule_ids.add(rule_id)
        problems += _rule(rule_id, body)
    steps = flowgraph.parse_steps(markdown.first_table(markdown.section(text, "Steps")))
    scenarios = markdown.first_table(markdown.section(text, "Scenarios"))
    problems += flowgraph.check(steps, scenarios, rule_ids)
    problems += _evidence(markdown.first_table(markdown.section(text, "Evidence")), rule_ids, roots)
    return problems


def _rule(rule_id: str, body: str) -> List[str]:
    problems = []
    for label in ("Rule", "Applies when", "Example", "Reason"):
        if not markdown.labelled(body, label):
            problems.append(f"{rule_id}: the line **{label}:** is missing.")
    rule = markdown.labelled(body, "Rule") or ""
    if markdown.words(rule) > MAX_RULE_WORDS:
        problems.append(f"{rule_id}: **Rule:** has {markdown.words(rule)} words; at most {MAX_RULE_WORDS}.")
    return problems


def _flow_coverage(unit: Unit, text: str, paths: Paths, discovery: Discovery) -> List[str]:
    """Checked once the form is right: nothing the code decides is left out, every code and term has a meaning
    from the input folder or a question, and the text is in plain words."""
    roots = tuple(paths.sources)
    problems = []
    elsewhere = markdown.first_table(markdown.section(text, coverage.NOT_IN_RULE))
    for row in elsewhere:
        where = f"{coverage.NOT_IN_RULE} {row.get('File:line', '?')}"
        problems += [f"{where}: {p}" for p in evidence.check(row.get("File:line", ""), row.get("Code", ""), roots)]
        if not row.get("Why", "").strip():
            problems.append(f"{where}: the column `Why` is empty.")
    found = coverage.reaches(paths, discovery, unit.id, text)
    missing = coverage.missing_conditions(text, paths, found)
    problems += _capped([f"The code decides something at {c.ref} (`{c.code}`) and no Evidence row covers that line. "
                         f"Cite it in the rule it belongs to, or list it under `## {coverage.NOT_IN_RULE}` with the "
                         f"reason." for c in missing], f"python .github/doc-kit/tools/doc.py conditions {unit.id}")
    for row in markdown.first_table(markdown.section(text, coverage.NOT_FOLLOWED)):
        where = f"{coverage.NOT_FOLLOWED} {row.get('File:line', '?')}"
        problems += [f"{where}: {p}" for p in evidence.check(row.get("File:line", ""), row.get("Code", ""), roots)]
        if not row.get("Where it leads", "").strip():
            problems.append(f"{where}: the column `Where it leads` is empty: name the class or system it reaches, "
                            f"or write a question.")
    problems += _capped([f"The tool could not follow the call at {c.ref} (`{c.code}`): an interface, a parent class "
                         f"or reflection. Read where it leads; cite that code in a rule, or list the call under "
                         f"`## {coverage.NOT_FOLLOWED}` with where it leads." for c in coverage.missing_calls(text, paths, found)],
                        f"python .github/doc-kit/tools/doc.py context {unit.id}")
    listed = coverage.covered(elsewhere, paths)
    prose = flow_prose(text)
    questions = markdown.section(text, "Questions for the SME") or ""
    known = terms.input_text(paths.input)
    unexplained = []
    for value in coverage.code_values(paths, found):
        if (value.file, value.line) in listed:
            continue  # its line is explained under Decision lines not in a rule (an output field, for example)
        if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(value.value)}(?![A-Za-z0-9_])", prose):
            unexplained.append(f"The code compares with or writes the code `{value.value}` ({value.file}:{value.line}) "
                               f"and no rule, step or scenario says what happens for it. Add it where it belongs; "
                               f"when it changes the path, give it a scenario.")
    problems += _capped(unexplained, "")
    problems += _capped(_undefined(prose, questions, known, tables_used(paths) | {paths.module.name.upper()}), "")
    return problems + _plain_words(prose)


def flow_prose(text: str) -> str:
    """The business text of a flow file: what a reader reads, without evidence, the origin of values and code."""
    body = markdown.strip_sections(text, ["Evidence", coverage.NOT_IN_RULE, coverage.NOT_FOLLOWED,
                                          "Questions for the SME"])
    lines = [line for line in body.splitlines()
             if not re.match(r"^\s*-?\s*\*\*(Entry point|Values|Outputs):\*\*", line)]
    # The basis of a reason may name the code comment it comes from: "(stated: PaymentResultListener.java:34)".
    return re.sub(r"\((?:stated|inferred|unknown)\b[^)]*\)", "", "\n".join(lines))


def _undefined(prose: str, questions: str, known: str, ignore) -> List[str]:
    """Codes and abbreviations in the text whose meaning is neither in the input folder nor asked."""
    return [f"`{t}` is used in the text, but its meaning is not in the input folder (glossary.csv, business/, "
            f"sme-answers.md). Write it in plain words, or add a question asking what it means."
            for t in terms.caps_terms(prose, ignore) if not terms.mentions(known, t) and not terms.mentions(questions, t)]


def tables_used(paths: Paths) -> set:
    """Table names the code uses: allowed in the text as they are."""
    if not paths.inventory_json.exists():
        return set()
    inventory = scan.load(paths)
    return {t.split(".")[-1].upper() for hit in inventory.sql for t in scan.TABLES.findall(hit.value or hit.text)}


def _capped(problems: List[str], command: str) -> List[str]:
    if len(problems) <= MAX_LISTED:
        return problems
    more = f"... and {len(problems) - MAX_LISTED} more of the same kind"
    return problems[:MAX_LISTED] + [more + (f": run `{command}` for the full list." if command else ".")]


# Outputs

def _output(unit: Unit, text: str, roots: Tuple[Path, ...], fields: List[spec.Field],
            rules: Dict[str, links.Rule]) -> List[str]:
    problems = _required(text, ["Questions for the SME"])
    found = {title.split(".")[0].strip(): (title, body) for title, body in markdown.sections(text, 2)}
    for f in fields:
        number = f"{f.number:02d}"
        if number not in found:
            problems.append(f"Field {number} {f.name}: no section `## {number}. {f.name} (...)`.")
            continue
        title, body = found[number]
        problems += _field(unit, f, title, body, roots, rules)
    return problems


def _rule_coverage(unit: Unit, paths: Paths, all_fields: List[spec.Field],
                   rules: Dict[str, links.Rule]) -> List[str]:
    """Checked with the last part of an output, when every field is written: a rule that says it writes this
    output must decide at least one of its fields."""
    found: List[links.FieldLink] = []
    for path in sorted((paths.out / "outputs").glob(f"{unit.output_id}*.md")):
        found += links.output_fields(path.read_text(encoding="utf-8"), unit.output_id, all_fields).values()
    return [f"{r.id} ({r.title}) says it writes {unit.output_id}, but no requirement of {unit.output_id} names it "
            f"in the column `{links.RULE_COLUMN}`. Name it on the requirements it decides."
            for r in links.unlinked_rules(rules, unit.output_id, found)]


def _field(unit: Unit, f: spec.Field, title: str, body: str, roots: Tuple[Path, ...],
           rules: Dict[str, links.Rule]) -> List[str]:
    where = f"Field {f.number:02d} {f.name}"
    problems = []
    if f.name.lower() not in title.lower():
        problems.append(f"{where}: the heading must name the field: `{f.number:02d}. {f.name} (...)`.")
    if f.start is not None:
        match = _POSITIONS.search(title)
        got = (int(match.group(1)), int(match.group(2) or match.group(1))) if match else None
        if got != (f.start, f.end):
            problems.append(f"{where}: the heading must say (positions {f.positions}) as in the spec.")
    record = re.match(r"\W*([A-Za-z0-9_]+)", markdown.labelled(body, "Record") or "")
    if f.record and (record.group(1) if record else "") != f.record:
        problems.append(f"{where}: the line **Record:** must name its record type {f.record}, as in the spec.")
    for label in ("Meaning", "Kind", "Source", "When missing"):
        if not markdown.labelled(body, label):
            problems.append(f"{where}: the line **{label}:** is missing.")
    if markdown.words(markdown.labelled(body, "Meaning") or "") > MAX_MEANING_WORDS:
        problems.append(f"{where}: **Meaning:** has more than {MAX_MEANING_WORDS} words.")
    problems += _requirements(unit, f, where, markdown.first_table(markdown.section(body, "Requirements")), rules)
    if (markdown.labelled(body, "Kind") or "").lower().startswith("variant") \
            and not markdown.first_table(markdown.section(body, "Decision table")):
        problems.append(f"{where}: a variant field needs a Decision table.")
    problems += _examples(f, where, markdown.first_table(markdown.section(body, "Examples")))
    rows = markdown.first_table(markdown.section(body, "Evidence"))
    if not rows:
        problems.append(f"{where}: the Evidence table is empty.")
    problems += [f"{where}: {p}" for row in rows
                 for p in evidence.check(row.get("File:line", ""), row.get("Code", ""), roots)]
    return problems


def _requirements(unit: Unit, f: spec.Field, where: str, rows: List[markdown.Row],
                  rules: Dict[str, links.Rule]) -> List[str]:
    if not rows:
        return [f"{where}: the Requirements table is empty."]
    problems, pattern = [], re.compile(rf"{unit.output_id}-{f.number:02d}-R\d+$")
    ids = [r.get("ID", "").strip() for r in rows]
    problems += [f"{where}: requirement id `{i}` must look like {unit.output_id}-{f.number:02d}-R1."
                 for i in ids if not pattern.match(i)]
    problems += [f"{where}: requirement id {i} is used twice." for i in sorted({i for i in ids if ids.count(i) > 1})]
    problems += [f"{where}: {r.get('ID')} has {markdown.words(r.get('Requirement', ''))} words; "
                 f"at most {MAX_RULE_WORDS}." for r in rows if markdown.words(r.get("Requirement", "")) > MAX_RULE_WORDS]
    return problems + _rule_links(f, where, rows, rules)


def _rule_links(f: spec.Field, where: str, rows: List[markdown.Row], rules: Dict[str, links.Rule]) -> List[str]:
    """Each requirement names the business rule it carries out, so a reader can go from a rule to its fields
    and back."""
    if links.RULE_COLUMN not in rows[0]:
        return [f"{where}: the Requirements table needs the column `{links.RULE_COLUMN}` "
                f"(| ID | Requirement | {links.RULE_COLUMN} |)."]
    problems = []
    for row in rows:
        ids, marker = links.cell_rules(row.get(links.RULE_COLUMN, ""))
        label = f"{where}: {row.get('ID', '?')}"
        if not marker:
            problems.append(f"{label}: `{links.RULE_COLUMN}` must name a flow rule (F01-BR05), or say "
                            f"`{links.FORMAT}` (layout only) or `{links.NONE}` (no flow rule decides it: add a question).")
        problems += [f"{label}: {i} is not a business rule in the flow files." for i in ids if i not in rules]
    link = links.field_link("", f.number, f.name, rows)
    if not link.rules and not link.format_only and not link.unlinked:
        problems.append(f"{where}: no requirement names the business rule that decides this field.")
    return problems


def _examples(f: spec.Field, where: str, rows: List[markdown.Row]) -> List[str]:
    if not rows:
        return [f"{where}: the Examples table is empty."]
    if f.length is None:
        return []
    problems = []
    for row in rows:
        written = markdown.backticked(row.get("Written", ""))
        if written and len(written[0]) != f.length:
            problems.append(f"{where}: example {row.get('#', '?')} writes `{written[0]}` "
                            f"({len(written[0])} characters); the field has {f.length}. Show spaces as ·.")
    return problems


# Concepts: the business page, written only from checked flow and output files

FIELDS_SECTION = "Fields this question changes"
CONCEPT_SECTIONS = ["In short", "What the business expects and what the system does", "Types and how each works",
                    FIELDS_SECTION, "Worked examples", "Questions for the SME"]
INTENT_SECTION = CONCEPT_SECTIONS[1]
TYPES_SECTION = CONCEPT_SECTIONS[2]
STATUSES = ("matches", "differs", "not found")
MAX_SHORT_WORDS = 150
BASED_ON = re.compile(r"\b[FO]\d{2}-(?:BR\d{2}|SC\d+|\d{2}-R\d+)\b")
CODE_WORDS = [
    (re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b"), "a Java name"),
    (re.compile(r"\b[A-Za-z_]\w*\((?!s\))"), "a method call"),
    (re.compile(r"==|!=|&&|\|\||\+\+"), "a code operator"),
    (re.compile(r"\.java\b|\.xml\b"), "a file name"),
    (re.compile(r"\bnull\b"), "null (write: no value)"),
]


def _concept(unit: Unit, text: str, paths: Paths, discovery: Discovery) -> List[str]:
    problems = _required(text, CONCEPT_SECTIONS)
    if problems:
        return problems
    item = next(c for c in discovery.concepts if c.id == unit.id)
    card = concept.load(paths.input / item.card, paths.input)
    known = _known_ids(paths, discovery)
    short = markdown.section(text, "In short") or ""
    if markdown.words(short) > MAX_SHORT_WORDS:
        problems.append(f"`## In short` has {markdown.words(short)} words; at most {MAX_SHORT_WORDS}.")
    problems += _intents(card, markdown.first_table(markdown.section(text, INTENT_SECTION)), known)
    problems += _types(item, markdown.first_table(markdown.section(text, TYPES_SECTION)), paths, discovery, known)
    problems += _fields_derived(item, markdown.section(text, FIELDS_SECTION) or "", paths, discovery,
                                known)
    problems += _worked_examples(markdown.section(text, "Worked examples") or "")
    problems += _walkthroughs(item, markdown.section(text, "Worked examples") or "", paths, discovery, known)
    problems += _plain_words(markdown.strip_sections(text, ["Questions for the SME"]))
    problems += asked_before(text, paths, ("flows", "outputs", "concepts"), paths.unit_file(unit.id))
    return problems


def _types(item, rows: List[markdown.Row], paths: Paths, discovery: Discovery, known: set) -> List[str]:
    """One row per type: each code that changes what the system does, how it is handled, and an example. Every
    code the concept's flows compare with, and that has a meaning in the input folder, must be a row."""
    if not rows:
        return [f"`## {TYPES_SECTION}` has no table."]
    problems = []
    for n, row in enumerate(rows, 1):
        for column in ("Type", "How the system handles it", "Example"):
            if not (row.get(column) or "").strip():
                problems.append(f"{TYPES_SECTION}, row {n}: the column `{column}` is empty.")
    problems += _based_on(rows, TYPES_SECTION, known)
    listed = " ".join(row.get("Type", "") for row in rows)
    meanings = terms.defined(paths.input)
    seen = set()
    for flow_id in item.flows:
        flow_file = paths.unit_file(flow_id)
        flow_text = flow_file.read_text(encoding="utf-8") if flow_file.exists() else ""
        for value in coverage.code_values(paths, coverage.reaches(paths, discovery, flow_id, flow_text)):
            if value.value in seen or value.value.lower() not in meanings:
                continue
            seen.add(value.value)
            if not terms.mentions(listed, value.value):
                problems.append(f"{TYPES_SECTION}: the code {value.value} changes what {flow_id} does "
                                f"({value.file}:{value.line}) but has no row. Add it, with how it is handled.")
    return problems


def _known_ids(paths: Paths, discovery: Discovery) -> set:
    """Rule, scenario and requirement ids written in the flow and output files of this run."""
    known = set()
    for folder in ("flows", "outputs"):
        for path in (paths.out / folder).glob("*.md"):
            known |= set(BASED_ON.findall(path.read_text(encoding="utf-8")))
    return known


def _intents(card: concept.Card, rows: List[markdown.Row], known: set) -> List[str]:
    problems, seen = [], [r.get("#", "").strip() for r in rows]
    for intent_id, _ in card.intents:
        if seen.count(intent_id) != 1:
            problems.append(f"{card.file} line {intent_id} must have exactly one row in the table "
                            f"`## {INTENT_SECTION}` (found {seen.count(intent_id)}).")
    problems += [f"Row {i}: not a line of {card.file}." for i in seen if i and i not in card.ids]
    for row in rows:
        where = f"Row {row.get('#', '?')}"
        status = (row.get("Status", "") or "").lower()
        if not any(s in status for s in STATUSES):
            problems.append(f"{where}: Status must be one of ✅ Matches, ⚠️ Differs, ❓ Not found in the code.")
        does = row.get("The system does", "").strip()
        if not does:
            problems.append(f"{where}: `The system does` is empty.")
        elif markdown.words(does) > MAX_RULE_WORDS:
            problems.append(f"{where}: `The system does` has {markdown.words(does)} words; at most {MAX_RULE_WORDS}.")
    problems += _based_on([r for r in rows if "not found" not in (r.get("Status", "") or "").lower()],
                          INTENT_SECTION, known)
    return problems


def _based_on(rows: List[markdown.Row], where: str, known: set) -> List[str]:
    """Each row stands on rules or requirements that were checked; ids that do not exist are made up."""
    problems = []
    for n, row in enumerate(rows, 1):
        cell = row.get("Based on", "")
        ids = BASED_ON.findall(cell)
        label = f"{where}, row {row.get('#') or n}"
        if not ids:
            problems.append(f"{label}: `Based on` names no rule or requirement id (F01-BR02, O01-05-R1).")
        problems += [f"{label}: {i} does not exist in the flow and output files." for i in ids if i not in known]
    return problems


def _fields_derived(item, text: str, paths: Paths, discovery: Discovery, known: set) -> List[str]:
    """Only the fields this question changes, so the page does not repeat the output section: every variant
    field of the concept's outputs, and any other field the page needs. The rest is linked, not copied."""
    problems, parts = [], dict(markdown.sections(text, 3))
    for output_id in item.outputs:
        output = next((o for o in discovery.outputs if o.id == output_id), None)
        if output is None or not output.spec:
            continue
        title = next((t for t in parts if t.strip().startswith(output_id)), None)
        if title is None:
            problems.append(f"`## {FIELDS_SECTION}` has no `### {output_id} ...` part.")
            continue
        rows = markdown.first_table(parts[title])
        fields = spec.load(paths.input / output.spec)
        by_label = {f.label: f.name for f in fields}
        named = set()
        for r in rows:
            cell = (markdown.backticked(r.get("Field", "")) or [r.get("Field", "").strip()])[0].strip()
            if cell:
                named.add(by_label.get(cell, cell))
        known_names = {f.name for f in fields}
        problems += [f"{output_id}: `{n}` is not a field of its specification." for n in sorted(named - known_names)]
        missing = [name for name in variant_fields(paths, output_id, fields) if name not in named]
        if missing:
            problems.append(f"{output_id}: the variant fields {', '.join(missing)} change by type and need a row.")
        for row in rows:
            derived = row.get("Derived as", "")
            if markdown.words(derived) > MAX_RULE_WORDS:
                problems.append(f"{output_id} {row.get('Field')}: `Derived as` has {markdown.words(derived)} words; "
                                f"at most {MAX_RULE_WORDS}.")
        problems += _based_on(rows, f"{output_id} fields", known)
    return problems


def fields_with(paths: Paths, output_id: str, label: str, prefix: str) -> List[int]:
    """Numbers of the fields of an output whose line **label:** starts with `prefix`, from its unit files."""
    found = []
    for path in sorted((paths.out / "outputs").glob(f"{output_id}*.md")):
        for title, body in markdown.sections(path.read_text(encoding="utf-8"), 2):
            number = title.split(".")[0].strip()
            if number.isdigit() and (markdown.labelled(body, label) or "").lower().startswith(prefix):
                found.append(int(number))
    return found


SPOT_SECTION = "Spot check"
SPOT_FIELDS = 3


def spot_fields(unit: Unit, paths: Paths, discovery: Discovery) -> List[spec.Field]:
    """Up to SPOT_FIELDS fields of an output unit that the verifier traces from the code itself: the variant
    fields first, then fields spread over the unit; never a fixed value. The same fields every time."""
    output = next(o for o in discovery.outputs if o.id == unit.output_id)
    fields = unit.fields(spec.load(paths.input / output.spec))
    fixed = set(fields_with(paths, unit.output_id, "Source", "fixed"))
    variant = set(fields_with(paths, unit.output_id, "Kind", "variant"))
    pool = [f for f in fields if f.number not in fixed]
    first = [f for f in pool if f.number in variant]
    rest = [f for f in pool if f.number not in variant]
    step = max(1, len(rest) // SPOT_FIELDS)
    return (first + rest[::step])[:SPOT_FIELDS]


def spot_problems(unit: Unit, paths: Paths, discovery: Discovery) -> List[str]:
    """The verifier's own trace of the spot-check fields must name the same business rules as the unit file.
    When they differ, one of the two is wrong."""
    text = paths.unit_file(unit.id).read_text(encoding="utf-8")
    output = next(o for o in discovery.outputs if o.id == unit.output_id)
    linked = links.output_fields(text, unit.output_id, spec.load(paths.input / output.spec))
    verify = paths.verify_file(unit.id).read_text(encoding="utf-8")
    rows = {(markdown.backticked(r.get("Field", "")) or [r.get("Field", "").strip()])[0].strip(): r
            for r in markdown.first_table(markdown.section(verify, SPOT_SECTION))}
    problems = []
    for f in spot_fields(unit, paths, discovery):
        row = rows.get(f.name)
        if row is None:
            problems.append(f"`## {SPOT_SECTION}` has no row for {f.number:02d} {f.name}: trace it from the code "
                            f"yourself (| Field | Source | Business rule |).")
            continue
        mine = set(BASED_ON.findall(row.get("Business rule", "")))
        link = linked.get(f.number)
        theirs = set(link.rules) if link else set()
        if theirs and not mine & theirs:
            problems.append(f"Spot check {f.name}: you found {', '.join(sorted(mine)) or 'no rule'}, the unit file "
                            f"names {', '.join(sorted(theirs))}. Read the code again: if the unit is wrong, FAIL "
                            f"it with that point; if you were wrong, correct your row.")
    return problems


def variant_fields(paths: Paths, output_id: str, fields: List[spec.Field]) -> List[str]:
    """The fields of an output whose **Kind:** is a variant, read from its checked unit files."""
    names = {f.number: f.name for f in fields}
    return [names[n] for n in fields_with(paths, output_id, "Kind", "variant") if n in names]


def asked_before(text: str, paths: Paths, folders: Tuple[str, ...], own: Path) -> List[str]:
    """A question another part already asks is not asked again: the document lists each question once."""
    earlier = []
    for folder in folders:
        for path in sorted((paths.out / folder).glob("*.md")):
            if path.parent.resolve() == own.parent.resolve() and path.stem >= own.stem:
                continue  # in its own folder, only the parts written before it
            earlier += [(q, path.stem) for q, _ in questions.of(path.read_text(encoding="utf-8"))]
    problems = []
    for question, _ in questions.of(text):
        match = max(earlier, key=lambda e: questions.score(e[0], question), default=None)
        if match and questions.same(match[0], question):
            problems.append(f"Question \"{question}\" is already asked in {match[1]} (\"{match[0]}\"). Remove it "
                            f"here: the document lists each question once, with every part that raised it.")
    return problems


def _worked_examples(text: str) -> List[str]:
    """At least one worked example, and each one says what happened."""
    examples = markdown.sections(text, 3)
    if not examples:
        return ["`## Worked examples` needs at least one `### Example 1. ...`."]
    return [f"{title}: the line **Event:** is missing: say what happened, with the amounts and dates."
            for title, body in examples if not markdown.labelled(body, "Event")]


_IN_FILE = re.compile(r"^(O\d{2})\s+line\s+(\d+)\s*$", re.I)
WALK_LABEL = "In the file"


def _walkthroughs(item, text: str, paths: Paths, discovery: Discovery, known: set) -> List[str]:
    """Connects the dots with real data: an example that names its line in the real output file
    (`**In the file:** O01 line 2`) lists field values, and each value must be exactly what that line holds.
    When the real file of a concept's output is there, at least one example must do it."""
    outputs = {o.id: o for o in discovery.outputs if o.id in item.outputs and o.spec}
    real = {oid: paths.test_file(oid, "actual") for oid in outputs if paths.test_file(oid, "actual").exists()}
    problems, walked = [], 0
    for title, body in markdown.sections(text, 3):
        where = markdown.labelled(body, WALK_LABEL)
        if where is None:
            continue
        match = _IN_FILE.match(where.strip("` "))
        if not match or match.group(1) not in real:
            problems.append(f"{title}: `**{WALK_LABEL}:**` must name an output with a real test file and a line, "
                            f"like `O01 line 2` (real files: {', '.join(real) or 'none'}).")
            continue
        output_id, number = match.group(1), int(match.group(2))
        lines = real[output_id].read_text(encoding="utf-8", errors="replace").splitlines()
        if not 1 <= number <= len(lines):
            problems.append(f"{title}: {output_id} has {len(lines)} lines, not line {number}.")
            continue
        line = lines[number - 1]
        all_fields = spec.load(paths.input / outputs[output_id].spec)
        by_delimiter = compare.delimited(all_fields)
        layout = {f.name: f for f in (all_fields if by_delimiter else spec.layout(line, all_fields))}
        rows = [r for table in markdown.tables(body) for r in table if "Field" in r and "Value" in r]
        if not rows:
            problems.append(f"{title}: no table `| Field | Value | Based on |` with the values of that line.")
            continue
        walked += 1
        for row in rows:
            name = (markdown.backticked(row.get("Field", "")) or [row.get("Field", "").strip()])[0]
            field = layout.get(name)
            if field is None or (field.start is None and not by_delimiter):
                problems.append(f"{title}: `{name}` is not a field of line {number} of {output_id}.")
                continue
            value = (markdown.backticked(row.get("Value", "")) or [row.get("Value", "").strip()])[0].replace("·", " ")
            real_value = compare.value(line, field, by_delimiter)
            if value.rstrip() != real_value.rstrip():
                problems.append(f"{title}: {name} is `{value}` here but `{real_value.replace(' ', '·')}` in line "
                                f"{number} of the real {output_id} file.")
        problems += _based_on(rows, f"{title} values", known)
    if real and not walked:
        problems.append(f"`## Worked examples`: at least one example must follow a real record into the file: add "
                        f"`**{WALK_LABEL}:** {next(iter(real))} line <n>` and a table `| Field | Value | Based on |`.")
    return problems


# The business summary: the whole module for a reader new to the domain, written from the checked files

SUMMARY_SECTIONS = ["In one paragraph", "Who and what is involved", "The process from start to end",
                    "A worked example", "What can go wrong", "Words to know", "Questions for the SME"]
MAX_PARAGRAPH_WORDS = 120
_SCENARIO = re.compile(r"\b(F\d{2})-SC\d+\b")


def _summary(text: str, paths: Paths, discovery: Discovery) -> List[str]:
    problems = _required(text, SUMMARY_SECTIONS)
    if problems:
        return problems
    known_ids = _known_ids(paths, discovery)
    paragraph = markdown.section(text, "In one paragraph") or ""
    if markdown.words(paragraph) > MAX_PARAGRAPH_WORDS:
        problems.append(f"`## In one paragraph` has {markdown.words(paragraph)} words; at most {MAX_PARAGRAPH_WORDS}.")
    if not markdown.first_table(markdown.section(text, "Who and what is involved")):
        problems.append("`## Who and what is involved` has no table (| Who or what | Role |).")
    cited = set()
    for title, column in (("The process from start to end", "What happens"), ("A worked example", "What happens"),
                          ("What can go wrong", "What happens")):
        rows = markdown.first_table(markdown.section(text, title))
        if not rows:
            problems.append(f"`## {title}` has no table.")
            continue
        problems += _based_on(rows, title, known_ids)
        problems += [f"{title}, row {r.get('#') or n}: `{column}` has {markdown.words(r.get(column, ''))} words; "
                     f"at most {MAX_RULE_WORDS}." for n, r in enumerate(rows, 1)
                     if markdown.words(r.get(column, "")) > MAX_RULE_WORDS]
        cited |= {i for r in rows for i in BASED_ON.findall(r.get("Based on", ""))}
    flows = [f.id for f in discovery.flows if discovery.in_scope(f.id)]
    problems += [f"`## The process from start to end` and the tables after it name no rule or scenario of {f}: every "
                 f"flow is part of the story." for f in flows if not any(i.startswith(f + "-") for i in cited)]
    scenarios = sorted({i for i in known_ids if _SCENARIO.fullmatch(i) and _SCENARIO.fullmatch(i).group(1) in flows})
    problems += _capped([f"Scenario {s} is not in the summary: name it in `Based on` of the process, the worked "
                         f"example or What can go wrong." for s in scenarios if s not in cited], "")
    known = terms.input_text(paths.input)
    words = markdown.first_table(markdown.section(text, "Words to know"))
    listed = [w.get("Term", "").strip().strip("`") for w in words]
    problems += [f"Words to know: `{t}` has no meaning in the input folder; move it to the questions."
                 for t in listed if t and not terms.mentions(known, t)]
    problems += [f"Words to know: the plan in discovery.md says to explain `{t}` first; it has no row."
                 for t in discovery.terms_first if not any(terms.mentions(term, t) for term in listed)]
    prose = markdown.strip_sections(text, ["Words to know", "Questions for the SME"])
    prose = "\n".join(line for line in prose.splitlines() if not line.startswith("# "))  # the title
    ignore = tables_used(paths) | {paths.module.name.upper()}
    problems += [f"`{t}` is used in the summary; give it a row in `## Words to know`."
                 for t in terms.caps_terms(prose, ignore) if not any(terms.mentions(term, t) for term in listed)]
    problems += asked_before(text, paths, ("flows", "outputs", "concepts"), paths.unit_file("SUMMARY"))
    return problems + _plain_words(prose)


def _plain_words(text: str) -> List[str]:
    """Business text is for a reader new to the domain: no code. Ids and table names are allowed."""
    problems = []
    for line in text.splitlines():
        if line.lstrip().startswith("#") or re.match(r"^\s*\|?[-:| ]+\|?\s*$", line):
            continue
        cells = markdown.split_row(line) if line.strip().startswith("|") else [line]
        for cell in cells:
            if BASED_ON.search(cell) and re.fullmatch(r"[\sA-Z0-9,;\-]*", cell):
                continue  # a Based on cell
            for pattern, what in CODE_WORDS:
                match = pattern.search(cell)
                if match:
                    problems.append(f"`{match.group()}` is {what}; business text uses plain words "
                                    f"(line: {line.strip()[:80]}).")
                    break
    return problems[:15]


# Shared

def _required(text: str, titles: List[str]) -> List[str]:
    return [f"The section `## {t}` is missing." for t in titles if markdown.section(text, t) is None]


def _evidence(rows: List[markdown.Row], rule_ids, roots: Tuple[Path, ...]) -> List[str]:
    problems = []
    cited = {r.get("Ref", "").strip() for r in rows}
    problems += [f"{r}: no row in the Evidence table." for r in sorted(rule_ids - cited)]
    for row in rows:
        problems += [f"Evidence {row.get('Ref', '?')}: {p}"
                     for p in evidence.check(row.get("File:line", ""), row.get("Code", ""), roots)]
    return problems
