# Demo runbook

The loop lives in the repository, so the demo does too. Nothing here needs a local UI.

## The two-minute recording

The only human action before the board appears is one click.

| | on screen | why it is there |
|---|---|---|
| 0:00 | `python -m demo.calendar` — four chores, all "(not implemented yet)" | the problem, in a form anyone reads |
| 0:10 | the issue, describing the bug; **add the `assay` label** | the single human action; nothing is invoked |
| 0:20 | `python -m assay watch` picks it up in the terminal | the agent is there, not summoned |
| 0:35 | the board posts itself into the thread: candidates A–D, verdicts, stop reasons, diffs | the comparison, blind, in the place code is already reviewed |
| 1:00 | read the failing cases on one candidate; note the one that wrote nothing at all | budget exhaustion and a wrong answer are different results |
| 1:15 | comment `/assay choose B` | the decision is a comment, and only write access makes it one |
| 1:25 | the reveal comment: who was who, tokens, reasoning tokens, cost, elapsed | the receipts, after the choice, never before |
| 1:35 | the pull request opens; **merge it** | the approval is the act the repository already had |
| 1:50 | `python -m demo.calendar` — real dates, 28 February among them | the bench output shipped |

A run takes longer than the video, so compress it on screen and say so.

## In GitHub, start to finish

1. **Open an issue** describing the task, with two machine-read lines in the body:

   ```
   pack: packs/chore-recurrence
   models: gemini:gemini-3.1-flash-lite,gemini:gemini-3.5-flash-lite,openrouter:nvidia/nemotron-3.5-lightning:free
   ```

2. **Run the round against it.** Every model gets its own copy of the tree and the same brief;
   a check none of them can read judges what each produced; the blind board posts itself into
   the thread.

   ```bash
   python -m assay issue RabHanz/assay <issue-number> --target-path demo/recurrence.py
   ```

3. **Read the board in the thread.** Candidates A, B, C with verdicts, stop reasons and the
   failing cases; each one's diff folded into a `<details>` block that GitHub renders itself.
   No model names, no costs, no timings.

4. **Choose in a comment:** `/assay choose B`. That is the decision, and it is irreversible.

5. **The reveal posts as the next comment** — who was who, turns, tokens, reasoning tokens,
   cost and elapsed time — and a **pull request** opens carrying exactly that attempt.

6. **Merge the pull request.** That is the approval; the repository already had the act.

7. `python -m demo.calendar` before and after: four chores reading "(not implemented yet)",
   then real dates, including the month-end case clamping to 28 February.

## The side-by-side view, when you want it

The thread is where the decision happens; the room is for reading four diffs at once.

```bash
python -m assay run packs/chore-recurrence --models a,b,c
python -m assay room runs/<round-id> --target . --target-path demo/recurrence.py --bind 0.0.0.0
```

## Budgets

OpenRouter `:free` models are capped at 50 requests a day on an account below the $10 purchase
threshold, and one round with two of them uses at most twelve. Gemini's free tier carries
development. Nothing in the demo path depends on paid credit.

## If something fails on camera

A provider 503 shows as `transport_error` on that candidate, not as a wrong answer, and the
round continues. A model that exhausts its budget shows as `no_artifact` with the ceiling named.
Both are real outcomes and both belong in the video.
