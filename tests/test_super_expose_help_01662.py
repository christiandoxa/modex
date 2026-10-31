"""Compare hidden Super expose help routes with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_root_help import isolated_run


class SuperExposeHelp01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_hidden_and_super_alias_help_match_without_mutations(self):
        expected_help = (ROOT / "docs/evidence/baseline-0.166.2/help/__super-expose.txt").read_bytes()
        cases = (
            (("__super-expose", "--help"), "prodex", "modex"),
            (("__super-expose", "-h"), "custom-prodex", "custom-modex"),
            (("help", "__super-expose"), "prodex", "modex"),
            (("super", "expose", "--help"), "custom-prodex", "custom-modex"),
            (("s", "expose", "-h"), "prodex", "modex"),
        )
        for arguments, oracle_argv0, modex_argv0 in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01662-super-expose-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01662-super-expose-help-modex"
                )
                expected_baseline = expected_help.replace(
                    b"Usage: prodex ", b"Usage: " + oracle_argv0.encode() + b" ", 1
                )
                expected_modex = expected_help.replace(
                    b"Usage: prodex ", b"Usage: " + modex_argv0.encode() + b" ", 1
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (0, expected_baseline, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, expected_modex, b""))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
