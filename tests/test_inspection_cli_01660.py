"""Compare current/info/status argument errors with Prodex 0.166.0."""

import hashlib
import os
from pathlib import Path
import unittest

from test_root_help import isolated_run


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


class InspectionCli01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def test_unknown_short_option_keeps_full_usage_after_seen_options(self):
        for arguments in (
            ("current", "-V", "--help"),
            ("info", "--json", "-V", "--help"),
            ("info", "--tokens", "-x", "--help"),
            ("status", "--interval=60", "-V", "--help"),
            ("status", "--once", "-x", "--help"),
            ("status", "--once", "--onc", "--help"),
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01660-inspection-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-inspection-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertIn(b"unexpected argument", baseline.stderr)
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ")
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_status_interval_errors_follow_later_parse_errors(self):
        cases = (
            (("status", "--interval", "bad", "--unknown", "--help"),
             b"error: unexpected argument '--unknown' found\n"),
            (("status", "--interval", "bad", "--", "--interval", "--help"),
             b"error: unexpected argument '--interval' found\n"),
            (("status", "--interval", "bad", "--once", "--help"),
             b"error: invalid value 'bad' for '--interval <SECONDS>': invalid digit found in string\n"),
            (("status", "--interval", "bad", "--once=true"),
             b"error: unexpected value 'true' for '--once' found; no more were expected\n"),
            (("status", "--interval=bad", "--once=false"),
             b"error: invalid value 'bad' for '--interval <SECONDS>': invalid digit found in string\n"),
            (("status", "--interval=bad", "--help=bad"),
             b"error: invalid value 'bad' for '--interval <SECONDS>': invalid digit found in string\n"),
            (("status", "--interval=bad", "-x=bad"),
             b"error: invalid value 'bad' for '--interval <SECONDS>': invalid digit found in string\n"),
            (("status", "--interval=bad", "--", "--"),
             b"error: invalid value 'bad' for '--interval <SECONDS>': invalid digit found in string\n"),
            (("status", "--interval=0", "--unknown"),
             b"error: invalid value '0' for '--interval <SECONDS>': 0 is not in 1..=60\n"),
            (("status", "--interval", "0", "--unknown"),
             b"error: unexpected argument '--unknown' found\n"),
            (("status", "--interval", "bad", "--", "--"),
             b"error: unexpected argument '--' found\n"),
        )
        for arguments, expected_error in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01660-interval-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-interval-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertTrue(baseline.stderr.startswith(expected_error), baseline.stderr)
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ")
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
