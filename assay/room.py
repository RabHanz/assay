"""The room server: one page, one state file, two human acts.

Serves `room/index.html`, the round's `state.json`, and accepts POST /choose and POST /apply.
The server is the only thing that can reveal identities: `identities.json` sits beside
`state.json` and is folded into the state only when a choice is committed. The page never
sees a model name before that.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .apply import ApplyRefused, apply_result
from .providers import parse_model

LOCK = threading.Lock()
HERE = Path(__file__).resolve().parent


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _reveal(round_dir: Path, label: str, spec: str) -> dict:
    rec_path = round_dir / label / "receipt.json"
    rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    provider, model = parse_model(spec)
    return {"model": model, "provider": provider,
            "completion_tokens": rec.get("completion_tokens"), "reasoning_tokens": rec.get("reasoning_tokens"),
            "prompt_tokens": rec.get("prompt_tokens"), "cost_usd": rec.get("cost_usd"),
            "cost_source": rec.get("cost_source"), "latency_s": rec.get("latency_s"), "turns": rec.get("turns")}


def choose(round_dir: Path, label: str) -> dict:
    with LOCK:
        state = json.loads((round_dir / "state.json").read_text())
        if state.get("phase") != "judged":
            raise RuntimeError(f"cannot choose in phase {state.get('phase')}")
        if label not in state["contestants"]:
            raise KeyError(label)
        identities = json.loads((round_dir / "identities.json").read_text())
        state["choice"] = {"label": label, "at": _now()}
        state["phase"] = "chosen"
        state["revealed"] = True
        for l, spec in identities.items():
            state["contestants"][l]["reveal"] = _reveal(round_dir, l, spec)
        (round_dir / "state.json").write_text(json.dumps(state, indent=2))
        return state


def serve(round_dir: Path, port: int = 8787, target: str | None = None, target_path: str | None = None,
          bind: str = "127.0.0.1") -> int:
    round_dir = Path(round_dir).resolve()
    page = (HERE / "room" / "index.html")

    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            elif self.path.startswith("/state.json"):
                self._send(200, (round_dir / "state.json").read_bytes())
            else:
                self._send(404, b'{"error":"not found"}')

        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, b'{"error":"bad json"}')
            label = str(body.get("label") or "")
            try:
                if self.path == "/choose":
                    state = choose(round_dir, label)
                    return self._send(200, json.dumps({"ok": True, "phase": state["phase"]}).encode())
                if self.path == "/apply":
                    if not target:
                        return self._send(409, b'{"error":"the room was started without --target; nothing to apply into"}')
                    with LOCK:
                        result = apply_result(round_dir, label, Path(target), target_path)
                    return self._send(200, json.dumps({"ok": True, "apply": result}).encode())
                return self._send(404, b'{"error":"not found"}')
            except (ApplyRefused, RuntimeError, KeyError) as e:
                return self._send(409, json.dumps({"error": str(e)[:300]}).encode())

        def log_message(self, fmt, *args):  # quiet
            return

    httpd = ThreadingHTTPServer((bind, port), H)
    print(f"room: http://{bind}:{port}/  round {round_dir.name}" + (f"  target {target}" if target else "  (no target: apply disabled)"), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
