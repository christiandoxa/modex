"""Compare literal update arguments with the pinned Prodex 0.166.2 CLI."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class UpdateLiteralArguments01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_unknown_arguments_after_terminator_keep_their_full_text(self):
        cases = (
            (("--help=x", "-x"), "--help=x"),
            (("--unknown=value",), "--unknown=value"),
            (("--help",), "--help"),
        )
        for tail, argument in cases:
            with self.subTest(tail=tail):
                arguments = ["update", "--", *tail]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01662-update-literal-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "01662-update-literal-modex"
                )
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ", 1)
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertIn(("unexpected argument '" + argument + "'").encode(), expected_stderr)
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_attached_help_value_before_terminator_keeps_option_diagnostic(self):
        arguments = ["update", "--help=x"]
        baseline, baseline_created = isolated_run(
            ORACLE, arguments, "prodex", "01662-update-attached-help-oracle"
        )
        modex, modex_created = isolated_run(
            MODEX, arguments, "modex", "01662-update-attached-help-modex"
        )
        expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ", 1)
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (2, b"", expected_stderr))
        self.assertIn(b"unexpected value 'x' for '--help'", expected_stderr)
        self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
