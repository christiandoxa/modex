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
    str(Path.home() / ".cache/modex/oracles/0.439.5/prodex-x86_64-unknown-linux-gnu"),
))
ORACLE_SHA256 = "96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5"
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
            raise AssertionError("Set PRODEX_ORACLE to the verified official 0.439.5 Linux binary")
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
                                     (0, b"prodex 0.439.5\n", b""))
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


if __name__ == "__main__":
    unittest.main()
