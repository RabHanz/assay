"""A round: one pack, several contestants, each in its own workspace, judged from outside.

The round writes `state.json` continuously so the room can show it live. Identities are
kept in a separate file (`identities.json`) and are NOT in state.json until the human's
choice is committed — that is what makes the choice blind. Labels are assigned to models
at random and the pane order is shuffled again, so neither position nor letter says
which model is which.
"""
from __future__ import annotations

import difflib
import json
import random
import re
import string
import threading
import time
from pathlib import Path

from . import pack as packmod
from .judge import judge
from .providers import parse_model
from .run import run_one

LOCK = threading.Lock()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _strip_identity(text: str, specs: list[str]) -> str:
    """Remove obvious identity strings (model ids, vendors) from a diff before it is shown blind."""
    out = text
    for spec in specs:
        provider, model = parse_model(spec)
        for token in {model, model.split("/")[-1], model.split("/")[0], provider}:
            if token and len(token) > 2:
                out = re.sub(re.escape(token), "[redacted]", out, flags=re.IGNORECASE)
    for vendor in ("openai", "google", "gemini", "anthropic", "claude", "deepseek", "qwen", "alibaba", "mistral", "nvidia", "nemotron", "meta", "llama", "gpt"):
        out = re.sub(rf"\b{vendor}\b", "[redacted]", out, flags=re.IGNORECASE)
    return out


class Round:
    def __init__(self, pack_path: str | Path, model_specs: list[str], runs_dir: str | Path = "runs",
                 *, blind: bool = True, allow_exec: bool = False, seed: int | None = None):
        self.pack = packmod.load(pack_path)
        self.specs = list(model_specs)
        if not 1 <= len(self.specs) <= 26:
            raise ValueError("between 1 and 26 contestants")
        rnd = random.Random(seed)
        labels = list(string.ascii_uppercase[: len(self.specs)])
        shuffled_specs = self.specs[:]
        rnd.shuffle(shuffled_specs)
        self.identity = dict(zip(labels, shuffled_specs))      # label -> model spec
        self.order = labels[:]
        rnd.shuffle(self.order)
        self.blind = blind
        self.allow_exec = allow_exec
        self.round_id = f"{time.strftime('%Y-%m-%dT%H-%M-%SZ', time.gmtime())}-{self.pack.name}"
        self.dir = Path(runs_dir) / self.round_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state = {
            "round_id": self.round_id,
            "pack": {"name": self.pack.name, "version": self.pack.version, "entrypoint": self.pack.entrypoint,
                     "brief_excerpt": self.pack.brief[:300]},
            "policy": {"max_turns": self.pack.max_turns, "max_completion_tokens": self.pack.max_tokens,
                       "wall_seconds": self.pack.wall_seconds, "allow_exec": allow_exec,
                       "label": "identical ceilings for every pane"},
            "phase": "running",
            "blind": blind,
            "revealed": not blind,
            "order": self.order,
            "contestants": {l: {"status": "queued", "turn": 0, "last_tool": None, "verdict": None,
                                "failures_count": None, "failures": [], "stopped_because": None,
                                "empty_output": False, "artifact_diff": "", "artifact_bytes": 0,
                                "reveal": self._reveal_stub(l) if not blind else None}
                            for l in labels},
            "choice": None,
            "apply": None,
            "started_at": _now(),
        }
        (self.dir / "identities.json").write_text(json.dumps(self.identity, indent=2))
        self._write()

    # ── state ────────────────────────────────────────────────────────────────
    def _reveal_stub(self, label: str) -> dict:
        provider, model = parse_model(self.identity[label])
        return {"model": model, "provider": provider}

    def _write(self) -> None:
        with LOCK:
            tmp = self.dir / "state.json.tmp"
            tmp.write_text(json.dumps(self.state, indent=2))
            tmp.replace(self.dir / "state.json")

    def _update(self, label: str, **fields) -> None:
        with LOCK:
            self.state["contestants"][label].update(fields)
        self._write()

    # ── one contestant ───────────────────────────────────────────────────────
    def _run_label(self, label: str) -> None:
        spec = self.identity[label]
        cdir = self.dir / label
        workspace = cdir / "workspace"
        self.pack.stage(workspace)
        self._update(label, status="running")

        def on_event(kind, **kw):
            if kind == "turn":
                self._update(label, turn=kw.get("turn"))
            elif kind == "tool":
                self._update(label, last_tool=f"{kw.get('tool')} {kw.get('path') or ''}".strip())
            elif kind == "error":
                self._update(label, last_tool="transport error")

        receipt = run_one(spec, self.pack, workspace, allow_exec=self.allow_exec, on_event=on_event)
        self._update(label, status="judging", stopped_because=receipt.stopped_because, empty_output=receipt.empty_output)
        verdict = judge(self.pack.check, workspace, self.pack.entrypoint)
        (cdir / "verdict.json").write_text(json.dumps(verdict.__dict__, indent=2))

        before = (self.pack.fixture / self.pack.entrypoint)
        after = workspace / self.pack.entrypoint
        before_text = before.read_text().splitlines(keepends=True) if before.exists() else []
        after_text = after.read_text().splitlines(keepends=True) if after.exists() else []
        diff = "".join(difflib.unified_diff(before_text, after_text, fromfile=f"fixture/{self.pack.entrypoint}",
                                            tofile=f"workspace/{self.pack.entrypoint}"))
        self._update(
            label, status="done", verdict=verdict.status,
            failures_count=len(verdict.failures), failures=verdict.failures[:6],
            check_detail=verdict.detail,
            artifact_diff=_strip_identity(diff, self.specs) if self.blind else diff,
            artifact_bytes=after.stat().st_size if after.exists() else 0,
        )

    # ── the round ────────────────────────────────────────────────────────────
    def run(self) -> dict:
        threads = [threading.Thread(target=self._run_label, args=(l,), daemon=True) for l in self.state["contestants"]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with LOCK:
            self.state["phase"] = "judged"
            self.state["finished_at"] = _now()
        self._write()
        return self.state

    # ── the human's two acts (also callable from the room server) ────────────
    def choose(self, label: str) -> dict:
        if label not in self.identity:
            raise KeyError(label)
        with LOCK:
            if self.state["phase"] != "judged":
                raise RuntimeError(f"cannot choose in phase {self.state['phase']}")
            self.state["choice"] = {"label": label, "at": _now()}
            self.state["phase"] = "chosen"
            self.state["revealed"] = True
        for l in self.identity:
            self._update(l, reveal=self.reveal_for(l))
        return self.state

    def reveal_for(self, label: str) -> dict:
        rec_path = self.dir / label / "receipt.json"
        rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
        provider, model = parse_model(self.identity[label])
        return {"model": model, "provider": provider,
                "completion_tokens": rec.get("completion_tokens"), "reasoning_tokens": rec.get("reasoning_tokens"),
                "prompt_tokens": rec.get("prompt_tokens"), "cost_usd": rec.get("cost_usd"),
                "cost_source": rec.get("cost_source"), "latency_s": rec.get("latency_s"), "turns": rec.get("turns")}


def table(state: dict, identities: dict | None = None) -> str:
    """A terminal table for a finished round. Identities are shown only if given (i.e. after reveal)."""
    rows = []
    hdr = f"{'label':5} {'verdict':12} {'stopped':22} {'turns':>5} {'out tok':>8} {'reason':>8} {'cost':>10} {'lat s':>6}  model"
    rows.append(hdr)
    for label in state["order"]:
        c = state["contestants"][label]
        r = c.get("reveal") or {}
        model = (identities or {}).get(label) or r.get("model") or "(hidden)"
        cost = r.get("cost_usd")
        cost_s = f"${cost:.5f}" if isinstance(cost, (int, float)) else "n/r"
        v = (c.get("verdict") or "").upper()
        if c.get("empty_output"):
            v = "EMPTY"
        rows.append(f"{label:5} {v:12} {str(c.get('stopped_because')):22} {r.get('turns') or c.get('turn') or 0:>5} "
                    f"{r.get('completion_tokens') or '-':>8} {r.get('reasoning_tokens') or '-':>8} {cost_s:>10} {r.get('latency_s') or '-':>6}  {model}")
    return "\n".join(rows)
