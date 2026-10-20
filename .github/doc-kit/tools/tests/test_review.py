"""Tests of saying each thing once, the business guide and reference, and the review by a business analyst.
Run from the tools folder: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dockit import checks, context, markdown, questions, review  # noqa: E402
from dockit.plan import Plan  # noqa: E402
from dockit.project import Module, Paths  # noqa: E402
from dockit.workflow import Run  # noqa: E402
from test_newcomer import FLOW, NOT_IN_RULE, SUMMARY, Shop, write  # noqa: E402


class QuestionsTest(unittest.TestCase):
    def test_the_same_question_in_other_words_is_merged(self):
        asked = [("What is the promised delivery date of an order?", "", "F01"),
                 ("Should a refund give back the shipping charge?", "", "F02"),
                 ("What is the promised delivery date of a return?", "", "C01"),
                 ("Should the refund give back the shipping charge too?", "", "SUMMARY")]
        merged = questions.merge(asked)
        self.assertEqual([m[2] for m in merged], [["F01", "C01"], ["F02", "SUMMARY"]])

    def test_the_best_match_wins_and_different_questions_stay(self):
        self.assertFalse(questions.same("Who approves a refund?", "Should gift cards expire?"))
        merged = questions.merge([("What does the status flag value H mean?", "", "F01"),
                                  ("What is the promised delivery date of an order?", "", "F01"),
                                  ("What is the promised delivery date of a gift card?", "", "C01")])
        self.assertEqual(merged[1][2], ["F01", "C01"])

    def test_questions_that_ask_different_things_are_kept(self):
        self.assertFalse(questions.same("Can a gift card pay for shipping?",
                                        "Can a gift card be refunded to the card?"))
        self.assertFalse(questions.same("F01-BR03: should a refund include shipping?",
                                        "F01-BR03: should the refund of shipping be taxed?"))


class WalkthroughTest(unittest.TestCase):
    SPEC = "record,field,start,end\nD,REC,1,1\nD,ORDER_NO,2,7\nD,AMOUNT,8,12\n"

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        write(root / "in" / "outputs" / "S.csv", self.SPEC)
        write(root / "in" / "test-data" / "O01" / "actual.dat", "DORD00100500\nDORD00200250\n")
        self.paths = Paths(root, root / "in", root / "out", Module("SHOP", "", "Orders", ["src"], False))
        self.discovery = SimpleNamespace(outputs=[SimpleNamespace(id="O01", spec="outputs/S.csv")])
        self.item = SimpleNamespace(outputs=["O01"])

    def tearDown(self):
        self.dir.cleanup()

    def check(self, amount):
        text = ("### Example 1. Paid order\n\n**In the file:** O01 line 2\n\n| Field | Value | Based on |\n"
                f"|---|---|---|\n| `ORDER_NO` | `ORD002` | O01-02-R1 |\n| `AMOUNT` | `{amount}` | O01-03-R1 |\n")
        return checks._walkthroughs(self.item, text, self.paths, self.discovery, {"O01-02-R1", "O01-03-R1"})

    def test_values_are_read_from_the_real_line(self):
        self.assertEqual(self.check("00250"), [])
        found = self.check("00500")
        self.assertEqual(len(found), 1)
        self.assertIn("`00250` in line 2", found[0])

    def test_a_table_output_is_read_by_its_columns(self):
        write(self.paths.input / "outputs" / "S.csv", "field,description\nORDER_NO,Order\nAMOUNT,Amount\n")
        write(self.paths.input / "test-data" / "O01" / "actual.dat", "ORD001|5.00\nORD002|2.50\n")
        self.assertEqual(self.check("2.50"), [])
        self.assertIn("`2.50` in line 2", self.check("5.00")[0])

    def test_an_example_must_reach_the_real_file(self):
        found = checks._walkthroughs(self.item, "### Example 1. Paid order\n\nNo line.\n", self.paths,
                                     self.discovery, set())
        self.assertIn("at least one example must follow a real record", found[0])


class ReviewLoopTest(Shop):
    """After every part passed and was read: the reviewer answers the tool's questions, a point goes back to the
    part that owns it, the facts are checked again, and the reviewer reads again."""

    def setUp(self):
        super().setUp()
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 2000)
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2001)
        write(self.paths.reader_file("F01"), "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 2002)
        write(self.paths.unit_file("SUMMARY"), SUMMARY, 2003)
        write(self.paths.verify_file("SUMMARY"), "**Verdict:** PASS\n", 2004)
        write(self.paths.reader_file("SUMMARY"), "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 2005)

    def review(self, chain, points="| None. | | | |", verdict="READY", when=3000):
        write(self.paths.unit_file("REVIEW"), f"## Answers\n\n| Q | Answer | Chain |\n|---|---|---|\n"
              f"| R1 | Paid cash on delivery and handed to the courier. | {chain} |\n\n## Points\n\n"
              f"| # | Part | What a business analyst cannot follow or connect | Suggestion |\n|---|---|---|---|\n"
              f"{points}\n\n## Result\n\n**Verdict:** {verdict}\n", when)

    def test_review_then_send_back_then_read_again(self):
        action = Run(self.paths).next()
        self.assertEqual((action.kind, action.agent), ("TASK", "doc-reviewer"))
        self.assertIn("Follow the worked example", self.paths.review_questions.read_text(encoding="utf-8"))
        self.assertTrue(self.paths.guide.exists() and self.paths.reference.exists())

        self.review("F01-BR99 → SUMMARY 1")  # an id that does not exist
        problems = " ".join(review.problems(self.paths, self.discovery, Plan.load(self.paths)))
        self.assertIn("F01-BR99 does not exist", problems)

        self.review("F01-SC1 → F01-BR01 → SUMMARY 1", "| 1 | F01 | R1: the rule does not say who the courier is. "
                    "| Name the courier. |", "NEEDS WORK")
        self.assertEqual(review.problems(self.paths, self.discovery, Plan.load(self.paths)), [])
        action = Run(self.paths).next()
        self.assertEqual(action.agent, "doc-explainer")
        self.assertIn("Part is F01", action.text)
        self.assertIn("review/REVIEW.md", action.text)

        write(self.paths.unit_file("F01"), self.paths.unit_file("F01").read_text(encoding="utf-8"), 3001)
        self.assertEqual(Run(self.paths).next().agent, "doc-verifier")
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 3002)
        self.assertEqual(Run(self.paths).next().agent, "doc-reader")
        write(self.paths.reader_file("F01"), "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 3003)
        write(self.paths.unit_file("SUMMARY"), SUMMARY, 3004)  # the writer refreshes the summary after F01
        write(self.paths.verify_file("SUMMARY"), "**Verdict:** PASS\n", 3005)
        write(self.paths.reader_file("SUMMARY"), "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 3006)
        self.assertEqual(Run(self.paths).next().agent, "doc-reviewer")
        self.assertEqual(Plan.load(self.paths).review_rounds, 1)

        self.review("F01-SC1 → F01-BR01 → SUMMARY 1", when=4000)
        action = Run(self.paths).next()
        self.assertEqual(action.kind, "FINISHED")
        self.assertIn("FINAL", action.text)
        guide = self.paths.guide.read_text(encoding="utf-8")
        self.assertIn("Review by a business analyst", guide)
        self.assertIn("Verdict: READY", guide)

    def test_an_open_review_keeps_the_document_a_draft(self):
        self.review("not found", "| 1 | F01 | R1: no example reaches the courier. | Add one. |", "NEEDS WORK")
        plan = Plan.build(self.discovery, self.paths, self.paths.discovery.stat().st_mtime)
        plan.review_rounds = review.MAX_REVIEW_ROUNDS
        plan.save(self.paths)
        action = Run(self.paths).next()
        self.assertEqual(action.kind, "FINISHED")
        self.assertIn("REVIEW (1 points open)", action.text)
        self.assertIn("Points still open", self.paths.guide.read_text(encoding="utf-8"))


class FixesTest(Shop):
    """Findings of the code review, each with the case that showed it."""

    def test_reader_retries_stop_on_the_same_version_and_restart_on_a_new_one(self):
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 2000)
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2001)
        write(self.paths.reader_file("F01"), "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 1500)
        agents = [Run(self.paths).next().agent for _ in range(4)]
        self.assertEqual(agents[:3], ["doc-reader"] * 3)
        self.assertNotEqual(agents[3], "doc-reader")  # out of attempts for this version of F01
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 2100)
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2101)
        self.assertEqual(Run(self.paths).next().agent, "doc-reader")  # F01 changed: a new set of attempts

    def test_a_spec_that_cannot_be_read_stops_with_a_reason(self):
        path = self.paths.input / "outputs" / "broken.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"field,start\n\xff\xfe,1\n")
        action = Run(self.paths).next()
        self.assertEqual(action.kind, "STOP")
        self.assertIn("broken.csv: cannot be read", action.text)

    def test_check_review_before_the_plan_is_saved(self):
        write(self.paths.unit_file("REVIEW"), "## Answers\n\n## Points\n\n## Result\n\n**Verdict:** READY\n")
        plan = Plan.build(self.discovery, self.paths, 0)
        self.assertIsInstance(checks.unit_problems(plan.unit("REVIEW"), self.paths, self.discovery), list)

    def test_a_review_older_than_a_part_keeps_the_document_a_draft(self):
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 5000)
        write(self.paths.unit_file("REVIEW"), "## Answers\n\n## Points\n\n## Result\n\n**Verdict:** READY\n", 4000)
        plan = Plan.build(self.discovery, self.paths, 0)
        from dockit import document
        _, _, open_items = document.build(self.paths, plan, self.discovery)
        self.assertIn("REVIEW (not reviewed since the last change)", open_items)


class RecordLineTest(unittest.TestCase):
    def test_the_record_code_is_read_whatever_follows_it(self):
        f = SimpleNamespace(number=6, name="DET_TYPE", record="D", start=1, end=1, positions="1", length=1)
        for line in ("**Record:** `D` (detail)", "**Record:** D, detail", "**Record:** D"):
            body = f"{line}\n**Meaning:** x\n**Kind:** Common\n**Source:** fixed\n**When missing:** never\n"
            found = checks._field(SimpleNamespace(output_id="O01"), f, "06. DET_TYPE (positions 1)", body, (), {})
            self.assertFalse(any("Record" in p for p in found), (line, found))


class FieldExampleTest(unittest.TestCase):
    def test_an_output_field_example_must_have_the_field_length(self):
        f = SimpleNamespace(number=2, name="ORDER_NO", length=6)
        rows = [{"#": "1", "Written": "`ORD001`"}, {"#": "2", "Written": "`ORD1`"}]
        found = checks._examples(f, "Field 02 ORDER_NO", rows)
        self.assertEqual(len(found), 1)
        self.assertIn("example 2", found[0])


class UnknownRecordTest(unittest.TestCase):
    def test_a_line_of_no_known_type_is_one_difference(self):
        from dockit import compare, spec
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root / "s.csv", "record,field,start,end\nH,HDR,1,1\nH,DATE,2,9\nD,DET,1,1\nD,NO,2,4\n")
            write(root / "e.dat", "H20261016\nD001\n")
            write(root / "a.dat", "H20261016\nX999\n")
            result = compare.compare(spec.load(root / "s.csv"), root / "e.dat", root / "a.dat")
            self.assertEqual(result.fields[compare.UNKNOWN_RECORD], 1)
            self.assertEqual(sum(v for k, v in result.fields.items() if k != compare.UNKNOWN_RECORD), 0)


class ContextTest(Shop):
    def test_a_flow_pack_has_its_code_decisions_and_meanings_only(self):
        plan = Plan.build(self.discovery, self.paths, 0)
        pack = context.report(self.paths, self.discovery, plan, "F01")
        self.assertIn("# Context of F01", pack)
        self.assertIn("Checkout", pack)
        self.assertIn("# Decision lines of F01", pack)
        self.assertLess(len(pack), len(self.paths.inventory_md.read_text(encoding="utf-8")) * 3)


if __name__ == "__main__":
    unittest.main()
