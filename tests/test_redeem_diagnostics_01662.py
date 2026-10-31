"""Compare read-only redeem parser failures with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


CASES = (
    ("required profile", ("redeem",)),
    ("required profile after options", ("redeem", "--yes", "--no-proxy", "--base-url", "https://quota.invalid")),
    ("missing base URL", ("redeem", "--base-url")),
    ("base URL followed by switch", ("redeem", "--base-url", "--yes")),
    ("base URL followed by itself", ("redeem", "--base-url", "--base-url")),
    ("base URL followed by help short option", ("redeem", "--base-url", "-h")),
    ("malformed help takes precedence", ("redeem", "--base-url", "--help=value")),
    ("malformed switch takes precedence", ("redeem", "--base-url", "--no-proxy=value")),
    ("missing URL precedes duplicate option", ("redeem", "--base-url", "one", "--base-url")),
    ("malformed help precedes missing duplicate URL", ("redeem", "--base-url=one", "--base-url", "--help=value")),
    ("switch value precedence keeps accepted options", ("redeem", "--yes", "--base-url", "--no-proxy=value")),
    ("switch value precedence without accepted options", ("redeem", "--base-url", "--yes=value")),
    ("unknown attached option follows missing URL", ("redeem", "--base-url", "--unknown=value")),
    ("short option cluster does not become URL", ("redeem", "--base-url", "-yfoo")),
    ("base URL followed by unknown option", ("redeem", "--base-url", "--unknown")),
    ("accepted prefix survives following unknown option", ("redeem", "--yes", "--base-url", "--unknown", "--help")),
    ("duplicate base URL", ("redeem", "--base-url", "one", "--base-url", "two")),
    ("duplicate no proxy", ("redeem", "--no-proxy", "--no-proxy")),
    ("attached switch value", ("redeem", "--yes=value")),
    ("attached no proxy value", ("redeem", "--no-proxy=value")),
    ("malformed help", ("redeem", "--help=value")),
    ("malformed help after switch", ("redeem", "--yes", "--help=value")),
    ("malformed help after attached URL", ("redeem", "--base-url=https://quota.invalid", "--help=value")),
    ("unknown option before profile", ("redeem", "--unknown")),
    ("unknown option after profile", ("redeem", "synthetic-profile", "--unknown")),
    ("extra profile", ("redeem", "synthetic-profile", "extra")),
)


class RedeemDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01662 must identify the verified 0.166.2 release")

    def test_parse_failures_match_without_state_or_provider_access(self):
        for label, arguments in CASES:
            with self.subTest(case=label):
                baseline, baseline_created = isolated_run(ORACLE, list(arguments), "modex", "redeem-oracle")
                actual, actual_created = isolated_run(MODEX, list(arguments), "modex", "redeem-modex")
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, actual_created), ([], []))


if __name__ == "__main__":
    unittest.main()
