"""Reading `discovery.md`, the reviewed list of flows and outputs a run documents."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import markdown

_FLOW_ID = re.compile(r"^F\d{2}$")
_OUTPUT_ID = re.compile(r"^O\d{2}$")
_CONCEPT_ID = re.compile(r"^C\d{2}$")
_IDS = re.compile(r"\b[FO]\d{2}\b")
_FLOW_IDS = re.compile(r"\bF\d{2}\b")
EXPLAIN_SECTION = "How the document will explain it"
EXPLAIN_ITEMS = ("Readers", "Reading order", "Main example", "Terms to explain first", "Cases to show")


@dataclass(frozen=True)
class FlowItem:
    id: str
    title: str
    trigger: str
    entry_point: str
    varies_by: str
    outputs: str


@dataclass(frozen=True)
class OutputItem:
    id: str
    title: str
    kind: str
    written_at: str
    spec: Optional[str]  # path relative to the input folder, or None


@dataclass(frozen=True)
class ConceptItem:
    id: str
    title: str
    card: str  # path relative to the input folder
    flows: List[str]  # flow ids that carry the concept out
    outputs: List[str]  # output ids it writes


@dataclass(frozen=True)
class Discovery:
    status: str
    flows: List[FlowItem]
    outputs: List[OutputItem]
    concepts: List[ConceptItem] = field(default_factory=list)
    explain: Dict[str, str] = field(default_factory=dict)  # the plan for how the document explains: item -> plan

    @property
    def reading_order(self) -> List[str]:
        """Flow ids in the order a newcomer should read them: the plan's order, then any flow it leaves out."""
        planned = [f for f in dict.fromkeys(_FLOW_IDS.findall(self.explain.get("Reading order", "")))
                   if any(item.id == f for item in self.flows)]
        return planned + [f.id for f in self.flows if f.id not in planned]

    @property
    def terms_first(self) -> List[str]:
        """The terms the plan says a newcomer must learn first."""
        cell = self.explain.get("Terms to explain first", "").replace("`", "")
        terms = [t.strip(" .") for t in re.split(r"[,;]|<br>", cell)]
        return [t for t in terms if t and t.lower() not in ("none", "-")]

    @property
    def reviewed(self) -> bool:
        return self.status.upper().startswith("REVIEWED")

    @staticmethod
    def load(path: Path) -> "Discovery":
        text = path.read_text(encoding="utf-8")
        status = markdown.labelled(text, "Status") or ""
        flows = [FlowItem(r.get("ID", ""), r.get("Flow", ""), r.get("Trigger", ""), r.get("Entry point", ""),
                          r.get("Varies by", ""), r.get("Outputs", ""))
                 for r in markdown.first_table(markdown.section(text, "Flows"))]
        outputs = [OutputItem(r.get("ID", ""), r.get("Output", ""), r.get("Kind", ""), r.get("Written at", ""),
                              _spec(r.get("Spec", "")))
                   for r in markdown.first_table(markdown.section(text, "Outputs"))]
        concepts = [ConceptItem(r.get("ID", ""), r.get("Concept", ""), r.get("Card", "").strip().strip("`"),
                                _IDS.findall(r.get("Flows", "")), _IDS.findall(r.get("Outputs", "")))
                    for r in markdown.first_table(markdown.section(text, "Concepts"))]
        explain = {r.get("Item", "").strip(): r.get("Plan", "").strip()
                   for r in markdown.first_table(markdown.section(text, EXPLAIN_SECTION))}
        return Discovery(status, flows, outputs, concepts, explain)

    @property
    def scoped(self) -> bool:
        """True when the run documents business concepts: only their flows and outputs are documented."""
        return bool(self.concepts)

    def in_scope(self, unit_id: str) -> bool:
        if not self.scoped:
            return True
        return any(unit_id in c.flows or unit_id in c.outputs for c in self.concepts)

    def problems(self, input_dir: Path) -> List[str]:
        found = []
        if not self.flows:
            found.append("Section Flows has no rows.")
        found += [f"Flow id `{f.id}` must look like F01." for f in self.flows if not _FLOW_ID.match(f.id)]
        found += [f"Output id `{o.id}` must look like O01." for o in self.outputs if not _OUTPUT_ID.match(o.id)]
        found += [f"{o.id}: spec file {o.spec} does not exist in {input_dir.as_posix()}."
                  for o in self.outputs if o.spec and not (input_dir / o.spec).exists()]
        found += [f"Concept id `{c.id}` must look like C01." for c in self.concepts if not _CONCEPT_ID.match(c.id)]
        flow_ids, output_ids = {f.id for f in self.flows}, {o.id for o in self.outputs}
        for c in self.concepts:
            if not (input_dir / c.card).is_file():
                found.append(f"{c.id}: card {c.card} does not exist in {input_dir.as_posix()}.")
            if not c.flows:
                found.append(f"{c.id}: name the flows that carry it out (F01, F02).")
            found += [f"{c.id}: flow {f} is not in the Flows table." for f in c.flows if f not in flow_ids]
            found += [f"{c.id}: output {o} is not in the Outputs table." for o in c.outputs if o not in output_ids]
        found += self._explain_problems()
        ids = [f.id for f in self.flows] + [o.id for o in self.outputs] + [c.id for c in self.concepts]
        found += [f"Id {i} is used twice." for i in sorted({i for i in ids if ids.count(i) > 1})]
        return found


    def _explain_problems(self) -> List[str]:
        """The plan for how the document explains the module, which the person reviews with the rest."""
        if not self.explain:
            return [f"Section `## 8. {EXPLAIN_SECTION}` is missing or has no table (| Item | Plan |)."]
        found = [f"{EXPLAIN_SECTION}: the row `{item}` is missing or empty."
                 for item in EXPLAIN_ITEMS if not self.explain.get(item)]
        planned = _FLOW_IDS.findall(self.explain.get("Reading order", ""))
        found += [f"{EXPLAIN_SECTION}: Reading order does not name {f.id}." for f in self.flows
                  if self.in_scope(f.id) and f.id not in planned]
        return found


def _spec(cell: str) -> Optional[str]:
    cell = cell.strip().strip("`")
    return cell if cell.lower().endswith(".csv") else None
