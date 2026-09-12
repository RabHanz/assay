# Assay

You have a real task in your own codebase, and several models that claim they can do it. You want to know which one actually can, before you trust it with your work.

Every leaderboard answers a different question. They rank models on somebody else's problems. Assay ranks them on yours, and it finishes with the work done rather than with a score.

## It happens in your repository

You do not go anywhere to use this. The whole loop is an issue thread and a pull request.

1. **You open an issue** describing the task, naming a pack and the models to try.
2. **Each model works alone** in its own copy of the tree, through a real tool loop, with the
   same brief and the same ceilings.
3. **A check judges what they produced.** It was written before any of them saw the task and it
   never enters their workspace, so no model can read the cases grading it or overwrite its grader.
4. **The board arrives as a comment** on your issue, and it shows what each attempt PRODUCES —
   the household schedule its code computes, side by side, with every cell they disagree on
   marked. Not the source. A diff is the instructions for the work; the outcome is the work, and
   it is the only form in which somebody who does not read code can see which attempt is wrong.
   The diffs are there too, folded, for whoever wants them. No model names, no costs, no timings.
5. **You choose in a reply:** `/assay choose B`. That is the decision, and nothing else can make it.
6. **The reveal posts next** — who was who, with every receipt — and a **pull request opens**
   carrying exactly that attempt.
7. **You merge it.** The approval is the act your repository already had.

The comparison, the decision and the merge are three things you already do here. All this adds is
that the attempts were several, isolated, and anonymous until you picked one.

There is also a local side-by-side room (`python -m assay room`) for reading four diffs at once,
and the whole thing runs from the command line without GitHub if you prefer.

## Reading the outcomes

Four outcomes, deliberately kept apart, because collapsing them is how a scoreboard starts lying:

- **pass / fail** — passed these checks. Not a proof of correctness.
- **no_artifact** — the model never wrote the file. Running out of budget is not a wrong answer, and this project shipped a bug that showed it as one until the first real run caught it.
- **transport_error** — the provider failed. Not the model's fault, and retried before it is recorded.

Every receipt carries completion tokens, reasoning tokens, cost and elapsed time as reported by the provider itself, never estimated from a price table. Turns, tokens and wall-clock are three separate ceilings enforced by the host, and the board always says which policy it ran under, because a token ceiling is a judging policy rather than a neutral setting.

## One round is a sample, not a verdict

The first thing this tool measured was its own limit. Two models, the same pack, the same
ceilings, five runs each:

```
 passed     tokens min–max  median  model
   3/5             951–2015    1165  gemini-3.1-flash-lite
   2/5            1288–2715    1439  gemini-3.5-flash-lite
```

Every run finished cleanly — no ceilings hit, no provider errors. The same model simply solves
the task on some attempts and not others, and on two consecutive rounds these two swapped
places. So a board from one round tells you what happened once. `assay repeat` is the answer:

```bash
python -m assay repeat packs/chore-recurrence --models a,b --n 5
```

It reports a pass rate, the token spread, and every distinct failing case each model produced.
The failing cases are worth as much as the rate: one of these two kept missing a fortnightly
rule, the other missed the month-end clamp — the same case two unrelated paid vendors failed in
an earlier measurement.

## The token ceiling is a judging policy, not a neutral setting

The same pack, the same model, the same check; only the completion-token ceiling changed:

```
 passed     tokens min–max  model                     ceiling
   0/3            7076–8000  qwen3.7-flash              8,000
   0/3           14020–16000 qwen3.7-flash             16,000
```

Doubling the budget bought twice the spending and the same verdict. These models expand to fill
whatever ceiling they are given, so the ceiling is part of the judgement and has to be declared
with the result. `--max-tokens` overrides a pack's budget and writes the override into the board's
policy line, because two rounds under different ceilings are not one board.

## What we found while building it

On one recurrence task with seven hidden cases, free models alone: one passed, one spent 7,464 of its 8,000 tokens reasoning and never wrote a file, one provider returned 503 through three retries, and an earlier contender missed a single edge case. On an easier task every model passed, which is why an easy task is a cost benchmark and never a quality one.

Earlier measurement on paid models turned up the finding worth keeping: two models from unrelated vendors failed the identical case, returning 31 March where a monthly rule on the 31st must clamp to 28 February. No public leaderboard would surface that, because it lives in the intersection of one specific requirement and several models at once. That is what a personal pack is for.

## What already exists, and what does not

Running several models on one task in isolation and applying the winner is not new, and we
checked rather than assumed. Cursor ships `/best-of-n`: the same task across multiple models at
once, each in its own worktree, "so the candidates stay isolated from each other and from your
main checkout", then `/apply-worktree` to land the one you pick
([docs](https://cursor.com/docs/configuration/worktrees)). GitHub's Agent HQ assigns one issue to
Copilot, Claude and Codex together and lets you compare their pull requests and merge the best.
Harbor and promptfoo run sandboxed agent evaluations against hidden checks.

Three things none of them do:

1. **Nobody hides which model is which.** Cursor names the model on the worktree; Agent HQ puts
   the agent's name on the pull request. Here you choose before you know.
2. **Nobody puts a pre-written test in the selection seat.** Cursor's own words are that
   `/best-of-n` "compares runs only"; its optional judge is a model suggesting a favourite. The
   evaluation frameworks end at a score. Here a check written before the attempts existed decides
   what can be chosen at all.
3. **Nobody shows what the code DOES.** Every one of them compares source. This shows the
   schedule each attempt produces, against the schedule it should have produced.

GitHub already argues the third point for us: it renders prose with source and rendered views,
turns a CSV into a table, and ships two-up, swipe and onion-skin for image diffs. It treats the
rendered artefact as primary everywhere except code. This applies that instinct to code.

Not a universal ranking. Sample sizes are shown as they are. And publishing a board publishes
that pack's expected values, so a public round spends its hidden cases — packs are cheap and
meant to be replaced, and the property that matters is that the check predates every attempt.

Built by Rabee Hanzla.

---

## Reference

### Run it

Python 3.12, standard library only, plus `gh` for the GitHub loop. Put provider keys in
`keys.local` beside this file (`OPENROUTER_API_KEY=…`, `GEMINI_API_KEY=…`); it is git-ignored.

```bash
# the whole loop, in an issue thread: run, post the blind board, wait for `/assay choose X`,
# reveal the receipts, open the pull request
python -m assay issue RabHanz/assay 1 --target-path demo/recurrence.py
```

The issue body carries two machine-read lines: `pack: packs/<name>` and `models: a,b,c`.

```bash
# one round: a pack, several contestants, judged from outside, receipts kept
python -m assay run packs/chore-recurrence \
  --models gemini:gemini-3.5-flash-lite,openrouter:nvidia/nemotron-3.5-lightning:free,openrouter:cohere/north-mini-code:free

# the room: compare the diffs blind, choose, reveal, apply one result into a repo
python -m assay room runs/<round-id> --target . --target-path demo/recurrence.py
# then open http://127.0.0.1:8787/

# what a non-developer sees before and after the apply
python -m demo.calendar
```

`python -m assay models gemini --grep flash` lists what a provider offers. `docs/DEMO.md` is the
six-command runbook. `python -m unittest discover -s tests` runs the isolation tests.

### What a pack is

```
packs/<name>/
  pack.toml     name, version, entrypoint, and the three ceilings
  brief.md      the only thing the model is told
  fixture/      the starting working tree, copied into each workspace
  check.py      the acceptance check. Never copied into a workspace.
```

Two packs are included: `merge-windows` (easy; every model passes, only cost and latency differ)
and `chore-recurrence` (daily/weekly/monthly rules, N-step skips, holiday roll-forward, month-end
clamping; seven hidden cases; models diverge).

### What a round leaves behind

```
runs/<round-id>/
  state.json          what the room shows; identities absent until the choice is committed
  identities.json     label → model, read by the server only at reveal
  fixture-snapshot/   the fixture as it was, so apply can refuse stale evidence
  <label>/workspace/  the model's isolated tree
  <label>/receipt.json   turns, tokens, cost, cost source, latency, stop reason, tool calls
  <label>/verdict.json   pass / fail (with cases) / no_artifact / check_error
```

### The guarantees, and where each one lives

1. **The check never enters the workspace.** `pack.stage` copies only `fixture/`; `judge` runs
   `check.py` from outside with the workspace merely importable. Tested.
2. **Receipts come from the provider's usage field.** `providers.chat` sends
   `usage: {include: true}` to OpenRouter and records what comes back; Gemini's endpoint reports
   tokens and no cost, and the receipt says so.
3. **Three ceilings, enforced by the host, reported separately.** `run.run_one` stops at
   whichever hits first and names it in `stopped_because`.
4. **An empty visible answer is its own status** (`empty_output`), billed and shown as such.
5. **The budget policy is on screen**, identical for every pane in a round.
6. **Blind means blind.** Labels assigned at random, pane order shuffled again; identity, cost
   and latency reach the page only after the choice is committed; model and vendor names are
   stripped from the diffs shown. Normalisation reduces identifying cues; diff style and length
   can still leak, and the page says so.
7. **"Pass" means passed this pack's checks.** Pack name and version on screen; `apply` refuses
   if the target file changed since the round's fixture was frozen.
8. **Apply exactly one result.** Only the chosen, passing artefact, once; the commit message
   carries the round, the label, the verdict and the artefact hash.

Every path a tool touches is confined to the workspace. `run_python` exists behind an
off-by-default flag (`--allow-exec`) because it executes model-authored code on your machine.

### Prior work

`assay/pack.py` and `assay/judge.py` were drafted before the hackathon window and never run; a
throwaway harness (not in this repo) measured six models on the recurrence task before the
window and is the reason the pack exists. Everything else here was written inside the window.
