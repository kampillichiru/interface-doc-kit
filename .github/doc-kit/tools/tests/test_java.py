"""Tests of the Java index and the Java parts of the scan. Run: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dockit import java_index, scan  # noqa: E402

CODES = """package x;
/** codes */
public interface Codes {
    // types
    String TYPE_A = "PP";
    String TYPE_B = "COD";
    int STATUS_ACTIVE = 1;
    int STATUS_CLOSED = 9;
    char YES = 'Y';
}
"""
SHIP_METHOD = """package x;
public enum ShipMethod {
    STANDARD("STD"),
    EXPRESS("EXP");
    private final String code;
    ShipMethod(String code) { this.code = code; }
}
"""
DAO = """package x;
import java.sql.*;
public class Dao {
    private static final String SQL_ALL = "SELECT A FROM T "
            + "WHERE STATUS = " + Codes.STATUS_ACTIVE + " AND B = ?";
    private final Connection con;
    public Dao(Connection con) { this.con = con; }
    public void load(String b) throws Exception {
        PreparedStatement ps = con.prepareStatement(SQL_ALL);
        ResultSet rs = ps.executeQuery();
        rs.close();
    }
    public void area(char a) throws Exception {
        StringBuffer sql = new StringBuffer();
        sql.append("SELECT M FROM P WHERE T = ?");
        if (a == Codes.YES) {
            sql.append(" AND AREA = 'U'");
        }
    }
    public void close() { }
}
"""
JOB = """package x;
import java.util.*;
public class Job extends TimerTask {
    private Dao dao;
    public void run() {
        dao.load("1");
        if (Codes.TYPE_A.equals(type())) { }
        switch (type()) {
            case Codes.TYPE_B:
                break;
        }
        if (status() == 9) { }
        if (count() == 0) { }
    }
    String type() { return "PP"; }
    int status() { return 1; }
    int count() { return 0; }
}
"""
STARTER = """package x;
import java.util.Timer;
public class Starter {
    public void start() {
        new Timer().schedule(new Job(), 1000L);
    }
}
"""
FILES = [("x/Codes.java", CODES), ("x/ShipMethod.java", SHIP_METHOD), ("x/Dao.java", DAO), ("x/Job.java", JOB),
         ("x/Starter.java", STARTER)]


class JavaIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = java_index.build(FILES)

    def test_every_interface_constant_is_found(self):
        values = {k: c.value for k, c in self.index.constants.items() if k.startswith("Codes.")}
        self.assertEqual(values, {"Codes.TYPE_A": "PP", "Codes.TYPE_B": "COD", "Codes.STATUS_ACTIVE": "1",
                                  "Codes.STATUS_CLOSED": "9", "Codes.YES": "Y"})

    def test_enum_values_and_codes(self):
        self.assertEqual(self.index.enums["ShipMethod"], ["STANDARD", "EXPRESS"])
        self.assertEqual(self.index.enum_codes["ShipMethod"], {"STANDARD": '"STD"', "EXPRESS": '"EXP"'})

    def test_method_lines(self):
        load = next(m for m in self.index.methods if m.key == "Dao.load")
        self.assertEqual((load.start, load.end), (8, 12))

    def test_calls_follow_field_types_and_skip_library_types(self):
        run = next(m for m in self.index.methods if m.key == "Job.run")
        self.assertIn("Dao.load", run.calls)
        load = next(m for m in self.index.methods if m.key == "Dao.load")
        self.assertNotIn("Dao.close", load.calls)  # rs.close() is ResultSet.close, not Dao.close

    def test_new_timer_task_links_to_run(self):
        start = next(m for m in self.index.methods if m.key == "Starter.start")
        self.assertIn("Job.run", start.calls)
        self.assertIn("Dao.load", [m.key for m in self.index.reach(start)])

    def test_comments_and_strings_are_masked(self):
        masked = java_index.mask('a = "x // y"; // note\nb = 1;')
        self.assertNotIn("note", masked)
        self.assertNotIn("y", masked.split("\n")[0][4:12])


class JavaScanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = java_index.build(FILES)
        cls.inv = scan.Inventory()
        for name, text in FILES:
            scan._scan_java(cls.inv, cls.index, name, text)

    def test_sql_with_constant_is_filled_in(self):
        hit = next(h for h in self.inv.sql if "SQL_ALL" in h.text)
        self.assertEqual(hit.value, "SELECT A FROM T WHERE STATUS = 1 AND B = ?")
        self.assertNotIn("dynamic", hit.text)

    def test_append_sql_is_reported_once(self):
        found = [h for h in self.inv.sql if "ROM P" in h.value or "FROM P" in h.value]
        self.assertEqual(len(found), 1)
        self.assertIn("append", found[0].kind)

    def test_comparisons_resolve_constants(self):
        values = {h.value.split(" ")[0] for h in self.inv.comparisons}
        self.assertTrue({"PP", "COD", "9", "Y", "U", "STATUS"} <= values, values)
        self.assertNotIn("0", values)  # count == 0 is not a code

    def test_sql_comparisons(self):
        hits = scan._sql_comparisons("f.sql", "WHERE S IN ('A', 'B') AND T = 3 AND x := 'Q'")
        self.assertEqual([h.value for h in hits], ["'A', 'B'", "T = 3"])


if __name__ == "__main__":
    unittest.main()
