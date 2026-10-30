"""Check Super's Gemini CLI/provider guard against the Prodex 0.166.0 release."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from session_oracle import sandbox_command


def isolated_run(binary, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-super-cli-01660-") as directory:
        root = Path(directory)
        for name in ("home", "workspace", "prodex"):
            (root / name).mkdir(mode=0o700)
        before = sorted(
            (str(path.relative_to(root)), path.read_bytes() if path.is_file() else None)
            for path in root.rglob("*")
        )
        command = sandbox_command(
            binary,
            root,
            arguments,
            argv0="modex" if Path(binary).resolve() == MODEX.resolve() else "prodex",
            environment={"PRODEX_HOME": str(root / "prodex")},
        )
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        after = sorted(
            (str(path.relative_to(root)), path.read_bytes() if path.is_file() else None)
            for path in root.rglob("*")
        )
        return result, before != after


class SuperCli01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex 0.166.0 oracle does not match its official SHA256SUMS entry")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_agy_cli_rejects_missing_or_non_gemini_provider_before_startup(self):
        cases = (
            ("super", "--cli", "agy"),
            ("super", "--provider", "deepseek", "--cli", "agy"),
            ("super", "exec", "--cli", "agy"),
            ("super", "exec", "--provider", "deepseek", "--cli", "agy"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_mutated = isolated_run(ORACLE, arguments)
                modex, modex_mutated = isolated_run(MODEX, arguments)
                expected_error = baseline.stderr.replace(
                    b"use prodex s gemini", b"use modex s gemini", 1
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, expected_error))
                self.assertEqual(baseline.stderr,
                                 b"Error: --cli agy requires --provider gemini; "
                                 b"use prodex s gemini --cli agy\n")
                self.assertFalse(baseline_mutated)
                self.assertFalse(modex_mutated)

    def test_other_invalid_combinations_precede_the_agy_guard(self):
        cases = (
            (("super", "--cli", "agy", "--sub-agent", "--no-sub-agent"),
             b"cannot be used with", b"--sub-agent conflicts with --no-sub-agent", 2),
            (("super", "--cli", "agy", "--provider", "deepseek", "--url", "http://127.0.0.1:8131"),
             b"cannot be used with '--url", b"--provider conflicts with --url", 2),
            (("super", "--cli", "agy", "--provider", "deepseek", "--no-presidio", "--require-tool", "presidio"),
             b"--no-presidio conflicts with --require-tool presidio",
             b"--no-presidio conflicts with --require-tool presidio", 1),
            (("super", "--cli", "agy", "--api-key", "synthetic-key"),
             b"required arguments were not provided", b"--api-key requires --provider", 2),
            (("super", "--cli", "agy", "--context-window", "1024"),
             b"required arguments were not provided", b"context-window options require --provider or --url", 2),
        )
        guard_error = b"--cli agy requires --provider gemini"
        for arguments, baseline_marker, modex_marker, baseline_exit in cases:
            with self.subTest(arguments=arguments):
                baseline, _ = isolated_run(ORACLE, arguments)
                modex, _ = isolated_run(MODEX, arguments)
                self.assertEqual(baseline.returncode, baseline_exit)
                self.assertIn(baseline_marker, baseline.stderr)
                self.assertEqual(modex.returncode, 1)
                self.assertIn(modex_marker, modex.stderr)
                self.assertNotIn(guard_error, modex.stderr)

    def test_invalid_provider_and_url_still_precede_the_agy_guard(self):
        cases = (
            ("super", "--cli", "agy", "--provider", "invalid"),
            ("super", "--cli", "agy", "--provider", "deepseek", "--base-url", "not-url"),
        )
        guard_error = b"--cli agy requires --provider gemini"
        for arguments in cases:
            with self.subTest(arguments=arguments):
                baseline, _ = isolated_run(ORACLE, arguments)
                modex, _ = isolated_run(MODEX, arguments)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertNotIn(guard_error, modex.stderr)

    def test_valid_gemini_agy_control_reaches_executable_lookup(self):
        arguments = ("super", "--cli", "agy", "--provider", "gemini")
        baseline, _ = isolated_run(ORACLE, arguments)
        modex, modex_mutated = isolated_run(MODEX, arguments)
        self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
        self.assertIn(b"Error: failed to execute agy:", baseline.stderr)
        self.assertNotIn(b"--cli agy requires --provider gemini", baseline.stderr)
        self.assertEqual((modex.returncode, modex.stdout), (1, b""))
        self.assertIn(b"Super startup is not implemented", modex.stderr)
        self.assertNotIn(b"--cli agy requires --provider gemini", modex.stderr)
        self.assertFalse(modex_mutated)


if __name__ == "__main__":
    unittest.main()
