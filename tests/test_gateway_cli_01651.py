"""Gateway parser precedence compared with pinned Prodex processes."""

import hashlib
import os
from pathlib import Path
import unittest

from test_gateway_cli import MODEX, run_cli


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
CASES = (
    (("gateway", "--presidio", "--no-presidio"), 2, b"the argument '--presidio' cannot be used with '--no-presidio'"),
    (("gateway", "--no-presidio", "--presidio"), 2, b"the argument '--no-presidio' cannot be used with '--presidio'"),
    (("gateway", "--no-presidio", "--listen", "127.0.0.1:0", "--presidio", "--api-key", "synthetic-key"), 2, b"the argument '--no-presidio' cannot be used with '--presidio'"),
    (("gateway", "--presidio", "--api-key", "synthetic-key", "--no-presidio"), 2, b"the argument '--presidio' cannot be used with '--no-presidio'"),
    (("gateway", "--presidio", "--presidio"), 2, b"the argument '--presidio' cannot be used multiple times"),
    (("gateway", "--no-presidio", "--no-presidio"), 2, b"the argument '--no-presidio' cannot be used multiple times"),
    (("gateway", "--no-presidio", "--presidio", "--presidio"), 2, b"the argument '--presidio' cannot be used multiple times"),
    (("gateway", "--no-presidio", "--presidio", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--no-presidio", "--unknown", "--presidio"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--unknown", "--no-presidio", "--presidio"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--no-presidio", "--presidio", "--help"), 0, b""),
    (("gateway", "--help", "--no-presidio", "--presidio"), 0, b""),
    (("gateway", "--no-presidio", "--help", "--presidio"), 0, b""),
    (("gateway", "--no-presidio", "--presidio", "--listen", "127.0.0.1:0", "--no-presidio"), 2, b"the argument '--no-presidio' cannot be used multiple times"),
    (("gateway", "--presidio", "--presidio", "--help"), 2, b"the argument '--presidio' cannot be used multiple times"),
    (("gateway", "--api-key", "synthetic-key", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--api-key=synthetic-key", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--listen", "127.0.0.1:0", "--api-key", "synthetic-key", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--listen=127.0.0.1:0", "--api-key=synthetic-key", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--url=https://example.com/v1", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--api-key", "synthetic-key", "--listen=127.0.0.1:0", "--unknown"), 2, b"unexpected argument '--unknown' found"),
    (("gateway", "--listen=127.0.0.1:0", "--api-key", "synthetic-key", "--base-url=https://example.com/v1", "--unknown"), 2, b"unexpected argument '--unknown' found"),
)


class GatewayCLI01651ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError(f"the Prodex oracle does not match pinned release 0.165.1: {ORACLE}")

    def test_conflict_duplicate_unknown_and_help_precedence_matches(self):
        for arguments, returncode, diagnostic in CASES:
            with self.subTest(arguments=arguments):
                baseline = run_cli(ORACLE, "prodex", arguments)
                self.assertEqual(baseline.returncode, returncode)
                self.assertIn(diagnostic, baseline.stderr)
                self.assertNotIn(b"synthetic-key", baseline.stdout + baseline.stderr)
                actual = run_cli(MODEX, "modex", arguments)
                expected_stdout = baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex ")
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ")
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr),
                    (returncode, expected_stdout, expected_stderr),
                )
                self.assertNotIn(b"synthetic-key", actual.stdout + actual.stderr)


if __name__ == "__main__":
    unittest.main()
