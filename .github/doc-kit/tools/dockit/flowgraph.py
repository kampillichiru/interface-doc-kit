"""The flow of a unit as a graph: parsed from the Steps table, checked, and drawn as Mermaid."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from . import markdown

KINDS = ("start", "step", "decision", "end")
SCENARIO_TYPES = ("main", "alternate", "exception")
MAX_STEP_WORDS = 12


@dataclass
class Step:
    id: str
    kind: str
    text: str
    edges: List[Tuple[str, str]] = field(default_factory=list)  # (label, target)
    rules: List[str] = field(default_factory=list)


def parse_steps(rows: List[markdown.Row]) -> Dict[str, Step]:
    steps = {}
    for row in rows:
        step = Step(row.get("Step", "").strip(), row.get("Kind", "").strip().lower(), row.get("Text", "").strip())
        for part in filter(None, (p.strip() for p in row.get("Next", "").split(";"))):
            label, _, target = part.rpartition(":")
            step.edges.append((label.strip(), target.strip()))
        step.rules = re.findall(r"[A-Z]\d{2}-BR\d+", row.get("Rules", ""))
        steps[step.id] = step
    return steps


def check(steps: Dict[str, Step], scenarios: List[markdown.Row], rule_ids: Set[str]) -> List[str]:
    problems = []
    if not steps:
        return ["Steps: the table is empty."]
    for step in steps.values():
        problems += _check_step(step, steps, rule_ids)
    starts = [s.id for s in steps.values() if s.kind == "start"]
    if not starts:
        problems.append("Steps: no step of kind start.")
    if not any(s.kind == "end" for s in steps.values()):
        problems.append("Steps: no step of kind end.")
    unreachable = set(steps) - _reachable(starts, steps)
    if unreachable:
        problems.append(f"Steps: {', '.join(sorted(unreachable))} cannot be reached from a start step.")
    problems += _check_scenarios(steps, scenarios)
    used = {r for s in steps.values() for r in s.rules}
    problems += [f"Rule {r} is not linked to any step (column Rules)." for r in sorted(rule_ids - used)]
    return problems


def _check_step(step: Step, steps: Dict[str, Step], rule_ids: Set[str]) -> List[str]:
    where = f"Step {step.id or '?'}"
    problems = []
    if step.kind not in KINDS:
        problems.append(f"{where}: kind `{step.kind}` must be one of {', '.join(KINDS)}.")
    if markdown.words(step.text) > MAX_STEP_WORDS:
        problems.append(f"{where}: text has {markdown.words(step.text)} words; at most {MAX_STEP_WORDS}.")
    expected = {"end": (0, 0), "decision": (2, 99)}.get(step.kind, (1, 1))
    if not expected[0] <= len(step.edges) <= expected[1]:
        problems.append(f"{where}: a {step.kind} step needs "
                        + {"end": "no Next", "decision": "two or more branches like `yes: S4; no: E1`"}
                        .get(step.kind, "exactly one Next"))
    if step.kind == "decision" and any(not label for label, _ in step.edges):
        problems.append(f"{where}: every branch needs a label, like `yes: S4`.")
    problems += [f"{where}: Next `{target}` is not a step." for _, target in step.edges if target not in steps]
    problems += [f"{where}: rule {r} has no section under Business rules." for r in step.rules if r not in rule_ids]
    return problems


def _reachable(starts: List[str], steps: Dict[str, Step]) -> Set[str]:
    seen, todo = set(), list(starts)
    while todo:
        current = todo.pop()
        if current in seen or current not in steps:
            continue
        seen.add(current)
        todo += [target for _, target in steps[current].edges]
    return seen


def _check_scenarios(steps: Dict[str, Step], scenarios: List[markdown.Row]) -> List[str]:
    problems, covered = [], set()
    if not any(r.get("Type", "").strip().lower() == "main" for r in scenarios):
        problems.append("Scenarios: at least one scenario of type main is needed.")
    for row in scenarios:
        where = f"Scenario {row.get('ID', '?')}"
        if row.get("Type", "").strip().lower() not in SCENARIO_TYPES:
            problems.append(f"{where}: type must be one of {', '.join(SCENARIO_TYPES)}.")
        path = re.findall(r"[A-Z]\d+", row.get("Path", ""))
        if not path or steps.get(path[0], Step("", "", "")).kind != "start" \
                or steps.get(path[-1], Step("", "", "")).kind != "end":
            problems.append(f"{where}: the path must begin at a start step and end at an end step.")
            continue
        for a, b in zip(path, path[1:]):
            if b not in [t for _, t in steps.get(a, Step("", "", "")).edges]:
                problems.append(f"{where}: there is no arrow from {a} to {b}.")
            covered.add((a, b))
    missing = [f"{s.id}->{t}" for s in steps.values() for _, t in s.edges if (s.id, t) not in covered]
    if missing:
        problems.append(f"Scenarios: no scenario follows {', '.join(missing)}. Every arrow needs one.")
    return problems


def mermaid(steps: Dict[str, Step]) -> str:
    def node(s: Step) -> str:
        text = s.text.replace('"', "'")
        return {"start": f'{s.id}(["{text}"])', "end": f'{s.id}(["{text}"])',
                "decision": f'{s.id}{{"{text}"}}'}.get(s.kind, f'{s.id}["{text}"]')

    lines = ["```mermaid", "flowchart TD"]
    lines += [f"  {node(s)}" for s in steps.values()]
    for s in steps.values():
        for label, target in s.edges:
            lines.append(f"  {s.id} -->|{label}| {target}" if label else f"  {s.id} --> {target}")
    return "\n".join(lines + ["```"])
