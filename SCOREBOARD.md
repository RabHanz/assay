# Scoreboard

Every attempt this repository has run, as it happened. A row is a measurement; a pass
rate is what this pack measured on this many runs and nothing wider. Rows that ran under
different ceilings sit in different groups and are never summed.

## By model, per pack and ceiling

| pack | ceilings | model | passed | ran out of budget / empty | median tokens | median s | cost |
|---|---|---|---|---|---|---|---|
| chore-recurrence v1 | 6t/8000tok/300s | `gemini:gemini-3.5-flash-lite` | **2/3** | 0 | 2114 | 7.6 | free tier / n.r. |
| chore-recurrence v1 | 6t/8000tok/300s | `gemini:gemini-3.1-flash-lite` | **1/3** | 0 | 1051 | 6.3 | free tier / n.r. |
| chore-recurrence v1 | 6t/8000tok/300s | `openrouter:nvidia/nemotron-3.5-lightning:free` | **0/1** | 1 | 8000 | 215.4 | $0.00000 |

## Every attempt

| when | pack | model | verdict | stopped | tokens | reasoning | s | cost | chosen | round |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.1-flash-lite` | fail | done | 1000 | 0 | 6.3 | n.r. |  | [C](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.5-flash-lite` | fail | done | 1760 | 0 | 6.6 | n.r. |  | [D](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2114 | 0 | 7.6 | n.r. | yes | [A](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.1-flash-lite` | fail | done | 1151 | 0 | 7.4 | n.r. |  | [B](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:14 | chore-recurrence v1 | `nvidia/nemotron-3.5-lightning:free` | no_artifact | max_completion_tokens | 8000 | 7569 | 215.4 | $0.00000 |  | [C](https://github.com/RabHanz/assay/issues/1) |
| 2026-09-12 19:14 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2761 | 0 | 10.1 | n.r. | yes | [B](https://github.com/RabHanz/assay/issues/1) |
| 2026-09-12 19:14 | chore-recurrence v1 | `gemini-3.1-flash-lite` | pass | done | 1051 | 0 | 4.8 | n.r. |  | [A](https://github.com/RabHanz/assay/issues/1) |
