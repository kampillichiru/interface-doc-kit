"""Tests of the lookup behind the skill ask-the-docs.
Run from the tools folder: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import lookup  # noqa: E402

DOC = """# SHOP: Business Logic Documentation (DRAFT)

> **Draft.** Not yet fully checked: F02 (SME).

## 1. Business view

### C01. Order refund

#### What the business expects and what the system does

| # | The business expects | The system does | Status | Based on |
|---|---|---|---|---|
| I1 | Shipping is kept. | The shipping charge is not refunded. | ✅ Matches | F01-BR05 |
| I2 | Refund within 30 days. | No rule checks the days. | ❓ Not found in the code | |

## 2. Business rules and the fields they decide

### F01. Refund of returned items

| Business rule | Fields it decides |
|---|---|
| F01-BR05 Refund amount split | O01 REFUND: TAX_AMT |

## 3. Flows

<a id="f01"></a>

### F01. Refund of returned items

#### Scenarios

| ID | Type | Scenario | Path | Outcome |
|---|---|---|---|---|
| [F01-SC1](#f01 "Refund") | main | Full return | S1 E1 | Everything back |
| [F01-SC2](#f01 "Refund") | alternate | Part return | S1 E2 | Shipping kept |

#### Business rules

<a id="f01-br05"></a>

##### F01-BR05. Refund amount split

- **Rule:** The refund gives back the item price and its tax; the shipping charge is kept.

## 4. Outputs

<a id="o01-02"></a>

#### 02. TAX_AMT (column REFUND.TAX_AMT)

**Meaning:** Tax given back.

##### Requirements

| ID | Requirement | Business rule |
|---|---|---|
| O01-02-R1 | The TAX_AMT shall be the tax of the returned items. | F01-BR05 |
"""


def titles(terms):
    return [part.heading for part, _ in lookup.find(DOC, terms)]


class LookupTest(unittest.TestCase):
    def test_ids_go_to_their_place(self):
        self.assertEqual(titles(["F01-BR05"]), ["F01-BR05. Refund amount split"])
        self.assertEqual(titles(["O01-02-R1"]), ["02. TAX_AMT (column REFUND.TAX_AMT)"])
        self.assertEqual(titles(["TAX_AMT"]), ["02. TAX_AMT (column REFUND.TAX_AMT)"])

    def test_a_field_comes_whole_with_its_requirements(self):
        text = lookup.answer_material(DOC, ["TAX_AMT"])
        self.assertIn("O01-02-R1", text)
        self.assertIn("(line ", text)

    def test_one_row_for_a_card_line_or_a_scenario(self):
        text = lookup.answer_material(DOC, ["C01-I2", "F01-SC2"])
        self.assertIn("| I2 |", text)
        self.assertNotIn("| I1 |", text)
        self.assertIn("Part return", text)
        self.assertNotIn("Full return", text)

    def test_words_find_the_rule_and_nothing_matches_gives_no_guess(self):
        self.assertIn("F01-BR05. Refund amount split", titles(["is", "shipping", "charge", "refunded?"]))
        self.assertIn("not in the checked documentation", lookup.answer_material(DOC, ["warehouse", "robots"]))

    def test_status(self):
        self.assertTrue(lookup.status(DOC).startswith("DRAFT. Not yet fully checked: F02 (SME)."))
        self.assertTrue(lookup.status("# SHOP: Business Logic Documentation\n").startswith("FINAL"))


if __name__ == "__main__":
    unittest.main()
