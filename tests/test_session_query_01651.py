"""Session-query contextual casing against the pinned 0.165.1 executable."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_cli import MODEX


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class SessionQuery01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_contextual_sigma_matches_unicode_properties(self):
        cases = (
            ("AΣ.A", "aσ.a", True),
            ("AΣ.A", "aς.a", False),
            ("AΣ\u200dA", "aσ\u200da", True),
            ("AʰΣ", "aʰς", True),
            ("Σ.A", "σ.a", True),
            ("AΣ.1", "aς.1", True),
            ("AΣ\u0301A", "aσ\u0301a", True),
            ("AΣ\u0301", "aς\u0301", True),
            ("\u1c89", "\u1c8a", True),
            ("\ua7cb", "\u0264", True),
            ("\ua7dc", "\u019b", True),
            ("\U00010d50\U00010d65", "\U00010d70\U00010d85", True),
            ("\U00016ea0\U00016eb8", "\U00016ebb\U00016ed3", True),
            ("A\u1c89Σ", "a\u1c8aς", True),
            ("\u1c89", "\u1c8b", False),
        )
        for title, query, expected in cases:
            with self.subTest(title=title, query=query):
                outputs = []
                for binary in (ORACLE, MODEX):
                    with tempfile.TemporaryDirectory(prefix="modex-query-01651-") as directory:
                        root = Path(directory)
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir()
                        sessions = root / "home/.codex/sessions/2026/01/01"
                        sessions.mkdir(parents=True)
                        (sessions / "rollout-fixture.jsonl").write_text(json.dumps({
                            "type": "session_meta", "payload": {"id": "synthetic-id", "thread_name": title}
                        }) + "\n")
                        result = subprocess.run(
                            sandbox_command(binary, root, ["session", "list", "--query", query, "--id-only"]),
                            capture_output=True, timeout=10, check=False,
                        )
                        outputs.append((result.returncode, result.stdout, result.stderr))
                wanted = b"synthetic-id\n" if expected else b""
                self.assertEqual(outputs, [(0, wanted, b""), (0, wanted, b"")])

    def test_shared_home_path_join_matches_release(self):
        for suffix, query, query_matches, internal_separator in (
            ("/", "//sessions", False, False),
            ("//", "//sessions", True, False),
            ("//.codex", "//.codex/sessions", True, True),
        ):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory(prefix="modex-session-path-01651-") as directory:
                    outputs = []
                    query_outputs = []
                    for label, binary in (("baseline", ORACLE), ("modex", MODEX)):
                        root = Path(directory) / label
                        root.mkdir()
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir()
                        shared = root / "home/.codex"
                        sessions = shared / "sessions/2026/01/01"
                        sessions.mkdir(parents=True)
                        (sessions / "rollout-fixture.jsonl").write_text(json.dumps({
                            "type": "session_meta", "payload": {
                                "id": "synthetic-id", "thread_name": "Fixture",
                            }, "timestamp": "2026-10-24T00:00:00Z",
                        }) + "\n")
                        shared_path = (str(root / "home") if internal_separator else str(shared)) + suffix
                        environment = {"PRODEX_SHARED_CODEX_HOME": shared_path}
                        for arguments, collected in (
                            (["session", "list", "--json"], outputs),
                            (["session", "list", "--query", query, "--id-only"], query_outputs),
                        ):
                            result = subprocess.run(
                                sandbox_command(binary, root, arguments, environment=environment),
                                capture_output=True, timeout=10, check=False,
                            )
                            collected.append((result.returncode,
                                              result.stdout.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                                              result.stderr))

                    self.assertEqual(outputs[0], outputs[1])
                    self.assertEqual(query_outputs[0], query_outputs[1])
                    wanted = b"synthetic-id\n" if query_matches else b""
                    self.assertEqual(query_outputs[0], (0, wanted, b""))


if __name__ == "__main__":
    unittest.main()
