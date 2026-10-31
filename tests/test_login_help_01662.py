"""Compare login parser help precedence without performing a login."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class LoginHelp01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file() or not ORACLE.is_file():
            raise AssertionError("Build Modex and provide the verified 0.166.2 oracle")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.2 oracle checksum is wrong")

    def test_unknown_double_dash_profile_value_before_help(self):
        for value in ("--bad", "--unknown=value"):
            with self.subTest(value=value):
                args = ["login", "--profile", value, "--help"]
                baseline, baseline_created = isolated_run(ORACLE, args, "modex", "login-oracle")
                actual, actual_created = isolated_run(MODEX, args, "modex", "login-modex")
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((baseline_created, actual_created), ([], []))

    def test_recognized_option_cannot_be_a_profile_value(self):
        for value in ("--", "--profile", "--profile=synthetic", "--help", "--help=synthetic", "-p", "-h", "-hh", "-hhh"):
            with self.subTest(value=value):
                args = ["login", "--profile", value]
                baseline, baseline_created = isolated_run(ORACLE, args, "modex", "login-oracle")
                actual, actual_created = isolated_run(MODEX, args, "modex", "login-modex")
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((baseline_created, actual_created), ([], []))


if __name__ == "__main__":
    unittest.main()
