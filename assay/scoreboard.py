"""The repository becomes the record.

Every completed round appends one row per attempt to `scoreboard/rounds.jsonl` — pack and
version, model, verdict, stop reason, tokens, cost, elapsed, the budget policy, the round's
URL — and `SCOREBOARD.md` is rendered from it. Models arrive every other day; this answers
"is the new one any good at MY work" in minutes, with your own history beside it, and it
needs no service: a file in the repo, committed by the same workflow that ran the round.

A row is a measurement, never a claim. Pass rates are computed from rows and shown with their
n, and rows that ran under different ceilings are never summed into one line.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from .providers import parse_model

ROWS = Path("scoreboard") / "rounds.jsonl"
TABLE = Path("SCOREBOARD.md")


def append_round(round_dir: Path, url: str | None = None, root: Path | None = None) -> int:
    """Append one row per attempt from a finished round. Returns how many rows were written."""
    round_dir = Path(round_dir)
    root = Path(root or ".")
    state = json.loads((round_dir / "state.json").read_text())
    identities = json.loads((round_dir / "identities.json").read_text())
    rows_path = root / ROWS
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if rows_path.exists():
        for line in rows_path.read_text().splitlines():
            try:
                d = json.loads(line)
                existing.add((d.get("round_id"), d.get("label")))
            except json.JSONDecodeError:
                pass
    n = 0
    with rows_path.open("a") as f:
        for label in state["order"]:
            if (state["round_id"], label) in existing:
                continue
            c = state["contestants"][label]
            rec_path = round_dir / label / "receipt.json"
            rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
            provider, model = parse_model(identities.get(label, "?"))
            pol = state["policy"]
            row = {
                "at": state.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "round_id": state["round_id"], "label": label, "url": url or "",
                "pack": state["pack"]["name"], "pack_version": state["pack"]["version"],
                "provider": provider, "model": model,
                "verdict": c.get("verdict"), "stopped_because": c.get("stopped_because"),
                "failures": c.get("failures_count") or 0, "empty_output": bool(c.get("empty_output")),
                "turns": rec.get("turns"), "completion_tokens": rec.get("completion_tokens"),
                "reasoning_tokens": rec.get("reasoning_tokens"), "cost_usd": rec.get("cost_usd"),
                "cost_source": rec.get("cost_source"), "latency_s": rec.get("latency_s"),
                "policy": f"{pol['max_turns']}t/{pol['max_completion_tokens']}tok/{pol['wall_seconds']}s",
                "chosen": bool(state.get("choice") and state["choice"].get("label") == label),
            }
            f.write(json.dumps(row) + "\n")
            n += 1
    return n


def render(root: Path | None = None) -> str:
    root = Path(root or ".")
    rows_path = root / ROWS
    rows = []
    if rows_path.exists():
        for line in rows_path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    lines = ["# Scoreboard", "",
             "Every attempt this repository has run, as it happened. A row is a measurement; a pass",
             "rate is what this pack measured on this many runs and nothing wider. Rows that ran under",
             "different ceilings sit in different groups and are never summed.", ""]
    if not rows:
        lines.append("_No rounds recorded yet. Label an issue `assay` to run one._")
        return "\n".join(lines) + "\n"

    # Pass rate per (pack, version, policy, model), with n.
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["pack"], r["pack_version"], r["policy"], r["provider"], r["model"])].append(r)
    lines += ["## By model, per pack and ceiling", "",
              "| pack | ceilings | model | passed | ran out of budget / empty | median tokens | median s | cost |",
              "|---|---|---|---|---|---|---|---|"]
    for key in sorted(groups, key=lambda k: (k[0], k[2], -sum(1 for r in groups[k] if r["verdict"] == "pass") / max(1, len(groups[k])))):
        rs = groups[key]
        passed = sum(1 for r in rs if r["verdict"] == "pass")
        budget = sum(1 for r in rs if r["stopped_because"] in ("max_completion_tokens", "max_turns", "wall_seconds", "empty_output"))
        toks = sorted(r["completion_tokens"] or 0 for r in rs)
        lats = sorted(r["latency_s"] or 0 for r in rs)
        costs = [r["cost_usd"] for r in rs if isinstance(r["cost_usd"], (int, float))]
        cost = f"${sum(costs):.5f}" if costs else "free tier / n.r."
        lines.append(f"| {key[0]} v{key[1]} | {key[2]} | `{key[3]}:{key[4]}` | **{passed}/{len(rs)}** | {budget} | "
                     f"{toks[len(toks)//2]} | {lats[len(lats)//2]:.1f} | {cost} |")
    lines += ["", "## Every attempt", "",
              "| when | pack | model | verdict | stopped | tokens | reasoning | s | cost | chosen | round |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["at"], reverse=True):
        v = r["verdict"] or "?"
        if r.get("empty_output"):
            v += " (empty)"
        cost = f"${r['cost_usd']:.5f}" if isinstance(r.get("cost_usd"), (int, float)) else "n.r."
        link = f"[{r['label']}]({r['url']})" if r.get("url") else r["label"]
        lines.append(f"| {r['at'][:16].replace('T', ' ')} | {r['pack']} v{r['pack_version']} | `{r['model']}` | {v} | "
                     f"{r['stopped_because']} | {r.get('completion_tokens') or '-'} | {r.get('reasoning_tokens') or 0} | "
                     f"{(r.get('latency_s') or 0):.1f} | {cost} | {'yes' if r.get('chosen') else ''} | {link} |")
    return "\n".join(lines) + "\n"


def write_table(root: Path | None = None) -> Path:
    root = Path(root or ".")
    (root / TABLE).write_text(render(root))
    return root / TABLE
