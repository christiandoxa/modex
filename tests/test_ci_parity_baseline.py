"""Parity verdict must not promote historical evidence to the active release."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("parity_verdict", ROOT / "scripts/ci/check-parity-complete.py")
verdict = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verdict)


class ParityBaselineTests(unittest.TestCase):
    def run_verdict(self, *, inventory_commit="current", trace_commit="current", verified=True, contract_status="PASS"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.txt").write_text("synthetic")
            targets = sorted(verdict.REQUIRED_TARGETS)
            baseline = {"reference": {"commit": "current", "release_targets": targets}}
            parity = {
                "baseline_commit": inventory_commit,
                "inventory_complete": True,
                "contracts": [{
                    "id": "TEST", "status": contract_status, "platforms": targets,
                    "platform_status": dict.fromkeys(targets, "PASS"),
                    "baseline": {"source_commit": trace_commit, "target_trace_verified": verified},
                    "evidence": ["evidence.txt"],
                }],
                "release_qualification": {target: {"status": "PASS", "evidence": ["evidence.txt"]} for target in targets},
            }
            (root / "baseline.json").write_text(json.dumps(baseline))
            (root / "parity.json").write_text(json.dumps(parity))
            old = verdict.ROOT, verdict.BASELINE, verdict.PARITY
            verdict.ROOT, verdict.BASELINE, verdict.PARITY = root, root / "baseline.json", root / "parity.json"
            try:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = verdict.main()
                return code, output.getvalue()
            finally:
                verdict.ROOT, verdict.BASELINE, verdict.PARITY = old

    def test_stale_inventory_and_trace_cannot_pass(self):
        self.assertEqual(self.run_verdict()[0], 0)
        code, output = self.run_verdict(inventory_commit="old")
        self.assertEqual(code, 1)
        self.assertIn("inventory does not match", output)
        for commit, verified in (("old", True), ("current", False)):
            code, output = self.run_verdict(trace_commit=commit, verified=verified)
            self.assertEqual(code, 1)
            self.assertIn("verified trace against the active baseline", output)
        _, output = self.run_verdict(trace_commit="old", contract_status="IN_PROGRESS")
        self.assertIn("verified trace against the active baseline", output)


if __name__ == "__main__":
    unittest.main()
