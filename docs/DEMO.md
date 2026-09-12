# Demo runbook

The loop lives in the repository, so the demo does too. Nothing runs anywhere but GitHub.

## The two-minute recording

The only human actions are a label, a reply, and a merge.

| | on screen | why it is there |
|---|---|---|
| 0:00 | `python -m demo.calendar` — four chores, all "(not implemented yet)" | the problem, in a form anyone reads |
| 0:10 | an issue written by the person with the problem: "the deep clean keeps landing on 31 March"; **add the `assay` label** | the single action that starts it; nobody runs anything |
| 0:20 | the Actions tab: the round is running on GitHub's own runners | the agent lives in the repository, not on a laptop |
| 0:40 | the board posts itself: what each attempt produced, a should-be column, only the rows somebody got wrong, one sentence per mistake | the comparison, blind, legible to the complainant |
| 1:05 | reply `/assay choose B` | the decision is a comment; only write access can make it |
| 1:20 | the reveal: who was who, receipts, and "the same model passed as A and failed as D" | receipts after the choice, never before |
| 1:30 | the pull request, carrying the schedule the code produces; **merge it** | the approval is the act the repository already had |
| 1:45 | `python -m demo.calendar` — real dates, 28 February among them | the bench output shipped |
| 1:55 | `SCOREBOARD.md`, updated by the same workflow | the repository is the record |

A round takes one to four minutes; compress it on screen and say so.

## Staged for the recording

- Issue **#3** is written in the complainant's voice and is **unlabelled**. Adding the label is the
  first beat. The Action is live on the repository; no local process is running.
- Issues **#6** and **#1** are complete public runs with their pull requests still open, in case
  the live round misbehaves. #6 shows the same model passing and failing; #1 shows a model burning
  its whole budget and writing nothing.

## If something fails on camera

A provider 503 shows as `transport_error` on that candidate, not as a wrong answer, and the round
continues. A model that exhausts its budget shows as `no artefact` with the ceiling named. Both are
real outcomes and both belong in the video. If the Action itself is delayed by runner queueing,
`python -m assay issue RabHanz/assay 3 --target-path demo/recurrence.py` does the same thing from
a terminal.

## Without GitHub at all

```bash
python -m assay demo                              # the chore pack, three free attempts, the board in the terminal
python -m assay demo --pack packs/split-the-bill  # the money pack
```

## Budgets

Gemini's free tier carries the defaults. OpenRouter `:free` models are capped at 50 requests a day
on an account below the $10 purchase threshold. Nothing in the demo path depends on paid credit.
