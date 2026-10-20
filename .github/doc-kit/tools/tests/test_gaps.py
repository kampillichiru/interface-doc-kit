"""Tests of the gaps a run must not leave silent: calls the scan cannot follow, data the code depends on, large
flows, what the test data proves, SME answers, and the verifier's spot check.
Run from the tools folder: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dockit import checks, java_index, proof, scan  # noqa: E402
from dockit.discovery import Discovery  # noqa: E402
from dockit.plan import Plan  # noqa: E402
from dockit.project import Module, Paths  # noqa: E402
from dockit.workflow import Run  # noqa: E402
from test_newcomer import DISCOVERY, FLOW, NOT_IN_RULE, Shop, write  # noqa: E402

GATE = "package shop;\n\npublic interface Gate {\n    void pay(String method);\n}\n"
CARD = ("package shop;\n\npublic class Card implements Gate {\n    public void pay(String method) {\n"
        "        System.out.println(method);\n    }\n}\n")
CHECKOUT = """package shop;

public class Checkout {
    private Gate gate;

    public static void main(String[] args) {
        new Checkout().place(args[0]);
    }

    void place(String method) {
        if ("COD".equals(method)) {
            hand(method);
        }
        gate.pay(method);
        String sql = "SELECT CODE FROM ORDER_STATUS_PARAM WHERE CODE = ?";
    }

    void hand(String method) {
        String service = method.length() > 3 ? "EXPRESS" : "STANDARD";
        System.out.println(service);
    }
}
"""


class UnfollowedCallTest(unittest.TestCase):
    def test_a_call_through_an_interface_is_listed(self):
        index = java_index.build([("Gate.java", GATE), ("Card.java", CARD), ("Checkout.java", CHECKOUT)])
        place = next(m for m in index.methods if m.key == "Checkout.place")
        self.assertEqual(place.unfollowed, [14])  # gate.pay(method): Gate has no body for pay


class InterfaceShop(Shop):
    """The shop, with a payment gate behind an interface and a status parameter table it only reads."""

    def setUp(self):
        super().setUp()
        root = self.paths.workspace
        write(root / "src" / "shop" / "Gate.java", GATE)
        write(root / "src" / "shop" / "Card.java", CARD)
        write(root / "src" / "shop" / "Checkout.java", CHECKOUT)
        scan.save(scan.scan(self.paths), self.paths)

    def flow(self, extra=""):
        text = FLOW.replace("src/shop/Checkout.java:4", "src/shop/Checkout.java:6").replace(
            "| F01-BR01 | Checkout.java:12 |", "| F01-BR01 | Checkout.java:11 |").replace(
            "## Questions for the SME", NOT_IN_RULE.replace("Checkout.java:18", "src/shop/Checkout.java:19").replace(
                '`method.length() > 3 ? "EXPRESS" : "STANDARD"`',
                '`String service = method.length() > 3 ? "EXPRESS" : "STANDARD";`') + extra)
        return " ".join(self.flow_problems(text))


class CallsNotFollowedTest(InterfaceShop):
    def test_the_flow_must_say_where_the_call_leads(self):
        write(self.paths.discovery, DISCOVERY.replace("Checkout.java:4", "Checkout.java:6"), 1000)
        self.discovery = Discovery.load(self.paths.discovery)
        self.assertIn("could not follow the call at src/shop/Checkout.java:14", self.flow())
        listed = ("\n\n## Calls not followed by the tool\n\n| File:line | Code | Where it leads |\n|---|---|---|\n"
                  "| src/shop/Checkout.java:14 | `gate.pay(method);` | Card, the card payment gate |\n\n"
                  "## Questions for the SME")
        self.assertNotIn("could not follow the call", self.flow(listed))


class DependencyTest(InterfaceShop):
    def discovery_with(self, extra):
        write(self.paths.discovery, DISCOVERY.replace("Checkout.java:4", "Checkout.java:6") + extra, 1000)
        return " ".join(checks.discovery_problems(self.paths))

    def test_a_table_the_code_only_reads_needs_its_content(self):
        self.assertIn("`ORDER_STATUS_PARAM` is read by the documented flows", self.discovery_with(""))
        section = ("\n## 9. Data the code depends on\n\n| Table or procedure | What it decides | Content |\n"
                   "|---|---|---|\n| ORDER_STATUS_PARAM | Which statuses can be shipped | business/status.csv |\n")
        self.assertIn("is not a file in the input folder", self.discovery_with(section))
        write(self.paths.input / "business" / "status.csv", "code,meaning\nSHIPPED,Handed to the courier\n")
        self.assertNotIn("ORDER_STATUS_PARAM", self.discovery_with(section))

    def test_a_large_flow_is_split_or_kept_with_a_reason(self):
        saved, scan.LARGE_FLOW_LINES = scan.LARGE_FLOW_LINES, 5
        try:
            deps = ("\n## 9. Data the code depends on\n\n| Table or procedure | What it decides | Content |\n"
                    "|---|---|---|\n| ORDER_STATUS_PARAM | Statuses | input |\n")
            self.assertIn("F01 reaches about", self.discovery_with(deps))
            kept = deps + "\n## 10. Large flows kept whole\n\n| Flow | Why |\n|---|---|\n| F01 | One business step |\n"
            self.assertNotIn("F01 reaches about", self.discovery_with(kept))
        finally:
            scan.LARGE_FLOW_LINES = saved


SPEC = "field,start,end,length\nSERVICE,1,8,8\n"
OUTPUT = """# O01. Courier service printed (fields 1-1)

## 01. SERVICE (positions 1-8)

**Meaning:** The courier service.
**Kind:** Variant by payment method
**Source:** calculated
**When missing:** Never.

### Requirements

| ID | Requirement | Business rule |
|---|---|---|
| O01-01-R1 | The SERVICE shall be EXPRESS for cash on delivery, else STANDARD. | F01-BR01 |

### Decision table

| Payment method | Value written | Requirement |
|---|---|---|
| COD | `EXPRESS·` | O01-01-R1 |
| ONLINE | `STANDARD` | O01-01-R1 |

### Examples

| # | Flow | Input | Written | Requirement |
|---|---|---|---|---|
| 1 | F01 | COD | `EXPRESS·` | O01-01-R1 |

### Evidence

| Hop | File:line | Code |
|---|---|---|
| Writer | src/shop/Checkout.java:19 | `String service = method.length() > 3 ? "EXPRESS" : "STANDARD";` |

## Questions for the SME

| # | Question | What the system does today |
|---|---|---|
| 1 | Should online orders get the express service? | They get STANDARD. |
"""


class OutputShop(Shop):
    """The shop with its printed courier service as an output with a spec, and the data check on."""

    def setUp(self):
        super().setUp()
        root = self.paths.workspace
        write(root / "doc-input" / "module.md", "| Key | Value |\n|---|---|\n| Name | SHOP |\n| Business domain | "
              "Online shop |\n| Source folders | src |\n| Data check | yes |\n")
        write(root / "doc-input" / "outputs" / "O01.csv", SPEC)
        self.paths = Paths(root, root / "doc-input", root / "doc-output", Module.load(root / "doc-input"))
        scan.save(scan.scan(self.paths), self.paths)
        write(self.paths.discovery, DISCOVERY.replace("| src/shop/Checkout.java:19 | none |",
                                                      "| src/shop/Checkout.java:19 | outputs/O01.csv |"), 1000)
        self.discovery = Discovery.load(self.paths.discovery)
        write(self.paths.unit_file("F01"), FLOW.replace("## Questions for the SME", NOT_IN_RULE), 2000)
        write(self.paths.verify_file("F01"), "**Verdict:** PASS\n", 2001)
        write(self.paths.unit_file("O01"), OUTPUT, 2002)
        self.plan = Plan.build(self.discovery, self.paths, self.paths.discovery.stat().st_mtime)


class ProofTest(OutputShop):
    def test_a_case_missing_from_the_test_data_is_named(self):
        write(self.paths.input / "test-data" / "O01" / "actual.dat", "EXPRESS \n")
        write(self.paths.input / "test-data" / "O01" / "expected.dat", "EXPRESS \n")
        shown = proof.compute(self.paths, self.plan, self.discovery)
        rule = next(r for r in shown.rules if r.rule == "F01-BR01")
        self.assertEqual(rule.status, proof.PARTLY)
        self.assertEqual([c.value for c in shown.missing], ["STANDARD"])
        self.assertIn("1 cases never occur in the test data", proof.guide_section(shown))

    def test_every_case_in_the_data_proves_the_rule(self):
        write(self.paths.input / "test-data" / "O01" / "actual.dat", "EXPRESS \nSTANDARD\n")
        write(self.paths.input / "test-data" / "O01" / "expected.dat", "EXPRESS \nSTANDARD\n")
        shown = proof.compute(self.paths, self.plan, self.discovery)
        self.assertEqual(next(r for r in shown.rules if r.rule == "F01-BR01").status, proof.PROVEN)
        self.assertIn("**1 of 1 business rules are proven by the test data**", proof.guide_section(shown))


class SmeAnswerTest(OutputShop):
    def test_an_answer_goes_to_the_part_that_asked_once(self):
        write(self.paths.input / "sme-answers.md", "| # | Question | Answer | Answered by | Date |\n|---|---|---|---|---|\n"
              "| 1 | Should online orders get the express service? | No, only cash on delivery. | Ops | 2026-10-20 |\n")
        action = Run(self.paths).next()
        self.assertEqual((action.agent, "Unit: O01." in action.text), ("doc-explainer", True))
        self.assertIn("sme-answers.md", action.text)
        self.assertNotIn("Apply the SME", Run(self.paths).next().text)  # sent once


class SpotCheckTest(OutputShop):
    def test_the_verifier_must_trace_the_field_itself_and_agree(self):
        unit = self.plan.unit("O01")
        self.assertEqual([f.name for f in checks.spot_fields(unit, self.paths, self.discovery)], ["SERVICE"])
        write(self.paths.verify_file("O01"), "## Spot check\n\n| Field | Source | Business rule |\n|---|---|---|\n"
              "| SERVICE | method length | F01-BR02 |\n\n**Verdict:** PASS\n", 3000)
        self.assertIn("the unit file names F01-BR01", " ".join(checks.spot_problems(unit, self.paths, self.discovery)))
        write(self.paths.verify_file("O01"), "## Spot check\n\n| Field | Source | Business rule |\n|---|---|---|\n"
              "| SERVICE | method length | F01-BR01 |\n\n**Verdict:** PASS\n", 3001)
        self.assertEqual(checks.spot_problems(unit, self.paths, self.discovery), [])


if __name__ == "__main__":
    unittest.main()
