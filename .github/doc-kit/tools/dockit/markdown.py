"""Reading the Markdown the agents write: headings, sections, pipe tables, labelled lines."""

import re
from typing import Dict, List, Optional, Tuple

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")

Row = Dict[str, str]


def headings(text: str) -> List[Tuple[int, int, str]]:
    """(line index, level, title) of every heading outside code blocks."""
    found, in_code = [], False
    for i, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        match = None if in_code else _HEADING.match(line)
        if match:
            found.append((i, len(match.group(1)), match.group(2)))
    return found


def _norm(title: str) -> str:
    return re.sub(r"^[\d.\s]+", "", title).strip().lower()


def section(text: str, title: str) -> Optional[str]:
    """Body of the first heading whose title starts with `title` (numbering ignored), up to the
    next heading of the same or a higher level. None when the heading does not exist."""
    lines = text.splitlines()
    marks = headings(text)
    wanted = _norm(title)
    for n, (index, level, heading) in enumerate(marks):
        if _norm(heading).startswith(wanted):
            end = next((i for i, lvl, _ in marks[n + 1:] if lvl <= level), len(lines))
            return "\n".join(lines[index + 1:end])
    return None


def sections(text: str, level: int) -> List[Tuple[str, str]]:
    """(title, body) of every heading of exactly `level`; a body ends at the next heading of that
    level or higher."""
    lines = text.splitlines()
    marks = headings(text)
    result = []
    for n, (index, lvl, title) in enumerate(marks):
        if lvl != level:
            continue
        end = next((i for i, l, _ in marks[n + 1:] if l <= level), len(lines))
        result.append((title, "\n".join(lines[index + 1:end])))
    return result


def split_row(line: str) -> List[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip().replace("\\|", "|") for cell in _CELL_SPLIT.split(body)]


def tables(text: str) -> List[List[Row]]:
    """Every pipe table in `text`, as rows keyed by the header cells."""
    found, lines, i = [], text.splitlines(), 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and _SEPARATOR.match(lines[i + 1]):
            header = split_row(lines[i])
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                cells += [""] * (len(header) - len(cells))
                rows.append(dict(zip(header, cells)))
                i += 1
            found.append(rows)
        else:
            i += 1
    return found


def first_table(text: Optional[str]) -> List[Row]:
    found = tables(text or "")
    return found[0] if found else []


def labelled(text: str, label: str) -> Optional[str]:
    """Value of a line such as `**Kind:** Variant by event` or `- **Rule:** ...`."""
    match = re.search(r"^\s*-?\s*\*\*" + re.escape(label) + r":\*\*\s*(.*)$", text, re.M | re.I)
    return match.group(1).strip() if match else None


def backticked(cell: str) -> List[str]:
    """The `code` parts of a cell, in order."""
    return re.findall(r"`([^`]*)`", cell)


def words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def strip_sections(text: str, titles: List[str]) -> str:
    """`text` without the sections whose titles start with any of `titles`."""
    lines = text.splitlines()
    marks = headings(text)
    drop = set()
    for n, (index, level, heading) in enumerate(marks):
        if any(_norm(heading).startswith(_norm(t)) for t in titles):
            end = next((i for i, lvl, _ in marks[n + 1:] if lvl <= level), len(lines))
            drop.update(range(index, end))
    return "\n".join(line for i, line in enumerate(lines) if i not in drop).strip()
