"""Compare split doctor --tail-bytes error precedence with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class DoctorTailBytesPrecedence01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_invalid_split_value_waits_for_later_syntax_errors(self):
        cases = (
            (
                "unknown option",
                ("--tail-bytes", "abc", "--bogus"),
                b"error: unexpected argument '--bogus' found",
            ),
            (
                "unknown short option",
                ("--tail-bytes", "abc", "-x"),
                b"error: unexpected argument '-x' found",
            ),
            (
                "malformed help",
                ("--tail-bytes", "abc", "--help=x"),
                b"error: unexpected value 'x' for '--help' found; no more were expected",
            ),
            (
                "unknown after terminator",
                ("--tail-bytes", "abc", "--", "--bogus"),
                b"error: unexpected argument '--bogus' found",
            ),
            (
                "positional after terminator",
                ("--tail-bytes", "abc", "--", "extra"),
                b"error: unexpected argument 'extra' found",
            ),
            (
                "overflow before unknown option",
                ("--tail-bytes", "18446744073709551616", "--bogus"),
                b"error: unexpected argument '--bogus' found",
            ),
            (
                "split value before help",
                ("--tail-bytes", "abc", "--help"),
                b"error: invalid value 'abc' for '--tail-bytes <BYTES>'",
            ),
            (
                "split value before later recognized option",
                ("--tail-bytes", "abc", "--json"),
                b"error: invalid value 'abc' for '--tail-bytes <BYTES>'",
            ),
            (
                "attached value remains immediate",
                ("--tail-bytes=abc", "--bogus"),
                b"error: invalid value 'abc' for '--tail-bytes <BYTES>'",
            ),
        )
        for label, tail, expected_error in cases:
            arguments = ["doctor", *tail]
            with self.subTest(label=label, arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "modex", "01662-doctor-tail-oracle"
                )
                actual, actual_created = isolated_run(
                    MODEX, arguments, "modex", "01662-doctor-tail-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertTrue(baseline.stderr.startswith(expected_error), baseline.stderr)
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr),
                    (baseline.returncode, baseline.stdout, baseline.stderr),
                )
                self.assertEqual((baseline_created, actual_created), ([], []))


if __name__ == "__main__":
    unittest.main()
