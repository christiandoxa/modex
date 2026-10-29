"""Compare unrelated state filenames and retain the real state guard."""

import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
from test_cli import (
    HISTORICAL_04395_ORACLE,
    HISTORICAL_04395_ORACLE_SHA256,
    MODEX,
    ORACLE,
    ORACLE_SHA256,
)


class SessionStateBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE, ORACLE_SHA256), (HISTORICAL_04395_ORACLE, HISTORICAL_04395_ORACLE_SHA256)):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"Release oracle checksum mismatch: {binary}")

    def test_unrelated_state_names_do_not_block_session_listing(self):
        for name in ("state.json.backup", "state.json.scratch", "state.last-good.json"):
            with self.subTest(name=name):
                results = []
                for binary in (ORACLE, HISTORICAL_04395_ORACLE, MODEX):
                    with tempfile.TemporaryDirectory(prefix="modex-session-state-name-") as directory:
                        root = Path(directory)
                        fixture(root)
                        app_root = root / "home/.prodex"
                        app_root.mkdir(mode=0o700)
                        unrelated = app_root / name
                        unrelated.write_bytes(b"synthetic unrelated file\n")
                        result = subprocess.run(
                            sandbox_command(binary, root, ["session", "list", "--json"]),
                            capture_output=True, timeout=10, check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(unrelated.read_bytes(), b"synthetic unrelated file\n")
                        payload = json.loads(result.stdout)
                        self.assertEqual([report["id"] for report in payload], [SESSION_ID])
                        results.append(json.loads(json.dumps(payload).replace(str(root), "<root>")))
                self.assertEqual(results[0], results[1])
                self.assertEqual(results[0], results[2])

    def test_real_state_and_journals_remain_fail_closed(self):
        names = (
            "state.json", "state.json.lock", "state.json.last-good",
            "state.json.123.456.0.tmp", "profile-lifecycle-journal",
            "profile-import-auth-journal",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="modex-session-state-guard-") as directory:
                root = Path(directory)
                fixture(root)
                app_root = root / "home/.prodex"
                app_root.mkdir(mode=0o700)
                state = app_root / name
                if name.endswith("-journal"):
                    state.mkdir(mode=0o700)
                    state = state / "fixture"
                state.write_bytes(b"synthetic state marker\n")
                with state.open("rb") as marker:
                    if name == "state.json.lock":
                        fcntl.flock(marker, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    result = subprocess.run(
                        sandbox_command(MODEX, root, ["session", "list", "--json"]),
                        capture_output=True, timeout=10, check=False,
                    )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"Error: locked state loading and recovery are not implemented\n")
                self.assertEqual(state.read_bytes(), b"synthetic state marker\n")

    def test_dangling_primary_keeps_backup_and_lock_guards(self):
        for marker in ("state.json.lock", "state.json.last-good"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory(prefix="modex-session-state-dangling-") as directory:
                root = Path(directory)
                fixture(root)
                app_root = root / "home/.prodex"
                app_root.mkdir(mode=0o700)
                target = root / "missing-state.json"
                state_link = app_root / "state.json"
                state_link.symlink_to(target)
                state_marker = app_root / marker
                state_marker.write_bytes(b"synthetic state marker\n")
                with state_marker.open("rb") as handle:
                    if marker == "state.json.lock":
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    result = subprocess.run(
                        sandbox_command(MODEX, root, ["session", "list", "--json"]),
                        capture_output=True, timeout=10, check=False,
                    )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"Error: locked state loading and recovery are not implemented\n")
                self.assertTrue(state_link.is_symlink())
                self.assertFalse(target.exists())
                self.assertEqual(state_marker.read_bytes(), b"synthetic state marker\n")


if __name__ == "__main__":
    unittest.main()
