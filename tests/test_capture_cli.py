"""Active CLI help capture stays separate from historical evidence."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import capture_cli


ROOT = Path(__file__).resolve().parents[1]


class CaptureCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.oracle = self.root / "oracle"
        self.oracle.write_bytes(b"synthetic verified active oracle")
        self.oracle_sha256 = hashlib.sha256(self.oracle.read_bytes()).hexdigest()
        self.write_reference(self.oracle_sha256)

        self.historical_inventory = self.root / "docs/cli-inventory-0.166.0.json"
        self.historical_inventory.parent.mkdir(parents=True, exist_ok=True)
        self.historical_inventory.write_bytes(b"historical inventory")
        self.historical_help = self.root / "docs/evidence/baseline-0.166.0/help/root.txt"
        self.historical_help.parent.mkdir(parents=True, exist_ok=True)
        self.historical_help.write_bytes(b"historical help")

    def write_reference(self, oracle_sha256):
        evidence_path = self.root / capture_cli.ACTIVE_EVIDENCE
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps({
            "version": capture_cli.ACTIVE_VERSION,
            "commit": capture_cli.ACTIVE_COMMIT,
            "linux_oracle_sha256": oracle_sha256,
        }), encoding="utf-8")
        baseline_path = self.root / "docs/baseline.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps({
            "reference": {
                "tag": capture_cli.ACTIVE_VERSION,
                "commit": capture_cli.ACTIVE_COMMIT,
                "evidence": capture_cli.ACTIVE_EVIDENCE,
            },
        }), encoding="utf-8")

    def test_inventory_and_fixtures_use_new_active_paths(self):
        captured_binaries = []

        def fake_sandbox(binary, root, arguments, *, argv0):
            captured_binaries.append(Path(binary))
            return [str(binary), *arguments]

        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, b"Usage: prodex\n", b"")

        with patch.object(capture_cli, "ROOT", self.root), \
             patch.object(capture_cli, "ORACLE", self.oracle), \
             patch.object(capture_cli, "ORACLE_SHA256", self.oracle_sha256), \
             patch.object(capture_cli, "sandbox_command", side_effect=fake_sandbox), \
             patch.object(capture_cli.subprocess, "run", side_effect=fake_run), \
             contextlib.redirect_stdout(io.StringIO()):
            capture_cli.main()

        active_inventory = self.root / "docs/cli-inventory-0.166.1.json"
        active_help = self.root / "docs/evidence/baseline-0.166.1/help/root.txt"
        self.assertTrue(active_inventory.is_file())
        self.assertEqual(active_help.read_bytes(), b"Usage: prodex\n")
        inventory_text = active_inventory.read_text(encoding="utf-8")
        inventory = json.loads(inventory_text)
        self.assertEqual(inventory["baseline_version"], "0.166.1")
        self.assertEqual(inventory["baseline_commit"], capture_cli.ACTIVE_COMMIT)
        self.assertEqual(inventory["oracle_sha256"], self.oracle_sha256)
        self.assertEqual(
            inventory["commands"][0]["fixture"],
            "docs/evidence/baseline-0.166.1/help/root.txt",
        )
        self.assertEqual(len(captured_binaries), 7)
        self.assertTrue(all(binary == self.oracle for binary in captured_binaries))
        self.assertNotIn(str(self.root), inventory_text)
        self.assertNotIn(str(self.oracle), inventory_text)
        self.assertEqual(self.historical_inventory.read_bytes(), b"historical inventory")
        self.assertEqual(self.historical_help.read_bytes(), b"historical help")

    def test_checksum_mismatch_fails_before_capture_or_output(self):
        wrong_digest = "0" * 64
        self.write_reference(wrong_digest)
        with patch.object(capture_cli, "ROOT", self.root), \
             patch.object(capture_cli, "ORACLE", self.oracle), \
             patch.object(capture_cli, "ORACLE_SHA256", wrong_digest), \
             patch.object(capture_cli, "sandbox_command") as sandbox, \
             patch.object(capture_cli.subprocess, "run") as run:
            with self.assertRaisesRegex(SystemExit, "checksum-verified"):
                capture_cli.main()

        sandbox.assert_not_called()
        run.assert_not_called()
        self.assertFalse((self.root / "docs/cli-inventory-0.166.1.json").exists())
        self.assertEqual(self.historical_inventory.read_bytes(), b"historical inventory")

    def test_import_uses_active_oracle_override(self):
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests"),
            "PRODEX_ORACLE": "/synthetic/active-01661",
            "PRODEX_ORACLE_04392": "/synthetic/historical-04392",
        }
        result = subprocess.run(
            [sys.executable, "-c", "import capture_cli; print(capture_cli.ORACLE)"],
            cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "/synthetic/active-01661")

    def test_checked_in_active_digest_matches_reference_evidence(self):
        baseline = json.loads((ROOT / "docs/baseline.json").read_text(encoding="utf-8"))["reference"]
        evidence = json.loads((ROOT / capture_cli.ACTIVE_EVIDENCE).read_text(encoding="utf-8"))
        self.assertEqual(baseline["tag"], capture_cli.ACTIVE_VERSION)
        self.assertEqual(baseline["commit"], capture_cli.ACTIVE_COMMIT)
        self.assertEqual(evidence["version"], capture_cli.ACTIVE_VERSION)
        self.assertEqual(evidence["commit"], capture_cli.ACTIVE_COMMIT)
        self.assertEqual(evidence["linux_oracle_sha256"], capture_cli.ORACLE_SHA256)


if __name__ == "__main__":
    unittest.main()
