"""The two guarantees a verdict rests on: the check never enters the workspace, and a tool
cannot reach outside it. No model is called here; these are properties of the host code."""
import json
import tempfile
import unittest
from pathlib import Path

from assay import pack as packmod
from assay.judge import judge
from assay.run import _confine, _execute

ROOT = Path(__file__).resolve().parents[1]


class Isolation(unittest.TestCase):
    def test_check_is_not_staged_into_the_workspace(self):
        p = packmod.load(ROOT / "packs" / "merge-windows")
        with tempfile.TemporaryDirectory() as d:
            ws = p.stage(Path(d) / "ws")
            names = {x.name for x in ws.rglob("*")}
            self.assertIn("solution.py", names)
            self.assertNotIn("check.py", names)
            self.assertNotIn("pack.toml", names)

    def test_paths_are_confined(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "ws"
            ws.mkdir()
            for bad in ("../secret", "/etc/passwd", "~/x", "a/../../b", ""):
                with self.assertRaises(ValueError, msg=bad):
                    _confine(ws, bad)
            self.assertTrue(str(_confine(ws, "sub/file.py")).startswith(str(ws.resolve())))

    def test_tool_errors_never_raise(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            out = json.loads(_execute(ws, "read_file", {"path": "../../etc/hostname"}, False))
            self.assertIn("error", out)
            out = json.loads(_execute(ws, "run_python", {"path": "x.py"}, False))
            self.assertIn("disabled", out["error"])
            out = json.loads(_execute(ws, "nonsense", {}, False))
            self.assertIn("error", out)

    def test_judge_reports_a_missing_artefact_as_no_artifact_not_fail(self):
        p = packmod.load(ROOT / "packs" / "merge-windows")
        with tempfile.TemporaryDirectory() as d:
            v = judge(p.check, Path(d), p.entrypoint)
            self.assertEqual(v.status, "no_artifact")

    def test_judge_passes_a_correct_artefact_and_fails_a_wrong_one(self):
        p = packmod.load(ROOT / "packs" / "merge-windows")
        good = ("def merge_windows(w):\n    w=sorted([list(x) for x in w]); out=[]\n"
                "    for s,e in w:\n        if out and s<=out[-1][1]: out[-1][1]=max(out[-1][1],e)\n"
                "        else: out.append([s,e])\n    return out\n")
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "ws"; ws.mkdir()
            (ws / "solution.py").write_text(good)
            self.assertEqual(judge(p.check, ws, p.entrypoint).status, "pass")
            (ws / "solution.py").write_text("def merge_windows(w):\n    return w\n")
            v = judge(p.check, ws, p.entrypoint)
            self.assertEqual(v.status, "fail")
            self.assertGreater(len(v.failures), 0)
            self.assertEqual(v.total, 5)


if __name__ == "__main__":
    unittest.main()
