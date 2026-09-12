"""assay command line.

    python -m assay run packs/chore-recurrence --models gemini:gemini-3.1-flash-lite,openrouter:qwen/qwen3.7-flash:free
    python -m assay room runs/<round-id> [--port 8787] [--target /path/to/repo --target-path solution.py]
    python -m assay models openrouter|gemini
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_run(a: argparse.Namespace) -> int:
    from .round import Round, table
    specs = [s.strip() for s in a.models.split(",") if s.strip()]
    rnd = Round(a.pack, specs, a.runs, blind=not a.open, allow_exec=a.allow_exec, seed=a.seed,
                budget={"max_tokens": a.max_tokens, "max_turns": a.max_turns, "wall_seconds": a.wall})
    print(f"round {rnd.round_id}: {len(specs)} contestants, pack {rnd.pack.name} v{rnd.pack.version}, "
          f"ceilings {rnd.pack.max_turns} turns · {rnd.pack.max_tokens} completion tokens · {rnd.pack.wall_seconds} s", flush=True)
    state = rnd.run()
    identities = None if (not a.open and not a.reveal) else rnd.identity
    if a.reveal or a.open:
        for l in rnd.identity:
            rnd._update(l, reveal=rnd.reveal_for(l))
    print(table(rnd.state, identities))
    print(f"state: {rnd.dir / 'state.json'}")
    return 0


def cmd_repeat(a: argparse.Namespace) -> int:
    from .reliability import repeat, table
    specs = [s.strip() for s in a.models.split(",") if s.strip()]
    print(f"repeat: {len(specs)} models × {a.n} runs on {a.pack}", flush=True)
    report = repeat(a.pack, specs, a.n, a.runs, allow_exec=a.allow_exec,
                    budget={"max_tokens": a.max_tokens, "max_turns": a.max_turns, "wall_seconds": a.wall})
    print()
    print(table(report))
    print(f"report: {report['path']}")
    return 0


def cmd_issue(a: argparse.Namespace) -> int:
    from .github import run_for_issue, serve_issue
    rnd = run_for_issue(a.repo, a.issue, a.runs, default_models=a.models or "", post=not a.dry_run)
    if a.dry_run:
        from .round import table
        print(table(rnd.state, rnd.identity))
        return 0
    result = serve_issue(a.repo, a.issue, rnd.dir, interval=a.interval, target_path=a.target_path,
                         timeout=a.timeout)
    print(f"chose {result['label']} ({result['by']}){'  pr ' + result['pr'] if result['pr'] else ''}")
    return 0


def cmd_watch(a: argparse.Namespace) -> int:
    from .github import watch
    watch(a.repo, label=a.label, interval=a.interval, runs_dir=a.runs,
          default_models=a.models or "", target_path=a.target_path, once=a.once)
    return 0


def cmd_demo(a: argparse.Namespace) -> int:
    """One command, no GitHub, one free key: run a round on the chore pack and print the board here."""
    from .github import DEFAULT_MODELS
    from .outcome import compare, defects
    from .round import Round, table
    specs = [s.strip() for s in (a.models or DEFAULT_MODELS).split(",") if s.strip()]
    rnd = Round(a.pack, specs, a.runs, blind=True)
    print(f"{len(specs)} attempts at {rnd.pack.name} v{rnd.pack.version}, each alone, same brief, ceilings "
          f"{rnd.pack.max_turns} turns · {rnd.pack.max_tokens} tokens · {rnd.pack.wall_seconds}s …", flush=True)
    st = rnd.run()
    comp = compare({l: (st["contestants"][l].get("outcome") or {}) for l in st["order"]})
    produced = [l for l in st["order"] if (st["contestants"][l].get("outcome") or {}).get("rows")]
    passed = [l for l in st["order"] if st["contestants"][l].get("verdict") == "pass"]
    print()
    print(f"{len(passed)} of {len(specs)} got every check right" + (f": {', '.join(passed)}" if passed else "") + ".")
    if comp.get("rows") and produced:
        print(f"\n{comp.get('title')}\n{comp.get('subtitle')}\n")
        w = max(len(r["label"]) for r in comp["rows"]) + 2
        print(" " * (w + 12) + "should be".ljust(16) + "".join(l.ljust(16) for l in produced))
        for r in comp["rows"]:
            if r.get("clean"):
                continue
            for i in range(r["width"]):
                wrong_here = any((r.get("wrong") or {}).get(l, [False] * r["width"])[i] for l in produced)
                if not wrong_here:
                    continue
                col = (comp.get("columns") or [""] * r["width"])[i] if i < len(comp.get("columns") or []) else ""
                exp = (r.get("expected") or [""] * r["width"])[i] if i < len(r.get("expected") or []) else ""
                cells = ""
                for l in produced:
                    got = (r["cells"].get(l) or [])
                    v = got[i] if i < len(got) else "—"
                    bad = (r.get("wrong") or {}).get(l, [False] * r["width"])[i]
                    cells += (f"{v} ✗" if bad else f"{v} ✓").ljust(16)
                print(f"{r['label'].ljust(w)}{col.ljust(12)}{str(exp).ljust(16)}{cells}")
        clean = sum(1 for r in comp["rows"] if r.get("clean"))
        if clean == len(comp["rows"]):
            print("every attempt produced exactly the right result in every row")
        elif clean:
            print(f"\n(the other {clean} rows are right in every attempt)")
        for cand, s in defects(comp).items():
            if s:
                print(f"{cand}: {s}")
    print()
    for l in rnd.identity:
        rnd._update(l, reveal=rnd.reveal_for(l))
    print("revealed, since this is your terminal and not a thread:")
    print(table(rnd.state, rnd.identity))
    return 0


def cmd_init(a: argparse.Namespace) -> int:
    """Scaffold a pack that already passes, so the real job is editing two files."""
    from pathlib import Path
    root = Path("packs") / a.name
    if root.exists():
        print(f"{root} already exists"); return 1
    (root / "fixture").mkdir(parents=True)
    (root / "pack.toml").write_text(f'name = "{a.name}"\nversion = "1"\n\n[task]\nentrypoint = "solution.py"\n'
                                    f'summary = "Describe the job in one line."\n\n[budget]\nmax_turns = 6\nmax_tokens = 8000\nwall_seconds = 300\n')
    (root / "brief.md").write_text("The file `solution.py` in your workspace contains `greet`, which is not implemented.\n\n"
                                   "Implement it: `greet(name)` returns `\"Hello, <name>!\"`, and `greet(\"\")` returns `\"Hello!\"`.\n\n"
                                   "Read the file first, then write the complete corrected file with `write_file`, then call `done`.\n")
    (root / "fixture" / "solution.py").write_text('def greet(name: str) -> str:\n    """Return a greeting. Empty name: just "Hello!"."""\n    raise NotImplementedError\n')
    (root / "check.py").write_text('"""Hidden check. Runs OUTSIDE the workspace; the workspace is on PYTHONPATH."""\nimport json\ntry:\n    from solution import greet\nexcept Exception as e:\n'
                                   '    print(json.dumps({"passed": False, "failures": [["import", f"EXC {type(e).__name__}"]], "total": 3, "passed_count": 0})); raise SystemExit(0)\n'
                                   'cases = [("Ada", "Hello, Ada!"), ("", "Hello!"), ("Grace Hopper", "Hello, Grace Hopper!")]\nbad = []\nfor arg, want in cases:\n'
                                   '    try:\n        got = greet(arg)\n    except Exception as e:\n        bad.append([repr(arg), f"EXC {type(e).__name__}"]); continue\n'
                                   '    if got != want: bad.append([repr(arg), f"{got!r} want {want!r}"])\n'
                                   'print(json.dumps({"passed": not bad, "failures": bad, "total": len(cases), "passed_count": len(cases) - len(bad)}))\n')
    (root / "outcome.py").write_text('"""What this attempt PRODUCES, for a reader who does not read code. Same isolation as check.py."""\nimport json\n'
                                     'try:\n    from solution import greet\nexcept Exception as e:\n    print(json.dumps({"error": f"{type(e).__name__}"})); raise SystemExit(0)\n'
                                     'PEOPLE = [("Ada", "Hello, Ada!"), ("nobody", "Hello!"), ("Grace Hopper", "Hello, Grace Hopper!")]\nrows = []\n'
                                     'for label, want in PEOPLE:\n    arg = "" if label == "nobody" else label\n'
                                     '    try:\n        got = greet(arg)\n    except Exception as e:\n        got = f"— {type(e).__name__}"\n'
                                     '    rows.append({"label": label, "note": "", "cells": [got], "expected": [want], "why": "an empty name gets a plain hello"})\n'
                                     'print(json.dumps({"title": "What each attempt says to three people", "subtitle": "", "columns": ["greeting"], "rows": rows}))\n')
    print(f"wrote {root}/ — pack.toml, brief.md, fixture/solution.py, check.py, outcome.py.\n"
          f"Edit brief.md and fixture/ for your task, then check.py (the truth) and outcome.py (the view).\n"
          f"Run it: python -m assay demo --pack {root}")
    return 0


def cmd_scoreboard(a: argparse.Namespace) -> int:
    from .scoreboard import append_round, write_table
    from pathlib import Path
    if a.round_dir:
        n = append_round(Path(a.round_dir), url=a.url)
        print(f"{n} rows appended")
    p = write_table()
    print(f"rendered {p}")
    return 0


def cmd_models(a: argparse.Namespace) -> int:
    import urllib.request
    from .providers import PROVIDERS, _load_keys
    cfg = PROVIDERS[a.provider]
    keys = _load_keys()
    name = next((n for n in cfg["key_names"] if keys.get(n)), None)
    req = urllib.request.Request(cfg["base"] + "/models", headers={"Authorization": f"Bearer {keys[name]}"} if name else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    for m in data.get("data", []):
        mid = m.get("id", "")
        if a.grep and a.grep.lower() not in mid.lower():
            continue
        print(mid)
    return 0


def cmd_room(a: argparse.Namespace) -> int:
    from .room import serve
    return serve(Path(a.round_dir), port=a.port, target=a.target, target_path=a.target_path, bind=a.bind)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="assay")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one round of a pack against several models")
    r.add_argument("pack")
    r.add_argument("--models", required=True, help="comma-separated provider:model specs")
    r.add_argument("--runs", default="runs")
    r.add_argument("--open", action="store_true", help="not blind: identities shown from the start")
    r.add_argument("--reveal", action="store_true", help="blind run, but print identities in the final table")
    r.add_argument("--allow-exec", action="store_true", help="give models run_python (executes model-authored code here)")
    r.add_argument("--seed", type=int, default=None)
    r.add_argument("--max-tokens", type=int, default=None, help="override the pack's completion-token ceiling (recorded as a policy change)")
    r.add_argument("--max-turns", type=int, default=None)
    r.add_argument("--wall", type=int, default=None)
    r.set_defaults(fn=cmd_run)
    rp = sub.add_parser("repeat", help="run the same pack N times per model and report pass rates")
    rp.add_argument("pack")
    rp.add_argument("--models", required=True)
    rp.add_argument("--n", type=int, default=5)
    rp.add_argument("--runs", default="runs")
    rp.add_argument("--allow-exec", action="store_true")
    rp.add_argument("--max-tokens", type=int, default=None, help="override the pack's completion-token ceiling (recorded as a policy change)")
    rp.add_argument("--max-turns", type=int, default=None)
    rp.add_argument("--wall", type=int, default=None)
    rp.set_defaults(fn=cmd_repeat)
    iss = sub.add_parser("issue", help="run a round for a GitHub issue, post the blind board, wait for a choice, open the PR")
    iss.add_argument("repo", help="owner/name")
    iss.add_argument("issue", type=int)
    iss.add_argument("--models", default="", help="fallback when the issue body has no `models:` line")
    iss.add_argument("--runs", default="runs")
    iss.add_argument("--interval", type=int, default=20)
    iss.add_argument("--timeout", type=int, default=3600)
    iss.add_argument("--target-path", default=None, help="path in the repo the artefact lands at (defaults to the pack entrypoint)")
    iss.add_argument("--dry-run", action="store_true", help="run and print the board, post nothing")
    iss.set_defaults(fn=cmd_issue)
    w = sub.add_parser("watch", help="stay in the repository: every issue labelled `assay` gets a round, a board and a PR")
    w.add_argument("repo", help="owner/name")
    w.add_argument("--label", default="assay")
    w.add_argument("--models", default="", help="fallback when an issue body has no `models:` line")
    w.add_argument("--runs", default="runs")
    w.add_argument("--interval", type=int, default=30)
    w.add_argument("--target-path", default=None)
    w.add_argument("--once", action="store_true", help="one sweep, then exit")
    w.set_defaults(fn=cmd_watch)
    d = sub.add_parser("demo", help="one command, no GitHub: run a round on a pack and print the board here")
    d.add_argument("--pack", default="packs/chore-recurrence")
    d.add_argument("--models", default="", help="defaults to three free Gemini attempts")
    d.add_argument("--runs", default="runs")
    d.set_defaults(fn=cmd_demo)
    ini = sub.add_parser("init", help="scaffold a pack that already passes under packs/<name>")
    ini.add_argument("name")
    ini.set_defaults(fn=cmd_init)
    sb = sub.add_parser("scoreboard", help="append a round to scoreboard/rounds.jsonl and re-render SCOREBOARD.md")
    sb.add_argument("round_dir", nargs="?", default=None)
    sb.add_argument("--url", default=None)
    sb.set_defaults(fn=cmd_scoreboard)
    m = sub.add_parser("models", help="list model ids a provider offers")
    m.add_argument("provider", choices=["openrouter", "gemini"])
    m.add_argument("--grep", default="")
    m.set_defaults(fn=cmd_models)
    ro = sub.add_parser("room", help="serve the room for one round")
    ro.add_argument("round_dir")
    ro.add_argument("--port", type=int, default=8787)
    ro.add_argument("--bind", default="127.0.0.1", help="interface to listen on (0.0.0.0 to reach it from another machine on your network)")
    ro.add_argument("--target", default=None, help="git repo the chosen artefact is applied into")
    ro.add_argument("--target-path", default=None, help="path inside the target repo (defaults to the pack entrypoint)")
    ro.set_defaults(fn=cmd_room)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
