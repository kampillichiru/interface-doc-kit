"""Builds the final document from the checked files. Copies; never rewrites what an agent wrote."""

import datetime
import re
from typing import Dict, List, Optional, Tuple

from . import checks, compare, coverage, flowgraph, links, markdown, proof, questions, readability, review, spec, terms
from .discovery import Discovery
from .plan import Plan, Unit
from .project import SUMMARY_ID, Paths, newer

GOLDEN_LINES = 10


class Builder:
    def __init__(self, paths: Paths, plan: Plan, discovery: Discovery):
        self.paths, self.plan, self.discovery = paths, plan, discovery
        self.questions: List[Tuple[str, str, str]] = []  # (question, today, from)
        self.trace: List[Tuple[str, str, str, str]] = []  # (id, evidence, second check, data)
        self.data: Dict[str, Optional[compare.Result]] = {}
        self.rules = links.flow_rules(paths.out / "flows")
        self.fields: Dict[str, Dict[int, links.FieldLink]] = {}  # output id -> field number -> its rules
        self.linked = True  # False when an output file has no `Business rule` column (written by an older kit)
        self.req_rules: Dict[str, List[str]] = {}
        self.by_rule: Dict[str, List[links.FieldLink]] = {}

    # Status

    def unit_status(self, unit: Unit) -> str:
        if unit.id in self.plan.stuck:
            return "SME"
        return checks.verdict(self.paths, unit.id) or "not checked"

    def open_items(self) -> List[str]:
        items = [f"{u.id} ({self.unit_status(u)})" for u in self.plan.units
                 if u.kind != "review" and self.unit_status(u) != "PASS"]
        if self.plan.unit(review.REVIEW_ID):
            review_file = self.paths.unit_file(review.REVIEW_ID)
            result = review.read(review_file)
            parts = [self.paths.unit_file(u.id) for u in self.plan.units if u.kind != "review"]
            if review.REVIEW_ID in self.plan.stuck:
                items.append(f"REVIEW (SME: {self.plan.stuck[review.REVIEW_ID]})")
            elif result is None or result.verdict is None:
                items.append("REVIEW (not reviewed yet)")
            elif not newer(review_file, *parts):
                items.append("REVIEW (not reviewed since the last change)")
            elif result.verdict != "READY":
                items.append(f"REVIEW ({len(result.points)} points open)")
        for output_id, result in self.data.items():
            if result is None:
                items.append(f"{output_id} (data check not run)")
            elif not result.matches:
                items.append(f"{output_id} (data check differences)")
        return items

    # Document

    def build(self) -> Tuple[str, str]:
        """Two documents, each fact in one place. The business guide is what a business reader reads: the
        summary, the answers to the business questions, the open questions and the glossary. The reference holds
        the evidence behind it: flows, every field, the data check and the traceability. The guide links into the
        reference; neither repeats the other."""
        self._load_data_checks()
        self._load_links()
        summary = self._summary()
        concepts = [self._concept(u) for u in self.plan.units if u.kind == "concept"]
        order = {f: n for n, f in enumerate(self.discovery.reading_order)}
        flows = [self._flow(u) for u in sorted((u for u in self.plan.units if u.kind == "flow"),
                                               key=lambda u: order.get(u.id, len(order)))]
        outputs = [self._output(o) for o in self.discovery.outputs if o.spec and self.plan.output_units(o.id)]
        open_items = self.open_items()
        targets = self._targets()
        name, draft = self.paths.module.name, " (DRAFT)" if open_items else ""
        stamp = (f"{datetime.date.today().isoformat()} · Business domain: {self.paths.module.domain} · "
                 f"Produced from the source code by the documentation kit.")
        note = [f"> **Draft.** Not yet fully checked: {', '.join(open_items)}.", ""] if open_items else []

        guide_body = [summary] if summary else []
        if concepts:
            guide_body += [self._business_view(), *concepts]
        shown = proof.compute(self.paths, self.plan, self.discovery)
        guide_body += [proof.guide_section(shown), self._review_section(), self._questions(), self._glossary()]
        guide_body = _link(_number("\n".join(guide_body)), targets, self.paths.reference.name)
        guide = [f"# {name}: Business guide{draft}", "", stamp, "", *note, self._guide_intro(guide_body), guide_body]

        ref_body = [self._overview(), self._rule_map(), "## Flows", "", *flows,
                    "## Outputs", "", *(outputs or ["No output has a specification, so outputs are "
                                                    "described inside the flows.", ""]),
                    self._data_section(), proof.reference_section(shown), self._readability(guide_body),
                    self._traceability()]
        ref_body = _link(_number("\n".join(ref_body)), targets)
        reference = [f"# {name}: Reference{draft}", "", stamp, "", *note, self._reference_intro(ref_body), ref_body]
        return _tidy(guide), _tidy(reference)

    def _review_section(self) -> str:
        if not self.plan.unit(review.REVIEW_ID):
            return ""
        result = review.read(self.paths.unit_file(review.REVIEW_ID))
        rows = ["## Review by a business analyst", ""]
        if result is None or result.verdict is None:
            return "\n".join(rows + ["Not reviewed yet.", ""])
        asked = len(review.questions(self.paths, self.discovery, self.plan))
        broken = sum(1 for _, chain in result.answers.values() if review.NOT_FOUND in chain.lower())
        rows += [f"A reviewer who knows the business but not this system read both documents and answered {asked} "
                 f"questions set by the tool, each with the chain of rules, scenarios and fields that connects it; the "
                 f"tool checked every link. Chains that could not be connected: {broken}. Rounds of fixes: "
                 f"{self.plan.review_rounds}. **Verdict: {result.verdict}.**", ""]
        if result.points:
            rows += ["### Points still open", "", "| # | Part | What a business analyst cannot follow or connect |",
                     "|---|---|---|"]
            rows += [f"| {r.get('#', '')} | {r.get('Part', '')} | "
                     f"{r.get('What a business analyst cannot follow or connect', '')} |" for r in result.points]
        return "\n".join(rows) + "\n"

    def _guide_intro(self, body: str) -> str:
        number = _numbers(body)
        ref = self.paths.reference.name
        text = "**How to read it.** "
        if "Business summary" in number:
            text += (f"Start with section {number['Business summary']}: the whole module in plain words, one example "
                     "from start to end, what can go wrong, and the words to know. ")
        if "Business view" in number:
            text += (f"Section {number['Business view']} answers each business question: what the business expects "
                     "and what the system does (✅ matches, ⚠️ differs, ❓ not found in the code), each type and how it "
                     "works, the fields the question changes, and worked examples followed into the real file. ")
        text += (f"Every statement names the checked rule or field it rests on (F01-BR03, O01-05-R1): click it to see "
                 f"the rule, the field and its code in the reference, [{ref}]({ref}). Each fact is explained once, "
                 f"there. Open questions are in section {number['Open questions for the SME']}, the glossary in "
                 f"section {number['Glossary']}.")
        return text + "\n"

    def _reference_intro(self, body: str) -> str:
        number = _numbers(body)
        guide = self.paths.guide.name
        rule_map = number.get("Business rules and the fields they decide")
        return (f"**How to read it.** The evidence behind the business guide, [{guide}]({guide}): read that first. "
                f"Section {number['Overview']} lists the flows and outputs. "
                + (f"Section {rule_map} maps each business rule to the fields it decides. " if rule_map else "")
                + f"Section {number['Flows']} explains each flow: its trigger, steps, scenarios and business rules. "
                f"Section {number['Outputs']} gives every field: where it comes from and the rules that decide it. "
                f"Section {number['Traceability']} links every id to its lines of code and its check status. "
                f"The open questions and the glossary are in the business guide.\n")

    def _business_view(self) -> str:
        rows = ["## Business view", "",
                "One part per business question. Written from the checked flow and output documentation and the "
                "intent cards of the business team only.", "", "### Where the system differs from the business "
                "intention", "", "| Concept | # | The business expects | The system does | Status |",
                "|---|---|---|---|---|"]
        gaps = 0
        for unit in (u for u in self.plan.units if u.kind == "concept"):
            path = self.paths.unit_file(unit.id)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for row in markdown.first_table(markdown.section(text, checks.INTENT_SECTION)):
                status = row.get("Status", "")
                if "matches" not in status.lower():
                    gaps += 1
                    rows.append(f"| {unit.id} {unit.title} | {row.get('#', '')} | {row.get('The business expects', '')}"
                                f" | {row.get('The system does', '')} | {status} |")
        if not gaps:
            rows = rows[:-2] + ["None: the system does what every intent card says."]
        return "\n".join(rows) + "\n"

    def _summary(self) -> str:
        unit = self.plan.unit(SUMMARY_ID)
        path = self.paths.unit_file(SUMMARY_ID)
        if unit is None or not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        self._collect_questions(text, SUMMARY_ID)
        body = markdown.strip_sections(text, ["Questions for the SME"])
        body = body.split("\n", 1)[1] if body.startswith("# ") else body  # without its own title
        status = self.unit_status(unit)
        note = "" if status == "PASS" else f"\n> Not yet checked by the second reader ({status}).\n"
        return "## Business summary\n" + note + "\n" + _shift(body, 1) + "\n"

    def _concept(self, unit: Unit) -> str:
        path = self.paths.unit_file(unit.id)
        if not path.exists():
            return f"### {unit.id}. {unit.title}\n\nNot documented yet.\n"
        text = path.read_text(encoding="utf-8")
        self._collect_questions(text, unit.id)
        for row in markdown.first_table(markdown.section(text, checks.INTENT_SECTION)):
            ids = ", ".join(checks.BASED_ON.findall(row.get("Based on", "")))
            self.trace.append((f"{unit.id}-{row.get('#', '').strip()}", f"based on {ids}" if ids else "-",
                               self.unit_status(unit), "-"))
        body = markdown.strip_sections(text, ["Questions for the SME"])
        return _shift(self._add_rule_column(body), 2) + "\n"

    def _add_rule_column(self, text: str) -> str:
        """In `Fields this question changes`, adds the business rules behind each field, found through the
        requirement ids the row is based on."""
        if not self.linked or not self.req_rules:
            return text
        out, inside, columns = [], False, None
        for line in text.splitlines():
            if line.startswith("## "):
                inside = markdown._norm(line[3:]).startswith(markdown._norm(checks.FIELDS_SECTION))
            if not inside or not line.strip().startswith("|"):
                columns = None if not line.strip().startswith("|") else columns
                out.append(line)
                continue
            cells = markdown.split_row(line)
            if columns is None:
                columns = list(cells)
                if "Based on" not in cells:
                    columns = []
                    out.append(line)
                    continue
            if not columns:
                out.append(line)
                continue
            at = columns.index("Based on")
            if set(line.replace("|", "").strip()) <= set("-: "):
                extra = "---"
            elif cells == columns:
                extra = "Business rules"
            else:
                based = cells[at] if at < len(cells) else ""
                rules = []
                for req in checks.BASED_ON.findall(based):
                    rules += [r for r in self.req_rules.get(req, []) if r not in rules]
                extra = "; ".join(self._rule_label(r) for r in rules) or "-"
            cells.insert(at, extra)
            out.append("| " + " | ".join(cells) + " |")
        return "\n".join(out)

    def _rule_label(self, rule_id: str) -> str:
        title = links.title_of(self.rules, rule_id)
        return f"{rule_id} {title}" if title else rule_id

    def _overview(self) -> str:
        text = self.paths.discovery.read_text(encoding="utf-8")
        purpose = (markdown.section(text, "Purpose") or "").strip() or self.paths.module.purpose
        rows = ["## Overview", "", purpose, "", "### Flows", "",
                "| ID | Flow | Trigger | Varies by | Outputs | Status |", "|---|---|---|---|---|---|"]
        for f in self.discovery.flows:
            unit = self.plan.unit(f.id)
            status = self.unit_status(unit) if unit else "not in the scope of this run"
            rows.append(f"| [{f.id}](#{_anchor(f.id + ' ' + f.title)}) | {f.title} | {f.trigger} | "
                        f"{f.varies_by or '-'} | {f.outputs or '-'} | {status} |")
        rows += ["", "### Outputs", "", "| ID | Output | Kind | Specification |", "|---|---|---|---|"]
        rows += [f"| {o.id} | {o.title} | {o.kind} | {o.spec or 'none: described in its flow'} |"
                 for o in self.discovery.outputs]
        business = [p.name for p in self.paths.business_files]
        rows += ["", "Business context given by the team: " + (", ".join(business) or "none") + ".", ""]
        return "\n".join(rows)

    def _flow(self, unit: Unit) -> str:
        text = self.paths.unit_file(unit.id).read_text(encoding="utf-8") \
            if self.paths.unit_file(unit.id).exists() else ""
        if not text:
            return f"### {unit.id}. {unit.title}\n\nNot documented yet.\n"
        self._collect_questions(text, unit.id)
        evidence = markdown.first_table(markdown.section(text, "Evidence"))
        for title, _ in markdown.sections(markdown.section(text, "Business rules") or "", 3):
            rule_id = title.split(".")[0].strip()
            refs = "; ".join(r.get("File:line", "") for r in evidence if r.get("Ref", "").strip() == rule_id)
            self.trace.append((rule_id, refs, self.unit_status(unit), "-"))
        steps = flowgraph.parse_steps(markdown.first_table(markdown.section(text, "Steps")))
        body = markdown.strip_sections(text, ["Steps", "Evidence", coverage.NOT_IN_RULE, coverage.NOT_FOLLOWED,
                                              "Questions for the SME",
                                              "Self-check"])
        header, _, rest = body.partition("\n## ")
        rest = ("## " + rest) if rest else ""
        return "\n".join([_target(unit.id), "", _shift(header, 2), "", "#### Flow diagram", "",
                          flowgraph.mermaid(steps), "", _shift(self._rule_fields(rest), 2), ""])

    def _rule_fields(self, text: str) -> str:
        """Puts an anchor on every business rule and, at its end, the fields it decides."""
        out, current = [], None

        def close():
            if current and self.linked and self.fields:
                out.append(f"- **Decides the fields:** {self._fields_of(current)}")

        for line in text.splitlines():
            match = re.match(r"^###\s+(F\d{2}-BR\d{2})\.", line)
            if line.startswith("#"):
                while out and not out[-1].strip():
                    out.pop()
                close()
                if out:
                    out.append("")
                current = match.group(1) if match else None
                if match:
                    out.extend([_target(current), ""])
            out.append(line)
        while out and not out[-1].strip():
            out.pop()
        close()
        out.append("")
        return "\n".join(out)

    def _fields_of(self, rule_id: str) -> str:
        found = self.by_rule.get(rule_id, [])
        if not found:
            return "no field of a documented output: it decides what is processed or changes other data (see the rule)."
        parts = []
        for output_id in dict.fromkeys(f.output_id for f in found):
            names = ", ".join(f"[{f.name}](#{f.anchor})" for f in found if f.output_id == output_id)
            parts.append(f"{output_id} {self._output_name(output_id)}: {names}")
        return "; ".join(parts) + "."

    def _output_name(self, output_id: str) -> str:
        item = next((o for o in self.discovery.outputs if o.id == output_id), None)
        return item.title.split(":")[0].strip() if item else ""

    def _output(self, item) -> str:
        fields = spec.load(self.paths.input / item.spec)
        units = self.plan.output_units(item.id)
        sections, kinds = [], {}
        for unit in units:
            path = self.paths.unit_file(unit.id)
            if not path.exists():
                sections.append(f"Fields {unit.first_field}-{unit.last_field}: not documented yet.\n")
                continue
            text = path.read_text(encoding="utf-8")
            self._collect_questions(text, unit.id)
            preamble = text.split("\n## ", 1)[0].split("\n", 1)[1:]  # what the explainer wrote under its title
            if preamble and preamble[0].strip():
                sections.append(preamble[0].strip() + "\n")
            for title, body in markdown.sections(text, 2):
                number = title.split(".")[0].strip()
                if not number.isdigit():
                    continue
                kinds[int(number)] = (markdown.labelled(body, "Kind") or "", markdown.labelled(body, "Source") or "")
                self._trace_field(unit, int(number), body, fields)
                cleaned = markdown.strip_sections(body, ["Evidence"])
                link = self.fields.get(item.id, {}).get(int(number))
                if link and self.linked:
                    decided = f"**Decided by:** {self._decided_by(link)}\n\n"
                    at = cleaned.find("\n## Requirements")
                    cleaned = (cleaned[:at + 1] + decided + cleaned[at + 1:]) if at >= 0 else decided + cleaned
                anchor = _target(f"{item.id}-{int(number):02d}")
                sections.append(anchor + "\n\n" + _shift(f"## {title}\n\n{cleaned}", 2))
        length = max((f.end for f in fields if f.end), default=None)
        decided = self.linked and bool(self.fields.get(item.id))
        records = spec.records(fields)
        matrix = ["| NN |" + (" Record |" if records else "") + " Field | Positions | Length | Kind | Source |"
                  + (" Decided by |" if decided else ""),
                  "|---|" + ("---|" if records else "") + "---|---|---|---|---|" + ("---|" if decided else "")]
        for f in fields:
            kind, source = kinds.get(f.number, ("-", "-"))
            row = f"| [{f.number:02d}](#{item.id.lower()}-{f.number:02d}) |" + (f" {f.record} |" if records else "") \
                + f" {f.name} | {f.positions or '-'} | {f.length or '-'} | {kind} | {source} |"
            if decided:
                link = self.fields[item.id].get(f.number)
                row += f" {', '.join(link.rules) if link and link.rules else self._decided_by(link) if link else '-'} |"
            matrix.append(row)
        head = [f"### {item.id}. {item.title}", "",
                f"Kind: {item.kind}. Written at: {item.written_at}. "
                + (f"Record length: {length} characters. " if length else "")
                + (f"Record types: {', '.join(records)}. " if records else "") + f"Fields: {len(fields)}.", "",
                "#### Field matrix", "", *matrix, ""]
        return "\n".join(head + sections) + "\n"

    # Business rules and fields

    def _load_links(self) -> None:
        self.req_rules = {}  # requirement id -> the rules it carries out
        for item in self.discovery.outputs:
            if not item.spec or not self.plan.output_units(item.id):
                continue
            fields = spec.load(self.paths.input / item.spec)
            for unit in self.plan.output_units(item.id):
                path = self.paths.unit_file(unit.id)
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8")
                if not links.has_column(text):
                    self.linked = False
                self.fields.setdefault(item.id, {}).update(links.output_fields(text, item.id, fields))
                for _, body in markdown.sections(text, 2):
                    for row in markdown.first_table(markdown.section(body, "Requirements")):
                        self.req_rules[row.get("ID", "").strip()] = links.cell_rules(row.get(links.RULE_COLUMN, ""))[0]
        self.by_rule = links.by_rule([f for fields in self.fields.values() for f in fields.values()])

    def _decided_by(self, link: links.FieldLink) -> str:
        parts = [self._rule_label(r) for r in link.rules]
        if link.format_only:
            parts.append("layout only, no business rule")
        if link.unlinked:
            parts.append(f"⚠️ {', '.join(link.unlinked)}: no documented business rule decides it (see the questions)")
        return "; ".join(parts) or "-"

    def _rule_map(self) -> str:
        rows = ["## Business rules and the fields they decide", ""]
        if not self.fields:
            return "\n".join(rows + ["No output has a specification, so the fields are described inside the flows.",
                                     ""])
        if not self.linked:
            return "\n".join(rows + ["Not available: the output files of this run were written before each "
                                     "requirement named its business rule. Delete them and run `/doc-run` again.", ""])
        rows += ["Each business rule of the flows, and the output fields whose value it decides. Click a field to "
                 "see how it is derived; the same link is on each field as **Decided by**.", ""]
        for flow in self.discovery.flows:
            rules = [r for r in self.rules.values() if r.flow == flow.id]
            if not rules:
                continue
            rows += [f"### {flow.id}. {flow.title}", "", "| Business rule | Fields it decides |", "|---|---|"]
            rows += [f"| {r.id} {r.title} | {self._fields_of(r.id)} |" for r in rules]
            rows.append("")
        others = [f for fields in self.fields.values() for f in fields.values() if not f.rules]
        if others:
            rows += ["### Fields no business rule decides", "", "| Field | Why |", "|---|---|"]
            rows += [f"| [{f.output_id} {f.name}](#{f.anchor}) | {self._decided_by(f)} |" for f in others]
            rows.append("")
        return "\n".join(rows)

    def _targets(self) -> Dict[str, Tuple[str, str]]:
        """Every id the document can link to: (anchor, title shown when pointing at the link)."""
        targets = {r.id: (r.id.lower(), r.title) for r in self.rules.values()}
        for unit in self.plan.units:
            if unit.kind == "flow":
                targets[unit.id] = (unit.id.lower(), unit.title)
        for fields in self.fields.values():
            for f in fields.values():
                targets[f"{f.output_id}-{f.number:02d}"] = (f.anchor, f"{f.output_id} {f.name}")
        return targets

    def _trace_field(self, unit: Unit, number: int, body: str, fields: List[spec.Field]) -> None:
        refs = "; ".join(r.get("File:line", "") for r in markdown.first_table(markdown.section(body, "Evidence")))
        field = next((f for f in fields if f.number == number), None)
        result = self.data.get(unit.output_id)
        data = result.field_result(field.label) if result and field else "-"
        for row in markdown.first_table(markdown.section(body, "Requirements")):
            self.trace.append((row.get("ID", ""), refs, self.unit_status(unit), data))

    def _collect_questions(self, text: str, source: str) -> None:
        self.questions += [(q, today, source) for q, today in questions.of(text)]

    def _questions(self) -> str:
        text = self.paths.discovery.read_text(encoding="utf-8")
        asked = [(r["Question"], r.get("What the system does today", ""), "discovery")
                 for r in markdown.first_table(markdown.section(text, "Questions")) if r.get("Question", "").strip()]
        merged = questions.merge(asked + self.questions)
        rows = ["## Open questions for the SME", "",
                f"Each question once, with every part that raised it ({len(asked) + len(self.questions)} asked, "
                f"{len(merged)} different).", "",
                "| # | Question | What the system does today | From | Answer |", "|---|---|---|---|---|"]
        rows += [f"| Q{n} | {q} | {today} | {', '.join(src)} | |" for n, (q, today, src) in enumerate(merged, 1)]
        return "\n".join(rows if merged else rows[:2] + ["None."]) + "\n"

    def _load_data_checks(self) -> None:
        if not self.paths.module.data_check:
            return
        for item in self.discovery.outputs:
            if not item.spec or not self.plan.output_units(item.id):
                continue
            expected = self.paths.test_file(item.id, "expected")
            actual = self.paths.test_file(item.id, "actual")
            self.data[item.id] = compare.compare(spec.load(self.paths.input / item.spec), expected, actual) \
                if expected.exists() and actual.exists() else None

    def _spec(self, output_id: str) -> List[spec.Field]:
        item = next(o for o in self.discovery.outputs if o.id == output_id)
        return spec.load(self.paths.input / item.spec)

    def _data_section(self) -> str:
        rows = ["## Data check", ""]
        if not self.data:
            return "\n".join(rows + ["Not run (Data check: no in module.md, or no output has a specification).", ""])
        for output_id, result in self.data.items():
            if result is None:
                rows += [f"**{output_id}:** not run yet.", ""]
                continue
            verdict = "every field matches" if result.matches else "differences found"
            rows += [f"**{output_id}:** {result.compared} lines compared, {verdict}. "
                     f"Details: data-check/{output_id}-report.md.", ""]
            actual = self.paths.test_file(output_id, "actual").read_text(encoding="utf-8").splitlines()
            if compare.delimited(self._spec(output_id)):
                rows += ["Golden records: the first rows of the real output, fields separated by |.", "", "```",
                         *actual[:GOLDEN_LINES], "```", ""]
                continue
            width = max((len(line) for line in actual[:GOLDEN_LINES]), default=0)
            ruler1 = "".join(str(i // 10 % 10) if i % 10 == 0 else " " for i in range(1, width + 1)).rstrip()
            ruler2 = "".join(str(i % 10) for i in range(1, width + 1))
            rows += [f"Golden records: the first lines of the real file. `·` = space.", "", "```", ruler1, ruler2,
                     *(line.replace(" ", "·") for line in actual[:GOLDEN_LINES]), "```", ""]
        return "\n".join(rows)

    def _traceability(self) -> str:
        rows = ["## Traceability", "",
                "Second check: an independent agent re-read the code and agreed (PASS). Data: the field "
                "rebuilt from this document matched the real file (MATCH). SME: to be ticked by the business "
                "expert.", "", "| ID | Code (file:line) | Second check | Data | SME |", "|---|---|---|---|---|"]
        rows += [f"| {i} | {refs or '-'} | {check} | {data} | ☐ |" for i, refs, check, data in self.trace]
        return "\n".join(rows) + "\n"

    def _glossary(self) -> str:
        """Every term with a meaning in the input folder (glossary.csv and the tables in business/), then the
        terms the documentation uses that have no meaning yet: those are questions for the SME."""
        rows = ["## Glossary", ""]
        entries = terms.defined(self.paths.input)
        if entries:
            rows += ["Meanings as the team gave them. Nothing here is taken from the code.", "",
                     "| Term | Meaning | Source |", "|---|---|---|"]
            rows += [f"| {t.term} | {t.meaning.replace('|', '/')} | {t.source} |"
                     for t in sorted(entries.values(), key=lambda t: t.term.lower())]
        else:
            rows.append("No meanings given yet (doc-input/glossary.csv or tables in doc-input/business/).")
        known = terms.input_text(self.paths.input)
        tables = checks.tables_used(self.paths)
        missing: Dict[str, List[str]] = {}
        for unit in (u for u in self.plan.units if u.kind == "flow"):
            path = self.paths.unit_file(unit.id)
            if not path.exists():
                continue
            for term in terms.caps_terms(checks.flow_prose(path.read_text(encoding="utf-8")), tables):
                if not terms.mentions(known, term):
                    missing.setdefault(term, []).append(unit.id)
        if missing:
            rows += ["", "### Terms without a meaning yet", "",
                     "Used in the documentation; their meaning is a question for the SME.", "",
                     "| Term | Used in |", "|---|---|"]
            rows += [f"| {t} | {', '.join(units)} |" for t, units in sorted(missing.items())]
        return "\n".join(rows) + "\n"

    def _readability(self, guide: str = "") -> str:
        """How easy the documentation is to read: what the newcomer reader could not follow, and the sentences."""
        rows = ["## How easy it is to read", "",
                "An agent that knows nothing of this business read each part with only the glossary at hand and "
                "listed every point it could not follow. The writer then rewrote those points in plainer words, and "
                "the second reader checked the facts again. Sentences are counted in the business text; a long "
                f"sentence has more than {readability.LONG_SENTENCE} words.", "",
                "| Part | Unclear points at each reading | Still unclear | Sentences | Words per sentence | "
                "Long sentences |", "|---|---|---|---|---|---|"]
        first = left = 0
        unclear = []
        for unit in (u for u in self.plan.units if u.kind in ("summary", "flow", "concept")):
            path = self.paths.unit_file(unit.id)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            prose = checks.flow_prose(text) if unit.kind == "flow" else \
                markdown.strip_sections(text, ["Questions for the SME", "Words to know"])
            m = readability.measure(prose)
            counts = self.plan.unclear.get(unit.id, [])
            reading = readability.reading(self.paths.reader_file(unit.id))
            still = reading.points if reading and reading.verdict == "UNCLEAR" else []
            if counts:
                first, left = first + counts[0], left + len(still)
            if still:
                unclear.append((unit, still))
            rows.append(f"| {unit.id} {unit.title} | {' → '.join(map(str, counts)) or 'not read yet'} | "
                        f"{len(still) if counts else '-'} | {m.sentences} | {m.average_words} | {m.long_sentences} |")
        read = any(self.plan.unclear.get(u.id) for u in self.plan.units)
        rows[2:2] = [f"**The newcomer found {first} unclear points on the first reading; {left} are left.**"
                     if read else "**Not read by the newcomer yet.**", ""]
        for unit, still in unclear:
            rows += ["", f"### Still unclear in {unit.id}", "", "| # | Where | What a newcomer cannot follow |",
                     "|---|---|---|"]
            rows += [f"| {n} | {r.get('Where', '')} | {r.get('What a newcomer cannot follow', '')} |"
                     for n, r in enumerate(still, 1)]
        return "\n".join(rows + self._repeats(guide)) + "\n"

    def _repeats(self, guide: str) -> List[str]:
        """How often the business guide cites each rule: a rule cited many times is a fact told many times."""
        counts: Dict[str, int] = {}
        for found in re.findall(r"\[(F\d{2}-BR\d{2})\]", guide):
            counts[found] = counts.get(found, 0) + 1
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        if not top:
            return []
        return ["", "### Facts the business guide cites most", "",
                "Each fact is explained once, in this reference; the guide names it. Rules cited most: "
                + ", ".join(f"{r} {links.title_of(self.rules, r)} ({n})" for r, n in top) + "."]

def _number(text: str) -> str:
    """Numbers the sections (## headings) in order, outside code blocks."""
    out, in_code, n = [], False, 0
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("## "):
            n += 1
            line = f"## {n}. {line[3:]}"
        out.append(line)
    return "\n".join(out)


def _shift(text: str, levels: int) -> str:
    """Moves every heading down `levels` levels (## becomes ####), outside code blocks."""
    out, in_code = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and re.match(r"^#{1,6}\s", line):
            line = "#" * levels + line
        out.append(line)
    return "\n".join(out)


def _anchor(title: str) -> str:
    return re.sub(r"[^a-z0-9 _-]", "", title.lower()).replace(" ", "-")


def _target(item_id: str) -> str:
    """An anchor a link can jump to: F01-BR05 becomes #f01-br05."""
    return f'<a id="{item_id.lower()}"></a>'


_ID = re.compile(r"(?<![\w\[#/-])(F\d{2}-BR\d{2}|F\d{2}-SC\d+|O\d{2}-\d{2}-R\d+|O\d{2}-\d{2})(?![\w\]-])")


def _link(text: str, targets: Dict[str, Tuple[str, str]], into: str = "") -> str:
    """Turns every rule, scenario and requirement id in the text into a link to its place, outside headings,
    code blocks and `code`. A scenario links to its flow, a requirement to its field. With `into`, the links
    point into that file: the business guide links into the reference."""
    def replace(match: re.Match) -> str:
        found = match.group(1)
        key = found
        if "-SC" in found:
            key = found.split("-")[0]
        elif re.fullmatch(r"O\d{2}-\d{2}-R\d+", found):
            key = found.rsplit("-", 1)[0]
        if key not in targets:
            return found
        anchor, title = targets[key]
        title = title.replace('"', "'").replace("|", "/")
        return f'[{found}]({into}#{anchor} "{title}")'

    out, in_code = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if in_code or line.lstrip().startswith(("```", "#", "<a id=")):
            out.append(line)
            continue
        parts = line.split("`")
        out.append("`".join(_ID.sub(replace, p) if i % 2 == 0 else p for i, p in enumerate(parts)))
    return "\n".join(out)


def _tidy(parts: List[str]) -> str:
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"


def _numbers(body: str) -> Dict[str, str]:
    """Section title -> its number, for the numbered ## headings of a body."""
    return {t.split(". ", 1)[1]: t.split(".", 1)[0] for t in re.findall(r"^## (\d+\. .+)$", body, re.M)}


def build(paths: Paths, plan: Plan, discovery: Discovery) -> Tuple[str, str, List[str]]:
    """The business guide, the reference, and what is not yet checked."""
    builder = Builder(paths, plan, discovery)
    guide, reference = builder.build()
    return guide, reference, builder.open_items()
