"""Finds the parts of the finished document that answer a question, so an answer is built from checked text only.

Used by the Copilot skill ask-the-docs: `doc.py lookup <ids, field names or words>`. The same question always
gives the same parts, in the same order.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import markdown

MAX_PARTS = 5
MAX_LINES = 60
_ANCHOR = re.compile(r'^<a id="([^"]+)"></a>\s*$')
_RULE = re.compile(r"^F\d{2}-BR\d{2}$")
_SCENARIO = re.compile(r"^(F\d{2})-SC\d+$")
_REQUIREMENT = re.compile(r"^(O\d{2}-\d{2})(?:-R\d+)?$")
_UNIT = re.compile(r"^[FOC]\d{2}$")
_INTENT = re.compile(r"^(C\d{2})-(I\d+|A\d+)$")
_FIELD = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")
_OWNER = re.compile(r"^(\d{2}\. [A-Z]|F\d{2}-BR\d{2}\.)")  # a field or a business rule
_STOP = set("""a an and are as at be by can do does for from has have how i if in is it its of on or the this that to
was what when where which who why will with each every system field fields value values derived derive explain
tell me about show please""".split())
_CUT = "(cut: open the document at this line for the rest)"


@dataclass
class Part:
    title: str  # the heading, with the headings above it
    line: int  # 1-based line of the heading in the document
    level: int
    lines: List[str]  # its own text, up to the next heading of any level
    full: List[str]  # its text with everything under it
    parent: int = -1  # index of the part it sits in
    anchor: str = ""

    @property
    def heading(self) -> str:
        return self.title.split(" > ")[-1]


def parts(text: str) -> List[Part]:
    """Every heading below the title, with its own text and its full section."""
    lines = text.splitlines()
    marks = markdown.headings(text)
    found: List[Part] = []
    stack: List[int] = []  # indexes of the open parts, outermost first
    for n, (index, level, title) in enumerate(marks):
        if level == 1:
            continue
        while stack and found[stack[-1]].level >= level:
            stack.pop()
        nxt = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        end = next((i for i, lvl, _ in marks[n + 1:] if lvl <= level), len(lines))
        before = lines[index - 2].strip() if index >= 2 else ""
        match = _ANCHOR.match(before)
        path = " > ".join([found[i].heading for i in stack] + [title])
        found.append(Part(path, index + 1, level, _trim(lines[index + 1:nxt]), _trim(lines[index + 1:end]),
                          stack[-1] if stack else -1, match.group(1) if match else ""))
        stack.append(len(found) - 1)
    return found


def _trim(body: List[str]) -> List[str]:
    body = list(body)
    while body and (not body[-1].strip() or _ANCHOR.match(body[-1])):
        body.pop()
    return body


def _owner(all_parts: List[Part], n: int) -> int:
    """The field or rule a part belongs to, so an answer gets the whole of it; else the part itself."""
    i = n
    while i >= 0:
        if _OWNER.match(all_parts[i].heading):
            return i
        i = all_parts[i].parent
    return n


def _words(terms: List[str]) -> List[str]:
    return [w for t in terms for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in _STOP and len(w) > 2]


def find(text: str, terms: List[str]) -> List[Tuple[Part, Optional[str]]]:
    """(part, row) for ids and field names first, exactly; then the best matches for the words. `row` keeps
    only that row of the part's table."""
    all_parts = parts(text)
    chosen: List[Tuple[Part, Optional[str]]] = []

    def add(part: Part, row: Optional[str] = None):
        if all(part is not c for c, _ in chosen):
            chosen.append((part, row))

    rest = []
    for term in terms:
        term = term.strip(" ,.;:?!`\"'()")
        exact = _exact(all_parts, term) if term else []
        for part, row in exact:
            add(part, row)
        if not exact:
            rest.append(term)
    words = _words(rest)
    if words:
        for n in _ranked(all_parts, words):
            if len(chosen) >= MAX_PARTS:
                break
            add(all_parts[_owner(all_parts, n)])
    return chosen


def _exact(all_parts: List[Part], term: str) -> List[Tuple[Part, Optional[str]]]:
    upper = term.upper()
    by_anchor: Dict[str, Part] = {p.anchor: p for p in all_parts if p.anchor}
    if _RULE.match(upper) or _UNIT.match(upper):
        if upper.lower() in by_anchor:
            return [(by_anchor[upper.lower()], None)]
        return [(p, None) for p in all_parts if p.heading.upper().startswith(upper + ".")][:1]
    match = _SCENARIO.match(upper)
    if match:  # the scenarios table of that flow, only that row
        flows = {i for i, p in enumerate(all_parts) if p.heading.upper().startswith(match.group(1) + ".")}
        table = next((p for p in all_parts if p.parent in flows and p.heading.lower().startswith("scenarios")), None)
        return [(table, upper)] if table else []
    match = _REQUIREMENT.match(upper)
    if match:
        part = by_anchor.get(match.group(1).lower())
        return [(part, None)] if part else []
    match = _INTENT.match(upper)
    if match:  # one line of an intent card, in the concept's tables
        concepts = [i for i, p in enumerate(all_parts) if p.heading.upper().startswith(match.group(1) + ".")]
        line = _row(match.group(2))
        hit = [p for p in all_parts if any(_within(all_parts, p, c) for c in concepts)
               and any(line.match(row.strip()) for row in p.lines)]
        return [(hit[0], match.group(2).upper())] if hit else []
    if _FIELD.match(term):
        return [(p, None) for p in all_parts
                if _OWNER.match(p.heading) and re.search(r"\b" + re.escape(term) + r"\b", p.heading)]
    return []


def _row(row_id: str):
    """A table row whose first cell is the id, plain or as a link: `| I3 |` or `| [F01-SC3](#f01) |`."""
    return re.compile(r"^\|\s*\[?" + re.escape(row_id) + r"\]?(\([^)]*\))?\s*\|", re.I)


def _within(all_parts: List[Part], part: Part, ancestor: int) -> bool:
    i = part.parent
    while i >= 0:
        if i == ancestor:
            return True
        i = all_parts[i].parent
    return False


def _ranked(all_parts: List[Part], words: List[str]) -> List[int]:
    scored: List[Tuple[int, int, int]] = []
    for n, part in enumerate(all_parts):
        title, body = part.title.lower(), "\n".join(part.lines).lower()
        hits = [w for w in set(words) if w in title or w in body]
        if not hits:
            continue
        score = 10 * len(hits) + sum(3 for w in hits if w in title) + sum(min(body.count(w), 5) for w in hits)
        scored.append((-score, part.line, n))
    return [n for _, _, n in sorted(scored)]


def render(part: Part, words: List[str], row: Optional[str] = None) -> str:
    """The whole section; a long one keeps its table headers and only the rows that mention the words."""
    lines = part.lines if row else part.full
    if row:  # one row of a table: its header and that row
        table = [line for line in lines if line.strip().startswith("|")]
        pattern = _row(row)
        lines = table[:2] + [line for line in table[2:] if pattern.match(line.strip())]
    elif len(lines) > MAX_LINES and words:
        kept, header = [], 0
        for line in lines:
            is_row = line.strip().startswith("|")
            if is_row and header < 2:
                kept.append(line)
                header += 1
            elif is_row:
                if any(w in line.lower() for w in words):
                    kept.append(line)
            else:
                header = 0
                if line.startswith("#") or any(w in line.lower() for w in words):
                    kept.append(line)
        lines = kept[:MAX_LINES] + ([_CUT] if len(kept) > MAX_LINES else [])
    elif len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + [_CUT]
    return f"### {part.title} (line {part.line})\n" + "\n".join(lines).strip()


def status(text: str) -> str:
    draft = re.search(r"^> \*\*Draft\.\*\*\s*(.*)$", text, re.M)
    if draft:
        return f"DRAFT. {draft.group(1)} Say so when the answer rests on those parts."
    return "FINAL. Every part passed the second reader (and the data check where there is one)."


def answer_material(text: str, terms: List[str]) -> str:
    found = find(text, terms)
    if not found:
        return ("Nothing in the document matches. Answer: not in the checked documentation. Suggest a line for an "
                "intent card in doc-input/concepts/, or a question for the SME.")
    words = _words(terms)
    return "\n\n".join(render(part, words, row) for part, row in found)
