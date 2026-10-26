"""Verify production Super help, selected baseline errors, and safe startup gaps."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from session_oracle import sandbox_command
from test_cli import HISTORICAL_04391_ORACLE_SHA256, MODEX, ORACLE, ORACLE_SHA256, ROOT


SUPER_ARGV_CAPTURE = ROOT / "tests/fixtures/super-argv/cases.json"


def isolated_super(binary, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-super-cli-") as directory:
        root = Path(directory)
        for name in ("home", "workspace", "prodex"):
            (root / name).mkdir(mode=0o700)
        cache = root / "prodex/update-check.json"
        cache.write_text(json.dumps({"source": "GitHub", "latest_version": "0.439.0", "checked_at": int(time.time())}))
        cache.chmod(0o600)
        before = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                  for path in root.rglob("*")}
        command = sandbox_command(binary, root, arguments, argv0="modex" if binary == MODEX else "prodex",
                                  environment={"PRODEX_HOME": str(root / "prodex")})
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        after = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                 for path in root.rglob("*")}
        return result, after != before


class SuperCliTests(unittest.TestCase):
    def test_help_matches_baseline_without_creating_application_state(self):
        for arguments in (["super", "--help"], ["super", "-h"], ["s", "--help"], ["help", "super"], ["help", "s"]):
            with self.subTest(arguments=arguments):
                baseline, _ = isolated_super(ORACLE, arguments)
                native, mutated = isolated_super(MODEX, arguments)
                expected = baseline.stdout.decode()
                for command in ("super", "run", "doctor", "login"):
                    expected = expected.replace("prodex " + command, "modex " + command)
                self.assertEqual((native.returncode, native.stdout.decode(), native.stderr),
                                 (baseline.returncode, expected, baseline.stderr))
                self.assertFalse(mutated)

    def test_positional_tail_validation_matches_baseline(self):
        cases = (
            ["exec", "--sub-agent-model", "fixture-model"],
            ["exec", "--sub-agent", "--no-sub-agent"],
            ["exec", "--api-key", "synthetic-key"],
            ["exec", "--context-window", "16384"],
            ["exec", "--presidio", "--no-presidio"],
            ["exec", "--no-presidio", "--require-tool", "presidio"],
            ["exec", "--provider", "deepseek", "--url", "http://127.0.0.1:8131"],
            ["exec", "--base-url", "http://127.0.0.1:8131", "--url", "http://127.0.0.1:8131"],
            ["exec", "--sub-agent", "--sub-agent-provider", "local"],
            ["exec", "--sub-agent", "--sub-agent-url", "http://127.0.0.1:8131"],
            ["gui", "--sub-agent"],
        )
        for tail in cases:
            with self.subTest(tail=tail):
                baseline, _ = isolated_super(ORACLE, ["super", *tail])
                native, mutated = isolated_super(MODEX, ["super", *tail])
                self.assertEqual((native.returncode, native.stdout, native.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertFalse(mutated)

    def test_credential_free_url_validation_matches_frozen_capture(self):
        capture = json.loads(SUPER_ARGV_CAPTURE.read_text())
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertEqual(capture["oracle_sha256"], HISTORICAL_04391_ORACLE_SHA256)
        self.assertTrue(capture["network_isolated"])
        for case in capture["cases"]:
            with self.subTest(name=case["name"]):
                baseline, _ = isolated_super(ORACLE, case["argv"])
                expected = (case["returncode"], case["stdout"].encode(), case["stderr"].encode())
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), expected)
                native, mutated = isolated_super(MODEX, case["argv"])
                self.assertEqual((native.returncode, native.stdout, native.stderr), expected)
                self.assertFalse(mutated)
                self.assertNotIn("synthetic-secret".encode(), native.stderr)

    def test_unavailable_startup_fails_before_side_effects_and_keeps_keys_private(self):
        sentinel = "synthetic-key-never-print-this"
        for arguments in (
            ["super"],
            ["s", "--provider", "deepseek", "--api-key", sentinel, "exec", "fixture prompt"],
            ["super", "--dry-run", "--url", "http://127.0.0.1:8131"],
        ):
            with self.subTest(arguments=arguments):
                result, mutated = isolated_super(MODEX, arguments)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"Super startup is not implemented", result.stderr)
                self.assertNotIn(sentinel.encode(), result.stderr)
                self.assertFalse(mutated)


if __name__ == "__main__":
    unittest.main()
