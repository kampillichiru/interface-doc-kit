"""Questions for the SME: each one asked once. Two questions are the same when they share most of their
words, or name the same rule or field ids."""

import re
from typing import Iterable, List, Set, Tuple

from . import markdown

SECTION = "Questions for the SME"
_IDS = re.compile(r"\b(F\d{2}-BR\d{2}|F\d{2}-SC\d+|O\d{2}-\d{2}(?:-R\d+)?)\b")
_STOP = set("""a an and are as at be been by can do does for from has have how in is it its of on or should that the
their them then there these this those to was what when where which who why will with would""".split())
SAME = 0.75  # share of the shorter question's words that the other must also have
NEAR = 0.8  # share of all the words of both: the same question in nearly the same words


def words(text: str) -> Set[str]:
    found = set()
    for word in re.findall(r"[a-z][a-z0-9-]+", text.lower()):
        if word in _STOP or len(word) < 3:
            continue
        found.add(word[:-1] if word.endswith("s") and len(word) > 4 else word)
    return found


def score(a: str, b: str) -> tuple:
    """How alike two questions are: (share of the shorter one's words in both, share of all words in both),
    or (0, 0) when they do not ask the same thing."""
    ids_a, ids_b = set(_IDS.findall(a)), set(_IDS.findall(b))
    wa, wb = words(_IDS.sub("", a)), words(_IDS.sub("", b))
    if not wa or not wb:
        return (0, 0)
    common = len(wa & wb)
    overlap, jaccard = common / min(len(wa), len(wb)), common / len(wa | wb)
    alike = (common >= 3 and overlap >= SAME) or (bool(ids_a & ids_b) and common >= 2 and overlap >= SAME) \
        or jaccard >= NEAR
    return (overlap, jaccard) if alike else (0, 0)


def same(a: str, b: str) -> bool:
    """True when two questions ask the same thing."""
    return score(a, b) > (0, 0)


def of(text: str) -> List[Tuple[str, str]]:
    """The (question, what the system does today) rows of a unit file."""
    rows = markdown.first_table(markdown.section(text, SECTION))
    return [(r.get("Question", "").strip(), r.get("What the system does today", "").strip()) for r in rows
            if r.get("Question", "").strip() and r.get("Question", "").strip().lower() not in ("none", "none.")]


def merge(asked: Iterable[Tuple[str, str, str]]) -> List[Tuple[str, str, List[str]]]:
    """(question, today, source) in the order asked → one row per question, with every part that asked it.
    The first wording is kept: the flows come first and are closest to the code."""
    merged: List[Tuple[str, str, List[str]]] = []
    for question, today, source in asked:
        best = max(merged, key=lambda m: score(m[0], question), default=None)
        found = best if best and same(best[0], question) else None
        if found:
            if source not in found[2]:
                found[2].append(source)
        else:
            merged.append((question, today, [source]))
    return merged
