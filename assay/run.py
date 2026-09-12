"""One model, one isolated workspace, a real tool loop, a full receipt.

Three ceilings are enforced HERE, never trusted to the model, and reported separately:
turns, cumulative completion tokens, wall-clock seconds. A run that hits one stops and
says which, because "ran out of budget" and "got it wrong" are different results and
must never be collapsed into one column.

An empty visible answer is its own status: a reasoning model can spend its whole
budget thinking and return nothing, billed in full. That is recorded as
`empty_output`, not as a failure and not as an error.

Every path a tool touches is confined to the workspace. The check never enters it.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .providers import Completion, ProviderError, chat, parse_model

MAX_FILE_BYTES = 60_000
SYSTEM = (
    "You are working alone in a small workspace to complete a task. You have tools: list_files, "
    "read_file, write_file, and done. Do the work by writing complete files with write_file. "
    "When the task is complete, call done. Do not explain your work in prose; act with the tools."
)


@dataclass
class Receipt:
    model: str
    provider: str
    pack: str
    pack_version: str
    workspace: str
    entrypoint: str
    policy: dict
    turns: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float | None = None
    cost_source: str = "not reported by provider"
    latency_s: float = 0.0
    stopped_because: str = ""
    empty_output: bool = False
    emitted_artifact: bool = False
    tool_calls: list = field(default_factory=list)
    transport_error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["latency_s"] = round(self.latency_s, 1)
        if self.cost_usd is not None:
            d["cost_usd"] = round(self.cost_usd, 8)
        return d


def _tool_schemas(allow_exec: bool) -> list:
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "List the files in your workspace.",
                                          "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "read_file", "description": "Read one file from your workspace.",
                                          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Write the COMPLETE contents of one file in your workspace, replacing it.",
                                          "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "done", "description": "Call this when your work is complete and ready to be graded.",
                                          "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}}}},
    ]
    if allow_exec:
        tools.insert(3, {"type": "function", "function": {"name": "run_python", "description": "Run one python file in your workspace and see its output (10 s limit).",
                                                           "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}})
    return tools


def _confine(workspace: Path, rel: str) -> Path:
    if not rel or rel.startswith("/") or rel.startswith("~"):
        raise ValueError("path must be relative to the workspace")
    p = (workspace / rel).resolve()
    if p != workspace.resolve() and workspace.resolve() not in p.parents:
        raise ValueError("path escapes the workspace")
    return p


def _execute(workspace: Path, name: str, args: dict, allow_exec: bool) -> str:
    try:
        if name == "list_files":
            files = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
            return json.dumps(files)
        if name == "read_file":
            p = _confine(workspace, str(args.get("path", "")))
            if not p.is_file():
                return json.dumps({"error": "no such file"})
            return p.read_bytes()[:MAX_FILE_BYTES].decode("utf-8", "replace")
        if name == "write_file":
            p = _confine(workspace, str(args.get("path", "")))
            content = args.get("content")
            if not isinstance(content, str):
                return json.dumps({"error": "content must be a string"})
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return json.dumps({"ok": True, "bytes": len(content.encode())})
        if name == "run_python":
            if not allow_exec:
                return json.dumps({"error": "run_python is disabled in this round"})
            import subprocess, sys
            p = _confine(workspace, str(args.get("path", "")))
            proc = subprocess.run([sys.executable, str(p)], cwd=str(workspace), capture_output=True, text=True, timeout=10)
            return json.dumps({"returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]})
        if name == "done":
            return json.dumps({"ok": True})
        return json.dumps({"error": f"unknown tool {name}"})
    except (ValueError, OSError) as e:
        return json.dumps({"error": str(e)[:200]})
    except Exception as e:  # a tool must never take the run down
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})


def run_one(model_spec: str, pack, workspace: Path, *, allow_exec: bool = False,
            on_event=None, per_call_timeout: int = 300) -> Receipt:
    """Run one contestant to completion or to a ceiling. Returns the receipt; writes receipt.json beside the workspace."""
    provider, model = parse_model(model_spec)
    fixture_entry = pack.fixture / pack.entrypoint
    before = fixture_entry.read_text() if fixture_entry.exists() else None
    policy = {"max_turns": pack.max_turns, "max_completion_tokens": pack.max_tokens, "wall_seconds": pack.wall_seconds}
    r = Receipt(model=model, provider=provider, pack=pack.name, pack_version=pack.version, workspace=str(workspace),
                entrypoint=pack.entrypoint, policy=policy, started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tools = _tool_schemas(allow_exec)
    messages: list = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": pack.brief}]
    t0 = time.time()
    nudged = False

    def emit(kind: str, **kw):
        if on_event:
            try:
                on_event(kind, **kw)
            except Exception:
                pass

    while True:
        if r.turns >= pack.max_turns:
            r.stopped_because = "max_turns"; break
        remaining = pack.max_tokens - r.completion_tokens
        if remaining <= 0:
            r.stopped_because = "max_completion_tokens"; break
        if time.time() - t0 > pack.wall_seconds:
            r.stopped_because = "wall_seconds"; break
        r.turns += 1
        emit("turn", turn=r.turns)
        try:
            c: Completion = chat(provider, model, messages, tools, max_tokens=remaining,
                                 timeout=min(per_call_timeout, max(30, int(pack.wall_seconds - (time.time() - t0)))))
        except ProviderError as e:
            r.transport_error = str(e)[:300]
            r.stopped_because = "transport_error"
            emit("error", detail=r.transport_error)
            break
        r.prompt_tokens += c.prompt_tokens
        r.completion_tokens += c.completion_tokens
        r.reasoning_tokens += c.reasoning_tokens
        if c.cost_usd is not None:
            r.cost_usd = (r.cost_usd or 0.0) + c.cost_usd
            r.cost_source = c.cost_source
        msg = c.message
        calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()
        if not calls:
            if not content:
                r.empty_output = True
                r.stopped_because = "empty_output" if c.finish_reason == "length" else "no_tool_call"
                emit("empty", finish=c.finish_reason)
                break
            # Prose instead of a tool call: allow exactly one nudge, then stop.
            messages.append({"role": "assistant", "content": content})
            if nudged:
                r.stopped_because = "no_tool_call"; break
            nudged = True
            messages.append({"role": "user", "content": "Use the tools to do the work; call done when finished."})
            continue
        messages.append({"role": "assistant", "content": msg.get("content") or None, "tool_calls": calls})
        finished = False
        for call in calls:
            fn = (call.get("function") or {})
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
                result = json.dumps({"error": "arguments were not valid JSON"})
            else:
                result = _execute(workspace, name, args, allow_exec)
            r.tool_calls.append({"turn": r.turns, "tool": name, "path": args.get("path") if isinstance(args, dict) else None})
            emit("tool", tool=name, path=args.get("path") if isinstance(args, dict) else None)
            messages.append({"role": "tool", "tool_call_id": call.get("id") or f"call_{r.turns}", "content": result})
            if name == "done":
                finished = True
        if finished:
            r.stopped_because = "done"; break

    r.latency_s = time.time() - t0
    r.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    after_path = workspace / pack.entrypoint
    r.emitted_artifact = after_path.exists() and (before is None or after_path.read_text() != before)
    # `empty_output` is the outcome where the budget was billed and NOTHING came back. A model
    # that wrote a passing file and then ended on a silent turn is not that: it is a completed
    # run with a stop reason of `no_tool_call`. Conflating the two put an EMPTY label on a
    # 7/7 PASS in the first four-model round (gpt-oss-20b, 2026-09-12).
    if r.emitted_artifact:
        r.empty_output = False
    (workspace.parent / "receipt.json").write_text(json.dumps(r.as_dict(), indent=2))
    return r
