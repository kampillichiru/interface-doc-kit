"""The links between business rules (flows) and fields (outputs).

Each requirement of a field names, in its column `Business rule`, the flow rule it carries out (F01-BR05), or
`format` when it only lays the value out (padding, cutting, date or number format). From these links the tool
checks that no rule and no field is left unexplained, and the document shows the rule-to-field map.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import markdown, spec

RULE_ID = re.compile(r"\bF\d{2}-BR\d{2}\b")
RULE_COLUMN = "Business rule"
FORMAT = "format"
NONE = "none"
_WRITES = re.compile(r"\(output (O\d{2})\)")


@dataclass
class Rule:
    id: str
    title: str
    flow: str
    writes: List[str]  # output ids the rule says it writes: "Writes REFUND_TXN (output O01)"


@dataclass
class FieldLink:
    output_id: str
    number: int
    name: str
    rules: List[str] = field(default_factory=list)  # in the order the requirements name them
    format_only: bool = False  # every requirement is layout only
    unlinked: List[str] = field(default_factory=list)  # requirement ids marked `none`

    @property
    def anchor(self) -> str:
        return f"{self.output_id}-{self.number:02d}".lower()


def flow_rules(flows_dir: Path) -> Dict[str, Rule]:
    """Every business rule written in the flow files, by id, in flow and rule order."""
    rules: Dict[str, Rule] = {}
    for path in sorted(flows_dir.glob("F*.md")):
        text = path.read_text(encoding="utf-8")
        for title, body in markdown.sections(markdown.section(text, "Business rules") or "", 3):
            rule_id, _, name = title.partition(".")
            rule_id = rule_id.strip()
            if RULE_ID.fullmatch(rule_id):
                rules[rule_id] = Rule(rule_id, name.strip(), path.stem, _WRITES.findall(body))
    return rules


def cell_rules(cell: str) -> Tuple[List[str], str]:
    """The rule ids of a `Business rule` cell, and its marker: 'rules', 'format', 'none' or '' (empty)."""
    ids = RULE_ID.findall(cell)
    if ids:
        return ids, "rules"
    word = cell.strip().strip("`").lower()
    return [], word if word in (FORMAT, NONE) else ""


def field_link(output_id: str, number: int, name: str, rows: List[markdown.Row]) -> FieldLink:
    link = FieldLink(output_id, number, name)
    markers = []
    for row in rows:
        ids, marker = cell_rules(row.get(RULE_COLUMN, ""))
        markers.append(marker)
        link.rules += [i for i in ids if i not in link.rules]
        if marker == NONE:
            link.unlinked.append(row.get("ID", "").strip())
    link.format_only = bool(markers) and all(m == FORMAT for m in markers)
    return link


def output_fields(text: str, output_id: str, fields: List[spec.Field]) -> Dict[int, FieldLink]:
    """The links of every field section in one output unit file."""
    names = {f.number: f.name for f in fields}
    found = {}
    for title, body in markdown.sections(text, 2):
        number = title.split(".")[0].strip()
        if number.isdigit() and int(number) in names:
            rows = markdown.first_table(markdown.section(body, "Requirements"))
            found[int(number)] = field_link(output_id, int(number), names[int(number)], rows)
    return found


def has_column(text: str) -> bool:
    """True when the output file was written with the `Business rule` column (older runs were not)."""
    for _, body in markdown.sections(text, 2):
        rows = markdown.first_table(markdown.section(body, "Requirements"))
        if rows:
            return RULE_COLUMN in rows[0]
    return False


def by_rule(fields: List[FieldLink]) -> Dict[str, List[FieldLink]]:
    found: Dict[str, List[FieldLink]] = {}
    for f in fields:
        for rule_id in f.rules:
            found.setdefault(rule_id, []).append(f)
    return found


def unlinked_rules(rules: Dict[str, Rule], output_id: str, fields: List[FieldLink]) -> List[Rule]:
    """Rules that say they write this output but that no field names."""
    named = set(by_rule(fields))
    return [r for r in rules.values() if output_id in r.writes and r.id not in named]


def title_of(rules: Dict[str, Rule], rule_id: str) -> Optional[str]:
    rule = rules.get(rule_id)
    return rule.title if rule else None
