"""Data check: compares the file rebuilt from the documentation with the real file, field by field."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from . import spec

MAX_LINES = 1000
MAX_LISTED = 20
UNKNOWN_RECORD = "(line of no known record type)"


@dataclass
class Difference:
    line: int
    field: str
    expected: str
    actual: str


@dataclass
class Result:
    expected_lines: int
    actual_lines: int
    compared: int
    fields: Dict[str, int] = field(default_factory=dict)  # field label -> lines that differ
    differences: List[Difference] = field(default_factory=list)

    @property
    def matches(self) -> bool:
        return self.expected_lines == self.actual_lines and not any(self.fields.values())

    def field_result(self, label: str) -> str:
        return "DIFF" if self.fields.get(label) or self.expected_lines != self.actual_lines else "MATCH"


def _read(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


DELIMITER = "|"


def delimited(fields: List[spec.Field]) -> bool:
    """A spec without positions is a table or message: one row per line, fields separated by |."""
    return bool(fields) and all(f.start is None for f in fields)


def value(line: str, f: spec.Field, by_delimiter: bool) -> str:
    """The value of one field in one line of the file."""
    return _values(line, f, by_delimiter)


def _values(line: str, f: spec.Field, by_delimiter: bool) -> str:
    if not by_delimiter:
        return line[f.start - 1:f.end]
    parts = line.split(DELIMITER)
    return parts[f.number - 1] if f.number <= len(parts) else ""


def compare(fields: List[spec.Field], expected: Path, actual: Path) -> Result:
    exp, act = _read(expected), _read(actual)
    by_delimiter = delimited(fields)
    if by_delimiter:  # rows of a table have no order: compare them sorted
        exp, act = sorted(exp), sorted(act)
    result = Result(len(exp), len(act), min(len(exp), len(act), MAX_LINES))
    checked = fields if by_delimiter else [f for f in fields if f.start is not None]
    for f in checked:
        result.fields[f.label] = 0
    for n in range(result.compared):
        if exp[n] == act[n]:
            continue
        on_line = checked if by_delimiter else _on_line(exp[n], act[n], checked)
        if not on_line:
            result.fields[UNKNOWN_RECORD] = result.fields.get(UNKNOWN_RECORD, 0) + 1
            result.differences.append(Difference(n + 1, UNKNOWN_RECORD, exp[n][:20], act[n][:20]))
            continue
        for f in on_line:
            e, a = _values(exp[n], f, by_delimiter), _values(act[n], f, by_delimiter)
            if e != a:
                result.fields[f.label] += 1
                result.differences.append(Difference(n + 1, f.label, e, a))
    return result


def _on_line(expected: str, actual: str, fields: List[spec.Field]) -> List[spec.Field]:
    """The fields of the record type of each line; both layouts when the two lines are of different types."""
    if not spec.records(fields):
        return fields
    exp_fields, act_fields = spec.layout(expected, fields), spec.layout(actual, fields)
    if not exp_fields or not act_fields:
        return []  # a line of no known record type: one difference, not a comparison with every layout
    return list(dict.fromkeys(exp_fields + act_fields))


def report(output_id: str, title: str, result: Result, fields: List[spec.Field]) -> str:
    def show(value: str) -> str:
        return "`" + value.replace(" ", "·") + "`"

    by_delimiter = delimited(fields)
    lines = [f"# Data check: {output_id} {title}", "",
             f"Lines expected: {result.expected_lines}. Lines actual: {result.actual_lines}. "
             f"Lines compared: {result.compared}.", "",
             "Written by the tool. Expected = rebuilt from the documentation; actual = the real file."
             + (" Rows are compared sorted, fields separated by |; a line number is the row's place "
                "after sorting." if by_delimiter else ""), "",
             "| NN | Field | Positions | Result | Lines different |", "|---|---|---|---|---|"]
    for f in fields:
        if f.start is not None or by_delimiter:
            lines.append(f"| {f.number:02d} | {f.label} | {f.positions or '-'} | {result.field_result(f.label)} "
                         f"| {result.fields.get(f.label, 0)} |")
    lines += ["", "## Differences", ""]
    if result.expected_lines != result.actual_lines:
        lines.append(f"The number of lines differs: a record is selected by one and not the other. "
                     f"Check the selection rules of the flow that writes {output_id}.")
        lines.append("")
    if not result.differences:
        lines.append("None.")
    else:
        lines += ["| Line | Field | Expected | Actual |", "|---|---|---|---|"]
        lines += [f"| {d.line} | {d.field} | {show(d.expected)} | {show(d.actual)} |"
                  for d in result.differences[:MAX_LISTED]]
        if len(result.differences) > MAX_LISTED:
            lines.append(f"\n{len(result.differences) - MAX_LISTED} more differences not listed.")
    return "\n".join(lines) + "\n"
