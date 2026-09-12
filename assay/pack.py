"""A task pack: the unit a person owns, versions and points at models.

A pack is a directory:

    packs/<name>/
      pack.toml      metadata + budget ceiling + tool allow-list
      brief.md       what the agent is told (the ONLY thing it sees)
      fixture/       the starting working tree, copied per run
      check.py       the acceptance check. NEVER copied into the workspace.

The separation is the whole point. `brief.md` and `fixture/` are the agent's
world; `check.py` is the judge and lives outside it, so a model cannot read
the cases it will be graded on, and cannot edit the thing grading it.
"""
from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Pack:
    name: str
    root: Path
    brief: str
    version: str
    max_tokens: int
    max_turns: int
    wall_seconds: int
    entrypoint: str

    @property
    def fixture(self) -> Path:
        return self.root / "fixture"

    @property
    def check(self) -> Path:
        return self.root / "check.py"

    @property
    def outcome(self) -> Path:
        """Optional: prints what this candidate's work PRODUCES, for a human who does not read code.

        Same isolation as the check — outside the workspace, workspace importable, never copied in.
        """
        return self.root / "outcome.py"

    def stage(self, into: Path) -> Path:
        """Copy the fixture into a fresh isolated workspace and return it.

        The check is deliberately NOT copied. If it were, a model could read
        the hidden cases or overwrite its own grader, and every verdict after
        that would be worthless.
        """
        into.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.fixture, into, dirs_exist_ok=True)
        return into


def load(path: str | Path) -> Pack:
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"no pack at {root}")
    meta_file = root / "pack.toml"
    brief_file = root / "brief.md"
    for required in (meta_file, brief_file, root / "fixture", root / "check.py"):
        if not required.exists():
            raise FileNotFoundError(f"pack {root.name} is missing {required.name}")

    meta = tomllib.loads(meta_file.read_text())
    task = meta.get("task", {})
    budget = meta.get("budget", {})
    return Pack(
        name=meta.get("name") or root.name,
        root=root,
        brief=brief_file.read_text(),
        version=str(meta.get("version", "0")),
        max_tokens=int(budget.get("max_tokens", 16000)),
        max_turns=int(budget.get("max_turns", 8)),
        wall_seconds=int(budget.get("wall_seconds", 900)),
        entrypoint=task.get("entrypoint", "solution.py"),
    )
