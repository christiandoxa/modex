"""Characterize session query behavior against the pinned Prodex release."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import SESSION_ID, sandbox_command


def unicode_query_roots(directory):
    roots = {}
    for label in ("baseline", "modex"):
        root = Path(directory) / label
        root.mkdir()
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        work = root / "workspace-é"
        work.mkdir()
        sessions = root / "home/.codex/sessions/2026/10/24"
        sessions.mkdir(parents=True)
        content = [
            {"timestamp": "2026-10-24T00:00:00Z", "type": "session_meta", "payload": {
                "id": SESSION_ID,
                "timestamp": "2026-10-24T00:00:00Z",
                "cwd": str(work),
                "thread_name": "SessionFixtureΟΣ",
                "model_provider": "PrÖviderİ",
            }},
            {"timestamp": "2026-10-24T01:00:00Z", "type": "turn_context", "payload": {}},
        ]
        path = sessions / f"rollout-{SESSION_ID}.jsonl"
        path.write_text("\n".join(json.dumps(line) for line in content) + "\n")
        roots[label] = root
    return roots


class SessionQuery04395Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(test_cli.HISTORICAL_04395_ORACLE.read_bytes()).hexdigest() != test_cli.HISTORICAL_04395_ORACLE_SHA256:
            raise AssertionError("oracle does not match historical Prodex 0.439.5")

    def test_query_controls_match_the_pinned_release(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-query-") as directory:
            roots = unicode_query_roots(directory)

            cases = (
                ("empty query", "", True),
                ("whitespace-only query", " ", True),
                ("padded meaningful query", " SessionFixture ", True),
                ("mixed-case title", "sESSIONfIXTURE", True),
                ("Unicode provider", "prövider", True),
                ("Unicode cwd", "workspace-é", True),
                ("session id", SESSION_ID[4:12], True),
                ("session path", "rollout-" + SESSION_ID, True),
                ("nonmatching query", "not-present", False),
                ("unretained event field", "fixture-model", False),
            )
            for label, query, matches in cases:
                with self.subTest(label=label, query=query):
                    outputs = []
                    for root_label, binary, argv0 in (("baseline", test_cli.HISTORICAL_04395_ORACLE, "prodex"),
                                                      ("modex", test_cli.MODEX, "modex")):
                        result = subprocess.run(
                            sandbox_command(binary, roots[root_label],
                                            ["session", "list", "--query", query, "--id-only"], argv0=argv0),
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(result.stderr, b"")
                        outputs.append(result.stdout)

                    expected = (SESSION_ID + "\n").encode() if matches else b""
                    self.assertEqual(outputs[0], expected)
                    self.assertEqual(outputs[1], outputs[0])

    def test_known_unicode_lowercase_cases_match_the_pinned_release(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-query-unicode-") as directory:
            roots = unicode_query_roots(directory)
            cases = (
                ("dotted-I lowercase expansion", "prövideri\u0307", (SESSION_ID + "\n").encode()),
                ("Greek final sigma", "ος", (SESSION_ID + "\n").encode()),
                ("Greek ordinary sigma", "οσ", b""),
            )
            for label, query, expected in cases:
                with self.subTest(label=label, query=query):
                    outputs = []
                    for root_label, binary, argv0 in (("baseline", test_cli.HISTORICAL_04395_ORACLE, "prodex"),
                                                      ("modex", test_cli.MODEX, "modex")):
                        result = subprocess.run(
                            sandbox_command(binary, roots[root_label],
                                            ["session", "list", "--query", query, "--id-only"], argv0=argv0),
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(result.stderr, b"")
                        outputs.append(result.stdout)

                    self.assertEqual(outputs, [expected, expected])

    def test_duplicate_keys_and_later_metadata_drive_query_filters(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-query-updates-") as directory:
            roots = {}
            for label in ("baseline", "modex"):
                root = Path(directory) / label
                root.mkdir()
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                work = root / "workspace-é"
                work.mkdir()
                sessions = root / "home/.codex/sessions/2026/10/24"
                sessions.mkdir(parents=True)
                first = (
                    '{"type":"session_meta","payload":{"id":"wrong-id",'
                    '"id":"query-session","thread_name":"OldName",'
                    '"thread_name":"FirstName","cwd":"/wrong/path","cwd":'
                    + json.dumps(str(work))
                    + ',"model_provider":"OldProvider",'
                    '"model_provider":"InitialProvider"}}'
                )
                second = (
                    '{"type":"event_msg","payload":{"thread_name":"SecondName",'
                    '"thread_name":"FinalName","model_provider":"StaleProvider",'
                    '"model_provider":"LaterProvider"}}'
                )
                path = sessions / f"rollout-{SESSION_ID}.jsonl"
                path.write_text(first + "\n" + second + "\n")
                roots[label] = root

            cases = (
                ("earlier duplicate ID", "wrong-id", False),
                ("final duplicate ID", "query-session", True),
                ("earlier duplicate thread name", "FirstName", False),
                ("final repeated thread name", "FinalName", True),
                ("earlier duplicate cwd", "wrong/path", False),
                ("final duplicate cwd", "workspace-é", True),
                ("overwritten provider", "InitialProvider", False),
                ("final provider", "LaterProvider", True),
                ("earlier duplicate provider", "StaleProvider", False),
            )
            for label, query, matches in cases:
                with self.subTest(label=label, query=query):
                    outputs = []
                    for root_label, binary, argv0 in (("baseline", test_cli.HISTORICAL_04395_ORACLE, "prodex"),
                                                      ("modex", test_cli.MODEX, "modex")):
                        result = subprocess.run(
                            sandbox_command(binary, roots[root_label],
                                            ["session", "list", "--query", query, "--id-only"], argv0=argv0),
                            stdin=subprocess.DEVNULL,
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(result.stderr, b"")
                        outputs.append(result.stdout)

                    expected = b"query-session\n" if matches else b""
                    self.assertEqual(outputs[0], expected)
                    self.assertEqual(outputs[1], outputs[0])


if __name__ == "__main__":
    unittest.main()
