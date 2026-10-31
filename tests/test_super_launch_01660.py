"""Historical Prodex 0.166.0 process checks for Super child exit status."""

import hashlib
import os
from pathlib import Path
import signal
import unittest

import test_super_launch as launch_support


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01660",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


class SuperLaunch01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "posix":
            raise unittest.SkipTest("signal exit-status comparison requires a POSIX host")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01660 must identify the verified 0.166.0 Linux release")

    def test_child_exit_status_matches_active_release(self):
        cases = (("exit-seven", 7), ("signal-term", 128 + signal.SIGTERM))
        for scenario, expected in cases:
            for label, binary in (("Prodex 0.166.0", ORACLE), ("Modex", MODEX)):
                with self.subTest(scenario=scenario, binary=label):
                    result, records, upstream, state = launch_support.run_private_launch(
                        binary, scenario=scenario,
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertEqual(sum(record["kind"] == "launch" for record in records), 1)
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
