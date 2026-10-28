"""Characterize the pinned release difference for unrelated state backups."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
from test_cli import (MODEX, HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)


class SessionStateBackupTests(unittest.TestCase):
    def test_unrelated_state_backup_exposes_fail_closed_guard_gap(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        with tempfile.TemporaryDirectory(prefix="modex-session-state-backup-") as directory:
            root = Path(directory)
            fixture(root)
            app_root = root / "home/.prodex"
            app_root.mkdir(mode=0o700)
            backup = app_root / "state.json.backup"
            backup.write_text("synthetic unrelated backup\n")
            before = backup.read_bytes()
            results = []
            for binary in (ORACLE, MODEX):
                results.append(subprocess.run(
                    sandbox_command(binary, root, ["session", "list", "--json"]),
                    capture_output=True,
                    timeout=10,
                    check=False,
                ))

            oracle, modex = results
            self.assertEqual(oracle.returncode, 0, oracle.stderr)
            self.assertEqual([report["id"] for report in json.loads(oracle.stdout)], [SESSION_ID])
            self.assertEqual(modex.returncode, 1)
            self.assertEqual(modex.stdout, b"")
            self.assertEqual(modex.stderr, b"Error: locked state loading and recovery are not implemented\n")
            self.assertEqual(backup.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
