# Demo runbook

The whole loop in six commands. Times are real; a round on the recurrence pack takes 5 s to
5 min per model depending on the model, so a recording compresses time and says so on screen.

```bash
cd assay
git checkout -- demo/recurrence.py            # start from "not implemented"
python -m demo.calendar                       # 1. before: four chores, all "(not implemented yet)"

python -m assay run packs/chore-recurrence \  # 2. the round: three vendors, one frozen task,
  --models gemini:gemini-3.5-flash-lite,openrouter:nvidia/nemotron-3.5-lightning:free,openrouter:cohere/north-mini-code:free
                                              #    identical ceilings, hidden check, receipts

python -m assay room runs/<round-id> --target . --target-path demo/recurrence.py --port 8787
                                              # 3. open http://127.0.0.1:8787 — panes in random order,
                                              #    labels only; verdict and stop-reason chips; diffs
                                              # 4. Choose one blind → reveal: model, tokens, cost, latency
                                              # 5. Apply this result → a commit in this repo, diff read back

python -m demo.calendar                       # 6. after: the calendar prints real dates
git log -1                                    # the commit names the round, label, verdict, artefact hash
```

Recording from another machine: start the room with `--bind 0.0.0.0` and open
`http://<this-machine>:8787` from the recording machine; nothing to install there.

What to show if something fails on camera: a provider 503 appears as a `transport_error`
stop reason on that pane, not as a wrong answer; the round continues; the other panes still
judge. That is the failure handling, and it is real.

Free-model budget: OpenRouter `:free` models are capped at 50 requests per day on an account
below the $10 purchase threshold. One demo round with two `:free` contestants uses at most
12 requests. Develop against Gemini; spend the OpenRouter calls on the recorded round.
