# assay

Point a task pack at several models. Each model does the task in its own isolated workspace,
with real tools. A check that was written before any model saw the task, and that no model can
read, judges what each one produced. You compare the produced code blind, choose one, see who it
was and what it cost, and one approval applies exactly that result into your repository.

An evaluation framework ends at a score. This ends at an applied patch.

## Run it

Python 3.12, standard library only. Put provider keys in `keys.local` beside this file
(`OPENROUTER_API_KEY=…`, `GEMINI_API_KEY=…`); it is git-ignored.

```bash
# one round: a pack, several contestants, judged from outside, receipts kept
python -m assay run packs/chore-recurrence \
  --models gemini:gemini-3.1-flash-lite,openrouter:nvidia/nemotron-3.5-lightning:free,openrouter:qwen/qwen3.7-flash

# the room: compare the diffs blind, choose, reveal, apply one result into a repo
python -m assay room runs/<round-id> --target . --target-path demo/recurrence.py
# then open http://127.0.0.1:8787/

# what a non-developer sees before and after the apply
python -m demo.calendar
```

`python -m assay models gemini --grep flash` lists what a provider offers.

## What a pack is

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

## What a receipt is

Every contestant leaves `receipt.json` with: turns, prompt tokens, completion tokens, reasoning
tokens, cost, cost source, wall-clock seconds, why it stopped, whether it emitted an artefact,
and each tool call. Cost is the provider's own figure (`usage.cost` from OpenRouter) or is marked
"not reported by provider"; there is no price table in this code. The verdict is separate:
`verdict.json` holds pass / fail with the failing cases / no_artifact / check_error.

## The guarantees, and where each one lives

1. **The check never enters the workspace.** `pack.stage` copies only `fixture/`; `judge` runs
   `check.py` from outside with the workspace merely importable. Tested.
2. **Receipts come from the provider's usage field.** `providers.chat` sends
   `usage: {include: true}` to OpenRouter and records what comes back; Gemini's endpoint reports
   tokens and no cost, and the receipt says so.
3. **Three ceilings, enforced by the host, reported separately:** turns, cumulative completion
   tokens, wall-clock. `run.run_one` stops at whichever hits first and names it in
   `stopped_because`. "Ran out of budget" and "got it wrong" are different columns.
4. **An empty visible answer is its own status.** A reasoning model can spend its whole budget
   thinking and return nothing, billed in full. That is `empty_output`, not a failure.
5. **The budget policy is on screen.** The room shows the ceilings, identical for every pane.
   Rows run under different ceilings are not comparable and are never shown as one board.
6. **Blind means blind.** Labels are assigned at random and pane order is shuffled again;
   identity, cost and latency are held in `identities.json` and the receipts, and reach the page
   only after the choice is committed. Model and vendor names are stripped from the diffs shown.
   Normalisation reduces identifying cues; diff style and length can still leak, and the page says so.
7. **"Pass" means passed this pack's checks.** The pack name and version are on screen; the
   fixture is snapshotted per round, and `apply` refuses if the target file changed since.
8. **Apply exactly one result.** Only the chosen, passing artefact can be applied, once; the
   commit message carries the round, the label, the verdict and the artefact hash.

Every path a tool touches is confined to the workspace. `run_python` exists behind an
off-by-default flag (`--allow-exec`) because it executes model-authored code on your machine.

## Limits, stated

- One round is one task. Six models on one problem is a wider sample of models, not of work.
  Early boards are provisional and say so.
- A token ceiling is a judging policy, not a neutral setting: the same model, same task and same
  verdict has cost nine times the wall-clock at a higher ceiling because it filled it.
- A "pass" is a pass on the pack's cases. Hidden cases test disclosed requirements; they do not
  prove correctness beyond them.
- Whether anyone will pay for this is untested.

## Neighbours

Portable task datasets, sandboxed agent runs and cost or latency assertions exist in
[Harbor](https://www.harborframework.com/) and [promptfoo](https://www.promptfoo.dev/), among
others. What assay adds is the last step: compare the produced artefacts blind, choose one, and
apply it into the working repository behind a single human approval.

## Prior work

`assay/pack.py` and `assay/judge.py` were drafted before the hackathon window and never run; a
throwaway harness (not in this repo) measured six models on the recurrence task before the
window and is the reason the pack exists. Everything else here was written inside the window.
