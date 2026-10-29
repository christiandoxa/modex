"""Session-report production comparisons against the active 0.165.1 release."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import test_sessions
from session_oracle import SESSION_ID, fixture, sandbox_command
from test_cli import MODEX


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class SessionReport01651Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 release")
        if not test_sessions.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE
        )
        self.assertEqual(modex, baseline)
        return baseline

    def test_profile_filter_remains_fail_closed_while_state_recovery_is_unavailable(self):
        outputs = {}
        states = {}
        file_effects = {}
        for label, binary in (("baseline", ORACLE), ("modex", MODEX)):
            with tempfile.TemporaryDirectory(prefix="modex-session-profile-01651-") as directory:
                root = Path(directory)
                fixture(root)
                app_root = root / "home/.prodex"
                app_root.mkdir(mode=0o700)
                state = {
                    "schema_version": 1,
                    "active_profile": "main",
                    "profiles": {
                        "main": {"codex_home": str(root / "home/.codex"), "managed": False},
                    },
                    "last_run_selected_at": {},
                    "response_profile_bindings": {},
                    "session_profile_bindings": {
                        SESSION_ID: {"profile_name": "main", "bound_at": int(time.time())},
                    },
                }
                state_path = app_root / "state.json"
                state_path.write_text(json.dumps(state))
                state_path.chmod(0o600)
                before = {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*") if path.is_file()
                }
                result = subprocess.run(
                    sandbox_command(binary, root, ["session", "list", "--json", "--profile", "main"]),
                    capture_output=True, timeout=10, check=False,
                )
                after = {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*") if path.is_file()
                }
                states[label] = (before["home/.prodex/state.json"], after["home/.prodex/state.json"])
                file_effects[label] = (
                    set(after) - set(before),
                    set(before) - set(after),
                )
                outputs[label] = (result.returncode, result.stdout, result.stderr)

        baseline_code, baseline_stdout, baseline_stderr = outputs["baseline"]
        self.assertEqual((baseline_code, baseline_stderr), (0, b""))
        report = json.loads(baseline_stdout)
        self.assertEqual(len(report), 1)
        self.assertEqual((report[0]["id"], report[0]["profile"]), (SESSION_ID, "main"))

        self.assertEqual(outputs["modex"], (
            1, b"", b"Error: locked state loading and recovery are not implemented\n",
        ))
        self.assertNotEqual(outputs["modex"], outputs["baseline"])
        self.assertEqual(states["baseline"][0], states["baseline"][1])
        self.assertEqual(states["modex"][0], states["modex"][1])
        self.assertIn("home/.prodex/state.json.lock", file_effects["baseline"][0])
        self.assertEqual(file_effects["baseline"][1], set())
        self.assertEqual(file_effects["modex"], (set(), set()))
