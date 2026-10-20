"""Output specifications from `doc-input/outputs/*.csv`: one row per field."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Field:
    number: int
    name: str
    start: Optional[int]
    end: Optional[int]
    length: Optional[int]
    type: str
    description: str
    record: str = ""  # the record type code a line of this layout starts with (H, D, T); empty for one layout

    @property
    def label(self) -> str:
        """The name, with its record type when the file has several (`D AMOUNT`)."""
        return f"{self.record} {self.name}" if self.record else self.name

    @property
    def positions(self) -> str:
        if self.start is None:
            return ""
        return f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"


def _int(value: str) -> Optional[int]:
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def load(path: Path) -> List[Field]:
    """Columns: field, start, end, length, type, description, record. Only `field` is required; without
    positions the output is documented field by field without the position checks. `record` is for a file with
    several record layouts (header, detail, trailer): the code each line of that layout starts with."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(handle)]
    fields = []
    for n, row in enumerate((r for r in rows if r.get("field")), 1):
        start, end, length = _int(row.get("start")), _int(row.get("end")), _int(row.get("length"))
        if start is not None and end is None and length:
            end = start + length - 1
        if length is None and start is not None and end is not None:
            length = end - start + 1
        fields.append(Field(n, row["field"], start, end, length, row.get("type", ""), row.get("description", ""),
                            row.get("record", "")))
    return fields


def records(fields: List[Field]) -> List[str]:
    """The record type codes of the spec, in spec order; empty for a file with one layout."""
    return list(dict.fromkeys(f.record for f in fields if f.record))


def layout(line: str, fields: List[Field]) -> List[Field]:
    """The fields that apply to one line: those of the record type the line starts with (the longest code that
    matches), or every field when the spec has one layout. No fields when the line matches no record type."""
    codes = records(fields)
    if not codes:
        return fields
    code = max((c for c in codes if line.startswith(c)), key=len, default=None)
    return [f for f in fields if f.record == code] if code is not None else []


def problems(fields: List[Field]) -> List[str]:
    """Gaps and overlaps in a positional spec."""
    found, previous = [], None
    if records(fields) and any(not f.record for f in fields):
        found.append("the record column is filled for some fields only: give every field its record type")
    for f in fields:
        if f.start is None:
            continue
        if previous and f.record != previous.record:
            previous = None  # each record layout starts again at position 1
            if f.start != 1:
                found.append(f"{f.label}: record {f.record} must start at position 1, not {f.start}")
        if f.length is not None and f.end - f.start + 1 != f.length:
            found.append(f"{f.label}: positions {f.positions} do not give length {f.length}")
        if previous and f.start != previous.end + 1:
            found.append(f"{f.label} starts at {f.start}, but {previous.label} ends at {previous.end}")
        previous = f
    return found
