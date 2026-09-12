"""Run the same pack against the same models several times, and report how often each one passes.

This exists because of a measurement, not a theory. On 2026-09-12, `gemini-3.1-flash-lite` and
`gemini-3.5-flash-lite` were each run five times against `chore-recurrence` under identical
ceilings: both passed some runs and failed others, and on one pair of consecutive rounds they
swapped places. A single round is therefore a sample, never a verdict on a model, and a board
that shows one run as a ranking is overstating what it knows.

So: `assay repeat` reports a pass rate k/n per model, the spread of tokens, cost and latency
across runs, and every distinct failing case seen. One run is reported as 1/1 and says so.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from .round import Round


def repeat(pack_path: str | Path, model_specs: list[str], n: int, runs_dir: str | Path = "runs",
           allow_exec: bool = False, budget: dict | None = None) -> dict:
    rounds = []
    for i in range(n):
        r = Round(pack_path, model_specs, runs_dir, blind=False, allow_exec=allow_exec, budget=budget)
        r.run()
        for label in r.identity:
            r._update(label, reveal=r.reveal_for(label))
        rounds.append(r)
        print(f"  repeat {i + 1}/{n}: {r.round_id}", flush=True)

    by_model: dict[str, dict] = {}
    for r in rounds:
        state = json.loads((r.dir / "state.json").read_text())
        for label, spec in r.identity.items():
            c = state["contestants"][label]
            rec = json.loads((r.dir / label / "receipt.json").read_text())
            m = by_model.setdefault(spec, {"model": spec, "runs": [], "failures": [], "stops": {}})
            m["runs"].append({
                "round": r.round_id, "verdict": c.get("verdict"), "stopped_because": c.get("stopped_because"),
                "completion_tokens": rec.get("completion_tokens"), "reasoning_tokens": rec.get("reasoning_tokens"),
                "cost_usd": rec.get("cost_usd"), "latency_s": rec.get("latency_s"),
                "passed_count": None,
            })
            for f in (c.get("failures") or []):
                case = f[0] if isinstance(f, list) and f else str(f)
                if case not in m["failures"]:
                    m["failures"].append(case)
            key = c.get("stopped_because") or "?"
            m["stops"][key] = m["stops"].get(key, 0) + 1

    report = {"pack": str(pack_path), "n": n, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "policy": rounds[0].state["policy"] if rounds else {}, "models": []}
    for spec, m in by_model.items():
        runs = m["runs"]
        passed = sum(1 for x in runs if x["verdict"] == "pass")
        toks = [x["completion_tokens"] or 0 for x in runs]
        costs = [x["cost_usd"] for x in runs if isinstance(x["cost_usd"], (int, float))]
        lats = [x["latency_s"] or 0 for x in runs]
        report["models"].append({
            "model": spec, "passed": passed, "n": len(runs),
            "pass_rate": round(passed / len(runs), 3),
            "tokens_min": min(toks), "tokens_max": max(toks), "tokens_median": int(statistics.median(toks)),
            "cost_total": round(sum(costs), 6) if costs else None,
            "cost_source": "provider usage field" if costs else "not reported by provider",
            "latency_median": round(statistics.median(lats), 1),
            "stops": m["stops"], "distinct_failing_cases": m["failures"][:8],
        })
    report["models"].sort(key=lambda x: (-x["passed"], x["tokens_median"]))
    out = Path(runs_dir) / f"reliability-{rounds[0].round_id}.json" if rounds else Path(runs_dir) / "reliability.json"
    out.write_text(json.dumps(report, indent=2))
    report["path"] = str(out)
    return report


def table(report: dict) -> str:
    n = report["n"]
    lines = [f"{'passed':>8} {'tokens min–max':>18} {'median':>7} {'cost':>10} {'lat s':>6}  model",
             "-" * 88]
    for m in report["models"]:
        cost = f"${m['cost_total']:.5f}" if m["cost_total"] is not None else "n/r"
        lines.append(f"{m['passed']:>4}/{n:<3} {str(m['tokens_min']) + '–' + str(m['tokens_max']):>18} "
                     f"{m['tokens_median']:>7} {cost:>10} {m['latency_median']:>6}  {m['model']}")
        if m["distinct_failing_cases"]:
            lines.append(f"{'':>8} failing cases seen: " + "; ".join(m["distinct_failing_cases"][:3]))
        stops = ", ".join(f"{k}×{v}" for k, v in m["stops"].items())
        lines.append(f"{'':>8} stopped: {stops}")
    lines.append("")
    lines.append(f"n={n} runs per model, identical ceilings ({report['policy'].get('max_turns')} turns · "
                 f"{report['policy'].get('max_completion_tokens')} completion tokens · {report['policy'].get('wall_seconds')} s). "
                 f"A pass rate is what this pack measured on this many runs, and nothing wider.")
    return "\n".join(lines)
