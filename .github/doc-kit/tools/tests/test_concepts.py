"""Tests of the concept checks, the coverage checks and the data check of tables.
Run from the tools folder: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import checks, compare, concept, markdown, scan, spec  # noqa: E402

CARD = """# Concept: Order refund

## What the business expects

| # | The business expects |
|---|---|
| I1 | Shipping is kept. |
| I2 | Refund within 30 days. |
"""


class CardTest(unittest.TestCase):
    def test_card_title_and_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "concepts").mkdir()
            (root / "concepts" / "refund.md").write_text(CARD, encoding="utf-8")
            (root / "concepts" / "README.md").write_text("# not a card", encoding="utf-8")
            cards = concept.load_all(root)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].title, "Order refund")
        self.assertEqual(cards[0].file, "concepts/refund.md")
        self.assertEqual(cards[0].ids, ["I1", "I2"])
        self.assertEqual(concept.problems(cards[0]), [])


class IntentTest(unittest.TestCase):
    card = concept.Card("concepts/refund.md", "Order refund", [("I1", "Shipping is kept."), ("I2", "Within 30 days.")])

    def rows(self, text):
        return markdown.first_table(text)

    def test_every_line_answered_with_a_status_and_known_ids(self):
        rows = self.rows("| # | The business expects | The system does | Status | Based on |\n|---|---|---|---|---|\n"
                         "| I1 | Shipping is kept. | The shipping charge is not refunded. | ✅ Matches | F01-BR03 |\n"
                         "| I2 | Within 30 days. | No rule checks the days. | ❓ Not found in the code | |\n")
        self.assertEqual(checks._intents(self.card, rows, {"F01-BR03"}), [])

    def test_missing_line_bad_status_and_made_up_id(self):
        rows = self.rows("| # | The business expects | The system does | Status | Based on |\n|---|---|---|---|---|\n"
                         "| I1 | Shipping is kept. | The shipping charge is not refunded. | yes | F01-BR09 |\n")
        problems = " ".join(checks._intents(self.card, rows, {"F01-BR03"}))
        self.assertIn("I2 must have exactly one row", problems)
        self.assertIn("Status must be one of", problems)
        self.assertIn("F01-BR09 does not exist", problems)


class ExampleTest(unittest.TestCase):
    def test_each_example_says_what_happened(self):
        text = ("### Example 1. Refund\n\n**Event:** 1 of 3 shirts returned on 2026-10-16.\n"
                "\n### Example 2. Missing\n\n**Before:** An order of 3 shirts.\n")
        problems = checks._worked_examples(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("Example 2", problems[0])

    def test_no_example(self):
        self.assertTrue(checks._worked_examples("No examples."))


class PlainWordsTest(unittest.TestCase):
    def test_code_is_rejected_ids_and_tables_are_not(self):
        self.assertEqual(checks._plain_words("| `ORDER_TXN.TAX_AMT` | Tax part | F01-BR03, O02-09-R1 |\n"
                                             "The order is closed when every item is delivered."), [])
        self.assertTrue(checks._plain_words("When shipCd is EXP, the charge is doubled."))
        self.assertTrue(checks._plain_words("Calls refund( with the amount."))
        self.assertTrue(checks._plain_words("If status == 9 the refund is refused."))


class CoverageTest(unittest.TestCase):
    def test_entry_points_and_tables_must_be_placed(self):
        inventory = scan.Inventory()
        inventory.entry_points = [scan.Hit("main", "src/a/OrderBatch.java", 10, "OrderBatch.main(String[] args)"),
                                  scan.Hit("web.xml", "web/WEB-INF/web.xml", 5, "/refund -> a.RefundServlet")]
        inventory.sql = [scan.Hit("UPDATE (java)", "src/a/Order.java", 3, "x", "UPDATE ORDER_HDR SET A = ?"),
                         scan.Hit("INSERT (java)", "src/a/Order.java", 4, "y", "INSERT INTO REFUND_TXN (A) VALUES (?)")]
        text = ("## 2. Flows\n\n| ID | Flow | Entry point |\n|---|---|---|\n| F01 | Orders | src/a/OrderBatch.java:10 |\n"
                "## 3. Outputs\n\n| ID | Output |\n|---|---|\n| O01 | REFUND_TXN rows |\n"
                "## 5. Not documented\n\nNone.\n")
        problems = " ".join(checks._coverage(inventory, text))
        self.assertIn("EP02", problems)  # the web.xml mapping: its servlet is in no flow
        self.assertNotIn("EP01", problems)
        self.assertIn("ORDER_HDR", problems)
        self.assertNotIn("Table REFUND_TXN", problems)


class DelimitedCompareTest(unittest.TestCase):
    def test_rows_in_any_order_and_the_field_that_differs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "s.csv").write_text("field,description\nREF,r\nAMOUNT,a\n", encoding="utf-8")
            (root / "e.txt").write_text("P2|10.00\nP1|5.00\n", encoding="utf-8")
            (root / "a.txt").write_text("P1|5.00\nP2|11.00\n", encoding="utf-8")
            fields = spec.load(root / "s.csv")
            result = compare.compare(fields, root / "e.txt", root / "a.txt")
            report = compare.report("O01", "REFUND", result, fields)
        self.assertTrue(compare.delimited(fields))
        self.assertEqual(result.fields, {"REF": 0, "AMOUNT": 1})
        self.assertFalse(result.matches)
        self.assertIn("| 02 | AMOUNT | - | DIFF | 1 |", report)


if __name__ == "__main__":
    unittest.main()
