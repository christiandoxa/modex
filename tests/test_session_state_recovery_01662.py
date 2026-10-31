"""Capture 0.166.2's locked last-good recovery and Modex's safe refusal."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from session_oracle import SESSION_ID, fixture, sandbox_command


class SessionStateRecovery01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")

    def test_modex_preserves_corrupt_primary_while_release_recovers_backup(self):
        results = {}
        states = {}
        for label, binary in (("prodex-0.166.2", ORACLE), ("modex", MODEX)):
            with tempfile.TemporaryDirectory(prefix="modex-session-recovery-01662-") as directory:
                root = Path(directory)
                fixture(root)
                app_root = root / "home/.prodex"
                app_root.mkdir(mode=0o700)
                backup_state = {
                    "schema_version": 1,
                    "active_profile": "main",
                    "profiles": {
                        "main": {
                            "codex_home": str(root / "home/.codex"),
                            "managed": False,
                        },
                    },
                    "last_run_selected_at": {},
                    "response_profile_bindings": {},
                    "session_profile_bindings": {
                        SESSION_ID: {
                            "profile_name": "main",
                            "bound_at": int(time.time()),
                        },
                    },
                }
                primary = app_root / "state.json"
                backup = app_root / "state.json.last-good"
                primary_before = b"{invalid primary\n"
                backup_before = json.dumps(backup_state).encode()
                primary.write_bytes(primary_before)
                primary.chmod(0o600)
                backup.write_bytes(backup_before)
                backup.chmod(0o600)

                result = subprocess.run(
                    sandbox_command(
                        binary,
                        root,
                        ["session", "list", "--json", "--profile", "main"],
                        argv0="modex" if label == "modex" else "prodex",
                    ),
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                results[label] = (result.returncode, result.stdout, result.stderr)
                states[label] = (
                    primary_before,
                    backup_before,
                    primary.read_bytes(),
                    backup.read_bytes(),
                )

        oracle_result = results["prodex-0.166.2"]
        self.assertEqual(oracle_result[0], 0, oracle_result[2])
        self.assertEqual(oracle_result[2], b"")
        reports = json.loads(oracle_result[1])
        self.assertEqual(len(reports), 1)
        self.assertEqual((reports[0]["id"], reports[0]["profile"]), (SESSION_ID, "main"))
        recovered_primary = json.loads(states["prodex-0.166.2"][2])
        recovered_backup = json.loads(states["prodex-0.166.2"][3])
        self.assertEqual(recovered_primary, recovered_backup)
        self.assertEqual(recovered_primary["active_profile"], "main")
        self.assertEqual(
            recovered_primary["session_profile_bindings"][SESSION_ID]["profile_name"],
            "main",
        )
        self.assertNotEqual(states["prodex-0.166.2"][0], states["prodex-0.166.2"][2])
        self.assertNotEqual(states["prodex-0.166.2"][1], states["prodex-0.166.2"][3])

        self.assertEqual(
            results["modex"],
            (1, b"", b"Error: locked state loading and recovery are not implemented\n"),
        )
        modex_states = states["modex"]
        self.assertEqual(
            modex_states,
            (modex_states[0], modex_states[1], modex_states[0], modex_states[1]),
        )


if __name__ == "__main__":
    unittest.main()
