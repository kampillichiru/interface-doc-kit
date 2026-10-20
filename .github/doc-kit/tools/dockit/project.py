"""Where everything is: the module settings from `doc-input/module.md`, and every file path of a run."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from . import markdown

KIT_DIR = Path(__file__).resolve().parents[2]  # .github/doc-kit
STEPS_DIR = KIT_DIR / "steps"
SUMMARY_ID = "SUMMARY"  # the unit of the business summary at the start of the document
REVIEW_ID = "REVIEW"  # the review of the finished documents by a business analyst
README_MARK = "Write your business context below this line."


class InputError(Exception):
    """The input folder is missing something only a person can provide."""


@dataclass(frozen=True)
class Module:
    name: str
    purpose: str
    domain: str
    source_folders: List[str]
    data_check: bool
    test_db: str = "Oracle"

    @staticmethod
    def load(input_dir: Path) -> "Module":
        path = input_dir / "module.md"
        if not path.exists():
            raise InputError(f"{path.as_posix()} is missing. Copy it from the kit and fill it in.")
        values = {row.get("Key", "").strip().lower(): row.get("Value", "").strip()
                  for row in markdown.first_table(path.read_text(encoding="utf-8"))}
        missing = [key for key in ("name", "business domain", "source folders") if not values.get(key)]
        if missing:
            raise InputError(f"Fill in {', '.join(missing)} in {path.as_posix()}.")
        name = re.sub(r"[^A-Za-z0-9_-]", "_", values["name"])
        folders = [f.strip() for f in re.split(r"[,;]", values["source folders"]) if f.strip()]
        return Module(name=name, purpose=values.get("purpose", ""), domain=values["business domain"],
                      source_folders=folders,
                      data_check=values.get("data check", "no").lower().startswith("y"),
                      test_db=values.get("test database", "") or "Oracle")


@dataclass(frozen=True)
class Paths:
    workspace: Path
    input: Path
    output_root: Path
    module: Module

    @property
    def out(self) -> Path:
        return self.output_root / self.module.name

    @property
    def sources(self) -> List[Path]:
        return [self.workspace / folder for folder in self.module.source_folders]

    # Files of the run
    @property
    def inventory_md(self) -> Path:
        return self.out / "inventory.md"

    @property
    def inventory_json(self) -> Path:
        return self.out / "work" / "inventory.json"

    @property
    def discovery(self) -> Path:
        return self.out / "discovery.md"

    @property
    def plan(self) -> Path:
        return self.out / "work" / "plan.json"

    @property
    def guide(self) -> Path:
        """The business guide: what a business reader reads."""
        return self.out / f"{self.module.name}-business-guide.md"

    @property
    def reference(self) -> Path:
        """The reference: flows, every field, the data check and the traceability behind the guide."""
        return self.out / f"{self.module.name}-reference.md"

    @property
    def business_files(self) -> List[Path]:
        return business_files(self.input)

    def unit_file(self, unit_id: str) -> Path:
        if unit_id == SUMMARY_ID:
            return self.out / "summary.md"
        if unit_id == REVIEW_ID:
            return self.out / "review" / "REVIEW.md"
        folder = {"F": "flows", "C": "concepts"}.get(unit_id[:1], "outputs")
        return self.out / folder / f"{unit_id}.md"

    @property
    def review_questions(self) -> Path:
        return self.out / "review" / "questions.md"

    def verify_file(self, unit_id: str) -> Path:
        return self.out / "verify" / f"{unit_id}.md"

    def reader_file(self, unit_id: str) -> Path:
        return self.out / "reader" / f"{unit_id}.md"

    def problems_file(self, unit_id: str) -> Path:
        return self.out / "work" / f"{unit_id}.problems.md"

    def check_sql(self, output_id: str) -> Path:
        return self.out / "data-check" / f"{output_id}.sql"

    def data_report(self, output_id: str) -> Path:
        return self.out / "data-check" / f"{output_id}-report.md"

    def test_file(self, output_id: str, kind: str) -> Path:
        """`kind` is expected or actual; any file extension is accepted."""
        folder = self.input / "test-data" / output_id
        found = sorted(folder.glob(f"{kind}.*")) if folder.exists() else []
        return found[0] if found else folder / f"{kind}.dat"

    def rel(self, path: Path) -> str:
        """Path as written in task lines and documents: relative to the workspace when possible."""
        try:
            return path.resolve().relative_to(self.workspace.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def business_files(input_dir: Path) -> List[Path]:
    """The files of business context in `business/`. Its README.md counts only when the team wrote below the
    line README_MARK; above it is the kit's own guidance."""
    folder = input_dir / "business"
    if not folder.exists():
        return []
    found = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        if path.name.lower() == "readme.md" and not readme_context(path):
            continue
        found.append(path)
    return found


def readme_context(path: Path) -> str:
    """What the team wrote in business/README.md below the line README_MARK, without HTML comments."""
    text = path.read_text(encoding="utf-8", errors="replace")
    at = text.find(README_MARK)
    if at < 0:
        return ""
    rest = re.sub(r"^\s*-->", "", text[at + len(README_MARK):])  # the mark itself sits in a comment
    return re.sub(r"<!--.*?-->", "", rest, flags=re.S).strip()


def business_text(path: Path) -> str:
    """The business context in one file; for README.md only the part the team wrote."""
    if path.name.lower() == "readme.md":
        return readme_context(path)
    return path.read_text(encoding="utf-8", errors="replace")


def newer(path: Path, *others: Path) -> bool:
    """True when `path` exists and is at least as new as every existing file in `others`."""
    if not path.exists():
        return False
    return all(path.stat().st_mtime >= other.stat().st_mtime for other in others if other.exists())
