"""Run a pack's outcome script against one finished workspace, and compare outcomes across candidates.

A diff is not the work; it is the instructions for the work. The outcome is what the work
produces — a schedule, a set of totals, a rendered page — and it is the only form in which
somebody who does not read code can judge which attempt is right.

`outcome.py` lives beside `check.py` in the pack and obeys the same isolation: outside the
workspace, workspace importable, never copied in. It prints one JSON object:

    {"title": str, "subtitle": str, "columns": [str], "rows": [{"label", "note", "cells": [str]}]}

or `{"error": "..."}` when the artefact cannot produce one at all.

Text by default, always. A pack whose product is inherently visual — a chart, a rendered page —
may instead print `{"image": "<path>", "alt": "..."}`, because there the image IS the outcome
rather than a picture of a table. Nothing else should reach for it: a table is selectable,
quotable, searchable and readable aloud, and a picture of one is none of those.

And the limit, stated rather than dressed up: if a pack's only observable result is its own
verdict, it has no outcome. The board says so instead of showing the verdict twice.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path


def run_outcome(outcome_script: Path, workspace: Path, timeout: int = 30) -> dict:
    outcome_script, workspace = Path(outcome_script).resolve(), Path(workspace).resolve()
    if not outcome_script.exists():
        return {}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace)
    for k in list(env):
        if k.startswith(("OPENROUTER_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")):
            env.pop(k, None)
    try:
        p = subprocess.run([sys.executable, str(outcome_script)], cwd=str(outcome_script.parent),
                           env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"the outcome did not finish within {timeout}s"}
    lines = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
    if not lines:
        return {"error": (p.stderr or "").strip()[-200:] or "the outcome script printed nothing"}
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {"error": f"the outcome was not JSON: {lines[-1][:160]}"}


def compare(outcomes: dict[str, dict]) -> dict:
    """Align candidates' outcomes row by row and mark every cell they disagree on.

    Disagreement is the signal deliberately, not a comparison against a stored answer: the
    board is looking at what several independent attempts produced, and the places where they
    part company are exactly the places worth a human's attention. The check still decides
    who passed; this decides where to look.
    """
    usable = {k: v for k, v in outcomes.items() if v and "rows" in v and not v.get("error")}
    if not usable:
        return {"rows": [], "labels": list(outcomes), "columns": []}
    first = next(iter(usable.values()))
    columns = first.get("columns") or []
    order = [r["label"] for r in first.get("rows", [])]
    by_label = {k: {r["label"]: r for r in v.get("rows", [])} for k, v in usable.items()}

    rows = []
    for label in order:
        note = first_note = None
        cells: dict[str, list] = {}
        for cand, rowmap in by_label.items():
            r = rowmap.get(label)
            if r is None:
                continue
            note = note or r.get("note")
            cells[cand] = list(r.get("cells") or [])
        width = max((len(c) for c in cells.values()), default=0)
        marks: list[bool] = []
        for i in range(width):
            # Only real answers count as disagreement. A candidate that produced nothing at all
            # differs from everyone by construction, and marking that as a disagreement would
            # paint the whole table red and hide the one cell where two working answers
            # genuinely part company — which is the cell worth a human's eye.
            values = [cells[c][i] for c in cells if i < len(cells[c]) and not str(cells[c][i]).startswith("—")]
            marks.append(len(values) > 1 and len(set(values)) > 1)
        rows.append({"label": label, "note": note or first_note, "cells": cells,
                     "disagrees": marks, "width": width})
    return {"rows": rows, "labels": list(outcomes), "columns": columns,
            "title": first.get("title"), "subtitle": first.get("subtitle")}


def majority(cells: dict[str, list], index: int) -> str | None:
    values = [v[index] for v in cells.values() if index < len(v)]
    if not values:
        return None
    common = Counter(values).most_common(1)[0]
    return common[0] if common[1] > 1 else None
