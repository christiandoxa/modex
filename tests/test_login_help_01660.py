"""Compare the read-only login help routes with Prodex 0.166.0."""

import hashlib
import os
from pathlib import Path
import unittest

from test_root_help import isolated_run


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01660",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


class LoginHelp01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01660 must identify the verified 0.166.0 Linux release")

    def _compare_help(self, arguments, oracle_argv0="prodex", modex_argv0="modex"):
        baseline, baseline_created = isolated_run(
            ORACLE, list(arguments), oracle_argv0, "01660-login-oracle"
        )
        modex, modex_created = isolated_run(
            MODEX, list(arguments), modex_argv0, "01660-login-modex"
        )
        expected = baseline.stdout.replace(
            b"Usage: " + oracle_argv0.encode() + b" ",
            b"Usage: " + modex_argv0.encode() + b" ",
            1,
        )
        self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, expected, b""))
        self.assertEqual((baseline_created, modex_created), ([], []))

    def test_direct_and_nested_help_routes_are_read_only(self):
        for arguments in (
            ("login", "--help"),
            ("login", "-h"),
            ("login", "-hh"),
            ("login", "--help", "ignored"),
            ("login", "--profile", "synthetic", "--help"),
            ("login", "--profile=synthetic", "--help"),
            ("login", "-p", "synthetic", "--help"),
            ("help", "login"),
        ):
            with self.subTest(arguments=arguments):
                self._compare_help(arguments)

    def test_custom_argv0_and_parser_errors_match(self):
        self._compare_help(("login", "--help"), "custom-prodex", "custom-modex")
        cases = (
            (("login", "--help=synthetic"),
             b"error: unexpected value 'synthetic' for '--help' found; no more were expected\n\n"
             b"Usage: modex login --help [PROFILE_OR_LOGIN_ARG]...\n\nFor more information, try '--help'.\n"),
            (("login", "--profile", "--help"),
             b"error: a value is required for '--profile <NAME>' but none was supplied\n\n"
             b"For more information, try '--help'.\n"),
            (("login", "--profile", "one", "--profile", "two", "--help"),
             b"error: the argument '--profile <NAME>' cannot be used multiple times\n\n"
             b"Usage: modex login [OPTIONS] [PROFILE_OR_LOGIN_ARG]...\n\n"
             b"For more information, try '--help'.\n"),
            (("help", "login", "extra"),
             b"error: unrecognized subcommand 'extra'\n\n"
             b"Usage: modex login [OPTIONS] [PROFILE_OR_LOGIN_ARG]...\n\n"
             b"For more information, try '--help'.\n"),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01660-login-error-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-login-error-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected.replace(b"Usage: modex ", b"Usage: prodex ")))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_login_execution_stays_fail_closed_and_does_not_create_state(self):
        modex, created = isolated_run(
            MODEX, ["login", "synthetic-profile"], "modex", "01660-login-unimplemented"
        )
        self.assertEqual(modex.returncode, 1)
        self.assertEqual(modex.stdout, b"")
        self.assertIn(b"has not implemented the requested command", modex.stderr)
        self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
