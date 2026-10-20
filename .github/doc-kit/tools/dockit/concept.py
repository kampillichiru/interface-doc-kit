"""Intent cards from `doc-input/concepts/`: what the business team expects a business concept to do.

A card is the business intention, written before the run. The documentation of a concept answers each of its
lines with what the system really does, so the reader sees at once where the code and the business agree.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from . import markdown

INTENT_ID = re.compile(r"^I\d+$")


@dataclass(frozen=True)
class Card:
    file: str  # path relative to the input folder, for example concepts/refund.md
    title: str
    intents: List[Tuple[str, str]]  # (I1, what the business expects)

    @property
    def ids(self) -> List[str]:
        return [i for i, _ in self.intents]


def load(path: Path, input_dir: Path) -> Card:
    text = path.read_text(encoding="utf-8")
    title = next((t for _, level, t in markdown.headings(text) if level == 1), path.stem)
    title = re.sub(r"^\s*Concept\s*:\s*", "", title, flags=re.I).strip()
    rows = markdown.first_table(markdown.section(text, "What the business expects"))
    intents = [(r.get("#", "").strip(), r.get("The business expects", "").strip()) for r in rows]
    return Card(path.relative_to(input_dir).as_posix(), title, [i for i in intents if i[0]])


def load_all(input_dir: Path) -> List[Card]:
    folder = input_dir / "concepts"
    if not folder.exists():
        return []
    return [load(p, input_dir) for p in sorted(folder.glob("*.md")) if p.name.lower() != "readme.md"]


def problems(card: Card) -> List[str]:
    """Problems in a card itself; only a person can fix them, so the run stops on them."""
    if not card.intents:
        return [f"{card.file}: the table under `## What the business expects` has no rows."]
    found = [f"{card.file}: `{i}` must look like I1." for i in card.ids if not INTENT_ID.match(i)]
    found += [f"{card.file}: {i} is used twice." for i in sorted({i for i in card.ids if card.ids.count(i) > 1})]
    return found
