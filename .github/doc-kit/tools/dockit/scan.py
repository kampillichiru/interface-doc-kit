"""Inventory of a Java backend: entry points and what they reach, SQL, outputs, code comparisons, settings.

Pattern based, so it lists candidates; the discover agent decides what they mean. Its value is that it
is complete: an agent asked to search a large codebase misses things, a scan does not.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

from . import java_index
from .project import Paths

JAVA = {".java"}
SQL = {".sql", ".pks", ".pkb", ".prc", ".fnc", ".trg", ".vw"}
XML = {".xml"}
CONFIG = {".properties", ".yml", ".yaml", ".conf", ".ini"}
SKIP_DIRS = {".git", "target", "build", "node_modules", ".idea", ".vscode", "bin", "out", "test", "tests"}
MAX_REACH = 60
LARGE_FLOW_LINES = 1500
VERSION = 3  # of the inventory: an older one is written again when the sources have not changed

_I = re.IGNORECASE
_SQL_START = re.compile(r"^\s*\(?\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)\b", _I)
SQL_KIND = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|MERGE)\b", _I)
TABLES = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE|MERGE\s+INTO)\s+([A-Za-z_][\w.$]*)", _I)
CODE_TABLE = re.compile(r"(REF|CODE|LOOKUP|LKP|TYPE|PARAM|MASTER|CONFIG|DOMAIN|STATUS)", _I)

# Entry points written as annotations or signatures; methods named main, doGet... are found from the index.
ENTRY_PATTERNS: List[Tuple[str, Pattern]] = [
    ("rest", re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping\b[^\n]*")),
    ("rest", re.compile(r"@(GET|POST|PUT|DELETE)\b")),
    ("soap", re.compile(r"@WebMethod\b[^\n]*")),
    ("listener", re.compile(r"@(JmsListener|KafkaListener|RabbitListener|EventListener|MessageDriven)\b[^\n]*")),
    ("scheduled", re.compile(r"@(Scheduled|Schedule)\b[^\n]*")),
]
ENTRY_METHODS = {  # method name -> (kind, condition on the class header or the parameters)
    "main": ("main", lambda m, t: "String" in m.params),
    "doGet": ("servlet", lambda m, t: True), "doPost": ("servlet", lambda m, t: True),
    "doPut": ("servlet", lambda m, t: True), "doDelete": ("servlet", lambda m, t: True),
    "service": ("servlet", lambda m, t: "HttpServletRequest" in m.params),
    "run": ("thread", lambda m, t: bool(re.search(r"Runnable|TimerTask|Thread|Callable", t.header))),
    "call": ("thread", lambda m, t: "Callable" in t.header),
    "execute": ("job", lambda m, t: bool(re.search(r"JobExecutionContext|ActionMapping|StepContribution",
                                                    m.params))),
    "onMessage": ("listener", lambda m, t: True),
    "contextInitialized": ("startup", lambda m, t: "ServletContextListener" in t.header),
    "afterPropertiesSet": ("startup", lambda m, t: "InitializingBean" in t.header),
}
OUTPUTS: List[Tuple[str, Pattern]] = [
    ("file", re.compile(r"new\s+(FileWriter|FileOutputStream|PrintWriter|BufferedWriter|OutputStreamWriter|"
                        r"RandomAccessFile)\b")),
    ("file", re.compile(r"\bFiles\.(write|writeString|newBufferedWriter|newOutputStream)\s*\(")),
    ("file", re.compile(r"\"[^\"\n]*\.(dat|txt|csv|out|fix|rpt|xls|xlsx)\"", _I)),
    ("console", re.compile(r"\bSystem\.(out|err)\.print")),
    ("file-line", re.compile(r"\b(?!System\b)\w+\.(write|println|print|newLine)\s*\(")),
    ("db-run", re.compile(r"\.(executeUpdate|executeBatch|addBatch|execute)\s*\(")),
    ("call-out", re.compile(r"\b\w+\.(send|convertAndSend|publish|produce|postForObject|exchange)\s*\(")),
    ("mail", re.compile(r"\b(Transport\.send|mailSender\.send)\s*\(")),
]
CALL_PROC = re.compile(r"\{\s*(?:\?\s*=\s*)?call\s+([\w.$]+)", _I)
COMPARE_LITERALS: List[Pattern] = [
    re.compile(r"\"([A-Za-z0-9_]{1,30})\"\s*\.\s*equals(?:IgnoreCase)?\s*\("),
    re.compile(r"\.\s*equals(?:IgnoreCase)?\s*\(\s*\"([A-Za-z0-9_]{1,30})\"\s*\)"),
    re.compile(r"\bcase\s+\"([^\"]{1,30})\"\s*:"),
    re.compile(r"\bcase\s+('.')\s*:"),
    re.compile(r"\bcase\s+(-?\d+)\s*:"),
    re.compile(r"[!=]=\s*('.'|-?\d{1,6})\b(?!\s*[.\d])"),
]
COMPARE_NAMES: List[Pattern] = [  # a name that may be a constant or an enum value
    re.compile(r"\b([A-Za-z_][\w.]*)\s*\.\s*equals(?:IgnoreCase)?\s*\("),
    re.compile(r"\.\s*equals(?:IgnoreCase)?\s*\(\s*([A-Za-z_][\w.]*)\s*\)"),
    re.compile(r"\bcase\s+([A-Za-z_][\w.]*)\s*:"),
    re.compile(r"[!=]=\s*([A-Z][\w.]*)\b"),
]
SQL_COMPARE: List[Pattern] = [
    re.compile(r"\bIN\s*\(\s*('[^']{1,30}'(?:\s*,\s*'[^']{1,30}')*)\s*\)", _I),
    re.compile(r"(?<!:)[=<>]\s*'([A-Za-z0-9_]{1,30})'"),
    re.compile(r"\b([A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)?\s*(?:=|<>|!=)\s*\d{1,4})\b(?!\s*[-+*/,)]?\s*\d)"),
    re.compile(r"\bDECODE\s*\(([^()]*'[^()]*)\)", _I),
    re.compile(r"\bWHEN\s+'([^']{1,30})'", _I),
]
CONFIG_READS = re.compile(r"@Value\(\s*\"\$\{([^}:\"]+)|getProperty\(\s*\"([^\"]+)\"|getString\(\s*\"([\w.]+)\"\)")
SETTING = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*[=:]\s*(.*?)\s*$")
SECRET = re.compile(r"pass|secret|token|credential|key(?!word)", _I)
PLSQL_UNITS = re.compile(r"^\s*(PROCEDURE|FUNCTION)\s+(\w+)\s*\(", _I | re.M)
SQL_DML = re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+([A-Za-z_][\w.$]*)", _I)
XML_SQL = re.compile(r"<(query|select|insert|update|delete|sql|statement|procedure)\b[^>]*\bid\s*=\s*\"([^\"]+)\"", _I)
SQL_OBJECTS = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|TRIGGER|PACKAGE\s+BODY|PACKAGE|VIEW)\s+([\w.$\"]+)", _I)
WEB_XML_SERVLET = re.compile(r"<servlet-name>\s*([^<]+?)\s*</servlet-name>\s*<servlet-class>\s*([^<]+?)\s*"
                             r"</servlet-class>", _I)
WEB_XML_MAPPING = re.compile(r"<servlet-name>\s*([^<]+?)\s*</servlet-name>\s*<url-pattern>\s*([^<]+?)\s*"
                             r"</url-pattern>", _I)
_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_CHAIN = re.compile(r'"(?:[^"\\\n]|\\.)*"(?:\s*\+\s*(?:"(?:[^"\\\n]|\\.)*"|[\w.()\[\]]+))*')
_APPEND = re.compile(r"\b([a-z]\w*)\s*\.\s*append\s*\(\s*(.*?)\s*\)\s*(?=[.;])")
# Decisions in Java (read on the text without comments and strings) and conditions in SQL: every line of a flow
# that can change what happens. The flow must cite each one, or say why it is not business.
JAVA_DECISION = re.compile(r"\b(?:if|while|switch|case|catch|throw)\b|\?[^;:?]*:|"
                           r"\.\s*(?:equals|equalsIgnoreCase|compareTo|isEmpty|isBlank|contains|startsWith|"
                           r"endsWith|matches)\s*\(|\bMath\.(?:max|min|abs)\b")
NOT_A_DECISION = re.compile(r"\b(?:log|logger|LOG|LOGGER)\s*\.|is(?:Debug|Trace|Info)Enabled|"
                            r"while\s*\(\s*\w+\s*\.\s*(?:next|hasNext)\s*\(\s*\)\s*\)")
SQL_CONDITION = re.compile(r"\b(?:WHERE|AND|OR|WHEN|HAVING|DECODE|NVL2?|COALESCE|CASE|EXISTS|ROWNUM)\b")
_XML_LINES = re.compile(r"; lines (\d+)-(\d+);")


@dataclass
class Hit:
    kind: str
    file: str
    line: int
    text: str
    value: str = ""


@dataclass
class Reach:
    entry: str  # entry point id
    kind: str
    method: str
    where: str
    methods: List[str] = field(default_factory=list)  # "Class.method file:start-end"
    sql: List[str] = field(default_factory=list)  # SQL ids
    lines: int = 0
    accessors: int = 0  # getters and setters reached, counted but not listed
    conditions: List[str] = field(default_factory=list)  # "file:line code" of every decision reached
    unfollowed: List[str] = field(default_factory=list)  # "file:line code" of every call the reach could not follow


@dataclass
class Inventory:
    files: Dict[str, int] = field(default_factory=dict)
    not_read: Dict[str, int] = field(default_factory=dict)
    entry_points: List[Hit] = field(default_factory=list)
    reach: List[Reach] = field(default_factory=list)
    sql: List[Hit] = field(default_factory=list)
    code_tables: List[str] = field(default_factory=list)
    outputs: List[Hit] = field(default_factory=list)
    comparisons: List[Hit] = field(default_factory=list)
    constants: List[Hit] = field(default_factory=list)
    settings: List[Hit] = field(default_factory=list)
    fingerprint: str = ""
    version: int = VERSION


# Reading the sources

def _source_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not SKIP_DIRS.intersection(p.lower() for p in path.relative_to(root).parts[:-1]):
                yield path


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _hits(kind: str, pattern: Pattern, text: str, name: str, scan_text: Optional[str] = None) -> List[Hit]:
    lines = text.splitlines()
    return [Hit(kind, name, n, lines[n - 1].strip()[:160])
            for n in sorted({_line_of(text, m.start()) for m in pattern.finditer(scan_text or text)})]


def _readable(paths: Paths) -> List[Tuple[Path, str, str]]:
    found = []
    for path in _source_files(paths.sources):
        ext = path.suffix.lower()
        if ext in JAVA | SQL | XML | CONFIG:
            found.append((path, paths.rel(path), ext))
    return found


def scan(paths: Paths) -> Inventory:
    inv = Inventory()
    java_files, xml_texts = [], {}
    for path in _source_files(paths.sources):
        ext = path.suffix.lower()
        if ext not in JAVA | SQL | XML | CONFIG:
            inv.not_read[ext or "(none)"] = inv.not_read.get(ext or "(none)", 0) + 1
            continue
        name = paths.rel(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        inv.files[name] = len(text.splitlines())
        if ext in JAVA:
            java_files.append((name, text))
        elif ext in SQL:
            _scan_sql_file(inv, name, text)
        elif ext in XML:
            xml_texts[name] = text
            _scan_xml(inv, name, text)
        else:
            _scan_config(inv, name, text)
    index = java_index.build(java_files)
    for name, text in java_files:
        _scan_java(inv, index, name, text)
    _entry_methods(inv, index)
    _reach(inv, index, xml_texts)
    inv.code_tables = sorted({t for hit in inv.sql for t in re.findall(r"tables: ([^;]*)", hit.text)
                              for t in t.split(", ") if CODE_TABLE.search(t)})
    inv.constants = [Hit("constant", c.file, c.line, f"{c.owner}.{c.name}", c.value)
                     for key, c in sorted(index.constants.items()) if "." in key]
    for name, values in sorted(index.enums.items()):
        typ = index.types[name]
        codes = index.enum_codes.get(name, {})
        inv.constants.append(Hit("enum", typ.file, typ.line, name,
                                 ", ".join(f"{v} ({codes[v]})" if v in codes else v for v in values)))
    inv.entry_points = _unique(inv.entry_points)
    inv.comparisons, inv.outputs = _unique(inv.comparisons), _unique(inv.outputs)
    inv.fingerprint = fingerprint(paths)
    return inv


def _scan_sql_file(inv: Inventory, name: str, text: str) -> None:
    for match in SQL_OBJECTS.finditer(text):
        inv.entry_points.append(Hit(match.group(1).upper(), name, _line_of(text, match.start()), match.group(2)))
    for match in PLSQL_UNITS.finditer(text):
        inv.entry_points.append(Hit(f"{match.group(1).upper()} (in package)", name,
                                    _line_of(text, match.start()), match.group(2)))
    for match in SQL_DML.finditer(text):
        line = _line_of(text, match.start())
        inv.sql.append(Hit(f"{match.group(1).split()[0].upper()} (sql)", name, line,
                           f"{match.group(2).upper()}; line {line}; tables: {match.group(2).upper()}"))
    inv.comparisons += _sql_comparisons(name, text)


def _sql_comparisons(name: str, sql: str, line_offset: int = 0) -> List[Hit]:
    """Codes compared in SQL text: IN lists, = 'X', COLUMN = 3, DECODE and CASE values."""
    found, lines = [], sql.splitlines() or [""]
    for pattern in SQL_COMPARE:
        for match in pattern.finditer(sql):
            line = _line_of(sql, match.start())
            found.append(Hit("sql", name, line + line_offset, lines[line - 1].strip()[:160], match.group(1).strip()))
    return found


def _scan_xml(inv: Inventory, name: str, text: str) -> None:
    for match in XML_SQL.finditer(text):
        close = text.find("</" + match.group(1), match.end())
        body = text[match.end():close if close > 0 else match.end() + 2000]
        line = _line_of(text, match.start())
        inv.sql.append(Hit(f"{_sql_kind(body)} (xml)", name, line, _describe(match.group(2), line,
                       _line_of(text, close) if close > 0 else line, body)))
    inv.comparisons += _sql_comparisons(name, text)
    servlets = dict(WEB_XML_SERVLET.findall(text))
    for servlet, url in WEB_XML_MAPPING.findall(text):
        if servlet in servlets:
            inv.entry_points.append(Hit("web.xml", name, _line_of(text, text.find(url)),
                                        f"{url} -> {servlets[servlet]}"))


def _scan_config(inv: Inventory, name: str, text: str) -> None:
    for number, line in enumerate(text.splitlines(), 1):
        match = SETTING.match(line)
        if not match or line.lstrip().startswith(("#", "!")):
            continue
        key, value = match.groups()
        if SECRET.search(key):
            value = "(secret, not shown)"
        if _SQL_START.match(value):
            inv.sql.append(Hit(f"{_sql_kind(value)} (config)", name, number, _describe(key, number, number, value)))
        inv.settings.append(Hit("setting", name, number, f"{key} = {value}"[:160]))


def _scan_java(inv: Inventory, index: java_index.JavaIndex, name: str, text: str) -> None:
    masked = index.masked[name]
    for kind, pattern in ENTRY_PATTERNS:
        inv.entry_points += _hits(kind, pattern, text, name, masked)
    for kind, pattern in OUTPUTS:
        inv.outputs += _hits(kind, pattern, text, name, masked if kind != "file" else text)
    inv.settings += [Hit("read", name, h.line, h.text) for h in _hits("read", CONFIG_READS, text, name)]
    before = len(inv.sql)
    _java_sql(inv, index, name, text)
    for hit in inv.sql[before:]:  # codes inside the SQL, with constants already filled in
        inv.comparisons += [Hit("sql", name, hit.line, f"{c.text}", c.value)
                            for c in _sql_comparisons(name, hit.value)]
    _java_comparisons(inv, index, name, text, masked)


def _java_sql(inv: Inventory, index: java_index.JavaIndex, name: str, text: str) -> None:
    """SQL built with append(), written as one string or a + chain, or a stored procedure call."""
    covered = set()  # lines already reported as part of an append-built SQL
    for method in (m for m in index.methods if m.file == name):
        body = text[method.body[0]:method.body[1]]
        pieces = {}
        for match in _APPEND.finditer(body):
            pieces.setdefault(match.group(1), []).append((match.group(2), method.body[0] + match.start()))
        for var, parts in pieces.items():
            sql, dynamic = _join(" + ".join(p for p, _ in parts), index, method.cls)
            if _SQL_START.match(sql):
                first, last = _line_of(text, parts[0][1]), _line_of(text, parts[-1][1])
                covered.update(range(first, last + 1))
                inv.sql.append(Hit(f"{_sql_kind(sql)} (java, append)", name, first,
                                   _describe(f"{method.key} {var}", first, last, sql, dynamic), sql[:300]))
    for match in _CHAIN.finditer(text):
        line = _line_of(text, match.start())
        method = index.method_at(name, line)
        sql, dynamic = _join(match.group(0), index, method.cls if method else "")
        if _SQL_START.match(sql) and line not in covered:
            covered.add(line)
            label = _owner_label(index, name, line, text, match.start())
            inv.sql.append(Hit(f"{_sql_kind(sql)} (java)", name, line,
                               _describe(label, line, _line_of(text, match.end()), sql, dynamic), sql[:300]))
    for match in CALL_PROC.finditer(text):
        line = _line_of(text, match.start())
        inv.sql.append(Hit("CALL (java)", name, line, _describe(match.group(1), line, line, match.group(0))))


def _join(expression: str, index: java_index.JavaIndex, owner: str) -> Tuple[str, int]:
    """The SQL text of a string expression. Constants are replaced by their values; other parts that are
    not literals are marked `?` and counted as dynamic."""
    parts, dynamic = [], 0
    for piece in re.split(r"\s*\+\s*(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", expression):
        piece = piece.strip()
        literal = _STRING.fullmatch(piece)
        constant = None if literal else index.resolve(piece, owner)
        if literal:
            parts.append(literal.group(1))
        elif constant:
            parts.append(constant.value)
        elif piece:
            parts.append(" ? ")
            dynamic += 1
    return re.sub(r"\s+", " ", "".join(parts)).strip(), dynamic


def _owner_label(index, name, line, text, offset) -> str:
    """Constant name when the SQL is assigned to one, else the method it is in."""
    before = text[max(0, offset - 120):offset]
    const = re.search(r"\b([A-Z][A-Z0-9_]*)\s*=\s*$", before)
    if const:
        return const.group(1)
    method = index.method_at(name, line)
    return method.key if method else "(field)"


def _describe(label: str, first: int, last: int, sql: str, dynamic: int = 0) -> str:
    tables = sorted({t.upper() for t in TABLES.findall(sql)})
    text = f"{label}; lines {first}-{last}; tables: {', '.join(tables) or '-'}"
    return text + (f"; built at run time ({dynamic} dynamic part(s))" if dynamic else "")


def _sql_kind(sql_text: str) -> str:
    found = SQL_KIND.search(sql_text)
    return found.group(1).upper() if found else "SQL"


def _java_comparisons(inv: Inventory, index: java_index.JavaIndex, name: str, text: str, masked: str) -> None:
    lines = text.splitlines()
    for pattern in COMPARE_LITERALS:
        for match in pattern.finditer(text):
            line = _line_of(text, match.start())
            if masked[match.start()] == " " and not text[match.start()].isspace():
                continue  # inside a comment
            if match.group(1) in {"0", "1", "-1"}:
                continue  # counts and flags, not codes
            inv.comparisons.append(Hit("literal", name, line, lines[line - 1].strip()[:160],
                                       match.group(1).strip("'")))
    for pattern in COMPARE_NAMES:
        for match in pattern.finditer(masked):
            expression = match.group(1)
            line = _line_of(text, match.start())
            method = index.method_at(name, line)
            constant = index.resolve(expression, method.cls if method else "")
            enum = _enum_of(index, expression)
            if constant:
                value = f"{constant.value} ({constant.owner}.{constant.name}, {constant.file}:{constant.line})"
                inv.comparisons.append(Hit("constant", name, line, lines[line - 1].strip()[:160], value))
            elif enum:
                inv.comparisons.append(Hit("enum", name, line, lines[line - 1].strip()[:160], enum))


def _enum_of(index: java_index.JavaIndex, expression: str) -> str:
    parts = expression.split(".")
    for enum, values in index.enums.items():
        if parts[-1] in values and (len(parts) == 1 or parts[-2] == enum):
            return f"{enum}.{parts[-1]}"
    return ""


def _entry_methods(inv: Inventory, index: java_index.JavaIndex) -> None:
    for method in index.methods:
        rule = ENTRY_METHODS.get(method.name)
        typ = index.types.get(method.cls)
        if rule and typ and rule[1](method, typ):
            inv.entry_points.append(Hit(rule[0], method.file, method.start, f"{method.key}({method.params})"))


def _reach(inv: Inventory, index: java_index.JavaIndex, xml_texts: Dict[str, str]) -> None:
    sql_by_method = {}
    for n, hit in enumerate(inv.sql, 1):
        method = index.method_at(hit.file, hit.line)
        if method:
            sql_by_method.setdefault((method.file, method.start), []).append(f"Q{n:02d}")
    xml_ids = {re.split(r";", h.text)[0]: f"Q{n:02d}" for n, h in enumerate(inv.sql, 1) if "(xml)" in h.kind}
    constant_sql = {re.split(r";", h.text)[0]: f"Q{n:02d}" for n, h in enumerate(inv.sql, 1)
                    if "(java)" in h.kind and re.match(r"[A-Z][A-Z0-9_]*;", h.text)}
    for n, hit in enumerate(_unique(inv.entry_points), 1):
        start = _method_for(index, hit)
        if not start:
            continue
        reached = index.reach(start, MAX_REACH)
        sql = []
        for m in reached:
            sql += sql_by_method.get((m.file, m.start), [])
            body = index.texts[m.file][m.body[0]:m.body[1]]
            sql += [q for key, q in xml_ids.items() if f'"{key.split("=")[-1]}"' in body]
            sql += [q for key, q in constant_sql.items() if re.search(rf"\b{key}\b", body)]
        listed = [m for m in reached if not index.is_accessor(m)]
        sql = sorted(set(sql))
        inv.reach.append(Reach(f"EP{n:02d}", hit.kind, start.key, start.where,
                               [f"{m.key} {m.where}" for m in listed], sql,
                               sum(m.end - m.start + 1 for m in reached), len(reached) - len(listed),
                               _conditions(index, listed, [inv.sql[int(q[1:]) - 1] for q in sql], xml_texts),
                               [f"{m.file}:{n} {index.texts[m.file].splitlines()[n - 1].strip()[:160]}"
                                for m in reached for n in m.unfollowed]))


def _conditions(index: java_index.JavaIndex, methods, sql_hits: List[Hit], xml_texts: Dict[str, str]) -> List[str]:
    """Every line of the reached methods and SQL that decides something: if, switch, ternary, catch, throw,
    comparisons; WHERE, AND, CASE and the like in SQL. Logging and `while (rs.next())` are left out."""
    found: List[str] = []
    for m in methods:
        text, masked = index.texts[m.file].splitlines(), index.masked[m.file].splitlines()
        for number in range(m.start, min(m.end, len(text)) + 1):
            code, bare = text[number - 1], masked[number - 1]
            strings = " ".join(_STRING.findall(code)) if bare.strip() else ""
            if (JAVA_DECISION.search(bare) and not NOT_A_DECISION.search(bare)) or SQL_CONDITION.search(strings):
                found.append(f"{m.file}:{number} {code.strip()[:160]}")
    for hit in sql_hits:
        lines = _XML_LINES.search(hit.text)
        if "(xml)" not in hit.kind or not lines or hit.file not in xml_texts:
            continue
        text = xml_texts[hit.file].splitlines()
        for number in range(int(lines.group(1)), min(int(lines.group(2)), len(text)) + 1):
            if SQL_CONDITION.search(text[number - 1].upper()):
                found.append(f"{hit.file}:{number} {text[number - 1].strip()[:160]}")
    return list(dict.fromkeys(found))


def _method_for(index: java_index.JavaIndex, hit: Hit):
    """The method an entry point hit belongs to: the one starting on or just below an annotation."""
    below = [m for m in index.methods if m.file == hit.file and 0 <= m.start - hit.line <= 5]
    return min(below, key=lambda m: m.start) if below else index.method_at(hit.file, hit.line)


def _unique(hits: List[Hit]) -> List[Hit]:
    seen, result = set(), []
    for hit in sorted(hits, key=lambda h: (h.file, h.line)):
        if (hit.file, hit.line, hit.value) not in seen:
            seen.add((hit.file, hit.line, hit.value))
            result.append(hit)
    return result


unique = _unique  # the entry points as numbered EP01, EP02 in the inventory


def tables_changed(inv: Inventory) -> set:
    """Tables the code inserts into, updates, deletes from or merges into."""
    return {m.group(2).split(".")[-1].strip('"').upper()
            for hit in inv.sql for m in SQL_DML.finditer(hit.value or hit.text)}


# Saving and showing

def fingerprint(paths: Paths) -> str:
    """Changes when any readable source file changes."""
    digest = hashlib.sha256()
    for path, name, _ in _readable(paths):
        digest.update(name.encode() + path.read_bytes())
    return digest.hexdigest()[:16]


def save(inv: Inventory, paths: Paths) -> None:
    paths.inventory_json.parent.mkdir(parents=True, exist_ok=True)
    paths.inventory_json.write_text(json.dumps(asdict(inv), indent=1), encoding="utf-8")
    paths.inventory_md.write_text(render(inv, paths), encoding="utf-8")


_LOADED: Dict[str, Tuple[float, "Inventory"]] = {}


def load(paths: Paths) -> Inventory:
    """The saved inventory. Read again only when its file changed: checks call this many times per run."""
    key, stamp = str(paths.inventory_json.resolve()), paths.inventory_json.stat().st_mtime
    if key in _LOADED and _LOADED[key][0] == stamp:
        return _LOADED[key][1]
    inv = _read(paths)
    _LOADED[key] = (stamp, inv)
    return inv


def _read(paths: Paths) -> Inventory:
    data = json.loads(paths.inventory_json.read_text(encoding="utf-8"))
    inv = Inventory(files=data["files"], not_read=data["not_read"], fingerprint=data["fingerprint"],
                    code_tables=data.get("code_tables", []), version=data.get("version", 1))
    for key in ("entry_points", "sql", "outputs", "comparisons", "constants", "settings"):
        setattr(inv, key, [Hit(**hit) for hit in data.get(key, [])])
    inv.reach = [Reach(**r) for r in data.get("reach", [])]
    return inv


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("`", "'")


def _table(title: str, prefix: str, hits: List[Hit], note: str, value: str = "") -> List[str]:
    out = [f"## {title}", "", note, ""]
    if not hits:
        return out + ["None found.", ""]
    head = "| ID | Kind | file:line | Code |" + (f" {value} |" if value else "")
    out += [head, "|---|---|---|---|" + ("---|" if value else "")]
    for n, hit in enumerate(hits, 1):
        row = f"| {prefix}{n:02d} | {hit.kind} | {hit.file}:{hit.line} | `{_cell(hit.text)}` |"
        out.append(row + (f" {_cell(hit.value)} |" if value else ""))
    return out + [""]


def _reach_section(inv: Inventory) -> List[str]:
    out = ["## What each entry point reaches", "",
           "Methods reached through calls the tool could follow (by name and variable type), and the SQL they "
           "use. Calls through interfaces, reflection or configuration may be missing: check the code.", ""]
    if not inv.reach:
        return out + ["None found.", ""]
    for r in inv.reach:
        warning = f" **Large: {r.lines} lines; consider splitting this flow.**" if r.lines > LARGE_FLOW_LINES else ""
        out += [f"### {r.entry} {r.kind}: {r.method} ({r.where})", "",
                f"{len(r.methods)} methods" + (f" (and {r.accessors} getters and setters)" if r.accessors else "")
                + f", about {r.lines} lines, {len(r.conditions)} decision lines. "
                f"SQL: {', '.join(r.sql) or 'none found'}.{warning}",
                ""]
        out += [f"- {m}" for m in r.methods] + [""]
        if r.unfollowed:
            out += ["Calls the tool could not follow (an interface, a parent class, reflection): read where each "
                    "one leads.", ""] + [f"- {u}" for u in r.unfollowed] + [""]
    return out


def render(inv: Inventory, paths: Paths) -> str:
    """The inventory as the agents read it. Written by the tool; do not edit."""
    specs_dir = paths.input / "outputs"
    business = [paths.rel(p) for p in paths.business_files]
    specs = sorted(paths.rel(p) for p in specs_dir.glob("*.csv")) if specs_dir.exists() else []
    out = [f"# Inventory: {paths.module.name}", "",
           f"Written by the tool from {len(inv.files)} source files. Do not edit; run `doc.py scan` again.", "",
           "## Source files", "", "| File | Lines |", "|---|---|"]
    out += [f"| {name} | {count} |" for name, count in inv.files.items()]
    out += ["", "Not read (file types the tool does not read, and test folders): "
            + (", ".join(f"{ext} ({n})" for ext, n in sorted(inv.not_read.items())) or "none"), ""]
    out += ["## Input folder", "", "Business context files: " + (", ".join(business) or "none"),
            "", "Output specifications: " + (", ".join(specs) or "none"), ""]
    out += _table("Entry points", "EP", _unique(inv.entry_points),
                  "Where work starts: main methods, servlets, threads and timer tasks, jobs, endpoints, "
                  "web.xml mappings, stored procedures.")
    out += _reach_section(inv)
    out += _table("SQL", "Q", inv.sql,
                  "SQL in XML by id, in Java (one string, + chains, append, constants), in configuration, and "
                  "stored procedure calls. In the SQL text, constants are filled in and '?' marks a part built at "
                  "run time.", "SQL text")
    out += ["## Possible code tables", "",
            "Tables whose names suggest codes or reference data. Ask the team to export them into "
            "doc-input/business/ so the meanings of codes are given, not guessed.", "",
            ", ".join(inv.code_tables) or "None found.", ""]
    out += _table("Outputs", "OUT", inv.outputs,
                  "Candidates: files and lines written, database changes run, calls to other systems.")
    out += _table("Comparisons with codes", "C", inv.comparisons,
                  "Places that compare a value with a code: a literal, a constant (resolved to its value) or an "
                  "enum value. The ones on business codes are variant points.", "Compares with")
    out += _table("Constants and enums", "K", inv.constants,
                  "Named codes and their values. A constants class is often the best list of business codes.",
                  "Value")
    out += _table("Configuration", "S", inv.settings,
                  "Settings in configuration files (secret values are not shown) and the code that reads them. "
                  "A setting that changes a business result is a business rule.")
    return "\n".join(out)
