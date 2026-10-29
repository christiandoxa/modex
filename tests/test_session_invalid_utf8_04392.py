"""Keep the invalid UTF-8 session-name mismatch reproducible."""

import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import SESSION_ID, fixture, sandbox_command


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


def add_invalid_utf8_session_name(root):
    sessions = root / "home/.codex/sessions/2026/10/24"
    path = os.fsencode(sessions) + b"/\x80.jsonl"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)


def disable_core_dumps():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


class SessionInvalidUtf8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if not ORACLE_01651.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE_01651}")
        if hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.165.1")

    def test_releases_skip_invalid_utf8_filename_but_modex_aborts(self):
        commands = (
            ("prodex-01651", ORACLE_01651, "prodex"),
            ("prodex-04392", test_cli.ORACLE, "prodex"),
            ("modex", test_cli.MODEX, "modex"),
        )
        with tempfile.TemporaryDirectory(prefix="modex-session-invalid-utf8-") as directory:
            parent = Path(directory)
            results = {}
            for name, binary, argv0 in commands:
                root = parent / name
                root.mkdir()
                fixture(root)
                add_invalid_utf8_session_name(root)
                result = subprocess.run(
                    sandbox_command(binary, root, ["session", "list", "--json"], argv0=argv0),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=10,
                    check=False,
                    preexec_fn=disable_core_dumps,
                )
                results[name] = result

            for name in ("prodex-01651", "prodex-04392"):
                with self.subTest(binary=name):
                    result = results[name]
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                    self.assertEqual(result.stderr, b"")
                    self.assertEqual([row["id"] for row in json.loads(result.stdout)], [SESSION_ID])

            modex = results["modex"]
            self.assertEqual(modex.returncode, 132)
            self.assertTrue(
                modex.stdout.startswith(
                    b"At: Mojo/stdlib/std/collections/string/string_span.mojo:397:41: "
                    b"Assert Error: String span starts on0 which is not a codepoint boundary."
                ),
                modex.stdout.decode("utf-8", "replace"),
            )
            self.assertIn(b"Stack dump without symbol names", modex.stderr)


if __name__ == "__main__":
    unittest.main()
