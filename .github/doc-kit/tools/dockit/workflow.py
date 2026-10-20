"""Decides the next step of a run from the files that exist. Does every step that needs no AI itself
(scan, plan, checks, compare, assemble) and returns only what needs an agent or a person."""

import csv
import hashlib
from dataclasses import dataclass
from typing import List, Optional

from . import checks, compare, concept, document, markdown, readability, review, scan, spec
from . import questions as questions_module
from .discovery import Discovery
from .plan import MAX_READER_ROUNDS, Plan, Unit
from .project import STEPS_DIR, Paths, newer

# Six agents, split by what each may read: the code (discoverer, explainer, verifier) or only the checked
# documentation (writer, reader, reviewer). The verifier runs on another model; the reader knows nothing of the
# business; the reviewer reads the finished documents as a business analyst.
AGENT_DISCOVER = "doc-discoverer"
AGENT_EXPLAIN = "doc-explainer"
AGENT_VERIFY = "doc-verifier"
AGENT_WRITE = "doc-writer"
AGENT_READER = "doc-reader"
AGENT_REVIEW = "doc-reviewer"
REVIEW_STEP = "5-reviewer.md"
STEPS = {"flow": ("2-explainer-flow.md", AGENT_EXPLAIN), "output": ("2-explainer-output.md", AGENT_EXPLAIN),
         "concept": ("4-writer-concept.md", AGENT_WRITE), "summary": ("4-writer-summary.md", AGENT_WRITE)}
READER_STEP = "4-reader.md"
REWRITE = ("Rewrite the parts the reader could not follow in plainer words, for a reader new to the domain. "
           "Change no fact, id, value or evidence.")


def _facts(files) -> str:
    """A fingerprint of what the output files say, without their questions: a question asked or removed does not
    make the check SQL old, so nobody runs it again for nothing."""
    digest = hashlib.sha256()
    for path in files:
        if path.exists():
            digest.update(markdown.strip_sections(path.read_text(encoding="utf-8"), ["Questions for the SME"])
                          .encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True)
class Action:
    kind: str  # TASK | STOP | FINISHED
    text: str
    agent: str = ""

    def render(self) -> str:
        return f"TASK {self.agent}: {self.text}" if self.kind == "TASK" else f"{self.kind}: {self.text}"


class Run:
    def __init__(self, paths: Paths):
        self.paths = paths
        self.discovery: Optional[Discovery] = None
        self.plan: Optional[Plan] = None

    def next(self) -> Action:
        # Concept pages and the summary come last: they are written from flow and output files that passed every
        # check. A newcomer reads each flow, concept and the summary once its facts are checked.
        for step in (self._inventory, self._discovery, self._plan, self._sme_answers, self._units, self._data_checks,
                     lambda: self._read(("flow",)), self._concepts, lambda: self._read(("concept",)),
                     self._summary, lambda: self._read(("summary",)), self._review):
            action = step()
            if action:
                if self.plan:
                    self.plan.save(self.paths)
                return action
        self.plan.save(self.paths)  # what the last steps learned (data_facts) is kept
        return self._finish()

    # Steps without AI, and the decisions between AI steps

    def _inventory(self) -> Optional[Action]:
        if self.paths.inventory_json.exists():
            old = scan.load(self.paths)
            if old.version < scan.VERSION and old.fingerprint == scan.fingerprint(self.paths):
                scan.save(scan.scan(self.paths), self.paths)  # same sources, written by an older kit
        if not self.paths.inventory_json.exists() or scan.load(self.paths).fingerprint != scan.fingerprint(self.paths):
            if self.paths.discovery.exists() and self.paths.inventory_json.exists():
                return Action("STOP", "Source files changed since this run started. Delete the folder "
                              f"{self.paths.rel(self.paths.out)} to document the new code from the start, "
                              "or put the files back.")
            scan.save(scan.scan(self.paths), self.paths)
        return None

    def _discovery(self) -> Optional[Action]:
        cards = [p for card in concept.load_all(self.paths.input) for p in concept.problems(card)]
        if cards:
            return Action("STOP", "Fix the intent cards, then run /doc-run again: " + " ".join(cards))
        layouts = self._spec_problems()
        if layouts:
            return Action("STOP", "Fix the output specifications in "
                          f"{self.paths.rel(self.paths.input / 'outputs')}, then run /doc-run again: " + "; ".join(layouts))
        if not self.paths.discovery.exists():
            return self._task(AGENT_DISCOVER, "1-discoverer.md", "")
        problems = checks.discovery_problems(self.paths)
        if problems:
            return self._task(AGENT_DISCOVER, "1-discoverer.md", "", self._write_problems("discovery", problems))
        self.discovery = Discovery.load(self.paths.discovery)
        if not self.discovery.reviewed:
            return Action("STOP", f"Review {self.paths.rel(self.paths.discovery)}: are the flows and outputs "
                                  "right, and are the business meanings from your input files? Then change its "
                                  "line **Status:** to REVIEWED and run /doc-run again.")
        return None

    def _plan(self) -> Optional[Action]:
        mtime = self.paths.discovery.stat().st_mtime
        self.plan = Plan.load(self.paths)
        if self.plan is None or self.plan.discovery_mtime != mtime:
            self.plan = Plan.build(self.discovery, self.paths, mtime)
        return None

    def _sme_answers(self) -> Optional[Action]:
        """An answer in sme-answers.md goes to every part that asked that question: it rewrites what the answer
        settles and drops the question. Then its facts are checked again like any change."""
        path = self.paths.input / "sme-answers.md"
        if not path.exists():
            return None
        answered = [r.get("Question", "").strip() for r in markdown.first_table(path.read_text(encoding="utf-8"))
                    if r.get("Question", "").strip() and r.get("Answer", "").strip()]
        for question in answered:
            for unit in self.plan.units:
                key = f"{unit.id}|{question}"
                unit_file = self.paths.unit_file(unit.id)
                if unit.kind not in STEPS or key in self.plan.sme_applied or not unit_file.exists():
                    continue
                if not any(questions_module.same(q, question) for q, _ in questions_module.of(
                        unit_file.read_text(encoding="utf-8"))):
                    continue
                self.plan.sme_applied.append(key)
                step, agent = STEPS[unit.kind]
                scope = (f"Apply the SME's answer to the question \"{question}\": change what the answer settles, "
                         f"with the answer as the source of its meaning, and remove the question. Change nothing else.")
                if unit.kind == "output":
                    scope = f"Fields {unit.first_field}-{unit.last_field} of the spec. " + scope
                return self._task(agent, step, unit.id, self.paths.rel(path), scope)
        return None

    def _units(self, kinds=("flow", "output")) -> Optional[Action]:
        for unit in self.plan.units:
            if unit.kind not in kinds or unit.id in self.plan.stuck:
                continue
            action = self._unit(unit)
            if action:
                return action
        return None

    def _concepts(self) -> Optional[Action]:
        return self._units(("concept",))

    def _summary(self) -> Optional[Action]:
        return self._units(("summary",))

    def _read(self, kinds) -> Optional[Action]:
        """The newcomer reader reads each checked unit. When it cannot follow some points, the writer rewrites
        them in plainer words (at most MAX_READER_ROUNDS times); the second reader then checks the facts again."""
        for unit in self.plan.units:
            unit_file = self.paths.unit_file(unit.id)
            if unit.kind not in kinds or unit.id in self.plan.stuck or not unit_file.exists() \
                    or checks.verdict(self.paths, unit.id) != "PASS":
                continue
            reader_file = self.paths.reader_file(unit.id)
            result = readability.reading(reader_file) if newer(reader_file, unit_file) else None
            if result is None or result.verdict is None:
                key = f"{unit.id}-reader"
                self.plan.new_version(key, unit_file.stat().st_mtime)
                if self.plan.out_of_attempts(key):
                    continue
                self.plan.count_attempt(key)
                return self._task(AGENT_READER, READER_STEP, unit.id)
            rounds = self.plan.reader_rounds.get(unit.id, 0)
            counts = self.plan.unclear.setdefault(unit.id, [])
            if len(counts) <= rounds:
                counts.append(len(result.points))
            if result.verdict == "UNCLEAR" and result.points and rounds < MAX_READER_ROUNDS:
                self.plan.reader_rounds[unit.id] = rounds + 1
                step, agent = STEPS[unit.kind]
                return self._task(agent, step, unit.id, self.paths.rel(reader_file), REWRITE)
        return None

    def _unit(self, unit: Unit) -> Optional[Action]:
        step, agent = STEPS[unit.kind]
        unit_file, verify_file = self.paths.unit_file(unit.id), self.paths.verify_file(unit.id)
        fix = ""
        if unit_file.exists():
            problems = checks.unit_problems(unit, self.paths, self.discovery)
            if problems:
                fix = self._write_problems(unit.id, problems)
            elif unit.kind == "summary" and self._summary_stale(unit_file):
                fix = self._write_problems(unit.id, ["The flow, output or concept files changed after this summary "
                                                     "was written. Write it again from them."])
            elif not newer(verify_file, unit_file):
                return self._task(AGENT_VERIFY, "2-verifier.md", unit.id, "", self._spot_scope(unit))
            elif checks.verdict(self.paths, unit.id) != "PASS":
                fix = self.paths.rel(verify_file)
            elif unit.kind == "output" and checks.spot_problems(unit, self.paths, self.discovery):
                key = f"{unit.id}-spot"
                self.plan.new_version(key, verify_file.stat().st_mtime)
                if not self.plan.out_of_attempts(key):
                    self.plan.count_attempt(key)
                    problems = checks.spot_problems(unit, self.paths, self.discovery)
                    return self._task(AGENT_VERIFY, "2-verifier.md", unit.id,
                                      self._write_problems(key, problems), self._spot_scope(unit))
                self.plan.stuck[unit.id] = "the verifier's spot check and the unit file still disagree"
                return None
            elif unit.kind == "output" and self._report_is_current(unit) and self._data_differs(unit):
                fix = self.paths.rel(self.paths.data_report(unit.output_id))
            else:
                return None
        if self.plan.out_of_attempts(unit.id):
            self.plan.stuck[unit.id] = f"still failing after {self.plan.attempts[unit.id]} attempts: {fix}"
            return None
        self.plan.count_attempt(unit.id)
        scope = f"Fields {unit.first_field}-{unit.last_field} of the spec." if unit.kind == "output" else ""
        return self._task(agent, step, unit.id, fix, scope)

    def _spot_scope(self, unit: Unit) -> str:
        if unit.kind != "output":
            return ""
        names = ", ".join(f"{f.number:02d} {f.name}" for f in checks.spot_fields(unit, self.paths, self.discovery))
        return (f"Spot check: trace the fields {names} from the code yourself, before you open the unit file, and "
                f"write them under `## {checks.SPOT_SECTION}`.")

    def _summary_stale(self, summary) -> bool:
        files = [p for folder in ("flows", "outputs", "concepts") for p in (self.paths.out / folder).glob("*.md")]
        return not newer(summary, *files)

    def _report_is_current(self, unit: Unit) -> bool:
        """The data report was written after the unit file and after the files it compares, so its
        differences are about this version of the documentation."""
        report = self.paths.data_report(unit.output_id)
        return newer(report, self.paths.unit_file(unit.id), self.paths.check_sql(unit.output_id),
                     self.paths.test_file(unit.output_id, "expected"), self.paths.test_file(unit.output_id, "actual"))

    def _data_differs(self, unit: Unit) -> bool:
        result = self._compare(unit.output_id)
        if not result:
            return False
        fields = unit.fields(self._fields(unit.output_id))
        return result.expected_lines != result.actual_lines or any(result.fields.get(f.label) for f in fields)

    def _data_checks(self) -> Optional[Action]:
        if not self.paths.module.data_check:
            return None
        for item in (o for o in self.discovery.outputs if o.spec):
            units = self.plan.output_units(item.id)
            if not units or any(u.id in self.plan.stuck for u in units):
                continue  # not in this run's scope, or waiting for the SME
            sql = self.paths.check_sql(item.id)
            unit_files = [self.paths.unit_file(u.id) for u in units]
            facts = _facts(unit_files)
            if newer(sql, *unit_files):
                self.plan.data_facts[item.id] = facts
            elif not sql.exists() or self.plan.data_facts.get(item.id) != facts:
                return self._task(AGENT_WRITE, "3-writer-check-sql.md", item.id)
            expected, actual = self.paths.test_file(item.id, "expected"), self.paths.test_file(item.id, "actual")
            if not (expected.exists() and actual.exists()) or not newer(expected, sql):
                return Action("STOP", f"Data check for {item.id}: run {self.paths.rel(sql)} on the TEST database "
                              f"and save the result (one line per row, no header) as "
                              f"{self.paths.rel(expected)}. Copy the real file of the same run as "
                              f"{self.paths.rel(actual)}"
                              + (" (for a table: the rows the run wrote, one per line, fields in spec order "
                                 "separated by |)" if compare.delimited(self._fields(item.id)) else "")
                              + ". Then run /doc-run again. To skip the data check, "
                              f"set Data check to no in {self.paths.rel(self.paths.input / 'module.md')}.")
            report = self.paths.data_report(item.id)
            if not newer(report, expected, actual, sql):
                result = self._compare(item.id)
                report.write_text(compare.report(item.id, item.title, result, self._fields(item.id)), encoding="utf-8")
                if not result.matches:
                    return self._units()  # send the fields that differ back to the explainer
        return None

    def _review(self) -> Optional[Action]:
        """A business analyst reads the finished documents and answers the tool's questions with chains of ids.
        Each point goes back to the part that owns it; when every point of the round is sent back, the facts are
        checked again and the reviewer reads again, at most MAX_REVIEW_ROUNDS times."""
        if self.plan.unit(review.REVIEW_ID) is None:
            return None
        self._write_documents()
        self.paths.review_questions.parent.mkdir(parents=True, exist_ok=True)
        self.paths.review_questions.write_text(review.render(review.questions(self.paths, self.discovery, self.plan)),
                                               encoding="utf-8")
        review_file = self.paths.unit_file(review.REVIEW_ID)
        parts = [self.paths.unit_file(u.id) for u in self.plan.units if u.kind != "review"]
        self.plan.new_version(review.REVIEW_ID, max((p.stat().st_mtime for p in parts if p.exists()), default=0))
        fresh = newer(review_file, *parts)
        if fresh:
            problems = review.problems(self.paths, self.discovery, self.plan)
            if problems:
                action = self._review_task(self._write_problems(review.REVIEW_ID, problems))
                if action is None:
                    self.plan.stuck[review.REVIEW_ID] = f"the review still fails its check: {problems[0]}"
                return action
        result = review.read(review_file)
        if result and result.verdict == "NEEDS WORK" and self.plan.review_rounds < review.MAX_REVIEW_ROUNDS                 and (fresh or self.plan.review_fixed):
            action = self._send_back(result, review_file)
            if action:
                return action
        if fresh:
            return None  # READY, out of rounds, or every point sent back and nothing changed
        if review_file.exists() and self.plan.review_fixed:  # the parts were fixed: a new round
            self.plan.review_rounds += 1
            self.plan.review_fixed = []
        return self._review_task("")

    def _review_task(self, fix: str) -> Optional[Action]:
        if self.plan.out_of_attempts(review.REVIEW_ID):
            return None
        self.plan.count_attempt(review.REVIEW_ID)
        return self._task(AGENT_REVIEW, REVIEW_STEP, review.REVIEW_ID, fix)

    def _send_back(self, result: review.Result, review_file) -> Optional[Action]:
        """The next part with review points that has not been sent back in this round."""
        for part in result.parts():
            target = self.plan.unit(part)
            if target is None or target.kind not in STEPS or part in self.plan.review_fixed                     or part in self.plan.stuck:
                continue
            self.plan.review_fixed.append(part)
            step, agent = STEPS[target.kind]
            scope = (f"Fix only the points of the review whose Part is {part}. Change no fact, id, value or "
                     f"evidence unless the point shows it is wrong.")
            if target.kind == "output":
                scope = f"Fields {target.first_field}-{target.last_field} of the spec. " + scope
            return self._task(agent, step, part, self.paths.rel(review_file), scope)
        return None

    def _write_documents(self) -> List[str]:
        """Writes the business guide and the reference; returns what is not yet checked."""
        guide, reference, open_items = document.build(self.paths, self.plan, self.discovery)
        self.paths.guide.write_text(guide, encoding="utf-8")
        self.paths.reference.write_text(reference, encoding="utf-8")
        return open_items

    def _finish(self) -> Action:
        open_items = self._write_documents()
        state = "DRAFT, not yet checked: " + ", ".join(open_items) if open_items else "FINAL"
        return Action("FINISHED", f"{self.paths.rel(self.paths.guide)}, with the evidence in "
                                  f"{self.paths.rel(self.paths.reference)} ({state}).")

    # Helpers

    def _spec_problems(self, limit: int = 10):
        """Positions that leave a gap or overlap, or a length that does not fit: the person fixes the spec before
        any field is traced against it."""
        found = []
        for path in sorted((self.paths.input / "outputs").glob("*.csv")):
            try:
                fields = spec.load(path)
            except (OSError, UnicodeError, ValueError, KeyError, csv.Error) as error:
                found.append(f"{path.name}: cannot be read as a CSV with a `field` column ({error})")
                continue
            if not fields:
                found.append(f"{path.name}: no row has a value in the `field` column")
            found += [f"{path.name}: {p}" for p in spec.problems(fields)]
        if any("starts at" in p for p in found):
            found.append("for unused positions, add a field such as FILLER with its positions")
        return found[:limit] + ([f"and {len(found) - limit} more"] if len(found) > limit else [])

    def _fields(self, output_id: str):
        item = next(o for o in self.discovery.outputs if o.id == output_id)
        return spec.load(self.paths.input / item.spec)

    def _compare(self, output_id: str) -> Optional[compare.Result]:
        expected = self.paths.test_file(output_id, "expected")
        actual = self.paths.test_file(output_id, "actual")
        if not (self.paths.module.data_check and expected.exists() and actual.exists()):
            return None
        return compare.compare(self._fields(output_id), expected, actual)

    def _write_problems(self, name: str, problems) -> str:
        path = self.paths.problems_file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Problems found by the tool in {name}\n\nFix every point, then run the check again.\n\n"
                        + "\n".join(f"{n}. {p}" for n, p in enumerate(problems, 1)) + "\n", encoding="utf-8")
        return self.paths.rel(path)

    def _task(self, agent: str, step_file: str, unit_id: str, fix: str = "", scope: str = "") -> Action:
        parts = [f"Read {self.paths.rel(STEPS_DIR / step_file)} and follow it.",
                 f"Input: {self.paths.rel(self.paths.input)}.", f"Output: {self.paths.rel(self.paths.out)}."]
        if unit_id:
            parts.append(f"Unit: {unit_id}.")
        if scope:
            parts.append(scope)
        if fix:
            parts.append(f"Fix the points in {fix}.")
        return Action("TASK", " ".join(parts), agent)
