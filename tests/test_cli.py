"""Isolated black-box tests; Python is never part of the product build/runtime."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    str(Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu"),
))
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
HISTORICAL_04395_ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04395",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.439.5/prodex-x86_64-unknown-linux-gnu",
))
HISTORICAL_04395_ORACLE_SHA256 = "96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5"
HISTORICAL_04392_ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
HISTORICAL_04391_ORACLE_SHA256 = "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a"


def isolated_run(binary, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-cli-test-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        result = subprocess.run(
            [str(binary), *arguments],
            cwd=root,
            env={"HOME": str(home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        mutations = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                           if path != home)
        return result, mutations


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file():
            raise AssertionError("Set PRODEX_ORACLE to the verified official 0.439.2 Linux binary")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match the pinned release checksum")

    def test_version_identity_mapping_and_no_mutations(self):
        for flag in ("--version", "-V"):
            for tail in ([], ["extra"], ["session", "list"], ["--unknown"], ["--help"], ["--"]):
                arguments = [flag, *tail]
                with self.subTest(arguments=arguments):
                    baseline, baseline_mutations = isolated_run(ORACLE, arguments)
                    modex, modex_mutations = isolated_run(MODEX, arguments)
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                     (0, b"prodex 0.439.2\n", b""))
                    self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                     (0, b"modex 0.1.0-dev\n", b""))
                    self.assertEqual(baseline_mutations, [])
                    self.assertEqual(modex_mutations, baseline_mutations)

    def test_unimplemented_command_fails_without_echoing_arguments(self):
        # This checks honest development behavior, not baseline command parity.
        sentinel = "synthetic-secret-that-must-not-appear"
        result, mutations = isolated_run(MODEX, ["gateway", "--api-key", sentinel])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"has not implemented", result.stderr)
        self.assertNotIn(sentinel.encode(), result.stderr)
        self.assertEqual(mutations, [])


class HistoricalSuperProviderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CliTests.setUpClass()

    def _run(self, binary, arguments, executable, label):
        from test_root_help import isolated_run

        return isolated_run(binary, arguments, executable, label)

    def test_invalid_provider_values_match_clap_errors(self):
        for arguments in (
            ["super", "--provider", "bad"],
            ["super", "--provider=Bad", "--help"],
            ["super", "--provider", " BAD ", "--help"],
            ["super", "--provider", "local", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider")
                expected_stderr = baseline.stderr.replace(b"prodex", b"modex")
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, baseline.stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_positional_provider_error_keeps_runtime_diagnostic(self):
        arguments = ["super", "exec", "--provider=local", "--help"]
        expected_stderr = (
            b'Error: invalid --provider: supported values are anthropic, copilot, deepseek, '
            b'gemini, kiro, got "local"\n'
        )
        baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider-tail")
        modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider-tail")
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                         (1, b"", expected_stderr))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (baseline.returncode, baseline.stdout, baseline.stderr))
        self.assertTrue(baseline_created)
        self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                            for path in baseline_created))
        self.assertEqual(modex_created, [])

    def test_provider_aliases_and_help_order_match(self):
        for arguments in (
            ["super", "--provider", "claude", "--help"],
            ["super", "--provider=github-copilot", "--help"],
            ["super", "--provider=github_copilot", "--help"],
            ["super", "--provider", "DEEPSEEK", "--help"],
            ["super", "--help", "--provider=bad"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider-help")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider-help")
                self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertIn(b"Usage: prodex super", baseline.stdout)
                self.assertIn(b"Usage: modex super", modex.stdout)
                self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
