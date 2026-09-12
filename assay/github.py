"""The bake-off, in the place developers already work: an issue thread and a pull request.

The loop, end to end, without leaving GitHub:

    1. Someone opens an issue labelled `assay` naming a pack.
    2. assay runs the round: every model gets its own isolated workspace and the same brief.
    3. A hidden check judges each artefact, and the board is posted back as ONE comment on that
       issue — candidates labelled A, B, C, their verdicts, their stop reasons, and their diffs
       folded into <details> blocks. No model names. No costs. No latencies.
    4. A human replies in the thread: `/assay choose B`.
    5. Only then does assay reveal who was who, with the receipts, and open a pull request
       carrying exactly that one artefact.
    6. Merging the pull request is the approval. It is the act the repository already has.

Why here rather than in a page of our own: the comparison, the decision and the merge are three
things a developer already does in this surface, with tools they already trust — GitHub renders
the diff, keeps the thread, and records who decided. The only thing assay adds is that the
attempts are several, isolated, and anonymous until the choice is made.

Everything goes through `gh`, which is already authenticated; no token is read or stored here.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from .round import Round
from .providers import parse_model

# The command must START a line — so a quoted line ("> /assay choose B") and a mention of the
# syntax inside prose never count as a decision — but anything may follow it on that line.
CHOICE = re.compile(r"^[^\S\n]*/assay\s+choose\s+([A-Za-z])\b", re.M)
PACK = re.compile(r"^\s*pack:\s*([A-Za-z0-9._/-]+)\s*$", re.M | re.I)
MODELS = re.compile(r"^\s*models:\s*(.+?)\s*$", re.M | re.I)
MARKER = "<!-- assay:board -->"
REVEAL_MARKER = "<!-- assay:reveal -->"


class GhError(RuntimeError):
    pass


def gh(*args: str, stdin: str | None = None) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, input=stdin)
    if p.returncode != 0:
        raise GhError(f"gh {' '.join(args[:3])}…: {(p.stderr or p.stdout).strip()[:400]}")
    return p.stdout


def gh_json(*args: str):
    return json.loads(gh(*args) or "null")


# ── the board comment ───────────────────────────────────────────────────────

def _fold(title: str, body: str, lang: str = "diff") -> str:
    return f"<details><summary>{title}</summary>\n\n```{lang}\n{body.rstrip()[:55000]}\n```\n\n</details>"


def board_comment(state: dict, round_id: str) -> str:
    pack, policy = state["pack"], state["policy"]
    lines = [
        MARKER,
        f"### {len(state['contestants'])} attempts at `{pack['name']}` v{pack['version']}, judged",
        "",
        f"Each attempt ran alone in its own copy of the tree, with the same brief and the same "
        f"ceilings: **{policy['max_turns']} turns · {policy['max_completion_tokens']} completion tokens · "
        f"{policy['wall_seconds']}s**. A check written before any of them saw the task, and that none of "
        f"them could read, judged what they produced.",
        "",
        "| | verdict | stopped | what the check said |",
        "|---|---|---|---|",
    ]
    for label in state["order"]:
        c = state["contestants"][label]
        verdict = {"pass": "**passed**", "fail": "**failed**", "no_artifact": "no file written",
                   "check_error": "check error"}.get(c.get("verdict"), str(c.get("verdict")))
        if c.get("verdict") == "fail" and c.get("failures_count"):
            verdict += f" ({c['failures_count']} cases)"
        note = ""
        if c.get("failures"):
            note = "; ".join(f"`{f[0]}` → {f[1]}" for f in c["failures"][:2])
        elif c.get("empty_output"):
            note = "billed its whole budget and returned nothing"
        elif c.get("verdict") == "no_artifact":
            note = "stopped before writing the file"
        lines.append(f"| **{label}** | {verdict} | `{c.get('stopped_because')}` | {note} |")
    lines += ["", "Identities, costs and timings stay hidden until someone chooses. Read the code:"]
    for label in state["order"]:
        c = state["contestants"][label]
        diff = c.get("artifact_diff") or ""
        if diff.strip():
            lines.append(_fold(f"Candidate {label} — {c.get('artifact_bytes', 0)} bytes", diff))
        else:
            lines.append(f"<!-- {label}: no file was written -->")
    lines += [
        "",
        "---",
        "",
        "**Reply `/assay choose B`** (any label above) to commit to one. That reveals every identity "
        "and receipt, and opens a pull request carrying exactly that attempt — nothing else is applied.",
        "",
        f"<sub>round `{round_id}` · a pass means it passed this pack's checks, not that the code is "
        f"correct · normalisation strips model names from these diffs, but style and length can still "
        f"hint at who wrote what</sub>",
    ]
    return "\n".join(lines)


def reveal_comment(round_dir: Path, identities: dict, chosen: str, pr_url: str | None) -> str:
    rows = ["<!-- assay:reveal -->", f"### Chosen blind: **{chosen}**", "",
            "| | model | verdict | turns | completion tokens | reasoning | cost | elapsed |",
            "|---|---|---|---|---|---|---|---|"]
    state = json.loads((round_dir / "state.json").read_text())
    for label in state["order"]:
        rec_path = round_dir / label / "receipt.json"
        rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
        provider, model = parse_model(identities.get(label, "?"))
        c = state["contestants"][label]
        cost = rec.get("cost_usd")
        cost_s = f"${cost:.5f}" if isinstance(cost, (int, float)) and cost else (
            "free tier" if rec.get("cost_source", "").startswith("not reported") else "$0.00000")
        mark = " ←" if label == chosen else ""
        rows.append(f"| **{label}**{mark} | `{provider}:{model}` | {c.get('verdict')} | {rec.get('turns')} | "
                    f"{rec.get('completion_tokens')} | {rec.get('reasoning_tokens')} | {cost_s} | "
                    f"{rec.get('latency_s')}s |")
    rows += ["", "Cost is the provider's own figure where it reports one; there is no price table in this tool."]
    if pr_url:
        rows += ["", f"The chosen attempt is now a pull request: {pr_url}", "",
                 "Merging it is the approval. Nothing has been written to the default branch."]
    return "\n".join(rows)


# ── the loop ────────────────────────────────────────────────────────────────

def read_issue(repo: str, number: int) -> dict:
    return gh_json("issue", "view", str(number), "--repo", repo, "--json",
                   "number,title,body,comments,labels,state")


def run_for_issue(repo: str, number: int, runs_dir: str | Path = "runs",
                  default_models: str = "", post: bool = True) -> dict:
    """Run one round for an issue and post the blind board. Returns the round."""
    issue = read_issue(repo, number)
    body = issue.get("body") or ""
    pack_m, models_m = PACK.search(body), MODELS.search(body)
    if not pack_m:
        raise GhError(f"issue #{number} does not name a pack. Add a line: `pack: packs/<name>`")
    specs = [s.strip() for s in (models_m.group(1) if models_m else default_models).split(",") if s.strip()]
    if not specs:
        raise GhError("no models: put `models: a,b,c` in the issue body or pass --models")
    print(f"issue #{number}: pack {pack_m.group(1)}, {len(specs)} attempts", flush=True)
    rnd = Round(pack_m.group(1), specs, runs_dir, blind=True)
    rnd.run()
    if post:
        comment = board_comment(rnd.state, rnd.round_id)
        gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-", stdin=comment)
        print(f"posted the board to {repo}#{number}", flush=True)
    (rnd.dir / "issue.json").write_text(json.dumps({"repo": repo, "issue": number}, indent=2))
    return rnd


def open_pr(repo: str, number: int, round_dir: Path, label: str, target_path: str | None = None) -> str:
    """Push the chosen artefact as a branch and open a pull request. Returns its URL."""
    state = json.loads((round_dir / "state.json").read_text())
    pack = state["pack"]
    entry = target_path or pack["entrypoint"]
    src = round_dir / label / "workspace" / pack["entrypoint"]
    if not src.exists():
        raise GhError(f"candidate {label} wrote no artefact")
    c = state["contestants"][label]
    branch = f"assay/{state['round_id'].lower()}/{label.lower()}"
    base = gh_json("repo", "view", repo, "--json", "defaultBranchRef")["defaultBranchRef"]["name"]

    # In its own clone, never the working checkout: the branch dance would otherwise carry
    # whatever the developer has open into the pull request, which is exactly the kind of
    # "what shipped is not what was reviewed" this tool exists to prevent.
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="assay-pr-"))
    subprocess.run(["gh", "repo", "clone", repo, str(work / "repo"), "--", "--depth", "1",
                    "--branch", base], capture_output=True, text=True, check=True)
    here = work / "repo"
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=here, check=True)
    dst = here / entry
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    subprocess.run(["git", "add", str(dst)], cwd=here, check=True)
    msg = (f"assay: candidate {label} from {state['round_id']}\n\n"
           f"pack {pack['name']} v{pack['version']} · verdict {c.get('verdict')} · "
           f"stopped {c.get('stopped_because')}\nchosen blind on #{number}; identity revealed only after the choice.")
    subprocess.run(["git", "-c", "user.name=assay", "-c", "user.email=assay@localhost",
                    "commit", "-q", "-m", msg], cwd=here, check=True)
    subprocess.run(["git", "push", "-q", "-u", "origin", branch], cwd=here, check=True)
    pr_body = (f"Chosen blind on #{number} as candidate **{label}** of {len(state['contestants'])}.\n\n"
               f"It passed the hidden check for pack `{pack['name']}` v{pack['version']} "
               f"({c.get('failures_count') or 0} failing cases), under ceilings of "
               f"{state['policy']['max_turns']} turns · {state['policy']['max_completion_tokens']} completion "
               f"tokens · {state['policy']['wall_seconds']}s.\n\n"
               f"Merging this is the approval. The other attempts were discarded.\n\n"
               f"Closes #{number}")
    url = gh("pr", "create", "--repo", repo, "--base", base, "--head", branch,
             "--title", f"assay: {pack['name']} — candidate {label}", "--body-file", "-", stdin=pr_body).strip()
    return url.splitlines()[-1] if url else ""


DECIDERS = {"admin", "maintain", "write"}


def may_decide(repo: str, login: str) -> bool:
    """Can this account decide what lands in this repository?

    Resolved from the repository's own permission API, never from the comment body and never
    from a name typed in text. The repo is public, so anyone at all can write
    `/assay choose B`; only someone who could merge the result may make the choice that opens
    the pull request. Same law the rest of this tool follows: a typed identity is a proposal,
    an authorisation comes from the server.
    """
    try:
        data = gh_json("api", f"repos/{repo}/collaborators/{login}/permission")
    except GhError:
        return False
    perm = (data or {}).get("permission") or ""
    return perm in DECIDERS


def find_choice(repo: str, number: int, refused: set[str] | None = None) -> tuple[str, str, bool] | None:
    """The first choice in the thread that has not already been answered.

    Positioned by the thread itself rather than by a clock: everything before the board comment
    is prologue, a reveal comment means the decision is already made, and a refusal we have
    already posted is remembered by comment id. A wall-clock cursor loses any choice made while
    the process was restarting — which happened the first time this ran.
    """
    issue = read_issue(repo, number)
    comments = issue.get("comments") or []
    seen_board = False
    for c in comments:
        body = c.get("body") or ""
        if REVEAL_MARKER in body:
            return None  # already decided
        if MARKER in body:
            seen_board = True
            continue
        if not seen_board:
            continue
        if c.get("url") in (refused or set()):
            continue
        m = CHOICE.search(body)
        if m:
            who = (c.get("author") or {}).get("login", "?")
            return m.group(1).upper(), who, may_decide(repo, who)
    return None


def watch(repo: str, label: str = "assay", interval: int = 30, runs_dir: str | Path = "runs",
          default_models: str = "", target_path: str | None = None, once: bool = False) -> None:
    """Live in the repository: any issue carrying the label gets a round, a board, and a pull request.

    This is the difference between a tool you run and an agent that is there: nobody invokes it
    per task. Someone files an issue the way they already file issues, adds the label, and the
    attempts arrive in the thread. An issue is taken once — the marker comment on it is the
    record that it has been handled, so a restart never re-runs a round someone has already read.
    """
    print(f"watching {repo} for issues labelled `{label}` …", flush=True)
    while True:
        try:
            issues = gh_json("issue", "list", "--repo", repo, "--label", label, "--state", "open",
                             "--json", "number,title", "--limit", "20") or []
        except GhError as e:
            print(f"list failed: {str(e)[:160]}", flush=True)
            issues = []
        for row in issues:
            number = row["number"]
            try:
                seen = read_issue(repo, number)
                if any(MARKER in (c.get("body") or "") for c in (seen.get("comments") or [])):
                    continue
                print(f"#{number} {row['title'][:60]}", flush=True)
                rnd = run_for_issue(repo, number, runs_dir, default_models=default_models)
                serve_issue(repo, number, rnd.dir, interval=interval, target_path=target_path)
            except Exception as e:  # one bad issue never stops the watch
                print(f"#{number}: {type(e).__name__}: {str(e)[:200]}", flush=True)
                try:
                    gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
                       stdin=f"{MARKER}\nassay could not run this issue: `{str(e)[:300]}`")
                except GhError:
                    pass
        if once:
            return
        time.sleep(interval)


def serve_issue(repo: str, number: int, round_dir: Path, interval: int = 20,
                target_path: str | None = None, timeout: int = 3600) -> dict:
    """Wait for a human to choose in the thread, then reveal and open the pull request."""
    identities = json.loads((round_dir / "identities.json").read_text())
    refused: set[str] = set()
    print(f"waiting for `/assay choose <label>` on {repo}#{number} …", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        choice = find_choice(repo, number, refused=refused)
        if choice:
            label, who, authorised = choice
            issue = read_issue(repo, number)
            url = next((c.get("url") for c in reversed(issue.get("comments") or [])
                        if CHOICE.search(c.get("body") or "")), None)
            if not authorised:
                gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
                   stdin=(f"@{who} — a choice here opens a pull request against this repository, so it is "
                          f"taken only from an account with write access. Your permission on this repo does "
                          f"not include it, so nothing has moved. The board above is unchanged and still blind."))
                print(f"{who} chose {label} without write access; refused", flush=True)
                refused.add(url)
                continue
            if label not in identities:
                gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
                   stdin=f"`{label}` is not one of the candidates ({', '.join(sorted(identities))}).")
                refused.add(url)
                continue
            print(f"{who} chose {label}", flush=True)
            state = json.loads((round_dir / "state.json").read_text())
            state["choice"] = {"label": label, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": who}
            state["phase"], state["revealed"] = "chosen", True
            (round_dir / "state.json").write_text(json.dumps(state, indent=2))
            pr = ""
            try:
                if state["contestants"][label].get("verdict") == "pass":
                    pr = open_pr(repo, number, round_dir, label, target_path)
            except Exception as e:
                gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
                   stdin=f"Chose **{label}**, but opening the pull request failed: `{str(e)[:300]}`")
            gh("issue", "comment", str(number), "--repo", repo, "--body-file", "-",
               stdin=reveal_comment(round_dir, identities, label, pr or None))
            return {"label": label, "by": who, "pr": pr}
        time.sleep(interval)
    raise GhError(f"no choice on #{number} within {timeout}s")
