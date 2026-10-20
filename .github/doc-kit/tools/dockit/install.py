"""Installs this kit into a project, or updates it, so every project runs the same standard kit.

The kit owns: the doc-* agents, the /doc-run prompt, the ask-the-docs skill, everything in .github/doc-kit and a
marked block in copilot-instructions.md. Only those are replaced. Every file replaced or removed is first copied to
<project>/.doc-kit-backup/<time>/. The input folder only gets template files that are missing; the output folder is
never touched.
"""

import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .project import KIT_DIR

KIT_ROOT = KIT_DIR.parents[1]  # the folder holding .github/
BACKUP_DIR = ".doc-kit-backup"
INSTRUCTIONS = ".github/copilot-instructions.md"
BLOCK_START, BLOCK_END = "<!-- doc-kit:start -->", "<!-- doc-kit:end -->"
OLD_KIT_HEADING = "# Documentation kit"  # copilot-instructions.md written by a kit from before the markers


def _skip(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def _owned(root: Path) -> List[str]:
    """The kit-owned files that exist under root, as posix paths relative to it."""
    found = []
    for pattern in (".github/agents/doc-*.agent.md", ".github/prompts/doc-run.prompt.md",
                    ".github/skills/ask-the-docs/**/*", ".github/doc-kit/**/*"):
        found += [p for p in root.glob(pattern) if p.is_file() and not _skip(p.relative_to(root))]
    return sorted({p.relative_to(root).as_posix() for p in found})


def _template_inputs() -> List[str]:
    return sorted(p.relative_to(KIT_ROOT).as_posix() for p in (KIT_ROOT / "doc-input").rglob("*") if p.is_file())


def _block() -> str:
    text = (KIT_ROOT / INSTRUCTIONS).read_text(encoding="utf-8")
    start, end = text.index(BLOCK_START), text.index(BLOCK_END) + len(BLOCK_END)
    return text[start:end]


def _instructions_after(current: str) -> str:
    """copilot-instructions.md with the kit's block in it; the project's own lines are kept."""
    block = _block()
    if BLOCK_START in current and BLOCK_END in current:
        start, end = current.index(BLOCK_START), current.index(BLOCK_END) + len(BLOCK_END)
        return current[:start] + block + current[end:]
    if not current.strip():
        return block + "\n"
    if current.lstrip().startswith(OLD_KIT_HEADING):  # an old kit's text, maybe with the project's lines after it
        lines = current.lstrip().splitlines()
        rest = next((i for i, line in enumerate(lines[1:], 1) if line.startswith("#")), len(lines))
        kept = "\n".join(lines[rest:]).strip()
        return block + "\n" + (f"\n{kept}\n" if kept else "")
    return current.rstrip("\n") + "\n\n" + block + "\n"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Changes:
    added: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)  # kit files the project has but this kit no longer has
    inputs: List[str] = field(default_factory=list)  # missing input templates

    @property
    def standard(self) -> bool:
        return not (self.added or self.updated or self.removed)

    def lines(self) -> List[str]:
        out = []
        for label, items in (("add", self.added), ("update", self.updated), ("remove", self.removed),
                             ("add input template", self.inputs)):
            out += [f"  {label}: {item}" for item in items]
        return out


def plan(target: Path) -> Changes:
    kit, project = set(_owned(KIT_ROOT)), set(_owned(target))
    changes = Changes()
    for rel in sorted(kit):
        if rel not in project:
            changes.added.append(rel)
        elif _digest(KIT_ROOT / rel) != _digest(target / rel):
            changes.updated.append(rel)
    changes.removed = sorted(project - kit)
    current = (target / INSTRUCTIONS).read_text(encoding="utf-8") if (target / INSTRUCTIONS).exists() else ""
    if _instructions_after(current) != current:
        (changes.updated if current else changes.added).append(INSTRUCTIONS)
    changes.inputs = [rel for rel in _template_inputs() if not (target / rel).exists()]
    return changes


def install(target: Path, changes: Changes) -> Path:
    """Applies the changes. Returns the backup folder (it exists only when something was replaced or removed)."""
    backup = target / BACKUP_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    for rel in changes.updated + changes.removed:
        (backup / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / rel, backup / rel)
    for rel in changes.removed:
        (target / rel).unlink()
    for rel in changes.added + changes.updated + changes.inputs:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel == INSTRUCTIONS:
            current = dest.read_text(encoding="utf-8") if dest.exists() else ""
            dest.write_text(_instructions_after(current), encoding="utf-8")
        else:
            shutil.copy2(KIT_ROOT / rel, dest)
    return backup


def check_target(target: Path) -> str:
    """Empty when the target can be installed into, else the reason."""
    if not target.is_dir():
        return f"{target} is not a folder."
    if target.resolve() == KIT_ROOT.resolve():
        return "That is the kit itself. Name the project folder to install into."
    return ""


def summary(changes: Changes) -> Dict[str, int]:
    return {"add": len(changes.added), "update": len(changes.updated), "remove": len(changes.removed),
            "input templates": len(changes.inputs)}
