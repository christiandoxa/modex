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


if __name__ == "__main__":
    unittest.main()
