"""Compare offline ping group diagnostics with the 0.166.2 release."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class PingDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_missing_and_invalid_commands_match_without_mutation(self):
        for arguments in (("ping",), ("ping", "--"), ("ping", "--bogus"),
                          ("ping", "--bogus=value"), ("ping", "-xyz"), ("ping", "nope"),
                          ("ping", "banana"), ("ping", "opena"), ("ping", "-"),
                          ("ping", "--", "bogus"), ("ping", "--", "--help")):
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, list(arguments), "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, list(arguments), "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_unknown_arguments_match_without_mutation(self):
        for tail in (("--bogus",), ("--bogus=value",), ("-xyz",), ("unexpected",),
                     ("--bogus", "--help"), ("--", "unexpected"),
                     ("--", "--foo=x"), ("--", "--json")):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_missing_option_values_match_without_mutation(self):
        for tail in (("--profile",), ("-p",), ("--model",), ("--effort",),
                     ("--base-url",), ("--profile", "--json")):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_openai_duplicate_options_match_without_mutation(self):
        cases = (
            ("--profile", "x", "-p", "y"),
            ("--profile=x", "--profile=y"),
            ("--model", "x", "--model", "y"),
            ("--effort=low", "--effort=high"),
            ("--base-url=x", "--base-url=y"),
            ("--no-proxy", "--no-proxy"),
            ("--json", "--json"),
        )
        for tail in cases:
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_empty_model_semantic_validation_remains_outside_guarded_slice(self):
        expected = (1, b"", b"Error: --model must be nonempty and contain no control characters\n")
        guard = (1, b"", b"Error: this Modex development build has not implemented the requested command\n")
        for tail in (("--model", ""), ("--model=",)):
            arguments = ["ping", "openai", *tail]
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, arguments, "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, arguments, "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout, reference.stderr), expected)
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), guard)
                self.assertEqual((reference_changes, actual_changes), ([], []))


    def test_valid_probe_options_remain_guarded(self):
        for tail in ((), ("--json",), ("--profile", "synthetic-profile")):
            result, changes = isolated_run(MODEX, ["ping", "openai", *tail], "modex", "ping-guard")
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (1, b"", b"Error: this Modex development build has not implemented the requested command\n"))
            self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
