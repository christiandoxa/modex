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

    def test_pre_mode_diagnostics_match_without_mutations(self):
        cases = (
            (("__super-expose", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--bogus=value"), "prodex", "modex"),
            (("__super-expose", "-xyz"), "prodex", "modex"),
            (("__super-expose", "-☃"), "prodex", "modex"),
            (("__super-expose", "-☃h"), "prodex", "modex"),
            (("__super-expose", "--listen"), "prodex", "modex"),
            (("__super-expose", "--profile"), "prodex", "modex"),
            (("__super-expose", "--listen", "--profile"), "prodex", "modex"),
            (("__super-expose", "--listen", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--profile", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--name", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--dry-run=1"), "prodex", "modex"),
            (("__super-expose", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--tool", "rtk", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--require-tool", "rtk", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--rollout-budget-reminders", "75", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--profile=x", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--dry-run", "--help=invalid"), "prodex", "modex"),
            (("__super-expose", "--bogus", "--help"), "prodex", "modex"),
            (("__super-expose", "--listen=", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--listen=127.0.0.1:0", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--listen", "127.0.0.1:0", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--profile=synthetic", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--profile", "synthetic", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--name=synthetic", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--name", "synthetic", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--dry-run", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--tool", "rtk", "--tool", "playwright-mcp", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--require-tool", "rtk", "--require-tool", "playwright-mcp", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--rollout-budget-reminders", "75", "--rollout-budget-reminders", "50", "--bogus"), "prodex", "modex"),
            (("__super-expose", "--profile=synthetic", "--dry-run=1"), "prodex", "modex"),
            (("__super-expose", "--profile=x", "--profile=y", "--help"), "prodex", "modex"),
            (("__super-expose", "--listen=x", "--listen=y", "--help"), "prodex", "modex"),
            (("__super-expose", "--name=x", "--name=y", "--help"), "prodex", "modex"),
            (("__super-expose", "--dry-run", "--dry-run", "--help"), "prodex", "modex"),
            (("__super-expose", "-p", "one", "--profile", "two", "--help"), "prodex", "modex"),
            (("super", "expose", "--listen"), "custom-prodex", "custom-modex"),
            (("super", "expose", "--bogus"), "custom-prodex", "custom-modex"),
            (("s", "expose", "-xyz"), "prodex", "modex"),
        )
        for arguments, oracle_argv0, modex_argv0 in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01662-super-expose-diagnostic-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01662-super-expose-diagnostic-modex"
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_help_after_valid_option_and_launcher_guard(self):
        for arguments in (
            ["__super-expose", "--profile", "synthetic", "--help"],
            ["__super-expose", "-h☃"],
            ["__super-expose", "--no-tunnel", "--tunnel", "--help"],
            ["__super-expose", "--tool", "rtk", "--tool", "playwright-mcp", "--help"],
            ["__super-expose", "--rollout-budget-reminders", "75", "--rollout-budget-reminders", "50", "--help"],
        ):
            baseline, baseline_created = isolated_run(
                ORACLE, arguments, "prodex", "01662-super-expose-help-precedence-oracle"
            )
            modex, modex_created = isolated_run(
                MODEX, arguments, "modex", "01662-super-expose-help-precedence-modex"
            )
            self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
            self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                             (0, baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex ", 1), b""))
            self.assertEqual((baseline_created, modex_created), ([], []))

    def test_invalid_optional_tool_semantics_remain_unimplemented(self):
        arguments = ["__super-expose", "--tool", "one", "--help"]
        baseline, baseline_created = isolated_run(
            ORACLE, arguments, "prodex", "01662-super-expose-invalid-tool-oracle"
        )
        modex, modex_created = isolated_run(
            MODEX, arguments, "modex", "01662-super-expose-invalid-tool-modex"
        )
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                         (2, b"", b"error: invalid value 'one' for '--tool <TOOL>': unknown optional tool one\n\nFor more information, try '--help'.\n"))
        self.assertEqual(modex.returncode, 0)
        self.assertTrue(modex.stdout.startswith(b"Usage: modex __super-expose"))
        self.assertEqual(modex.stderr, b"")
        self.assertEqual((baseline_created, modex_created), ([], []))

    def test_valid_public_expose_remains_guarded(self):
        guarded, guarded_created = isolated_run(
            MODEX, ["super", "expose", "--listen", "127.0.0.1:0"],
            "modex", "01662-super-expose-launch-guard",
        )
        self.assertEqual((guarded.returncode, guarded.stdout, guarded.stderr),
                         (1, b"", b"Error: Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable\n"))
        self.assertEqual(guarded_created, [])


if __name__ == "__main__":
    unittest.main()
