# Scoreboard

Every attempt this repository has run, as it happened. A row is a measurement; a pass
rate is what this pack measured on this many runs and nothing wider. Rows that ran under
different ceilings sit in different groups and are never summed.

## By model, per pack and ceiling

| pack | ceilings | model | passed | ran out of budget / empty | median tokens | median s | cost |
|---|---|---|---|---|---|---|---|
| chore-recurrence v1 | 6t/8000tok/300s | `openrouter:openai/gpt-oss-20b` | **2/2** | 1 | 8000 | 131.3 | $0.00209 |
| chore-recurrence v1 | 6t/8000tok/300s | `gemini:gemini-3.5-flash-lite` | **5/7** | 0 | 2347 | 8.5 | free tier / n.r. |
| chore-recurrence v1 | 6t/8000tok/300s | `gemini:gemini-3.1-flash-lite` | **2/4** | 0 | 1051 | 6.3 | free tier / n.r. |
| chore-recurrence v1 | 6t/8000tok/300s | `openrouter:nvidia/nemotron-3.5-lightning:free` | **0/1** | 1 | 8000 | 215.4 | $0.00000 |
| chore-recurrence v1 | 6t/8000tok/300s | `openrouter:qwen/qwen3.7-flash` | **0/2** | 2 | 8000 | 70.2 | $0.00218 |

## Every attempt

| when | pack | model | verdict | stopped | tokens | reasoning | s | cost | chosen | round |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-12 21:58 | chore-recurrence v1 | `qwen/qwen3.7-flash` | no_artifact (empty) | empty_output | 8000 | 7972 | 70.2 | $0.00109 |  | [B](https://github.com/RabHanz/assay/issues/14) |
| 2026-09-12 21:58 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2450 | 0 | 10.3 | n.r. | yes | [C](https://github.com/RabHanz/assay/issues/14) |
| 2026-09-12 21:58 | chore-recurrence v1 | `openai/gpt-oss-20b` | pass | empty_output | 8000 | 5442 | 103.2 | $0.00093 |  | [A](https://github.com/RabHanz/assay/issues/14) |
| 2026-09-12 21:27 | chore-recurrence v1 | `openai/gpt-oss-20b` | pass | done | 6831 | 2938 | 131.3 | $0.00116 | yes | [B](https://github.com/RabHanz/assay/issues/12) |
| 2026-09-12 21:27 | chore-recurrence v1 | `gemini-3.5-flash-lite` | fail | done | 2347 | 0 | 8.5 | n.r. |  | [A](https://github.com/RabHanz/assay/issues/12) |
| 2026-09-12 21:27 | chore-recurrence v1 | `qwen/qwen3.7-flash` | no_artifact (empty) | empty_output | 8000 | 7972 | 67.2 | $0.00109 |  | [C](https://github.com/RabHanz/assay/issues/12) |
| 2026-09-12 20:17 | chore-recurrence v1 | `gemini-3.1-flash-lite` | pass | done | 1011 | 0 | 4.4 | n.r. | yes | [A](https://github.com/RabHanz/assay/issues/9) |
| 2026-09-12 20:17 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 1610 | 0 | 5.9 | n.r. |  | [B](https://github.com/RabHanz/assay/issues/9) |
| 2026-09-12 20:17 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2821 | 0 | 9.5 | n.r. |  | [C](https://github.com/RabHanz/assay/issues/9) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.1-flash-lite` | fail | done | 1000 | 0 | 6.3 | n.r. |  | [C](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.5-flash-lite` | fail | done | 1760 | 0 | 6.6 | n.r. |  | [D](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2114 | 0 | 7.6 | n.r. | yes | [A](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:43 | chore-recurrence v1 | `gemini-3.1-flash-lite` | fail | done | 1151 | 0 | 7.4 | n.r. |  | [B](https://github.com/RabHanz/assay/issues/6) |
| 2026-09-12 19:14 | chore-recurrence v1 | `nvidia/nemotron-3.5-lightning:free` | no_artifact | max_completion_tokens | 8000 | 7569 | 215.4 | $0.00000 |  | [C](https://github.com/RabHanz/assay/issues/1) |
| 2026-09-12 19:14 | chore-recurrence v1 | `gemini-3.5-flash-lite` | pass | done | 2761 | 0 | 10.1 | n.r. | yes | [B](https://github.com/RabHanz/assay/issues/1) |
| 2026-09-12 19:14 | chore-recurrence v1 | `gemini-3.1-flash-lite` | pass | done | 1051 | 0 | 4.8 | n.r. |  | [A](https://github.com/RabHanz/assay/issues/1) |
