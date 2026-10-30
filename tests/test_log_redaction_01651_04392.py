"""Unicode-whitespace transcript redaction across both pinned releases."""

import hashlib
import os
import unittest
from pathlib import Path

from log_mismatches import UNICODE_WHITESPACE_MATCHING_CASE
from test_cli import MODEX
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_log_redaction import run_message


ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


class LogRedactionCrossReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"Prodex oracle does not match its pinned release: {binary}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_unquoted_unicode_whitespace_matches_both_pinned_releases(self):
        fixture = UNICODE_WHITESPACE_MATCHING_CASE
        outputs = (
            run_message(ORACLE_01651, fixture["input"]),
            run_message(ORACLE_04392, fixture["input"]),
            run_message(MODEX, fixture["input"]),
        )
        for output in outputs:
            self.assertEqual(output[0], 0)
            self.assertEqual(output[1], fixture["stdout"])
            self.assertEqual(output[2], b"")
            self.assertNotIn(fixture["secret"].encode(), output[1])
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
