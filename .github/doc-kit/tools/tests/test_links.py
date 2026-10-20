"""Tests of the links between business rules and fields.
Run from the tools folder: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import checks, document, links, markdown, spec  # noqa: E402

FLOW = """# F01. Refund of a return

## Business rules

### F01-BR05. Refund amount split

- **Rule:** Item price, tax, shipping.

### F01-BR08. Refund record of a return

- **Rule:** One line for the items and one for the tax. Writes REFUND_TXN (output O01).

### F01-BR09. Zero parts get no line

- **Rule:** A zero part is not written. Writes REFUND_TXN (output O01).
"""

FIELDS = [spec.Field(1, "AMOUNT", None, None, None, "", ""), spec.Field(2, "PAD", None, None, None, "", "")]


def table(text):
    return markdown.first_table(text)


class RuleLinkTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        flows = Path(self.folder.name)
        (flows / "F01.md").write_text(FLOW, encoding="utf-8")
        self.rules = links.flow_rules(flows)

    def tearDown(self):
        self.folder.cleanup()

    def test_rules_and_what_they_write(self):
        self.assertEqual(list(self.rules), ["F01-BR05", "F01-BR08", "F01-BR09"])
        self.assertEqual(self.rules["F01-BR05"].title, "Refund amount split")
        self.assertEqual(self.rules["F01-BR08"].writes, ["O01"])

    def test_good_links(self):
        rows = table("| ID | Requirement | Business rule |\n|---|---|---|\n"
                     "| O01-01-R1 | The part. | F01-BR05, F01-BR08 |\n| O01-01-R2 | Two decimals. | format |\n")
        self.assertEqual(checks._rule_links(FIELDS[0], "Field 01", rows, self.rules), [])

    def test_missing_column_unknown_rule_and_empty_cell(self):
        old = table("| ID | Requirement |\n|---|---|\n| O01-01-R1 | The part. |\n")
        self.assertIn("needs the column", checks._rule_links(FIELDS[0], "Field 01", old, self.rules)[0])
        rows = table("| ID | Requirement | Business rule |\n|---|---|---|\n"
                     "| O01-01-R1 | The part. | F01-BR77 |\n| O01-01-R2 | Two decimals. | |\n")
        problems = " ".join(checks._rule_links(FIELDS[0], "Field 01", rows, self.rules))
        self.assertIn("F01-BR77 is not a business rule", problems)
        self.assertIn("O01-01-R2: `Business rule` must name", problems)

    def test_field_needs_a_rule_unless_layout_only(self):
        layout = table("| ID | Requirement | Business rule |\n|---|---|---|\n| O01-02-R1 | Spaces. | format |\n")
        self.assertEqual(checks._rule_links(FIELDS[1], "Field 02", layout, self.rules), [])
        link = links.field_link("O01", 2, "PAD", layout)
        self.assertTrue(link.format_only)

    def test_rule_that_writes_the_output_must_be_named(self):
        output = ("# O01. REFUND\n\n## 01. AMOUNT (column REFUND.AMOUNT)\n\n### Requirements\n\n"
                  "| ID | Requirement | Business rule |\n|---|---|---|\n| O01-01-R1 | The part. | F01-BR05, F01-BR08 |\n")
        found = list(links.output_fields(output, "O01", FIELDS).values())
        self.assertEqual([r.id for r in links.unlinked_rules(self.rules, "O01", found)], ["F01-BR09"])
        self.assertEqual([f.name for f in links.by_rule(found)["F01-BR05"]], ["AMOUNT"])


class LinkTextTest(unittest.TestCase):
    targets = {"F01-BR05": ("f01-br05", 'Split "order"'), "F01": ("f01", "Refund of a return"), "O01-01": ("o01-01", "O01 AMOUNT")}

    def test_ids_become_links_outside_code_and_headings(self):
        text = ("#### F01-BR05. Split\n| I1 | F01-BR05, F01-SC2, O01-01-R1 | `F01-BR05` |\n"
                "```mermaid\nS1[F01-BR05]\n```\n[F01-BR05](#f01-br05) F01-BR99")
        out = document._link(text, self.targets).splitlines()
        self.assertEqual(out[0], "#### F01-BR05. Split")
        self.assertIn("[F01-BR05](#f01-br05 \"Split 'order'\")", out[1])
        self.assertIn("[F01-SC2](#f01 \"Refund of a return\")", out[1])
        self.assertIn("[O01-01-R1](#o01-01 \"O01 AMOUNT\")", out[1])
        self.assertIn("`F01-BR05`", out[1])
        self.assertEqual(out[3], "S1[F01-BR05]")
        self.assertTrue(out[5].startswith("[F01-BR05](#f01-br05)"))
        self.assertTrue(out[5].endswith(" F01-BR99"))


if __name__ == "__main__":
    unittest.main()
