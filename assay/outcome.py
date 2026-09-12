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
        note = why = expected = None
        cells: dict[str, list] = {}
        for cand, rowmap in by_label.items():
            r = rowmap.get(label)
            if r is None:
                continue
            note = note or r.get("note")
            why = why or r.get("why")
            expected = expected or r.get("expected")
            cells[cand] = list(r.get("cells") or [])
        width = max((len(c) for c in cells.values()), default=0)
        if expected:
            width = max(width, len(expected))
        marks: list[bool] = []
        wrong: dict[str, list[bool]] = {c: [] for c in cells}
        for i in range(width):
            # Only real answers count as disagreement. A candidate that produced nothing at all
            # differs from everyone by construction, and marking that as a disagreement would
            # paint the whole table red and hide the one cell where two working answers
            # genuinely part company — which is the cell worth a human's eye.
            values = [cells[c][i] for c in cells if i < len(cells[c]) and not str(cells[c][i]).startswith("—")]
            marks.append(len(values) > 1 and len(set(values)) > 1)
            for c in cells:
                v = cells[c][i] if i < len(cells[c]) else None
                wrong[c].append(bool(expected) and i < len(expected) and v is not None and v != expected[i])
        rows.append({"label": label, "note": note, "why": why, "expected": expected,
                     "cells": cells, "disagrees": marks, "wrong": wrong, "width": width,
                     "clean": not any(any(w) for w in wrong.values()) and not any(marks)})
    return {"rows": rows, "labels": list(outcomes), "columns": columns,
            "title": first.get("title"), "subtitle": first.get("subtitle"),
            "has_expected": any(r.get("expected") for r in rows)}


def defects(comparison: dict) -> dict[str, str]:
    """One plain sentence per candidate naming the first thing it got wrong, or None.

    A table tells a reader where to look; a sentence tells them what they are looking at.
    Written from the pack's own explanation of the row, so it reads as English rather than
    as a cell reference: "puts the deep clean on 31 March, when the 31st of a month has to
    land on 28 February".
    """
    out: dict[str, str] = {}
    for cand in comparison.get("labels", []):
        said = None
        for r in comparison.get("rows", []):
            flags = (r.get("wrong") or {}).get(cand) or []
            bad_idx = [i for i, bad in enumerate(flags) if bad]
            if not bad_idx:
                continue
            # The rightmost wrong cell: in a row that ends with a total it is the total, which
            # is the one a reader recognises ("£99.99 under a £100.00 bill"); in a schedule it is
            # the latest date, which is where a skipped week shows. Unless the row died with an
            # error — then name the cell where it died, not the blank cells after it.
            errored = [i for i in bad_idx if str(r["cells"][cand][i]).startswith("— ") and len(str(r["cells"][cand][i])) > 2]
            i = errored[0] if errored else bad_idx[-1]
            got = r["cells"][cand][i]
            want = r["expected"][i]
            col = (comparison.get("columns") or [None] * (i + 1))[i] if i < len(comparison.get("columns") or []) else None
            where = f"“{r['label'].lower()}”" + (f", {col}" if col else "")
            if str(got).startswith("—"):
                said = f"stops with an error on {where}"
            else:
                said = (f"{where}: {got}, where it should be {want}"
                        + (f" — {r['why']}" if r.get("why") else ""))
            break
        out[cand] = said
    return out


def majority(cells: dict[str, list], index: int) -> str | None:
    values = [v[index] for v in cells.values() if index < len(v)]
    if not values:
        return None
    common = Counter(values).most_common(1)[0]
    return common[0] if common[1] > 1 else None
