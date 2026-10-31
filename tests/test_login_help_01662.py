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

    def test_repeated_split_profile_reports_missing_value_before_duplicate(self):
        cases = (
            ("long option", ["login", "--profile", "synthetic", "--profile", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("short alias", ["login", "--profile", "synthetic", "-p", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("no following value", ["login", "--profile", "synthetic", "--profile"],
             b"error: a value is required for '--profile <NAME>'"),
            ("attached prior then split missing", ["login", "--profile=synthetic", "--profile", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("attached prior then short missing", ["login", "--profile=synthetic", "-p", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("terminator after missing option", ["login", "--profile", "synthetic", "--profile", "--", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("next attached profile option", ["login", "--profile", "synthetic", "--profile", "--profile=other", "--help"],
             b"error: a value is required for '--profile <NAME>'"),
            ("malformed help value", ["login", "--profile", "synthetic", "--profile", "--help=x"],
             b"error: unexpected value 'x' for '--help'"),
            ("attached profile then malformed help", ["login", "--profile=synthetic", "--help=x"],
             b"error: unexpected value 'x' for '--help'"),
            ("attached profile then empty help", ["login", "--profile=synthetic", "--help="],
             b"error: unexpected value '' for '--help'"),
            ("split profile then malformed help", ["login", "--profile", "synthetic", "--help=x"],
             b"error: unexpected value 'x' for '--help'"),
            ("short profile then malformed help", ["login", "-p", "synthetic", "--help="],
             b"error: unexpected value '' for '--help'"),
            ("attached valued duplicate", ["login", "--profile=synthetic", "--profile=other", "--help"],
             b"error: the argument '--profile <NAME>' cannot be used multiple times"),
            ("attached empty duplicate", ["login", "--profile=synthetic", "--profile=", "--help"],
             b"error: the argument '--profile <NAME>' cannot be used multiple times"),
            ("unknown option remains a consumed value", ["login", "--profile", "synthetic", "--profile", "--bad", "--help"],
             b"error: the argument '--profile <NAME>' cannot be used multiple times"),
            ("valued duplicate control", ["login", "--profile", "synthetic", "--profile", "other", "--help"],
             b"error: the argument '--profile <NAME>' cannot be used multiple times"),
        )
        for label, args, expected_error in cases:
            with self.subTest(label=label):
                baseline, baseline_created = isolated_run(ORACLE, args, "modex", "login-oracle")
                actual, actual_created = isolated_run(MODEX, args, "modex", "login-modex")
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertTrue(baseline.stderr.startswith(expected_error), baseline.stderr)
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, actual_created), ([], []))


if __name__ == "__main__":
    unittest.main()
