"""Selected session output comparisons against the active 0.166.0 release."""

import hashlib
import json
import os

import test_sessions
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


class SessionOutputs01660Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        return baseline

    def test_pre_epoch_file_time_falls_back_to_unix_epoch(self):
        def change(root):
            session = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(session.read_text().splitlines()[0])
            metadata.pop("timestamp", None)
            metadata["payload"].pop("timestamp", None)
            session.write_text(json.dumps(metadata) + "\n")
            os.utime(session, (-1, -1))

        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual(reports[0]["updated_at"], "1970-01-01 00:00:00 +00:00")
