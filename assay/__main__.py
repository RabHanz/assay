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
    rnd = Round(a.pack, specs, a.runs, blind=not a.open, allow_exec=a.allow_exec, seed=a.seed)
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
    r.set_defaults(fn=cmd_run)
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
