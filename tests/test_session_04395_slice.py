"""Focused black-box parity checks for session metadata admission."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, HISTORICAL_04395_ORACLE as ORACLE


class SessionMetadataAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != test_cli.HISTORICAL_04395_ORACLE_SHA256:
            raise AssertionError("oracle does not match historical Prodex 0.439.5")

    def assert_admission_matches(self, content, expected):
        outputs = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-session-admission-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                sessions = root / "home/.codex/sessions/2026/10/24"
                sessions.mkdir(parents=True)
                path = sessions / "rollout-fixture.jsonl"
                path.write_text(content)
                result = subprocess.run(
                    sandbox_command(binary, root, ["session", "list", "--id-only"]),
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                outputs.append(result.stdout)
        self.assertEqual(outputs, [expected, expected])

    def test_resume_id_fallbacks_and_type_class_control_jsonl_admission(self):
        cases = (
            ({"type": "session_meta", "payload": {"id": "minimal-session"}}, b"minimal-session\n"),
            ({"type": "session_meta", "payload": {"session_id": "payload-session-id"}}, b"payload-session-id\n"),
            ({"type": "session_meta", "id": "root-id"}, b"root-id\n"),
            ({"type": "session_meta", "session_id": "root-session-id"}, b"root-session-id\n"),
            ({"payload": {"id": "legacy-session"}}, b"legacy-session\n"),
            ({"type": 7, "payload": {"id": "numeric-type"}}, b"numeric-type\n"),
            ({"type": None, "payload": {"id": "null-type"}}, b"null-type\n"),
            ({"type": "turn_context", "payload": {"id": "turn-context"}}, b""),
            ({"type": "event", "payload": {"id": "event-session"}}, b""),
            ({"type": "session_meta", "payload": {"id": "  ", "session_id": "payload-fallback"}, "id": "root-fallback"}, b"payload-fallback\n"),
            ({"type": "session_meta", "payload": {"id": "\u2003"}, "session_id": "root-fallback"}, b"root-fallback\n"),
            ({"type": "session_meta", "id": "  ", "session_id": ""}, b""),
            ({"type": "session_meta", "payload": {"id": []}}, b""),
            ({"type": "session_meta", "payload": {"id": 7, "session_id": "nonstring-id-fallback"}}, b"nonstring-id-fallback\n"),
            ({"type": "session_meta", "payload": [], "id": "malformed-payload-fallback"}, b"malformed-payload-fallback\n"),
            ("{bad json}\n", b""),
            ("{bad json}\n{\"type\":\"session_meta\",\"payload\":{\"id\":\"later-session\"}}\n", b""),
        )
        for metadata, expected in cases:
            with self.subTest(metadata=metadata):
                content = metadata if isinstance(metadata, str) else json.dumps(metadata)
                self.assert_admission_matches(content + "\n", expected)

    def test_nonobject_first_record_keeps_baseline_panic_visible(self):
        results = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-session-malformed-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                sessions = root / "home/.codex/sessions/2026/10/24"
                sessions.mkdir(parents=True)
                (sessions / "rollout-fixture.jsonl").write_text("[]\n")
                results.append(subprocess.run(
                    sandbox_command(binary, root, ["session", "list", "--id-only"]),
                    capture_output=True,
                    timeout=10,
                    check=False,
                ))
        self.assertEqual(results[0].returncode, 101)
        self.assertIn(b"session-report metadata planner returned invalid output", results[0].stderr)
        # This safer Modex result is a known mismatch, not a parity PASS.
        self.assertEqual((results[1].returncode, results[1].stdout, results[1].stderr), (0, b"", b""))


if __name__ == "__main__":
    unittest.main()
