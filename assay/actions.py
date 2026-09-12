"""assay as a GitHub Action: the loop with no process of ours running anywhere.

Two entry points, one per event, both stateless:

  round   — fired when an issue gains the `assay` label. Runs the round, posts the board, and
            writes the round directory where the workflow can upload it as an artifact named
            after the issue. The board carries the workflow run id in a hidden marker so the
            second event can find that artifact.
  choose  — fired when a comment is created. Ignores everything but `/assay choose X` from an
            account the EVENT ITSELF says may decide (author_association of OWNER, MEMBER or
            COLLABORATOR — GitHub computes it; nothing here trusts a typed name). Downloads
            the round, reveals, opens the pull request. Never merges.

Why this is the product rather than the polling watch: a workflow file is a thing a repository
carries. "Add one file and any issue you label gets a board" is the agent living where the work
already is, with no laptop, no daemon and no token of ours involved. The watch remains for
running it locally.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .github import (CHOICE, MARKER, REVEAL_MARKER, GhError, board_comment, gh, may_decide, open_pr,
                     read_issue, reveal_comment, run_for_issue)

RUN_MARKER = "<!-- assay:run {run_id} -->"
# author_association is a pre-filter only. CONTRIBUTOR means a commit was once merged, not that
# the account holds write today, and NONE-versus-CONTRIBUTOR is not a permission model. The gate
# is the repository's real permission, read from the API, exactly as in the local watch.
PREFILTER = {"OWNER", "MEMBER", "COLLABORATOR"}


def action_gate(repo: str, number: int, comment_body: str, author: str, association: str) -> int:
    """First step of the choose job, before any artifact is fetched: may this person decide?

    On a public repository `issue_comment` fires for ANY commenter and the job runs in the base
    repository's context. A gate that runs after work has happened is an audit log, not a gate,
    so this step decides whether the rest of the job exists at all.
    """
    m = CHOICE.search(comment_body or "")
    if not m:
        _out(allowed="false", reason="not-a-choice")
        return 0
    allowed = (association or "").upper() in PREFILTER and may_decide(repo, author)
    if not allowed:
        gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
           stdin=(f"@{author} — a choice here opens a pull request against this repository, so it is "
                  f"taken only from an account with write access, read from the repository's own "
                  f"permissions. Yours does not include it, so nothing has moved. The board above is "
                  f"unchanged and still blind."))
        print(f"{author} ({association}) chose {m.group(1).upper()}; refused at the gate", flush=True)
    _out(allowed="true" if allowed else "false", reason="ok" if allowed else "no-write-access",
         label=m.group(1).upper())
    return 0


def _out(**kv) -> None:
    """Write step outputs for the workflow."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        for k, v in kv.items():
            print(f"{k}={v}")
        return
    with open(path, "a") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def action_round(repo: str, number: int, runs_dir: str = "runs", default_models: str = "") -> int:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    rnd = run_for_issue(repo, number, runs_dir, default_models=default_models, post=False)
    body = board_comment(rnd.state, rnd.round_id)
    if run_id:
        body = body.replace(MARKER, MARKER + "\n" + RUN_MARKER.format(run_id=run_id), 1)
    gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-", stdin=body)
    print(f"posted the board to {repo}#{number} (run {run_id or 'local'})", flush=True)
    _out(round_dir=str(rnd.dir), round_id=rnd.round_id)
    return 0


def _find_run_id(repo: str, number: int) -> str | None:
    issue = read_issue(repo, number)
    for c in issue.get("comments") or []:
        body = c.get("body") or ""
        if MARKER in body and "<!-- assay:run " in body:
            start = body.index("<!-- assay:run ") + len("<!-- assay:run ")
            return body[start:body.index(" -->", start)].strip()
    return None


def action_choose(repo: str, number: int, comment_body: str, author: str, association: str,
                  round_dir: str | None, target_path: str | None = None) -> int:
    m = CHOICE.search(comment_body or "")
    if not m:
        print("not a choice; nothing to do", flush=True)
        _out(acted="false")
        return 0
    label = m.group(1).upper()
    issue = read_issue(repo, number)
    comments = issue.get("comments") or []
    if any(REVEAL_MARKER in (c.get("body") or "") for c in comments):
        print("already decided; nothing to do", flush=True)
        _out(acted="false")
        return 0
    if not any(MARKER in (c.get("body") or "") for c in comments):
        print("no board on this issue yet; nothing to do", flush=True)
        _out(acted="false")
        return 0
    # Defence in depth: the gate step already refused anyone without write access before this
    # step could run; check again here so this function is safe even when called on its own.
    if (association or "").upper() not in PREFILTER or not may_decide(repo, author):
        print(f"{author} ({association}) chose {label}; refused", flush=True)
        _out(acted="refused")
        return 0
    if not round_dir or not Path(round_dir, "identities.json").exists():
        gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
           stdin="The round's workspaces could not be retrieved for this issue, so nothing can be applied. "
                 "Re-label the issue to run a fresh round.")
        _out(acted="false")
        return 1
    rd = Path(round_dir)
    identities = json.loads((rd / "identities.json").read_text())
    if label not in identities:
        gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
           stdin=f"`{label}` is not one of the candidates ({', '.join(sorted(identities))}).")
        _out(acted="false")
        return 0
    state = json.loads((rd / "state.json").read_text())
    import time
    state["choice"] = {"label": label, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": author}
    state["phase"], state["revealed"] = "chosen", True
    (rd / "state.json").write_text(json.dumps(state, indent=2))
    pr = ""
    try:
        if state["contestants"][label].get("verdict") == "pass":
            pr = open_pr(repo, number, rd, label, target_path)
    except Exception as e:
        gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
           stdin=f"Chose **{label}**, but opening the pull request failed: `{str(e)[:300]}`")
    gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
       stdin=reveal_comment(rd, identities, label, pr or None))
    print(f"{author} chose {label}; pr {pr or '(none opened)'}", flush=True)
    # The repository becomes the record: one row per attempt, rendered into SCOREBOARD.md.
    # The workflow commits these two files after this step.
    try:
        from .scoreboard import append_round, write_table
        issue_url = f"https://github.com/{repo}/issues/{number}"
        n = append_round(rd, url=issue_url)
        write_table()
        print(f"scoreboard: {n} rows appended", flush=True)
    except Exception as e:  # the record must never break the reveal
        print(f"scoreboard append failed: {type(e).__name__}: {str(e)[:200]}", flush=True)
    _out(acted="true", label=label, pr=pr)
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "round":
        repo, number = rest[0], int(rest[1])
        return action_round(repo, number, default_models=os.environ.get("ASSAY_MODELS", ""))
    if cmd == "gate":
        repo, number = rest[0], int(rest[1])
        return action_gate(repo, number,
                           comment_body=os.environ.get("ASSAY_COMMENT_BODY", ""),
                           author=os.environ.get("ASSAY_COMMENT_AUTHOR", "?"),
                           association=os.environ.get("ASSAY_COMMENT_ASSOCIATION", ""))
    if cmd == "choose":
        repo, number = rest[0], int(rest[1])
        return action_choose(repo, number,
                             comment_body=os.environ.get("ASSAY_COMMENT_BODY", ""),
                             author=os.environ.get("ASSAY_COMMENT_AUTHOR", "?"),
                             association=os.environ.get("ASSAY_COMMENT_ASSOCIATION", ""),
                             round_dir=os.environ.get("ASSAY_ROUND_DIR") or None,
                             target_path=os.environ.get("ASSAY_TARGET_PATH") or None)
    if cmd == "run-id":
        repo, number = rest[0], int(rest[1])
        rid = _find_run_id(repo, number) or ""
        _out(run_id=rid)
        print(rid)
        return 0
    print(f"unknown action command {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
