"""What the test data proves. A rule is proven by data when the output rebuilt from the documentation matched the
real file on every field the rule decides, and every case of those fields (each row of their decision tables)
occurs in the real file. Everything else is read from the code only: right as far as two readers can tell, but
not shown by a real record. The list of cases the test data never contains says which records to add."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import compare, links, markdown, spec
from .discovery import Discovery
from .plan import Plan
from .project import Paths

PROVEN, PARTLY, CODE_ONLY = "proven by data", "partly: a case is missing from the test data", "read from the code only"


@dataclass
class Case:
    output_id: str
    field: str  # label: name, with its record type when the file has several
    case: str  # the decision row's conditions
    value: str  # the value written, with · for spaces; empty when the row gives no exact value
    seen: Optional[bool]  # None: the row gives no exact value to look for


@dataclass
class RuleProof:
    rule: str
    title: str
    fields: List[str]
    status: str
    why: str


@dataclass
class Proof:
    data_check: bool
    cases: List[Case] = field(default_factory=list)
    rules: List[RuleProof] = field(default_factory=list)

    @property
    def missing(self) -> List[Case]:
        return [c for c in self.cases if c.seen is False]

    def count(self, status: str) -> int:
        return sum(1 for r in self.rules if r.status == status)


def _decision_rows(body: str) -> List[Dict[str, str]]:
    return markdown.first_table(markdown.section(body, "Decision table"))


def compute(paths: Paths, plan: Plan, discovery: Discovery) -> Proof:
    proof = Proof(paths.module.data_check)
    rules = links.flow_rules(paths.out / "flows")
    decided: Dict[str, List[str]] = {}  # rule -> labels of the fields it decides, in outputs with real data
    field_ok: Dict[str, bool] = {}  # label -> matched in the data check and every case seen
    for item in (o for o in discovery.outputs if o.spec and plan.output_units(o.id)):
        actual, expected = paths.test_file(item.id, "actual"), paths.test_file(item.id, "expected")
        if not (proof.data_check and actual.exists()):
            continue
        fields = spec.load(paths.input / item.spec)
        by_number = {f.number: f for f in fields}
        delimited = compare.delimited(fields)
        lines = actual.read_text(encoding="utf-8", errors="replace").splitlines()
        result = compare.compare(fields, expected, actual) if expected.exists() else None
        for unit in plan.output_units(item.id):
            path = paths.unit_file(unit.id)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            link_of = links.output_fields(text, item.id, fields)
            for title, body in markdown.sections(text, 2):
                number = title.split(".")[0].strip()
                if not number.isdigit() or int(number) not in by_number:
                    continue
                f = by_number[int(number)]
                key = f"{item.id} {f.label}"
                matched = bool(result) and result.field_result(f.label) == "MATCH"
                all_seen = True
                for row in _decision_rows(body):
                    value_cell = next((v for k, v in row.items() if "value" in k.lower()), "")
                    exact = markdown.backticked(value_cell)
                    conditions = ", ".join(v.strip() for k, v in row.items()
                                           if v.strip() and "value" not in k.lower() and "requirement" not in k.lower())
                    if not exact:
                        proof.cases.append(Case(item.id, f.label, conditions, "", None))
                        continue
                    wanted = exact[0].replace("·", " ").rstrip()
                    seen = any(compare.value(line, f, delimited).rstrip() == wanted for line in lines
                               if delimited or f in spec.layout(line, fields))
                    all_seen &= seen
                    proof.cases.append(Case(item.id, f.label, conditions, exact[0], seen))
                field_ok[key] = matched and all_seen
                link = link_of.get(int(number))
                for rule in (link.rules if link else []):
                    decided.setdefault(rule, []).append(key)
    for rule in rules.values():
        keys = decided.get(rule.id, [])
        if not keys:
            why = "Data check is off." if not proof.data_check else \
                "It decides no field of an output with a real test file (a selection rule, or another output)."
            proof.rules.append(RuleProof(rule.id, rule.title, [], CODE_ONLY, why))
        elif all(field_ok.get(k) for k in keys):
            proof.rules.append(RuleProof(rule.id, rule.title, keys, PROVEN, "Every field it decides matched, in "
                                         "every case."))
        else:
            weak = [k for k in keys if not field_ok.get(k)]
            proof.rules.append(RuleProof(rule.id, rule.title, keys, PARTLY,
                                         f"Not shown for {', '.join(weak)}: the data check differs or a case of "
                                         f"the field is not in the test data."))
    return proof


def guide_section(proof: Proof) -> str:
    """For the business reader: how much of the guide is shown by real records."""
    rows = ["## How sure we are", ""]
    total = len(proof.rules)
    if not proof.data_check:
        return "\n".join(rows + [f"The data check is off, so all {total} business rules are read from the code only: "
                                 "checked by two readers, not by real records. Set `Data check: yes` in module.md "
                                 "to prove them with test data.", ""])
    rows.append(f"**{proof.count(PROVEN)} of {total} business rules are proven by the test data**: the output rebuilt "
                f"from this documentation matched the real file on every field they decide, in every case. "
                f"{proof.count(PARTLY)} are partly shown; {proof.count(CODE_ONLY)} are read from the code only "
                f"(checked by two readers). The reference lists each rule.")
    if proof.missing:
        rows += ["", f"{len(proof.missing)} cases never occur in the test data. Add records for them to prove them:",
                 "", "| Output | Field | Case | Value |", "|---|---|---|---|"]
        rows += [f"| {c.output_id} | {c.field} | {c.case} | `{c.value}` |" for c in proof.missing]
    return "\n".join(rows) + "\n"


def reference_section(proof: Proof) -> str:
    rows = ["## What the test data proves", ""]
    if not proof.rules:
        return "\n".join(rows + ["No business rules yet.", ""])
    rows += ["| Business rule | Fields it decides | Status | Why |", "|---|---|---|---|"]
    rows += [f"| {r.rule} {r.title} | {', '.join(r.fields) or '-'} | {r.status} | {r.why} |" for r in proof.rules]
    unknown = [c for c in proof.cases if c.seen is None]
    if unknown:
        rows += ["", "Cases whose decision row gives no exact value, so the tool cannot look for them in the file:", "",
                 "| Output | Field | Case |", "|---|---|---|"]
        rows += [f"| {c.output_id} | {c.field} | {c.case} |" for c in unknown]
    return "\n".join(rows) + "\n"
