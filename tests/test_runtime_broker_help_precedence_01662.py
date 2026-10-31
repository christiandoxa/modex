"""Compare the hidden runtime broker help parser with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_root_help import isolated_run


class RuntimeBrokerHelpPrecedence01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_help_precedence_and_invalid_arguments_match_without_mutations(self):
        expected_help = (ROOT / "docs/evidence/baseline-0.166.2/help/__runtime-broker.txt").read_bytes()
        cases = (
            (("__runtime-broker", "-hh"), "prodex", "modex", 0),
            (("__runtime-broker", "-hx"), "custom-prodex", "custom-modex", 0),
            (("__runtime-broker", "--help", "--bogus"), "prodex", "modex", 0),
            (("__runtime-broker", "-xh"), "prodex", "modex", 2),
            (("__runtime-broker", "--bogus", "--help"), "custom-prodex", "custom-modex", 2),
            (("__runtime-broker", "extra"), "prodex", "modex", 2),
            (("__runtime-broker", "--help=bad"), "prodex", "modex", 2),
            (("__runtime-broker", "--bad=foo"), "prodex", "modex", 2),
            (("__runtime-broker", "-☃"), "custom-prodex", "custom-modex", 2),
            (("__runtime-broker", "--", "extra"), "prodex", "modex", 2),
            (("__runtime-broker", "--", "--help"), "prodex", "modex", 2),
            (("__runtime-broker", "--", "--bad=foo"), "prodex", "modex", 2),
        )
        for arguments, oracle_argv0, modex_argv0, status in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01662-runtime-broker-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01662-runtime-broker-modex"
                )
                expected_stdout = expected_help.replace(
                    b"Usage: prodex ", b"Usage: " + oracle_argv0.encode() + b" ", 1
                ) if status == 0 else b""
                expected_modex_stdout = expected_help.replace(
                    b"Usage: prodex ", b"Usage: " + modex_argv0.encode() + b" ", 1
                ) if status == 0 else b""
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(baseline.returncode, status)
                if status == 0:
                    self.assertEqual(baseline.stdout, expected_stdout)
                    self.assertEqual(baseline.stderr, b"")
                else:
                    self.assertEqual(baseline.stdout, b"")
                    self.assertTrue(baseline.stderr)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (status, expected_modex_stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_runtime_broker_entry_stays_guarded(self):
        for tail in ((), ("--",)):
            with self.subTest(tail=tail):
                modex, created = isolated_run(
                    MODEX,
                    ["__runtime-broker", *tail],
                    "modex",
                    "01662-runtime-broker-runtime-guard",
                )
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
