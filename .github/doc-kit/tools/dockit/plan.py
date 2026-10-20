"""The run plan: the work units, and the little state that files alone cannot show (attempts).

Everything else about the state is read from the files that exist, so a run can stop at any time
and continue later.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from . import spec
from .discovery import Discovery
from .project import REVIEW_ID, SUMMARY_ID, Paths

MAX_FIELDS_PER_UNIT = 12
MAX_ATTEMPTS = 3
MAX_READER_ROUNDS = 2  # rewrites asked by the newcomer reader; after that the unclear points are listed


@dataclass(frozen=True)
class Unit:
    id: str  # F01, O01, O01-P2 for the second part of a long output, C01 for a business concept, or SUMMARY
    kind: str  # flow | output | concept | summary
    title: str
    output_id: str = ""  # outputs only
    first_field: int = 0  # outputs only: 1-based, inclusive
    last_field: int = 0

    def fields(self, all_fields: List[spec.Field]) -> List[spec.Field]:
        return [f for f in all_fields if self.first_field <= f.number <= self.last_field]


SUMMARY_UNIT = Unit(SUMMARY_ID, "summary", "Business summary")
REVIEW_UNIT = Unit(REVIEW_ID, "review", "Review by a business analyst")


@dataclass
class Plan:
    discovery_mtime: float
    units: List[Unit]
    attempts: Dict[str, int] = field(default_factory=dict)
    stuck: Dict[str, str] = field(default_factory=dict)
    reader_rounds: Dict[str, int] = field(default_factory=dict)  # rewrites asked by the newcomer reader
    unclear: Dict[str, List[int]] = field(default_factory=dict)  # unclear points found at each reading
    review_rounds: int = 0  # times the reviewer sent points back
    review_fixed: List[str] = field(default_factory=list)  # parts already sent back in this round
    data_facts: Dict[str, str] = field(default_factory=dict)  # output id -> facts its check SQL was written from
    read_for: Dict[str, float] = field(default_factory=dict)  # task key -> time of what it read when counted
    sme_applied: List[str] = field(default_factory=list)  # "unit|question" answers already sent to their part

    @staticmethod
    def build(discovery: Discovery, paths: Paths, mtime: float) -> "Plan":
        # With concepts, only the flows and outputs they need are documented, and the concepts come last:
        # a concept page is written from the checked flow and output files.
        units = [Unit(f.id, "flow", f.title) for f in discovery.flows if discovery.in_scope(f.id)]
        for item in discovery.outputs:
            if not item.spec or not discovery.in_scope(item.id):
                continue  # an output without a spec is described inside its flow
            count = len(spec.load(paths.input / item.spec))
            parts = [(s, min(s + MAX_FIELDS_PER_UNIT - 1, count)) for s in range(1, count + 1, MAX_FIELDS_PER_UNIT)]
            for n, (first, last) in enumerate(parts, 1):
                unit_id = item.id if len(parts) == 1 else f"{item.id}-P{n}"
                units.append(Unit(unit_id, "output", item.title, item.id, first, last))
        units += [Unit(c.id, "concept", c.title) for c in discovery.concepts]
        units += [SUMMARY_UNIT, REVIEW_UNIT]
        return Plan(mtime, units)

    @staticmethod
    def load(paths: Paths) -> Optional["Plan"]:
        if not paths.plan.exists():
            return None
        data = json.loads(paths.plan.read_text(encoding="utf-8"))
        units = [Unit(**u) for u in data["units"]]
        if not any(u.kind == "summary" for u in units):  # a plan written by an older kit
            units.append(SUMMARY_UNIT)
        if not any(u.kind == "review" for u in units):
            units.append(REVIEW_UNIT)
        return Plan(data["discovery_mtime"], units, data.get("attempts", {}), data.get("stuck", {}),
                    data.get("reader_rounds", {}), data.get("unclear", {}), data.get("review_rounds", 0),
                    data.get("review_fixed", []), data.get("data_facts", {}), data.get("read_for", {}), data.get("sme_applied", []))

    def save(self, paths: Paths) -> None:
        paths.plan.parent.mkdir(parents=True, exist_ok=True)
        paths.plan.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")

    def unit(self, unit_id: str) -> Optional[Unit]:
        return next((u for u in self.units if u.id == unit_id), None)

    def output_units(self, output_id: str) -> List[Unit]:
        return [u for u in self.units if u.output_id == output_id]

    def count_attempt(self, unit_id: str) -> int:
        self.attempts[unit_id] = self.attempts.get(unit_id, 0) + 1
        return self.attempts[unit_id]

    def new_version(self, key: str, stamp: float) -> None:
        """What a task reads changed since its attempts were counted: it gets a new set of attempts. A task that
        keeps failing on the same version still stops after MAX_ATTEMPTS."""
        if self.read_for.get(key) != stamp:
            self.attempts.pop(key, None)
            self.read_for[key] = stamp

    def out_of_attempts(self, unit_id: str) -> bool:
        return self.attempts.get(unit_id, 0) >= MAX_ATTEMPTS
