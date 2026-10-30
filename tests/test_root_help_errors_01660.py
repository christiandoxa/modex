"""Compare unknown root help operands with the active 0.166.0 release."""

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


class RootHelpErrors01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def test_unknown_help_operand_matches_release_without_mutations(self):
        cases = (
            (("help", "statuz"), "prodex", "modex"),
            (("help", "statuz", "ignored"), "prodex", "modex"),
            (("help", "--unknown"), "prodex", "modex"),
            (("help", "--"), "prodex", "modex"),
            (("help", "--help"), "prodex", "modex"),
            (("help", "-h"), "prodex", "modex"),
            (("help", "--version"), "prodex", "modex"),
            (("help", "-V"), "prodex", "modex"),
            (("help", "statusz"), "custom-prodex", "custom-modex"),
        )
        for arguments, oracle_argv0, modex_argv0 in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-root-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-root-help-modex"
                )
                expected_baseline = (
                    b"error: unrecognized subcommand '" + arguments[1].encode()
                    + b"'\n\nUsage: " + oracle_argv0.encode()
                    + b" <COMMAND>\n\nFor more information, try '--help'.\n"
                )
                expected_modex = expected_baseline.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_baseline))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_modex))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_help_help_matches_release_without_mutations(self):
        for arguments in (("help", "help"), ("help", "help", "status"),
                          ("help", "help", "--help")):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "synthetic", "01660-help-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "synthetic", "01660-help-help-modex"
                )
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_logout_help_matches_release_without_execution_or_mutation(self):
        cases = (
            (("logout", "--help"), 0, "prodex", "modex"),
            (("logout", "-h"), 0, "prodex", "modex"),
            (("logout", "-hfoo"), 0, "prodex", "modex"),
            (("logout", "--help", "--unknown"), 0, "prodex", "modex"),
            (("logout", "--profile=synthetic", "--help"), 0, "prodex", "modex"),
            (("logout", "--profile", "-", "--help"), 0, "prodex", "modex"),
            (("logout", "-psynthetic", "--help"), 0, "prodex", "modex"),
            (("logout", "synthetic-profile", "--help"), 0, "prodex", "modex"),
            (("help", "logout"), 0, "prodex", "modex"),
            (("logout", "--profile", "--help"), 2, "prodex", "modex"),
            (("logout", "--unknown", "--help"), 2, "prodex", "modex"),
            (("logout", "-z", "--help"), 2, "prodex", "modex"),
            (("logout", "one", "two", "--help"), 2, "prodex", "modex"),
            (("logout", "--profile", "one", "--profile", "two", "--help"), 2, "prodex", "modex"),
            (("logout", "--help=synthetic"), 2, "prodex", "modex"),
            (("help", "logout", "--help"), 2, "prodex", "modex"),
            (("help", "logout", "extra"), 2, "prodex", "modex"),
            (("help", "logout", "--"), 2, "prodex", "modex"),
            (("logout", "--help"), 0, "custom-prodex", "custom-modex"),
        )
        for arguments, expected_status, oracle_argv0, modex_argv0 in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-logout-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-logout-modex"
                )
                self.assertEqual(baseline.returncode, expected_status)
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                )
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (expected_status, expected_stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

        for arguments in (("logout", "synthetic-profile"), ("logout", "--", "--help")):
            modex, created = isolated_run(
                MODEX, list(arguments), "modex", "01660-logout-unimplemented-control"
            )
            with self.subTest(modex_only_control=arguments):
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
