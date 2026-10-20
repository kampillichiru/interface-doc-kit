"""What a flow must cover: every decision line the scan found in the code the flow reaches, and every code
value the code compares with there. Nothing the code decides may be left out of a flow silently."""

import re
from dataclasses import dataclass
from typing import List, Set, Tuple

from . import evidence, markdown, scan
from .discovery import Discovery
from .project import Paths

NOT_IN_RULE = "Decision lines not in a rule"
NOT_FOLLOWED = "Calls not followed by the tool"
MAX_COVER_LINES = 15  # a citation wider than this does not count as covering the lines inside it
_REF = re.compile(r"^\s*(?P<path>[^:]+?)\s*:\s*(?P<start>\d+)(?:\s*[-–]\s*(?P<end>\d+))?\s*$")
_RANGE = re.compile(r"(\S+):(\d+)-(\d+)$")
_LOCATION = re.compile(r"^(\S+):(\d+) (.*)$")


@dataclass(frozen=True)
class Condition:
    file: str  # as the inventory writes it: relative to the workspace
    line: int
    code: str

    @property
    def ref(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class CodeValue:
    value: str
    file: str
    line: int


def reaches(paths: Paths, discovery: Discovery, unit_id: str, flow_text: str = "") -> List[scan.Reach]:
    """The scan's reach of every entry point of the flow: from its row in discovery.md and its file."""
    if not paths.inventory_json.exists():
        return []
    inventory = scan.load(paths)
    item = next((f for f in discovery.flows if f.id == unit_id), None)
    refs = re.split(r"[;,]|<br>", item.entry_point if item else "")
    refs += re.split(r"[;,]|<br>", markdown.labelled(flow_text, "Entry point") or "")
    roots = tuple(paths.sources)
    found: List[scan.Reach] = []
    for ref in (r.strip().strip("`") for r in refs):
        match = _REF.match(ref)
        if not match:
            continue
        path, _ = evidence.resolve(match.group("path"), roots)
        if path is None:
            continue
        line = int(match.group("start"))
        for reach in inventory.reach:
            where = _RANGE.match(reach.where)
            if where and where.group(1) == paths.rel(path) \
                    and int(where.group(2)) - 6 <= line <= int(where.group(3)) and reach not in found:
                found.append(reach)
    return found


def conditions(found: List[scan.Reach]) -> List[Condition]:
    result: List[Condition] = []
    for reach in found:
        for text in reach.conditions:
            match = _LOCATION.match(text)
            if match:
                condition = Condition(match.group(1), int(match.group(2)), match.group(3))
                if condition not in result:
                    result.append(condition)
    return result


def code_values(paths: Paths, found: List[scan.Reach]) -> List[CodeValue]:
    """Codes the reached code compares with or writes in SQL (`"GOLD".equals`, `STATUS = 'CANCELLED'`)."""
    if not found:
        return []
    inventory = scan.load(paths)
    ranges = []
    for reach in found:
        for method in reach.methods + [f"{reach.method} {reach.where}"]:
            where = _RANGE.match(method.rsplit(" ", 1)[-1])
            if where:
                ranges.append((where.group(1), int(where.group(2)), int(where.group(3))))
        for q in reach.sql:
            hit = inventory.sql[int(q[1:]) - 1]
            lines = re.search(r"; lines (\d+)-(\d+);", hit.text)
            if lines:
                ranges.append((hit.file, int(lines.group(1)), int(lines.group(2))))
    result: List[CodeValue] = []
    seen: Set[str] = set()
    for hit in inventory.comparisons:
        if not any(hit.file == f and start <= hit.line <= end for f, start, end in ranges):
            continue
        for value in _values(hit):
            if value not in seen:
                seen.add(value)
                result.append(CodeValue(value, hit.file, hit.line))
    return result


def _values(hit: scan.Hit) -> List[str]:
    """The code words of a comparison; numbers are left to the condition check."""
    value = hit.value.strip()
    if hit.kind == "constant":
        value = value.split(" (", 1)[0].strip().strip("\"'")
        words = [value]
    elif hit.kind == "enum":
        words = [value.split(".")[-1]]
    elif "'" in value:
        words = re.findall(r"'([^']+)'", value)
    else:
        words = [value.strip("'")]
    return [w for w in words if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,29}", w)]


def covered(rows: List[markdown.Row], paths: Paths) -> Set[Tuple[str, int]]:
    """(file, line) of every line a citation covers; a citation over MAX_COVER_LINES lines covers nothing."""
    roots, lines = tuple(paths.sources), set()
    for row in rows:
        match = _REF.match(row.get("File:line", "").strip().strip("`"))
        if not match:
            continue
        path, _ = evidence.resolve(match.group("path"), roots)
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if path is None or end - start + 1 > MAX_COVER_LINES:
            continue
        lines.update((paths.rel(path), n) for n in range(start, end + 1))
    return lines


def missing_conditions(text: str, paths: Paths, found: List[scan.Reach]) -> List[Condition]:
    rows = markdown.first_table(markdown.section(text, "Evidence"))
    rows += markdown.first_table(markdown.section(text, NOT_IN_RULE))
    cited = covered(rows, paths)
    return [c for c in conditions(found) if (c.file, c.line) not in cited]


def unfollowed(found: List[scan.Reach]) -> List[Condition]:
    """Calls the scan could not follow in the code a flow reaches: an interface, a parent class, reflection."""
    result = []
    for reach in found:
        for item in reach.unfollowed:
            match = _LOCATION.match(item)
            if match:
                result.append(Condition(match.group(1), int(match.group(2)), match.group(3)))
    return list(dict.fromkeys(result))


def missing_calls(text: str, paths: Paths, found: List[scan.Reach]) -> List[Condition]:
    """Calls not followed by the tool that the flow neither cites in its Evidence (it followed them itself) nor
    lists under NOT_FOLLOWED with where they lead."""
    rows = markdown.first_table(markdown.section(text, "Evidence"))
    rows += markdown.first_table(markdown.section(text, NOT_FOLLOWED))
    cited = covered(rows, paths)
    return [c for c in unfollowed(found) if (c.file, c.line) not in cited]


def report(paths: Paths, discovery: Discovery, unit_id: str) -> str:
    """For `doc.py conditions F01`: every decision line of the flow, and whether the flow file covers it."""
    path = paths.unit_file(unit_id)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    found = reaches(paths, discovery, unit_id, text)
    if not found:
        return (f"{unit_id}: no entry point of the inventory matches its Entry point in discovery.md, so there is "
                "no list. Follow the code from the entry point yourself.")
    missing = set(missing_conditions(text, paths, found)) if text else set()
    every = conditions(found)
    out = [f"# Decision lines of {unit_id}", "",
           f"{len(every)} lines in the code this flow reaches ({', '.join(r.entry for r in found)}). Cite each one in "
           f"the Evidence of a rule (a citation of at most {MAX_COVER_LINES} lines), or list it under "
           f"`## {NOT_IN_RULE}` with the reason.", "", "| Covered | File:line | Code |", "|---|---|---|"]
    out += [f"| {'no' if c in missing or not text else 'yes'} | {c.ref} | `{c.code.replace('|', '¦')}` |"
            for c in every]
    calls = unfollowed(found)
    if calls:
        open_calls = set(missing_calls(text, paths, found)) if text else set(calls)
        out += ["", f"# Calls the tool could not follow ({len(calls)})", "",
                "An interface, a parent class or reflection: read where each one leads. Follow it and cite the code "
                f"it reaches in a rule, or list it under `## {NOT_FOLLOWED}` with where it leads.", "",
                "| Accounted for | File:line | Code |", "|---|---|---|"]
        out += [f"| {'no' if c in open_calls else 'yes'} | {c.ref} | `{c.code.replace('|', '¦')}` |" for c in calls]
    values = code_values(paths, found)
    if values:
        out += ["", "Code values compared or written here (each one needs a rule or scenario that says what "
                "happens for it): " + ", ".join(f"{v.value} ({v.file}:{v.line})" for v in values)]
    return "\n".join(out)
