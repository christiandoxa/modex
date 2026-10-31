"""Compare offline logout argument errors with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class LogoutDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_invalid_arguments_match_without_mutations(self):
        for tail in (("--bogus",), ("-x",), ("--profile",), ("-p",),
                     ("--profile", "synthetic", "--profile", "other"),
                     ("synthetic", "other"), ("--", "synthetic", "other"),
                     ("--profile", "synthetic", "--bogus"),
                     ("synthetic", "--bogus"),
                     ("--profile", "synthetic", "other", "--bogus"),
                     ("synthetic", "--profile", "main", "--bogus"),
                     ("--profile", "synthetic", "--profile", "--bogus"),
                     ("--profile", "synthetic", "--profile", "other", "--bogus"),
                     ("--profile", "synthetic", "--profile", "other", "--help"),
                     ("--profile", "synthetic", "--profile", "--help"),
                     ("--profile", "synthetic", "--profile", "other", "--help=bad"),
                     ("--profile", "synthetic", "--profile", "--help=bad"),
                     ("--profile", "synthetic", "-p=other", "--help=bad"),
                     ("--profile=synthetic", "-pother", "--bogus"),
                     ("--profile", "synthetic", "other"),
                     ("synthetic", "--profile", "other"),
                     ("--profile", "synthetic", "other", "--help=bad")):
            arguments = ["logout", *tail]
            with self.subTest(arguments=arguments):
                reference, before = isolated_run(ORACLE, arguments, "modex", "logout-oracle")
                actual, after = isolated_run(MODEX, arguments, "modex", "logout-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((before, after), ([], []))

    def test_valid_arguments_remain_guarded(self):
        for tail in ((), ("synthetic",), ("--profile", "synthetic")):
            actual, changes = isolated_run(MODEX, ["logout", *tail], "modex", "logout-guard")
            self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                             (1, b"", b"Error: this Modex development build has not implemented the requested command\n"))
            self.assertEqual(changes, [])

    def test_help_precedes_profile_name_conflicts(self):
        for tail in (("--profile", "synthetic", "name", "--help"),
                     ("synthetic", "--profile", "main", "--help")):
            with self.subTest(tail=tail):
                reference, before = isolated_run(ORACLE, ["logout", *tail], "modex", "logout-help-oracle")
                actual, after = isolated_run(MODEX, ["logout", *tail], "modex", "logout-help-modex")
                self.assertEqual((reference.returncode, reference.stderr), (0, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((before, after), ([], []))


if __name__ == "__main__":
    unittest.main()
