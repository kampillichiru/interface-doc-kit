"""The review: a business analyst or SME reads the finished documents and must connect the dots.

The tool sets the questions (the same ones every run, from the documents themselves): every difference between
the business intention and the system, every type, the fields that vary and a sample of the others, and the main
example. The reviewer answers each with a chain of ids, from the business question to the rule, the scenario and
the field (`O01-16 → F01-BR09 → F01-SC3 → SUMMARY 6`). The tool checks that every link of each chain is real.
A link the reviewer cannot find is written `not found`, with a point that says what is missing and which part
owns it; the part is sent back to its writer.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import checks, links, markdown, spec
from .discovery import Discovery
from .plan import Plan
from .project import SUMMARY_ID, Paths

REVIEW_ID = "REVIEW"
MAX_REVIEW_ROUNDS = 2
MAX_FIELD_QUESTIONS = 12  # besides the variant fields, which are always asked
NOT_FOUND = "not found"
_FIELD = re.compile(r"^(O\d{2})-(\d{2})(?:-R\d+)?$")
_SUMMARY_ROW = re.compile(r"SUMMARY\s+(\d+)", re.I)
_ID = re.compile(r"\b(F\d{2}-BR\d{2}|F\d{2}-SC\d+|O\d{2}-\d{2}(?:-R\d+)?|C\d{2}-[IA]\d+)\b")
VERDICT = re.compile(r"\*\*Verdict:\*\*\s*(READY|NEEDS WORK)", re.I)


@dataclass
class Question:
    id: str  # R1, R2, ...
    text: str
    kind: str  # difference | type | field | example
    target: str = ""  # the field id (O01-16), the intent (C01-I6) or the concept (C01)
    expect: List[str] = field(default_factory=list)  # ids one of which the chain must name


def _field_links(paths: Paths, discovery: Discovery, plan: Plan) -> Dict[str, links.FieldLink]:
    found: Dict[str, links.FieldLink] = {}
    for item in discovery.outputs:
        if not item.spec or not plan.output_units(item.id):
            continue
        fields = spec.load(paths.input / item.spec)
        for unit in plan.output_units(item.id):
            path = paths.unit_file(unit.id)
            if path.exists():
                for number, link in links.output_fields(path.read_text(encoding="utf-8"), item.id, fields).items():
                    found[f"{item.id}-{number:02d}"] = link
    return found


def questions(paths: Paths, discovery: Discovery, plan: Plan) -> List[Question]:
    """The questions of the review, in a fixed order, so two runs ask the same."""
    found: List[Question] = []

    def add(text, kind, target="", expect=()):
        found.append(Question(f"R{len(found) + 1}", text, kind, target, list(expect)))

    for unit in (u for u in plan.units if u.kind == "concept"):
        path = paths.unit_file(unit.id)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for row in markdown.first_table(markdown.section(text, checks.INTENT_SECTION)):
            status = row.get("Status", "").lower()
            if "matches" in status:
                continue
            add(f"{unit.id}-{row.get('#', '').strip()}: the business expects \"{row.get('The business expects', '')}\". "
                f"What does the system do instead, and which rule and field show it?", "difference",
                f"{unit.id}-{row.get('#', '').strip()}", checks.BASED_ON.findall(row.get("Based on", "")))
        for row in markdown.first_table(markdown.section(text, checks.TYPES_SECTION)):
            add(f"{unit.id}, type {row.get('Type', '').strip()}: how does the system handle it, and which rule says "
                f"so?", "type", unit.id, checks.BASED_ON.findall(row.get("Based on", "")))
    field_links = _field_links(paths, discovery, plan)
    variant = set()
    for o in (o for o in discovery.outputs if o.spec and plan.output_units(o.id)):
        names = set(checks.variant_fields(paths, o.id, spec.load(paths.input / o.spec)))
        variant |= {f"{o.id}-{n:02d}" for n, name in _numbered(paths, o) if name in names}
    fixed = _fixed_fields(paths, discovery, plan)
    decided = [fid for fid, link in field_links.items() if link.rules and fid not in variant and fid not in fixed]
    room = max(0, MAX_FIELD_QUESTIONS - len(variant))
    step = max(1, len(decided) // max(1, room))
    chosen = sorted(variant) + decided[::step][:room]
    for fid in sorted(set(chosen), key=lambda f: (f[:3], int(f[4:]))):
        link = field_links.get(fid)
        add(f"{fid} {link.name if link else ''}: which business rule decides it, in which scenario of the flow, and "
            f"which step of the summary tells it?", "field", fid, link.rules if link else [])
    if paths.unit_file(SUMMARY_ID).exists():
        rows = markdown.first_table(markdown.section(paths.unit_file(SUMMARY_ID).read_text(encoding="utf-8"),
                                                     "A worked example"))
        ids = [i for r in rows for i in checks.BASED_ON.findall(r.get("Based on", ""))]
        add("Follow the worked example of the summary from start to end: which rules does it pass through, and "
            "which fields of the output does it fill?", "example", SUMMARY_ID, ids)
    return found


def _fixed_fields(paths: Paths, discovery: Discovery, plan: Plan) -> set:
    """Fields whose **Source:** is a fixed value: nothing for a reader to connect."""
    return {f"{item.id}-{n:02d}" for item in discovery.outputs if item.spec and plan.output_units(item.id)
            for n in checks.fields_with(paths, item.id, "Source", "fixed")}


def _numbered(paths: Paths, output) -> List[Tuple[int, str]]:
    return [(f.number, f.name) for f in spec.load(paths.input / output.spec)]


def render(found: List[Question]) -> str:
    rows = ["# Review questions", "",
            "Written by the tool. Answer every question in `review/REVIEW.md`, with the chain of ids that connects it.",
            "", "| Q | Question |", "|---|---|"]
    rows += [f"| {q.id} | {q.text.replace('|', '/')} |" for q in found]
    return "\n".join(rows) + "\n"


@dataclass
class Result:
    verdict: Optional[str]
    answers: Dict[str, Tuple[str, str]]  # Q -> (answer, chain)
    points: List[Dict[str, str]]  # rows: # | Part | What ... | Suggestion

    def parts(self) -> List[str]:
        found = []
        for row in self.points:
            part = row.get("Part", "").strip().strip("`")
            if part and part not in found:
                found.append(part)
        return found


def read(path: Path) -> Optional[Result]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    verdict = VERDICT.search(text)
    answers = {r.get("Q", "").strip(): (r.get("Answer", ""), r.get("Chain", ""))
               for r in markdown.first_table(markdown.section(text, "Answers")) if r.get("Q", "").strip()}
    points = [r for r in markdown.first_table(markdown.section(text, "Points"))
              if any(v.strip() and v.strip().lower() not in ("none", "none.", "-") for k, v in r.items() if k != "#")]
    return Result(verdict.group(1).upper() if verdict else None, answers, points)


def problems(paths: Paths, discovery: Discovery, plan: Plan) -> List[str]:
    """Every question answered, and every link of every chain real."""
    result = read(paths.unit_file(REVIEW_ID))
    if result is None:
        return ["review/REVIEW.md is missing."]
    found = []
    if result.verdict is None:
        found.append("The line `**Verdict:** READY` or `**Verdict:** NEEDS WORK` is missing.")
    known = checks._known_ids(paths, discovery)
    known |= {f"{o.id}-{n:02d}" for o in discovery.outputs if o.spec for n, _ in _numbered(paths, o)}
    for unit in (u for u in plan.units if u.kind == "concept" and paths.unit_file(u.id).exists()):
        text = paths.unit_file(unit.id).read_text(encoding="utf-8")
        for table in (checks.INTENT_SECTION, "Also in the system"):
            known |= {f"{unit.id}-{r.get('#', '').strip()}" for r in markdown.first_table(markdown.section(text, table))}
    rules = links.flow_rules(paths.out / "flows")
    field_links = _field_links(paths, discovery, plan)
    summary_rows = markdown.first_table(markdown.section(
        paths.unit_file(SUMMARY_ID).read_text(encoding="utf-8"), "The process from start to end")) \
        if paths.unit_file(SUMMARY_ID).exists() else []
    point_text = " ".join(" ".join(r.values()) for r in result.points)
    valid_parts = {u.id for u in plan.units} | {"discovery"}
    for q in questions(paths, discovery, plan):
        if q.id not in result.answers:
            found.append(f"{q.id}: no answer.")
            continue
        _, chain = result.answers[q.id]
        ids = _ID.findall(chain)
        if NOT_FOUND in chain.lower():
            if not re.search(rf"\b{q.id}\b", point_text):
                found.append(f"{q.id}: the chain says `{NOT_FOUND}`; add a point that names {q.id}, says what is "
                             f"missing and which part owns it.")
            continue
        found += [f"{q.id}: {i} does not exist in the documents." for i in ids if i not in known]
        if q.expect and not any(i in q.expect for i in ids):
            found.append(f"{q.id}: the chain names none of the rules or fields the documents give for it "
                         f"({', '.join(q.expect[:6])}). Find them, or write `{NOT_FOUND}` and add a point.")
        if q.kind == "field":
            if not any(_FIELD.match(i) and _FIELD.match(i).group(0).startswith(q.target) for i in ids):
                found.append(f"{q.id}: the chain must start at the field {q.target}.")
            link = field_links.get(q.target)
            for i in ids:
                if re.fullmatch(r"F\d{2}-BR\d{2}", i) and link and link.rules and i not in link.rules \
                        and i in rules:
                    found.append(f"{q.id}: {i} does not decide {q.target}; the field section names "
                                 f"{', '.join(link.rules)}.")
            rule_flows = {r[:3] for r in ids if re.fullmatch(r"F\d{2}-BR\d{2}", r)}
            for s in (i for i in ids if re.fullmatch(r"F\d{2}-SC\d+", i)):
                if rule_flows and s[:3] not in rule_flows:
                    found.append(f"{q.id}: scenario {s} is not of the flow of its rule ({', '.join(sorted(rule_flows))}).")
            for n in _SUMMARY_ROW.findall(chain):
                row = next((r for r in summary_rows if r.get("#", "").strip() == n), None)
                cited = set(checks.BASED_ON.findall(row.get("Based on", ""))) if row else set()
                if row is None:
                    found.append(f"{q.id}: the summary has no step {n}.")
                elif not cited & set(ids):
                    found.append(f"{q.id}: step {n} of the summary names none of the rules or scenarios of the chain.")
    found += [f"Point {r.get('#', '?')}: `{r.get('Part')}` is not a part of this run "
              f"({', '.join(sorted(valid_parts))})." for r in result.points
              if r.get("Part", "").strip().strip("`") not in valid_parts]
    if len(result.points) > 10:
        found.append(f"{len(result.points)} points; at most 10, the most blocking first.")
    if result.verdict == "READY" and result.points:
        found.append("A READY review has no points: change the verdict to NEEDS WORK or remove the points.")
    return found
