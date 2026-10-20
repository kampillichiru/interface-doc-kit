"""Files with several record layouts (header, detail, trailer), and the Types section of a concept page.
Run from the tools folder: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import checks, compare, markdown, spec  # noqa: E402
from dockit.project import Module, Paths  # noqa: E402

SPEC = """record,field,start,end,length,type,description
H,HDR_TYPE,1,1,1,A,Record type H
H,RUN_DATE,2,9,8,N,Run date
D,DET_TYPE,1,1,1,A,Record type D
D,ORDER_NO,2,7,6,A,Order number
D,AMOUNT,8,12,5,N,Amount
T,TRL_TYPE,1,1,1,A,Record type T
T,RECORD_COUNT,2,4,3,N,Number of details
"""


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "s.csv").write_text(SPEC, encoding="utf-8")
        self.fields = spec.load(self.root / "s.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_each_layout_starts_at_one(self):
        self.assertEqual(spec.records(self.fields), ["H", "D", "T"])
        self.assertEqual(spec.problems(self.fields), [])
        self.assertEqual(self.fields[3].label, "D ORDER_NO")

    def test_a_layout_with_a_gap_or_a_missing_record_is_named(self):
        (self.root / "bad.csv").write_text("record,field,start,end\nH,A,1,1\nH,B,3,4\nD,C,2,3\n,X,4,4\n",
                                           encoding="utf-8")
        found = spec.problems(spec.load(self.root / "bad.csv"))
        self.assertTrue(any("some fields only" in p for p in found))
        self.assertTrue(any("H B starts at 3" in p for p in found))
        self.assertTrue(any("record D must start at position 1" in p for p in found))

    def test_each_line_is_read_with_its_own_layout(self):
        (self.root / "e.dat").write_text("H20261016\nDORD00100500\nT001\n", encoding="utf-8")
        (self.root / "a.dat").write_text("H20261016\nDORD00100499\nT001\n", encoding="utf-8")
        result = compare.compare(self.fields, self.root / "e.dat", self.root / "a.dat")
        self.assertEqual(result.fields["D AMOUNT"], 1)
        self.assertEqual(sum(result.fields.values()), 1)  # header and trailer are not read as details
        self.assertEqual(result.field_result("H RUN_DATE"), "MATCH")


class TypesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "in").mkdir()
        module = Module("SHOP", "", "Orders", ["src"], False)
        self.paths = Paths(root, root / "in", root / "out", module)
        self.item = SimpleNamespace(flows=[])

    def tearDown(self):
        self.dir.cleanup()

    def rows(self, table):
        return markdown.first_table(table)

    def test_a_types_table_is_required(self):
        self.assertTrue(checks._types(self.item, [], self.paths, None, set())[0].endswith("has no table."))

    def test_each_type_says_how_it_is_handled_with_an_example(self):
        rows = self.rows("| Type | Meaning | How the system handles it | Example | Based on |\n|---|---|---|---|---|\n"
                         "| `COD` | Cash on delivery | | | F01-BR02 |\n")
        found = checks._types(self.item, rows, self.paths, None, {"F01-BR02"})
        self.assertEqual(len(found), 2)
        self.assertTrue(all("is empty" in p for p in found))


if __name__ == "__main__":
    unittest.main()
