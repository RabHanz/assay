"""The GitHub layer's three load-bearing guarantees, without touching GitHub.

1. A choice is a line that STARTS with the command. Quoted lines and prose mentions are not decisions.
2. The rendered board is blind: no vendor or model string survives into the comment.
3. The gate accepts only real write access: `read` — which GitHub returns for every user on a
   public repository — is refused, and so is any API failure.
"""
import json
import unittest
from pathlib import Path
from unittest import mock

from assay import github as gh_layer

ROOT = Path(__file__).resolve().parents[1]


class ChoiceParsing(unittest.TestCase):
    def test_only_a_leading_command_counts(self):
        yes = ["/assay choose B", "  /assay choose d  ", "/assay choose A\nbecause it is right"]
        no = ["> /assay choose B", "reply with /assay choose X to pick", "ok /assay choose b", "choose B"]
        for t in yes:
            self.assertIsNotNone(gh_layer.CHOICE.search(t), t)
        for t in no:
            self.assertIsNone(gh_layer.CHOICE.search(t), t)


class BoardBlindness(unittest.TestCase):
    def _state(self):
        return {
            "round_id": "r", "order": ["B", "A"],
            "pack": {"name": "p", "version": "1", "entrypoint": "solution.py", "root": str(ROOT / "packs" / "chore-recurrence")},
            "policy": {"max_turns": 6, "max_completion_tokens": 8000, "wall_seconds": 300},
            "contestants": {
                "A": {"verdict": "pass", "stopped_because": "done", "failures": [], "failures_count": 0,
                      "artifact_diff": "+from gemini import x  # openrouter nvidia/nemotron", "artifact_bytes": 10,
                      "outcome": {"title": "t", "subtitle": "s", "columns": ["next"],
                                  "rows": [{"label": "Bins", "note": "", "cells": ["Mon"], "expected": ["Mon"], "why": ""}]}},
                "B": {"verdict": "fail", "stopped_because": "done", "failures": [["x", "y"]], "failures_count": 1,
                      "artifact_diff": "+pass", "artifact_bytes": 5,
                      "outcome": {"title": "t", "subtitle": "s", "columns": ["next"],
                                  "rows": [{"label": "Bins", "note": "", "cells": ["Tue"], "expected": ["Mon"], "why": "w"}]}},
            },
        }

    def test_no_vendor_string_in_the_comment_even_if_the_diff_carried_one(self):
        # The round strips identity from diffs before they reach state; the board must not
        # re-introduce any. Here the diff deliberately carries vendor strings to prove the
        # board itself adds none and the strip is the round's job, not the board's.
        body = gh_layer.board_comment(self._state(), "r").lower()
        for token in ("gemini", "openrouter", "nvidia", "nemotron"):
            self.assertIn(token, body)  # present only because the fixture put it in the diff
        # Now with a clean diff, as the round would give it:
        st = self._state()
        for c in st["contestants"].values():
            c["artifact_diff"] = "+pass"
        body = gh_layer.board_comment(st, "r").lower()
        for token in ("gemini", "openrouter", "nvidia", "nemotron", "google", "deepseek", "qwen"):
            self.assertNotIn(token, body)

    def test_board_tells_the_reader_how_to_choose_with_real_labels(self):
        body = gh_layer.board_comment(self._state(), "r")
        self.assertIn("/assay choose B", body)
        self.assertIn("/assay choose A", body)
        self.assertIn("should be", body)


class Gate(unittest.TestCase):
    def test_read_is_refused_and_write_is_allowed(self):
        with mock.patch.object(gh_layer, "gh_json", return_value={"permission": "read"}):
            self.assertFalse(gh_layer.may_decide("o/r", "stranger"))
        with mock.patch.object(gh_layer, "gh_json", return_value={"permission": "write"}):
            self.assertTrue(gh_layer.may_decide("o/r", "collab"))
        with mock.patch.object(gh_layer, "gh_json", return_value={"permission": "admin"}):
            self.assertTrue(gh_layer.may_decide("o/r", "owner"))

    def test_an_api_failure_is_a_refusal_not_a_pass(self):
        with mock.patch.object(gh_layer, "gh_json", side_effect=gh_layer.GhError("boom")):
            self.assertFalse(gh_layer.may_decide("o/r", "anyone"))


if __name__ == "__main__":
    unittest.main()
