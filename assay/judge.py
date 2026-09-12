"""Run a pack's hidden check against one finished workspace.

The check runs in a subprocess with the workspace importable but the check
file itself kept OUTSIDE the workspace, so nothing the model wrote can
shadow, patch or delete it. It must print one JSON object on its last line:

    {"passed": bool, "failures": [...], "total": int, "passed_count": int}

Anything else is reported as `check_error`, never silently as a failure. A
broken check is our bug and must not be charged to the model.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Verdict:
    status: str  # "pass" | "fail" | "check_error" | "no_artifact"
    failures: list = field(default_factory=list)
    total: int = 0
    passed_count: int = 0
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def judge(check: Path, workspace: Path, entrypoint: str, timeout: int = 60) -> Verdict:
    artifact = workspace / entrypoint
    if not artifact.exists():
        return Verdict("no_artifact", detail=f"{entrypoint} was never written")

    env = dict(os.environ)
    # The workspace is importable; the check is not inside it.
    env["PYTHONPATH"] = str(workspace)
    env.pop("OPENROUTER_API_KEY", None)  # the grader never needs credentials
    try:
        proc = subprocess.run(
            [sys.executable, str(check)],
            cwd=str(check.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Verdict("fail", detail=f"check timed out after {timeout}s")

    lines = [l for l in (proc.stdout or "").strip().splitlines() if l.strip()]
    if not lines:
        return Verdict("check_error", detail=(proc.stderr or "")[-400:] or "check printed nothing")
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError:
        return Verdict("check_error", detail=f"last line was not JSON: {lines[-1][:200]}")

    failures = data.get("failures") or []
    return Verdict(
        status="pass" if data.get("passed") else "fail",
        failures=failures,
        total=int(data.get("total") or 0),
        passed_count=int(data.get("passed_count") or 0),
        detail=data.get("detail", ""),
    )
