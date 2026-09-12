"""Apply exactly ONE result to a real repository, behind a human's choice, and read it back.

The evidence the human chose on was produced against a frozen fixture. Before anything is
written, the target file is compared to that fixture: if it moved since, the evidence is
stale and the apply refuses rather than writing on top of a base nobody judged. The commit
message carries the round id, the label, the pack, the verdict and the artefact hash, so the
repo's own history says what was applied and why.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path


class ApplyRefused(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if p.returncode != 0:
        raise ApplyRefused(f"git {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout


def apply_result(round_dir: Path, label: str, target_repo: Path, target_path: str | None = None) -> dict:
    round_dir = Path(round_dir)
    state = json.loads((round_dir / "state.json").read_text())
    if state.get("phase") not in ("chosen",):
        raise ApplyRefused(f"apply needs phase 'chosen', round is '{state.get('phase')}'")
    if not state.get("choice") or state["choice"].get("label") != label:
        raise ApplyRefused("only the chosen result can be applied")
    if state.get("apply"):
        raise ApplyRefused("this round has already applied a result")
    c = state["contestants"][label]
    if c.get("verdict") != "pass":
        raise ApplyRefused(f"the chosen result did not pass the pack's checks (verdict {c.get('verdict')})")

    pack = state["pack"]
    entry = target_path or pack["entrypoint"]
    src = round_dir / label / "workspace" / pack["entrypoint"]
    if not src.exists():
        raise ApplyRefused("the chosen workspace has no artefact")

    repo = Path(target_repo).resolve()
    if not (repo / ".git").exists():
        raise ApplyRefused(f"{repo} is not a git repository")
    dst = (repo / entry).resolve()
    if repo not in dst.parents:
        raise ApplyRefused("target path escapes the repository")

    # Staleness: the base the human judged against must still be what is in the repo.
    fixture_path = round_dir / "fixture-snapshot" / pack["entrypoint"]
    if fixture_path.exists() and dst.exists() and dst.read_bytes() != fixture_path.read_bytes():
        raise ApplyRefused("the target file changed since the round's fixture was frozen; re-run the round rather than apply stale evidence")

    content = src.read_bytes()
    artefact_sha = hashlib.sha256(content).hexdigest()
    before = _git(repo, "rev-parse", "HEAD").strip() if _git(repo, "rev-list", "--count", "HEAD").strip() != "0" else None
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(content)
    _git(repo, "add", str(dst.relative_to(repo)))
    msg = (f"assay: apply {label} from {state['round_id']}\n\n"
           f"pack {pack['name']} v{pack['version']} · verdict {c.get('verdict')} · "
           f"stopped {c.get('stopped_because')} · artefact sha256 {artefact_sha[:16]}\n"
           f"chosen blind at {state['choice'].get('at')}; identity revealed after the choice.")
    _git(repo, "commit", "-q", "-m", msg)
    commit = _git(repo, "rev-parse", "--short", "HEAD").strip()
    readback = _git(repo, "show", "--stat", "--format=%h %s", "HEAD")
    diff = _git(repo, "diff", f"{before}..HEAD", "--", str(dst.relative_to(repo))) if before else _git(repo, "show", "HEAD", "--", str(dst.relative_to(repo)))
    result = {"label": label, "commit": commit, "path": str(dst), "artefact_sha256": artefact_sha,
              "diff_readback": diff[-6000:], "stat": readback[-1000:], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    state["apply"] = result
    state["phase"] = "applied"
    (round_dir / "state.json").write_text(json.dumps(state, indent=2))
    return result
