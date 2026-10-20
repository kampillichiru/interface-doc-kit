"""The context pack of one unit: only what its agent needs, so the agent does not read the whole inventory.

`doc.py context F01` for a flow: its entry point, the methods and SQL it reaches, its settings, its decision lines
and the code values compared there, with their meanings from the input folder.
`doc.py context O01-P2` for part of an output: its fields from the spec, the flows that write it with their rule
titles, and the writer lines the scan found in the code those flows reach.
"""

import re
from typing import List

from . import coverage, links, markdown, scan, spec, terms
from .discovery import Discovery
from .plan import Plan
from .project import Paths

_RANGE = re.compile(r"^(.*):(\d+)-(\d+)$")


def _files(found: List[scan.Reach]) -> set:
    files = set()
    for reach in found:
        for method in reach.methods + [f"{reach.method} {reach.where}"]:
            where = _RANGE.match(method.rsplit(" ", 1)[-1])
            if where:
                files.add(where.group(1))
    return files


def _meanings(paths: Paths, values: List[str]) -> List[str]:
    known = terms.defined(paths.input)
    return [f"- {v}: {known[v.lower()].meaning} ({known[v.lower()].source})" if v.lower() in known
            else f"- {v}: no meaning in the input folder (ask)" for v in values]


def flow(paths: Paths, discovery: Discovery, unit_id: str) -> str:
    item = next((f for f in discovery.flows if f.id == unit_id), None)
    if item is None:
        return f"{unit_id} is not a flow of discovery.md."
    inventory = scan.load(paths)
    text = paths.unit_file(unit_id).read_text(encoding="utf-8") if paths.unit_file(unit_id).exists() else ""
    found = coverage.reaches(paths, discovery, unit_id, text)
    out = [f"# Context of {unit_id}: {item.title}", "",
           f"Trigger: {item.trigger}. Entry point: {item.entry_point}. Varies by: {item.varies_by or '-'}. "
           f"Outputs: {item.outputs or '-'}.", "",
           "Read the code at these places. The list follows calls by name and type; calls through interfaces, "
           "reflection or configuration may be missing, so follow the code where it stops.", ""]
    sql_ids = []
    for reach in found:
        out += [f"## {reach.entry} {reach.method} ({reach.where})", ""]
        out += [f"- {m}" for m in reach.methods]
        out.append("")
        sql_ids += [q for q in reach.sql if q not in sql_ids]
    if sql_ids:
        out += ["## SQL", ""]
        for q in sql_ids:
            hit = inventory.sql[int(q[1:]) - 1]
            out.append(f"- {q} {hit.file}:{hit.line}: {hit.value or hit.text}")
        out.append("")
    files = _files(found)
    settings = [s for s in inventory.settings if s.file in files or s.kind == "setting"]
    if settings:
        out += ["## Settings", ""] + [f"- {s.file}:{s.line} `{s.text}`" for s in settings] + [""]
    out += [coverage.report(paths, discovery, unit_id), ""]
    values = [v.value for v in coverage.code_values(paths, found)]
    if values:
        out += ["## Meanings of the code values", ""] + _meanings(paths, values)
    return "\n".join(out) + "\n"


def output(paths: Paths, discovery: Discovery, plan: Plan, unit_id: str) -> str:
    unit = plan.unit(unit_id)
    if unit is None or unit.kind != "output":
        return f"{unit_id} is not an output unit of the plan."
    item = next(o for o in discovery.outputs if o.id == unit.output_id)
    fields = unit.fields(spec.load(paths.input / item.spec))
    out = [f"# Context of {unit_id}: {item.title}, fields {unit.first_field}-{unit.last_field}", "",
           f"Kind: {item.kind}. Written at: {item.written_at}. Specification: {item.spec}.", "",
           "## Fields of this unit", "", "| NN | Record | Field | Positions | Length | Type | Description |",
           "|---|---|---|---|---|---|---|"]
    out += [f"| {f.number:02d} | {f.record or '-'} | {f.name} | {f.positions or '-'} | {f.length or '-'} | "
            f"{f.type or '-'} | {f.description} |" for f in fields]
    writers = [f for f in discovery.flows if item.id in (f.outputs or "")]
    rules = links.flow_rules(paths.out / "flows")
    others = [f for f in discovery.flows if f not in writers and discovery.in_scope(f.id)]
    out += ["", "## Business rules", "",
            "Name the rule that decides each value in the column `Business rule`. The flows that write this output "
            "come first; a value can come from an earlier flow through an intermediate file or table.", ""]
    for f in writers + others:
        role = "writes it" if f in writers else "earlier or other flow"
        out.append(f"- {f.id} {f.title} ({role}): "
                   + "; ".join(f"{r.id} {r.title}" for r in rules.values() if r.flow == f.id))
    inventory = scan.load(paths)
    files = set()
    for f in writers:
        files |= _files(coverage.reaches(paths, discovery, f.id))
    hits = [h for h in inventory.outputs if h.file in files and h.kind != "console"]
    if hits:
        out += ["", "## Where the code writes (start each field here)", ""]
        out += [f"- {h.kind} {h.file}:{h.line} `{h.text}`" for h in hits]
    return "\n".join(out) + "\n"


def report(paths: Paths, discovery: Discovery, plan: Plan, unit_id: str) -> str:
    if re.fullmatch(r"F\d{2}", unit_id):
        return flow(paths, discovery, unit_id)
    return output(paths, discovery, plan, unit_id)
