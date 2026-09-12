# The room — one HTML page over a JSON state file

The room is what the human sees while a round runs and after it. It is served by
`assay/room.py` (Python http.server) from `assay/room/index.html`. The page is ONE
self-contained HTML file: inline CSS and JS, no CDN, no framework, no build step.

## Endpoints (all served by room.py; the page never reads the filesystem)

- `GET /`            → index.html
- `GET /state.json`  → the round state below; the page polls it every 1000 ms
- `POST /choose`     body `{"label":"B"}` → records the blind choice; server flips `revealed`
- `POST /apply`      body `{"label":"B"}` → applies that contestant's artefact (only after reveal, only once)

## state.json (authoritative shape; the page must tolerate missing optional fields)

```json
{
  "round_id": "2026-09-12T18-40-11Z-chore-recurrence",
  "pack": {"name": "chore-recurrence", "version": "1", "entrypoint": "solution.py",
           "brief_excerpt": "first 300 chars of brief.md"},
  "policy": {"max_turns": 6, "max_completion_tokens": 8000, "wall_seconds": 300,
             "label": "identical ceilings for every pane"},
  "phase": "running" | "judged" | "chosen" | "applied",
  "blind": true,
  "revealed": false,
  "order": ["C","A","B"],
  "contestants": {
    "A": {
      "status": "queued" | "running" | "judging" | "done",
      "turn": 3,
      "last_tool": "write_file solution.py",
      "verdict": null | "pass" | "fail" | "no_artifact" | "check_error",
      "failures_count": 2,
      "failures": [["monthly:1:31 after 2026-01-31", "2026-03-31 want 2026-02-28"]],
      "stopped_because": "done" | "max_turns" | "max_completion_tokens" | "wall_seconds" | "empty_output" | "transport_error",
      "empty_output": false,
      "artifact_diff": "unified diff of fixture → workspace for the entrypoint, model names stripped",
      "artifact_bytes": 1830,
      "reveal": null
    }
  },
  "choice": null | {"label": "B", "at": "2026-09-12T18:45:02Z"},
  "apply": null | {"label": "B", "commit": "abc1234", "path": "…/solution.py", "diff_readback": "…", "at": "…"}
}
```

After `revealed` is true, each contestant's `reveal` is filled:

```json
"reveal": {"model": "google/gemini-3.1-flash-lite", "provider": "gemini",
           "completion_tokens": 3855, "reasoning_tokens": 3177, "prompt_tokens": 1200,
           "cost_usd": 0.00478, "cost_source": "provider usage field" | "not reported by provider (free tier)",
           "latency_s": 91.2, "turns": 3}
```

## What the page must do, in order of importance

1. Show one pane per contestant, in `order` (already randomised by the server), labelled
   A/B/C…, with live status while `phase` is `running`: status, turn count, last tool.
   Never show model, provider, cost, tokens or latency before `revealed`.
2. When `verdict` arrives, show it as a first-class chip: PASS / FAIL (with failures count and
   the failing cases) / NO ARTIFACT / CHECK ERROR. Show `stopped_because` as its own chip,
   separate from the verdict — "ran out of budget" and "got it wrong" are different results.
   `empty_output` true renders its own chip: EMPTY OUTPUT (billed, nothing returned).
3. Show `artifact_diff` in a scrollable monospace block per pane (this is what the human compares).
4. A "Choose" button per pane, enabled only when `phase` is `judged`. Clicking POSTs /choose.
   After that, the page shows the reveal fields per pane and the chosen pane highlighted.
5. After reveal, an "Apply this result" button on the chosen pane only (enabled when phase is
   `chosen`). Clicking POSTs /apply; then show the commit hash and the diff read back.
6. Two standing lines of text, always visible: the policy label ("Ceilings: 6 turns · 8,000
   completion tokens · 300 s — identical for every pane") and the honesty line ("Blind mode
   hides identity, cost and latency until you choose. Normalisation reduces identifying cues;
   diff style and length can still leak."). Also: "PASS means passed THIS pack's checks
   (pack <name> v<version>)".
7. Light theme, readable at 1280 px wide with 3 panes side by side, stacking below 900 px.
   No emoji. No animation beyond a subtle status pulse. System font stack. Tabular numerals
   for the numbers. It should look like a serious tool, not a dashboard template.

Keep it under ~500 lines. Everything deterministic; no model call from the page.
