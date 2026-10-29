"""Exercise session resume selection in isolated real processes."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
from test_cli import MODEX, ORACLE as ORACLE_04392
from test_cli_01651 import ORACLE as ORACLE_01651


ORACLE_SHA256 = {
    "0.165.1": "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51",
    "0.439.2": "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e",
}


def write_session(root, session_id, *, archived=False):
    area = "archived_sessions" if archived else "sessions"
    session_dir = root / f"home/.codex/{area}/2026/10/24"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"rollout-{session_id}.jsonl").write_text(
        json.dumps({
            "timestamp": "2026-10-24T00:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "cwd": str(root / "workspace"),
                "thread_name": "Synthetic resume session",
                "model_provider": "openai",
            },
        }) + "\n"
    )


def run_resume(
    binary, selector, *, duplicate=False, prefix_collision=False,
    locked=False, invalid_state=False,
):
    with tempfile.TemporaryDirectory(prefix="modex-session-resume-") as directory:
        root = Path(directory)
        fixture(root)
        if duplicate:
            write_session(root, SESSION_ID, archived=True)
        elif prefix_collision:
            write_session(root, SESSION_ID + "-long")
        if locked or invalid_state:
            state = root / "home/.prodex"
            state.mkdir(mode=0o700)
            if locked:
                (state / "state.json.lock").write_text("")
            if invalid_state:
                state_file = state / "state.json"
                state_file.write_text("{")
                state_file.chmod(0o600)
        result = subprocess.run(
            sandbox_command(binary, root, ["session", "resume", selector]),
            capture_output=True,
            timeout=15,
            check=False,
        )
        return (
            result.returncode,
            result.stdout.replace(str(root).encode(), b"<ROOT>"),
            result.stderr.replace(str(root).encode(), b"<ROOT>"),
        )


class SessionResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        for label, binary in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            digest = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.is_file() else ""
            if digest != ORACLE_SHA256[label]:
                raise AssertionError(f"Pinned Prodex {label} Linux oracle is missing or changed")

    def test_missing_and_ambiguous_errors_match_both_releases(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector, duplicate, error in (
                ("missing-session", False, b"Error: session could not be resolved\n"),
                (" \t \u2000", False, b"Error: session could not be resolved\n"),
                ("019a1234", True, b"Error: session selector is ambiguous\n"),
            ):
                with self.subTest(release=label, selector=selector):
                    baseline = run_resume(oracle, selector, duplicate=duplicate)
                    modex = run_resume(MODEX, selector, duplicate=duplicate)
                    self.assertEqual(baseline, (1, b"", error))
                    self.assertEqual(modex, baseline)

    def test_valid_selection_stops_before_unmanaged_launch(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector in (
                " \t" + SESSION_ID.upper() + " \t",
                "\u2000" + SESSION_ID.upper() + "\u00a0",
            ):
                with self.subTest(release=label, selector=repr(selector)):
                    baseline = run_resume(oracle, selector, prefix_collision=True)
                    self.assertEqual(baseline, (
                        1,
                        b"",
                        b"Prodex launch: preparing runtime launch...\n"
                        b"Error: no active profile selected and no Codex-compatible profiles are available; use `prodex use --profile <name>` or pass --profile\n",
                    ))
                    self.assertEqual(run_resume(MODEX, selector, prefix_collision=True), (
                        1,
                        b"",
                        b"Error: session resume requires managed profile authorization and launch, which are not implemented\n",
                    ))

    def test_duplicate_exact_ids_are_not_deduplicated(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                expected = (1, b"", b"Error: session selector is ambiguous\n")
                self.assertEqual(run_resume(oracle, SESSION_ID, duplicate=True), expected)
                self.assertEqual(run_resume(MODEX, SESSION_ID, duplicate=True), expected)

    def test_state_load_failures_precede_session_selection(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector in ("missing-session", SESSION_ID):
                with self.subTest(release=label, selector=selector):
                    baseline = run_resume(oracle, selector, invalid_state=True)
                    self.assertEqual(baseline, (
                        1,
                        b"",
                        b"Error: failed to read <ROOT>/home/.prodex/state.json.last-good after primary load error: "
                        b"failed to parse <ROOT>/home/.prodex/state.json: EOF while parsing an object at line 1 "
                        b"column 1: No such file or directory (os error 2)\n",
                    ))
                    self.assertEqual(run_resume(MODEX, selector, invalid_state=True), (
                        1,
                        b"",
                        b"Error: locked state loading and recovery are not implemented\n",
                    ))

    def test_session_resume_keeps_state_lock_guard(self):
        lock_only = run_resume(MODEX, "missing-session", locked=True)
        self.assertEqual(lock_only, (
            1,
            b"",
            b"Error: locked state loading and recovery are not implemented\n",
        ))
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                self.assertEqual(run_resume(oracle, "missing-session", locked=True), (
                    1, b"", b"Error: session could not be resolved\n"
                ))


if __name__ == "__main__":
    unittest.main()
