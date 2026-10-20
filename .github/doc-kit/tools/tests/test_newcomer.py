"""Tests of what makes the document complete and easy for a reader new to the domain: decision lines and code
values a flow must cover, terms and their meanings, the explanation plan, the business summary, the newcomer
reader and the measures of how easy the text is. Run from the tools folder: python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import checks, coverage, document, markdown, readability, scan, terms  # noqa: E402
from dockit.discovery import Discovery  # noqa: E402
from dockit.plan import Plan  # noqa: E402
from dockit.project import Module, Paths, business_files  # noqa: E402
from dockit.workflow import Run  # noqa: E402

JAVA = """package shop;

public class Checkout {
    public static void main(String[] args) {
        new Checkout().place(args[0]);
    }

    void place(String method) {
        if (log.isDebugEnabled()) {
            log.debug("placing");
        }
        if ("COD".equals(method)) {
            hand(method);
        }
    }

    void hand(String method) {
        String service = method.length() > 3 ? "EXPRESS" : "STANDARD";
        System.out.println(service);
    }
}
"""

CODES = """# Codes

| Code | Kind | Meaning |
|---|---|---|
| COD, ONLINE | Payment method | Cash on delivery; paid online |
| EXPRESS | Courier service | Next day |
"""

DISCOVERY = """# Discovery: SHOP

**Status:** REVIEWED

## 1. Purpose

Orders of the shop.

## 2. Flows

| ID | Flow | Trigger | Entry point | Varies by | Outputs |
|---|---|---|---|---|---|
| F01 | Place an order | A customer orders | src/shop/Checkout.java:4 | payment method | - |

## 3. Outputs

| ID | Output | Kind | Written at | Spec |
|---|---|---|---|---|
| O01 | Courier service printed | message | src/shop/Checkout.java:19 | none |

## 5. Not documented

None.

## 6. Concepts

None.

## 7. Questions

None.

## 8. How the document will explain it

| Item | Plan |
|---|---|
| Readers | Business analysts new to the domain |
| Reading order | F01 |
| Main example | A customer pays cash on delivery |
| Terms to explain first | COD |
| Cases to show | Online payment |
"""

FLOW = """# F01. Place an order

**Trigger:** A customer places an order.
**Entry point:** src/shop/Checkout.java:4

## Steps

| Step | Kind | Text | Next | Rules |
|---|---|---|---|---|
| S1 | start | Customer places an order | S2 | |
| S2 | decision | Pays cash on delivery (COD)? | yes: E1; no: E2 | F01-BR01 |
| E1 | end | Handed to the courier | | |
| E2 | end | Nothing more happens | | |

## Scenarios

| ID | Type | Scenario | Path | Outcome |
|---|---|---|---|---|
| F01-SC1 | main | Customer pays cash on delivery | S1 S2 E1 | Handed to the courier |
| F01-SC2 | alternate | Customer pays online | S1 S2 E2 | Nothing more happens |

## Business rules

### F01-BR01. Cash on delivery goes to the courier

- **Rule:** An order paid cash on delivery (COD) is handed to the courier.
- **Applies when:** Always.
- **Example:** COD order 100045 is handed to the courier.
- **Reason:** Not known from the code. (unknown)

## Evidence

| Ref | File:line | Code |
|---|---|---|
| F01-BR01 | Checkout.java:12 | `if ("COD".equals(method)) {` |

## Questions for the SME

None.
"""

NOT_IN_RULE = """## Decision lines not in a rule

| File:line | Code | Why |
|---|---|---|
| Checkout.java:18 | `method.length() > 3 ? "EXPRESS" : "STANDARD"` | Decides the courier service printed (O01) |

## Questions for the SME"""

SUMMARY = """# Business summary: SHOP

## In one paragraph

The shop takes orders and hands cash on delivery orders to the courier.

## Who and what is involved

| Who or what | Role in the process |
|---|---|
| Customer | Places orders. |

## The process from start to end

| # | What happens | Based on |
|---|---|---|
| 1 | A customer places an order and chooses how to pay. | F01-BR01, F01-SC1 |

## A worked example

| # | What happens | Based on |
|---|---|---|
| 1 | Order 100045 is paid cash on delivery and handed to the courier. | F01-SC1 |

## What can go wrong

| Situation | What happens | Based on |
|---|---|---|
| The customer pays online | Nothing more happens here. | F01-SC2 |

## Words to know

| Term | Meaning |
|---|---|
| COD | Cash on delivery |

## Questions for the SME

None.
"""


def write(path: Path, text: str, when: float = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if when is not None:
        os.utime(path, (when, when))


class Shop(unittest.TestCase):
    """A small shop module, its input folder and a reviewed discovery."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        write(root / "src" / "shop" / "Checkout.java", JAVA)
        write(root / "doc-input" / "module.md", "| Key | Value |\n|---|---|\n| Name | SHOP |\n"
                                                "| Business domain | Online shop |\n| Source folders | src |\n")
        write(root / "doc-input" / "business" / "codes.md", CODES)
        write(root / "doc-input" / "glossary.csv", "term,meaning,source\nCourier,The company that delivers,ops\n")
        self.paths = Paths(root, root / "doc-input", root / "doc-output", Module.load(root / "doc-input"))
        scan.save(scan.scan(self.paths), self.paths)
        write(self.paths.discovery, DISCOVERY, 1000)
        self.discovery = Discovery.load(self.paths.discovery)

    def tearDown(self):
        self.dir.cleanup()

    def flow_problems(self, text):
        write(self.paths.unit_file("F01"), text)
        plan = Plan.build(self.discovery, self.paths, 0)
        return checks.unit_problems(plan.unit("F01"), self.paths, self.discovery)


class DecisionLinesTest(Shop):
    def test_scan_lists_decisions_but_not_logging(self):
        lines = [c.line for c in coverage.conditions(coverage.reaches(self.paths, self.discovery, "F01"))]
        self.assertIn(12, lines)  # if ("COD".equals(method))
        self.assertIn(18, lines)  # the ternary
        self.assertNotIn(9, lines)  # if (log.isDebugEnabled())

    def test_a_decision_line_left_out_is_reported_and_can_be_placed(self):
        problems = " ".join(self.flow_problems(FLOW))
        self.assertIn("Checkout.java:18", problems)
        self.assertNotIn("Checkout.java:12", problems)
        self.assertEqual(self.flow_problems(FLOW.replace("## Questions for the SME", NOT_IN_RULE)), [])

    def test_a_wide_citation_covers_nothing(self):
        wide = FLOW.replace("Checkout.java:12 |", "Checkout.java:1-20 |")
        self.assertIn("Checkout.java:12", " ".join(self.flow_problems(wide)))

    def test_a_code_value_needs_a_rule_or_scenario(self):
        text = FLOW.replace("## Questions for the SME", NOT_IN_RULE).replace("(COD)", "").replace("(COD) ", "")
        text = text.replace("COD order", "Order")
        self.assertIn("`COD`", " ".join(self.flow_problems(text)))

    def test_conditions_report(self):
        write(self.paths.unit_file("F01"), FLOW)
        report = coverage.report(self.paths, self.discovery, "F01")
        self.assertIn("| yes | src/shop/Checkout.java:12 |", report)
        self.assertIn("| no | src/shop/Checkout.java:18 |", report)


class TermsTest(Shop):
    def test_meanings_from_glossary_and_business_tables(self):
        found = terms.defined(self.paths.input)
        self.assertEqual(found["cod"].meaning, "Payment method: Cash on delivery")
        self.assertEqual(found["online"].meaning, "Payment method: paid online")
        self.assertEqual(found["online"].source, "business/codes.md")
        self.assertEqual(found["courier"].source, "ops")

    def test_a_code_of_two_kinds_keeps_both_meanings(self):
        write(self.paths.input / "business" / "tiers.md", "| Code | Kind | Meaning |\n|---|---|---|\n"
                                                          "| EXPRESS | Customer tier | Pays for speed |\n")
        self.assertEqual(terms.defined(self.paths.input)["express"].meaning,
                         "Courier service: Next day / Customer tier: Pays for speed")

    def test_caps_terms_skip_ids_tables_and_technical_words(self):
        text = "F01-BR02: order PENDING_PAYMENT in ORDERS.STATUS, sent by HTTP POST; `NOT_PROSE` stays."
        self.assertEqual(terms.caps_terms(text), ["PENDING_PAYMENT"])

    def test_an_undefined_term_needs_a_question(self):
        text = FLOW.replace("## Questions for the SME", NOT_IN_RULE).replace("Nothing more happens", "Status HOLD")
        self.assertIn("`HOLD`", " ".join(self.flow_problems(text)))
        asked = text.replace("None.\n", "| # | Question | What the system does today |\n|---|---|---|\n"
                                       "| 1 | What does HOLD mean? | Nothing more happens |\n")
        self.assertEqual(self.flow_problems(asked), [])

    def test_code_in_flow_text_is_rejected(self):
        text = FLOW.replace("## Questions for the SME", NOT_IN_RULE).replace("Always.", "When method == null.")
        self.assertIn("a code operator", " ".join(self.flow_problems(text)))

    def test_readme_counts_only_below_the_mark(self):
        readme = self.paths.input / "business" / "README.md"
        write(readme, "# guidance\n\nCodes go here.\n\n<!-- Write your business context below this line. -->\n")
        self.assertNotIn(readme, business_files(self.paths.input))
        write(readme, readme.read_text(encoding="utf-8") + "\n| Code | Meaning |\n|---|---|\n| VIP | Top buyer |\n")
        self.assertIn(readme, business_files(self.paths.input))
        self.assertEqual(terms.defined(self.paths.input)["vip"].meaning, "Top buyer")


class PlanTest(Shop):
    def test_the_explanation_plan_is_required(self):
        self.assertEqual(checks.discovery_problems(self.paths), [])
        write(self.paths.discovery, DISCOVERY.split("## 8.")[0])
        self.assertIn("is missing", " ".join(checks.discovery_problems(self.paths)))

    def test_reading_order_names_every_flow_and_terms_need_a_meaning(self):
        write(self.paths.discovery, DISCOVERY.replace("| Reading order | F01 |", "| Reading order | first the order |")
              .replace("| COD |", "| COD, SPLIT |"))
        problems = " ".join(checks.discovery_problems(self.paths))
        self.assertIn("Reading order does not name F01", problems)
        self.assertIn("`SPLIT`", problems)
        self.assertNotIn("`COD`", problems)


class SummaryTest(Shop):
    def setUp(self):
        super().setUp()
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE))
        self.plan = Plan.build(self.discovery, self.paths, 0)

    def problems(self, text):
        write(self.paths.unit_file("SUMMARY"), text)
        return checks.unit_problems(self.plan.unit("SUMMARY"), self.paths, self.discovery)

    def test_a_complete_summary_passes(self):
        self.assertEqual(self.problems(SUMMARY), [])

    def test_every_scenario_and_planned_term(self):
        text = SUMMARY.replace("| F01-SC2 |", "| F01-BR01 |").replace("| COD | Cash on delivery |\n", "")
        problems = " ".join(self.problems(text))
        self.assertIn("Scenario F01-SC2 is not in the summary", problems)
        self.assertIn("says to explain `COD` first", problems)

    def test_words_need_a_meaning_from_the_input(self):
        text = SUMMARY.replace("| COD | Cash on delivery |", "| COD | Cash on delivery |\n| HOLD | Waiting |")
        self.assertIn("`HOLD` has no meaning", " ".join(self.problems(text)))


class ReadabilityTest(unittest.TestCase):
    def test_measure_counts_sentences_and_long_ones(self):
        long = " ".join(["word"] * 30) + "."
        m = readability.measure(f"# Title\n\nShort one here. {long}\n\n| A | B |\n|---|---|\n| One cell of text | x |\n")
        self.assertEqual((m.sentences, m.long_sentences), (3, 1))

    def test_reading_counts_points_and_ignores_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "F01.md"
            write(path, "## 2. Unclear points\n\n| # | Where | What a newcomer cannot follow | Suggestion |\n"
                        "|---|---|---|---|\n| 1 | F01-BR01 | What is a courier? | Say it |\n\n"
                        "## 3. Result\n\n**Verdict:** UNCLEAR\n")
            self.assertEqual((readability.reading(path).verdict, len(readability.reading(path).points)),
                             ("UNCLEAR", 1))
            write(path, "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n")
            self.assertEqual(readability.reading(path).points, [])


class ReaderLoopTest(Shop):
    """The run after a flow is checked: the newcomer reads it, the writer rewrites what was unclear, the second
    reader checks the facts again, then the summary is written."""

    def setUp(self):
        super().setUp()
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 2000)
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2001)

    def next(self):
        return Run(self.paths).next()

    def test_read_rewrite_verify_then_summary(self):
        action = self.next()
        self.assertEqual((action.kind, action.agent), ("TASK", "doc-reader"))
        self.assertIn("4-reader.md", action.text)
        reader = self.paths.reader_file("F01")
        write(reader, "## 2. Unclear points\n\n| # | Where | What a newcomer cannot follow | Suggestion |\n"
                      "|---|---|---|---|\n| 1 | F01-BR01 | What is a courier? | Say it |\n\n**Verdict:** UNCLEAR\n", 2002)
        action = self.next()
        self.assertEqual(action.agent, "doc-explainer")
        self.assertIn("reader/F01.md", action.text)
        self.assertIn("Change no fact", action.text)
        write(self.paths.unit_file("F01"), self.paths.unit_file("F01").read_text(encoding="utf-8"), 2003)
        self.assertEqual(self.next().agent, "doc-verifier")
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2004)
        self.assertEqual(self.next().agent, "doc-reader")
        write(reader, "## 2. Unclear points\n\nNone.\n\n**Verdict:** CLEAR\n", 2005)
        action = self.next()
        self.assertEqual(action.agent, "doc-writer")
        self.assertEqual(Plan.load(self.paths).unclear["F01"], [1, 0])

    def test_rewrites_stop_after_the_last_round(self):
        plan = Plan.build(self.discovery, self.paths, self.paths.discovery.stat().st_mtime)
        plan.reader_rounds["F01"] = 2
        plan.unclear["F01"] = [3, 2]
        plan.save(self.paths)
        write(self.paths.reader_file("F01"), "## 2. Unclear points\n\n| # | Where | What a newcomer cannot follow | "
                                             "Suggestion |\n|---|---|---|---|\n| 1 | S2 | COD? | Say it |\n\n"
                                             "**Verdict:** UNCLEAR\n", 2002)
        self.assertEqual(self.next().agent, "doc-writer")
        self.assertEqual(Plan.load(self.paths).unclear["F01"], [3, 2, 1])


class DocumentTest(Shop):
    def test_summary_first_glossary_and_readability(self):
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE).replace(
            "Nothing more happens |\n\n## Business", "Nothing more happens |\n\n## Business"), 2000)
        write(self.paths.unit_file("SUMMARY"), SUMMARY, 2001)
        write(self.paths.reader_file("F01"), "## 2. Unclear points\n\n| # | Where | What a newcomer cannot follow | "
                                             "Suggestion |\n|---|---|---|---|\n| 1 | S2 | COD? | Say it |\n\n"
                                             "**Verdict:** UNCLEAR\n")
        plan = Plan.build(self.discovery, self.paths, 0)
        plan.unclear["F01"] = [4, 1]
        guide, reference, _ = document.build(self.paths, plan, self.discovery)
        titles = [t for _, level, t in markdown.headings(guide) if level == 2]
        self.assertEqual(titles[0], "1. Business summary")
        self.assertIn("Start with section 1", guide)
        self.assertNotIn("Overview", titles)  # flows and fields are in the reference only
        self.assertIn("SHOP-reference.md#", guide)  # ids in the guide link into the reference
        text = guide + reference
        self.assertIn("| EXPRESS | Courier service: Next day | business/codes.md |", text)
        self.assertIn("| F01 Place an order | 4 → 1 | 1 |", text)
        self.assertIn("The newcomer found 4 unclear points on the first reading; 1 are left.", text)
        self.assertIn("### Still unclear in F01", text)
        self.assertNotIn("Decision lines not in a rule", text)


if __name__ == "__main__":
    unittest.main()
