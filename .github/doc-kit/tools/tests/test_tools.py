"""Tests of the exact parts. Run from the tools folder: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import compare, evidence, flowgraph, markdown, spec  # noqa: E402

FLOW = """# F01. Feed

**Trigger:** nightly

## Steps

| Step | Kind | Text | Next | Rules |
|---|---|---|---|---|
| S1 | start | Job starts | S2 | |
| S2 | decision | Amount is zero? | yes: E1; no: E2 | F01-BR01 |
| E1 | end | Skipped | | |
| E2 | end | Written | | |

## Scenarios

| ID | Type | Scenario | Path | Outcome |
|---|---|---|---|---|
| F01-SC1 | main | Normal | S1 S2 E2 | written |
| F01-SC2 | exception | Zero | S1 S2 E1 | skipped |
"""


class MarkdownTest(unittest.TestCase):
    def test_section_ignores_numbering_and_stops_at_same_level(self):
        text = "# T\n## 2. Flows\nA\n### Sub\nB\n## 3. Outputs\nC"
        self.assertEqual(markdown.section(text, "Flows"), "A\n### Sub\nB")

    def test_table_keeps_escaped_pipes(self):
        rows = markdown.first_table("| Ref | Code |\n|---|---|\n| R1 | `a \\|\\| b` |")
        self.assertEqual(rows, [{"Ref": "R1", "Code": "`a || b`"}])

    def test_labelled_line(self):
        self.assertEqual(markdown.labelled("- **Rule:** Do X.", "Rule"), "Do X.")

    def test_headings_in_code_blocks_are_ignored(self):
        self.assertEqual([t for _, _, t in markdown.headings("```\n# not\n```\n# yes")], ["yes"])


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "pkg").mkdir()
        (root / "pkg" / "A.java").write_text("class A {\n  int x = 1;\n  if (a  >  b) {\n}\n", encoding="utf-8")
        self.roots = (root,)
        evidence._all_files.cache_clear()

    def tearDown(self):
        self.dir.cleanup()

    def test_quote_on_cited_line_passes_with_any_spacing(self):
        self.assertEqual(evidence.check("pkg/A.java:3", "`if (a > b)`", self.roots), [])

    def test_short_path_is_resolved(self):
        self.assertEqual(evidence.check("A.java:2", "`int x = 1;`", self.roots), [])

    def test_wrong_line_gives_the_right_one(self):
        problems = evidence.check("A.java:2", "`if (a > b)`", self.roots)
        self.assertIn("line 3", problems[0])

    def test_missing_file_and_bad_reference(self):
        self.assertIn("not found", evidence.check("B.java:1", "`x`", self.roots)[0])
        self.assertIn("not a citation", evidence.check("A.java", "`x`", self.roots)[0])


class FlowGraphTest(unittest.TestCase):
    def parse(self, text=FLOW):
        steps = flowgraph.parse_steps(markdown.first_table(markdown.section(text, "Steps")))
        return steps, markdown.first_table(markdown.section(text, "Scenarios"))

    def test_valid_flow_has_no_problems(self):
        steps, scenarios = self.parse()
        self.assertEqual(flowgraph.check(steps, scenarios, {"F01-BR01"}), [])

    def test_uncovered_arrow_and_unknown_rule(self):
        steps, scenarios = self.parse()
        problems = flowgraph.check(steps, scenarios[:1], {"F01-BR01", "F01-BR02"})
        self.assertTrue(any("S2->E1" in p for p in problems))
        self.assertTrue(any("F01-BR02 is not linked" in p for p in problems))

    def test_decision_needs_two_branches(self):
        steps, scenarios = self.parse(FLOW.replace("yes: E1; no: E2", "E2"))
        self.assertTrue(any("two or more branches" in p for p in flowgraph.check(steps, scenarios, {"F01-BR01"})))

    def test_mermaid(self):
        steps, _ = self.parse()
        self.assertIn("S2 -->|yes| E1", flowgraph.mermaid(steps))


class SpecAndCompareTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "s.csv").write_text("field,start,end,length\nA,1,3,3\nB,4,5,\n", encoding="utf-8")
        self.fields = spec.load(self.root / "s.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_spec_fills_length_and_has_no_gaps(self):
        self.assertEqual(self.fields[1].length, 2)
        self.assertEqual(spec.problems(self.fields), [])

    def test_compare_names_the_field_that_differs(self):
        (self.root / "e.dat").write_text("abc12\nxyz34\n", encoding="utf-8")
        (self.root / "a.dat").write_text("abc12\nxyz99\n", encoding="utf-8")
        result = compare.compare(self.fields, self.root / "e.dat", self.root / "a.dat")
        self.assertEqual(result.fields, {"A": 0, "B": 1})
        self.assertEqual(result.field_result("A"), "MATCH")
        self.assertFalse(result.matches)


if __name__ == "__main__":
    unittest.main()
