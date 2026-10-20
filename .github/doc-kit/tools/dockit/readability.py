"""How easy the documentation is to read: the newcomer reader's verdict, and simple measures of the text.

The reader is an agent that knows nothing of the domain and reads one unit with only the glossary at hand. It
lists every point it cannot follow. The tool counts those points at each reading and measures the sentences, so
the document can say how easy it is to read, not only claim it.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import markdown

LONG_SENTENCE = 25  # words
VERDICT = re.compile(r"\*\*Verdict:\*\*\s*(CLEAR|UNCLEAR)", re.I)
UNCLEAR_SECTION = "Unclear points"


@dataclass(frozen=True)
class Reading:
    verdict: Optional[str]  # CLEAR, UNCLEAR, or None when the file has no verdict
    points: List[markdown.Row]


def reading(path: Path) -> Optional[Reading]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    found = VERDICT.search(text)
    rows = [r for r in markdown.first_table(markdown.section(text, UNCLEAR_SECTION))
            if any(v.strip() and v.strip().lower() not in ("none", "none.", "-") for k, v in r.items() if k != "#")]
    return Reading(found.group(1).upper() if found else None, rows)


@dataclass(frozen=True)
class Measures:
    sentences: int
    average_words: float
    long_sentences: int


def measure(prose: str) -> Measures:
    """Sentences of the business text: each table cell and each sentence of a line counts as one."""
    sentences = []
    for line in prose.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "<a id=", "```")) or re.fullmatch(r"\|?[-:| ]+\|?", line):
            continue
        cells = markdown.split_row(line) if line.startswith("|") else [line]
        for cell in cells:
            cell = re.sub(r"`[^`]*`", "x", re.sub(r"\*\*[^*]+:\*\*", "", cell))
            sentences += [s for s in re.split(r"(?<=[.!?])\s+", cell) if markdown.words(s) >= 3]
    counts = [markdown.words(s) for s in sentences]
    return Measures(len(counts), round(sum(counts) / len(counts), 1) if counts else 0.0,
                    sum(1 for c in counts if c > LONG_SENTENCE))
