"""Compare session-query Unicode lowercase behavior with Prodex 0.439.2."""

import hashlib
import json
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import sandbox_command
from test_session_query_04395 import unicode_query_roots


SESSION_ID = "019a1234-5678-7123-8123-0123456789ab"
CONTEXT_SESSION_ID = "019a1234-5678-7123-8123-1123456789ab"


def add_context_session(root, identifier):
    workspace = root / "workspace-é"
    path = root / "home/.codex/sessions/2026/10/24" / f"rollout-{identifier}.jsonl"
    record = {"timestamp": "2026-10-24T00:00:00Z", "type": "session_meta", "payload": {
        "id": identifier,
        "timestamp": "2026-10-24T00:00:00Z",
        "cwd": str(workspace),
        "thread_name": "GreekΟΣ\u0301Α-Ο\u0301Σ",
        "model_provider": "openai",
    }}
    path.write_text(json.dumps(record) + "\n")


def query(binary, root, argv0, text):
    return subprocess.run(
        sandbox_command(binary, root, ["session", "list", "--query", text, "--id-only"], argv0=argv0),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        check=False,
    )


class SessionQuery04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(test_cli.ORACLE.read_bytes()).hexdigest() != test_cli.ORACLE_SHA256:
            raise AssertionError("oracle does not match frozen Prodex 0.439.2")

    def test_unicode_lowercase_queries_match_the_frozen_release(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-query-04392-") as directory:
            roots = unicode_query_roots(directory)
            for root in roots.values():
                add_context_session(root, CONTEXT_SESSION_ID)

            cases = (
                ("dotted-I lowercase expansion", "prövideri\u0307", SESSION_ID),
                ("dotted-I query expansion", "PRÖVIDERİ", SESSION_ID),
                ("ordinary Unicode lowercase", "prövider", SESSION_ID),
                ("Greek final sigma", "ος", SESSION_ID),
                ("non-final Greek sigma", "οσ", CONTEXT_SESSION_ID),
                ("sigma before a combining mark and cased letter", "οσ\u0301α", CONTEXT_SESSION_ID),
                ("final sigma after a combining mark", "ο\u0301ς", CONTEXT_SESSION_ID),
                ("ordinary sigma does not match final sigma", "ο\u0301σ", None),
            )
            for label, text, expected_id in cases:
                with self.subTest(label=label, query=text):
                    outputs = []
                    for root_label, binary, argv0 in (
                        ("baseline", test_cli.ORACLE, "prodex"),
                        ("modex", test_cli.MODEX, "modex"),
                    ):
                        result = query(binary, roots[root_label], argv0, text)
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(result.stderr, b"")
                        outputs.append(result.stdout)

                    expected = f"{expected_id}\n".encode() if expected_id else b""
                    self.assertEqual(outputs, [expected, expected])


if __name__ == "__main__":
    unittest.main()
