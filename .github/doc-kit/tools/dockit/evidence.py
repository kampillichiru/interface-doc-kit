"""Checks that a quoted piece of code really is at the cited lines."""

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

_REF = re.compile(r"^\s*(?P<path>[^:]+?)\s*:\s*(?P<start>\d+)(?:\s*[-–]\s*(?P<end>\d+))?\s*$")
_NEARBY = 5


@lru_cache(maxsize=None)
def _lines(path: Path) -> Tuple[str, ...]:
    return tuple(path.read_text(encoding="utf-8", errors="replace").splitlines())


@lru_cache(maxsize=None)
def _all_files(roots: Tuple[Path, ...]) -> Tuple[Path, ...]:
    unique = {p.resolve() for root in roots if root.exists() for p in root.rglob("*") if p.is_file()}
    return tuple(sorted(unique))


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def resolve(path_text: str, roots: Tuple[Path, ...]) -> Tuple[Optional[Path], Optional[str]]:
    """The source file a citation means: a path under one of the roots, or a unique path ending."""
    path_text = path_text.strip().strip("`").replace("\\", "/")
    for root in roots:
        candidate = root / path_text
        if candidate.is_file():
            return candidate, None
    matches = [p for p in _all_files(roots) if p.as_posix().endswith("/" + path_text)]
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"file `{path_text}` not found in the source folders"
    return None, f"file `{path_text}` is ambiguous ({len(matches)} files end like this); give more of the path"


def check(reference: str, code_cell: str, roots: Tuple[Path, ...]) -> List[str]:
    """Problems with one evidence row; empty when every quote is at the cited lines."""
    match = _REF.match(reference.strip().strip("`"))
    if not match:
        return [f"`{reference}` is not a citation like `path/File.java:12` or `path/File.java:12-15`"]
    path, problem = resolve(match.group("path"), roots)
    if problem:
        return [problem]
    lines = _lines(path)
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if not 1 <= start <= end <= len(lines):
        return [f"`{reference}`: lines {start}-{end} do not exist ({path.name} has {len(lines)} lines)"]
    quotes = [q for q in (code_cell and re.findall(r"`([^`]+)`", code_cell)) or [] if q.strip()]
    if not quotes:
        return [f"`{reference}`: the Code cell has no `quoted` code"]
    cited = _squash(" ".join(lines[start - 1:end]))
    problems = []
    for quote in quotes:
        if _squash(quote) in cited:
            continue
        hint = _find_near(lines, quote, start, end)
        problems.append(f"`{reference}`: `{quote}` is not on those lines" + (f"; it is on line {hint}" if hint else ""))
    return problems


def _find_near(lines: Tuple[str, ...], quote: str, start: int, end: int) -> Optional[int]:
    wanted = _squash(quote)
    for number in range(max(1, start - _NEARBY), min(len(lines), end + _NEARBY) + 1):
        if wanted in _squash(lines[number - 1]):
            return number
    return None
