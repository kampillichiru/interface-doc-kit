"""Business terms: their meanings from the input folder, and the terms a piece of documentation uses.

A reader new to the domain must find the meaning of every code and business term the document uses. A meaning
comes only from the input folder (glossary.csv, business/, sme-answers.md); a term without one becomes a question.
"""

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from . import markdown
from .project import business_files, business_text

# Codes and abbreviations written in capitals: GOLD, COD, PENDING_PAYMENT. Not ids (F01-BR02), not TABLE.COLUMN.
CAPS = re.compile(r"(?<![\w./\-])([A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]|[A-Z]{2,}[0-9]*)(?![\w./(\-])")
TECHNICAL = {"SQL", "HTTP", "HTTPS", "URL", "API", "ID", "IDS", "XML", "JSON", "CSV", "OK", "POST", "GET", "PUT",
             "DELETE", "PATCH", "UTF", "SME", "PDF", "FTP", "SFTP", "JDBC", "REST", "SOAP", "DB", "TXT", "DAT",
             "AM", "PM", "UTC", "YYYY", "YYYYMMDD", "MM", "DD", "HH", "SS", "NA", "TBD", "FINAL", "DRAFT", "PASS",
             "FAIL", "CLEAR", "UNCLEAR", "MATCH", "INSERT", "UPDATE", "SELECT", "MERGE", "WHERE", "AND", "OR",
             "NOT", "NULL", "IN", "IS"}
_TERM_HEADERS = ("term", "code", "value", "name", "abbreviation", "word")
_MEANING_HEADERS = ("meaning", "description", "definition", "explanation")


@dataclass(frozen=True)
class Term:
    term: str
    meaning: str
    source: str


def defined(input_dir: Path) -> Dict[str, Term]:
    """Every term with a meaning in the input folder, keyed by its lower-case form. The glossary comes first;
    then tables in business/ with a term or code column and a meaning column."""
    found: Dict[str, Term] = {}
    from_glossary = set()

    def add(term: str, meaning: str, source: str, glossary: bool = False) -> None:
        term, meaning = term.strip().strip("`"), meaning.strip()
        if not term or not meaning:
            return
        key = term.lower()
        if key not in found:
            found[key] = Term(term, meaning, source)
            if glossary:
                from_glossary.add(key)
        elif key not in from_glossary and meaning not in found[key].meaning:
            # The same code under another kind (STANDARD as a tier and as a courier service): keep both.
            old = found[key]
            sources = old.source if source in old.source else f"{old.source}, {source}"
            found[key] = Term(old.term, f"{old.meaning} / {meaning}", sources)

    glossary = input_dir / "glossary.csv"
    if glossary.exists():
        with glossary.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                add(row.get("term") or "", row.get("meaning") or "", (row.get("source") or "").strip() or "glossary",
                    glossary=True)
    for path in business_files(input_dir):
        text = business_text(path)
        if path.suffix.lower() == ".csv":
            tables = [list(csv.DictReader(io.StringIO(text)))]
        elif path.suffix.lower() in (".md", ".txt"):
            tables = markdown.tables(text)
        else:
            continue
        for rows in tables:
            for row in rows:
                term_key = _column(row, _TERM_HEADERS)
                meaning_key = _column(row, _MEANING_HEADERS)
                if not term_key or not meaning_key:
                    continue
                kind_key = _column(row, ("kind", "type", "category"))
                kind = (row.get(kind_key) or "").strip() if kind_key else ""
                codes = [t for t in re.split(r"\s*(?:,|/|\bor\b)\s*", row[term_key] or "") if t.strip()]
                meanings = [m.strip() for m in (row[meaning_key] or "").split(";")]
                if len(meanings) != len(codes):  # "EXPRESS, STANDARD | Next day; 3 to 5 days" pairs them up
                    meanings = [(row[meaning_key] or "").strip()] * len(codes)
                source = f"business/{path.relative_to(input_dir / 'business').as_posix()}"
                for code, meaning in zip(codes, meanings):
                    add(code, f"{kind}: {meaning}" if kind and meaning else meaning, source)
    return found


def _column(row: Dict[str, str], names) -> str:
    return next((k for k in row if k and k.strip().lower() in names), "")


def input_text(input_dir: Path) -> str:
    """All the team's words, for a plain search: glossary, business/, SME answers, module.md, specifications."""
    parts = [business_text(p) for p in business_files(input_dir)]
    for name in ("glossary.csv", "sme-answers.md", "module.md"):
        if (input_dir / name).exists():
            parts.append((input_dir / name).read_text(encoding="utf-8", errors="replace"))
    specs = input_dir / "outputs"
    if specs.exists():
        parts += [p.read_text(encoding="utf-8", errors="replace") for p in sorted(specs.glob("*.csv"))]
    return "\n".join(parts)


def mentions(text: str, term: str) -> bool:
    """True when `term` is in `text` as a whole word, in any case."""
    return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text, re.I))


def caps_terms(text: str, ignore=()) -> List[str]:
    """Codes and abbreviations a text uses, in order of first use, without technical words and `ignore`."""
    skip = {i.upper() for i in ignore} | TECHNICAL
    found: List[str] = []
    for line in text.splitlines():
        line = re.sub(r"`[^`]*`", " ", line)  # quoted code is not prose
        for term in CAPS.findall(line):
            if term not in skip and term not in found:
                found.append(term)
    return found
