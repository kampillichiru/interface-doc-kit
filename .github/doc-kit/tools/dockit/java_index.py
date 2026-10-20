"""A light index of Java source: classes, methods (with line ranges), constants, enums and calls.

Pattern based, not a compiler: good enough to list what an entry point reaches and to turn
`Codes.RETURNED.equals(x)` into "compares with RT". It aims to over-report rather than miss.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

KEYWORDS = {"if", "for", "while", "switch", "catch", "synchronized", "return", "new", "else", "try", "do",
            "throw", "super", "this", "assert", "case", "default", "finally", "instanceof"}
MAX_CANDIDATES = 4  # a call by name to more methods than this is too vague to follow

_TYPE_DECL = re.compile(r"\b(class|interface|enum)\s+([A-Za-z_]\w*)([^{;]*)\{")
_METHOD = re.compile(
    r"(?:\b(?:public|protected|private|static|final|synchronized|abstract|native|default)\s+)*"
    r"(?:<[^<>]*>\s+)?([\w.$<>\[\],? ]+?)\s+([A-Za-z_]\w*)\s*\(([^()]*)\)\s*(?:throws\s+[\w.,\s]+)?\{")
_CONSTRUCTOR = re.compile(r"(?:\b(?:public|protected|private)\s+)?([A-Z]\w*)\s*\(([^()]*)\)\s*(?:throws\s+[\w.,\s]+)?\{")
_CONSTANT = re.compile(r"\bstatic\s+final\s+([\w.<>\[\]]+)\s+([A-Za-z_]\w*)\s*=\s*([^;]+);")
_INTERFACE_FIELD = re.compile(r"(?:^|(?<=[;{}]))\s*(?:public\s+)?(?:static\s+)?(?:final\s+)?"
                              r"(String|int|long|short|byte|char|Integer|Long)\s+([A-Za-z_]\w*)\s*=\s*([^;]+);", re.M)
_VARIABLE = re.compile(r"\b([A-Z]\w*)(?:<[^<>;()]*>)?(?:\[\])?\s+([a-z_]\w*)\s*[;=,)]")
_CALL = re.compile(r"(?:\b([A-Za-z_]\w*)\s*\.\s*)?\b([A-Za-z_]\w*)\s*\(")
_NEW = re.compile(r"\bnew\s+([A-Z]\w*)\s*\(")
_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


@dataclass
class Method:
    cls: str
    name: str
    params: str
    file: str
    start: int  # line numbers, 1-based, inclusive
    end: int
    body: Tuple[int, int] = (0, 0)  # offsets of the body in the file text
    calls: Set[str] = field(default_factory=set)  # resolved method keys "Class.name"
    unfollowed: List[int] = field(default_factory=list)  # lines of calls into this code that could not be followed

    @property
    def key(self) -> str:
        return f"{self.cls}.{self.name}"

    @property
    def where(self) -> str:
        return f"{self.file}:{self.start}-{self.end}"


@dataclass
class TypeInfo:
    name: str
    kind: str  # class | interface | enum
    header: str  # text between the name and the opening brace (extends, implements)
    file: str
    line: int
    span: Tuple[int, int]
    fields: Dict[str, str] = field(default_factory=dict)  # variable name -> type name


@dataclass
class Constant:
    owner: str
    name: str
    value: str
    file: str
    line: int


@dataclass
class JavaIndex:
    types: Dict[str, TypeInfo] = field(default_factory=dict)
    methods: List[Method] = field(default_factory=list)
    constants: Dict[str, Constant] = field(default_factory=dict)  # "Owner.NAME" and "NAME" -> constant
    enums: Dict[str, List[str]] = field(default_factory=dict)  # enum name -> constant names
    enum_codes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # enum -> constant -> constructor args
    texts: Dict[str, str] = field(default_factory=dict)  # file -> original text
    masked: Dict[str, str] = field(default_factory=dict)  # file -> text without comments and string contents

    def method_at(self, file: str, line: int) -> Optional[Method]:
        found = [m for m in self.methods if m.file == file and m.start <= line <= m.end]
        return min(found, key=lambda m: m.end - m.start) if found else None

    def resolve(self, expression: str, owner: str = "") -> Optional[Constant]:
        """The constant an expression like `RETURNED`, `Codes.RETURNED` or `a.b.Codes.RETURNED` names."""
        parts = expression.split(".")
        if len(parts) >= 2 and f"{parts[-2]}.{parts[-1]}" in self.constants:
            return self.constants[f"{parts[-2]}.{parts[-1]}"]
        if owner and f"{owner}.{parts[-1]}" in self.constants:
            return self.constants[f"{owner}.{parts[-1]}"]
        return self.constants.get(parts[-1]) if len(parts) == 1 else None

    def is_accessor(self, m: Method) -> bool:
        """A getter or setter of one or two lines: not worth listing in a flow."""
        return bool(re.match(r"(get|set|is)[A-Z]", m.name)) and m.end - m.start <= 2

    def reach(self, start: Method, limit: int = 60) -> List[Method]:
        """Methods reachable from `start` through resolved calls, in the order first found."""
        by_key = defaultdict(list)
        for m in self.methods:
            by_key[m.key].append(m)
        seen, order, todo = set(), [], [start]
        while todo and len(order) < limit:
            current = todo.pop(0)
            ident = (current.file, current.start)
            if ident in seen:
                continue
            seen.add(ident)
            order.append(current)
            for key in sorted(current.calls):
                todo += by_key.get(key, [])
        return order


def mask(text: str) -> str:
    """Comments and the inside of string and char literals replaced by spaces; newlines and offsets kept."""
    out, i, n = list(text), 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out[i:j] = [ch if ch == "\n" else " " for ch in text[i:j]]
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out[i + 1:min(j, n)] = " " * (min(j, n) - i - 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _close(masked: str, open_at: int) -> int:
    """Offset of the brace that closes the one at `open_at`."""
    depth = 0
    for j in range(open_at, len(masked)):
        if masked[j] == "{":
            depth += 1
        elif masked[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return len(masked) - 1


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _literal(raw: str) -> Optional[str]:
    raw = raw.strip()
    string = _STRING.fullmatch(raw)
    if string:
        return string.group(1)
    if re.fullmatch(r"'(\\.|[^'])'", raw):
        return raw[1:-1]
    if re.fullmatch(r"-?\d+[lL]?", raw):
        return raw.rstrip("lL")
    return None


def build(files: Iterable[Tuple[str, str]]) -> JavaIndex:
    """Index (name, text) pairs of Java files."""
    index = JavaIndex()
    pending = []  # constants whose value is another constant, resolved after the first pass
    for name, text in files:
        masked = mask(text)
        index.texts[name], index.masked[name] = text, masked
        types = _types(index, name, text, masked)
        for t in types:
            _constants(index, t, text, masked, pending)
        _methods(index, name, masked, types)
    for owner, cname, raw, file, line in pending:
        target = index.resolve(raw.strip(), owner)
        if target:
            _add_constant(index, Constant(owner, cname, target.value, file, line))
    for method in index.methods:
        method.calls = _calls(index, method)
        method.unfollowed = _unfollowed(index, method)
    return index


def _types(index: JavaIndex, name: str, text: str, masked: str) -> List[TypeInfo]:
    types = []
    for match in _TYPE_DECL.finditer(masked):
        open_at = match.end() - 1
        info = TypeInfo(match.group(2), match.group(1), match.group(3).strip(), name, _line(text, match.start()),
                        (open_at, _close(masked, open_at)))
        body = masked[info.span[0]:info.span[1]]
        info.fields = {var: typ for typ, var in _VARIABLE.findall(body)}
        types.append(info)
        index.types.setdefault(info.name, info)
        if info.kind == "enum":
            first = body[1:].split(";")[0]
            names = re.findall(r"(?:^|,)\s*([A-Z][A-Z0-9_]*)\s*(?=\(|,|$|\{)", first.strip(), re.M)
            original = text[info.span[0] + 1:info.span[0] + 1 + len(first)]
            args = dict(re.findall(r"\b([A-Z][A-Z0-9_]*)\s*\(([^()]*)\)", original))
            index.enums[info.name] = names
            index.enum_codes[info.name] = {n: args[n].strip() for n in names if n in args}
    return types


def _innermost(types: List[TypeInfo], offset: int) -> Optional[TypeInfo]:
    inside = [t for t in types if t.span[0] < offset < t.span[1]]
    return min(inside, key=lambda t: t.span[1] - t.span[0]) if inside else None


def _constants(index: JavaIndex, info: TypeInfo, text: str, masked: str, pending: list) -> None:
    body = masked[info.span[0]:info.span[1]]
    patterns = [_CONSTANT] + ([_INTERFACE_FIELD] if info.kind == "interface" else [])
    for pattern in patterns:
        for match in pattern.finditer(body):
            start = info.span[0] + match.start(3)
            raw = text[start:info.span[0] + match.end(3)]
            line = _line(text, start)
            value = _literal(raw)
            if value is not None:
                _add_constant(index, Constant(info.name, match.group(2), value, info.file, line))
            elif re.fullmatch(r"\s*[\w.]+\s*", raw):
                pending.append((info.name, match.group(2), raw, info.file, line))


def _add_constant(index: JavaIndex, constant: Constant) -> None:
    index.constants[f"{constant.owner}.{constant.name}"] = constant
    index.constants.setdefault(constant.name, constant)


def _methods(index: JavaIndex, name: str, masked: str, types: List[TypeInfo]) -> None:
    text = index.texts[name]
    found = []
    for match in _METHOD.finditer(masked):
        method_name = match.group(2)
        if method_name in KEYWORDS or match.group(1).strip() in KEYWORDS | {"else"}:
            continue
        found.append((match, method_name, match.group(3)))
    for match in _CONSTRUCTOR.finditer(masked):
        owner = _innermost(types, match.start())
        if owner and owner.name == match.group(1):
            found.append((match, match.group(1), match.group(2)))
    seen = set()
    for match, method_name, params in found:
        open_at = match.end() - 1
        if open_at in seen:
            continue
        seen.add(open_at)
        owner = _innermost(types, match.start())
        if owner is None:
            continue
        close = _close(masked, open_at)
        start_line = _line(text, match.start() + len(match.group(0)) - len(match.group(0).lstrip()))
        index.methods.append(Method(owner.name, method_name, " ".join(params.split()), name, start_line,
                                    _line(text, close), (open_at, close)))


_REFLECTION = re.compile(r"\b(Class\s*\.\s*forName|getMethod|getDeclaredMethod|newInstance|invoke)\s*\(")


def _unfollowed(index: JavaIndex, method: Method) -> List[int]:
    """Lines of calls the reach could not follow: a method of this code called on a type that does not have
    it (an interface or a parent class), a name too common to resolve, or reflection. Library calls are not
    listed: their methods are not in this code."""
    body = index.masked[method.file][method.body[0]:method.body[1]]
    owner = index.types.get(method.cls)
    local = dict(owner.fields if owner else {})
    local.update({var: typ for typ, var in _VARIABLE.findall(method.params + ";")})
    local.update({var: typ for typ, var in _VARIABLE.findall(body)})
    names = defaultdict(set)
    for m in index.methods:
        names[m.name].add(m.cls)
    lines = set()
    for match in _CALL.finditer(body):
        receiver, name = match.group(1), match.group(2)
        if name in KEYWORDS or name not in names:
            continue
        cls = local.get(receiver) or (receiver if receiver in index.types else None)
        if cls and cls in index.types and cls not in names[name]:
            lines.add(_line(index.texts[method.file], method.body[0] + match.start()))  # interface or parent
        elif not cls and (not receiver or receiver[0].islower()) and method.cls not in names[name] \
                and len(names[name]) > MAX_CANDIDATES:
            lines.add(_line(index.texts[method.file], method.body[0] + match.start()))  # too common a name
    for match in _REFLECTION.finditer(body):
        lines.add(_line(index.texts[method.file], method.body[0] + match.start()))
    return sorted(lines)


def _calls(index: JavaIndex, method: Method) -> Set[str]:
    body = index.masked[method.file][method.body[0]:method.body[1]]
    owner = index.types.get(method.cls)
    local = dict(owner.fields if owner else {})
    local.update({var: typ for typ, var in _VARIABLE.findall(method.params + ";")})
    local.update({var: typ for typ, var in _VARIABLE.findall(body)})
    by_name = defaultdict(set)
    for m in index.methods:
        by_name[m.name].add(m.key)
    keys = set()
    for receiver, name in _CALL.findall(body):
        if name in KEYWORDS:
            continue
        cls = local.get(receiver) or (receiver if receiver in index.types else None)
        if cls and f"{cls}.{name}" in {m.key for m in index.methods if m.cls == cls}:
            keys.add(f"{cls}.{name}")
        elif cls and cls not in index.types:
            continue  # a library type such as ResultSet: its methods are not in this code
        elif not receiver and f"{method.cls}.{name}" in by_name[name]:
            keys.add(f"{method.cls}.{name}")
        elif 0 < len(by_name[name]) <= MAX_CANDIDATES and (not receiver or receiver[0].islower()):
            keys |= by_name[name]
    for cls in _NEW.findall(body):
        if cls in index.types:
            runnable = re.search(r"Runnable|TimerTask|Thread|Callable", index.types[cls].header)
            keys |= {m.key for m in index.methods
                     if m.cls == cls and (m.name == cls or (runnable and m.name in ("run", "call")))}
    keys.discard(method.key)
    return keys
