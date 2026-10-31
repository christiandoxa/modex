"""Compare unknown root help operands with historical Prodex 0.166.0."""

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


class RootHelpErrors01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01660 must identify the verified 0.166.0 Linux release")

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

    def test_hidden_runtime_broker_help_matches_without_mutations(self):
        cases = (
            (("help", "__runtime-broker"), "prodex", "modex", 0),
            (("__runtime-broker", "--help"), "prodex", "modex", 0),
            (("__runtime-broker", "-h"), "custom-prodex", "custom-modex", 0),
            (("help", "__runtime-broker", "extra"), "prodex", "modex", 2),
            (("__runtime-broker", "--help=bad"), "prodex", "modex", 2),
        )
        for arguments, oracle_argv0, modex_argv0, expected_status in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-runtime-broker-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-runtime-broker-modex"
                )
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(baseline.returncode, expected_status)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (expected_status, expected_stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

        modex, created = isolated_run(
            MODEX, ["__runtime-broker"], "modex", "01660-runtime-broker-guard"
        )
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
        )
        self.assertEqual(created, [])

    def test_hidden_mcp_jsonl_bridge_help_matches_without_mutations(self):
        cases = (
            (("help", "__mcp-jsonl-bridge"), "prodex", "modex", 0),
            (("__mcp-jsonl-bridge", "--help"), "prodex", "modex", 0),
            (("__mcp-jsonl-bridge", "-h", "ignored"), "custom-prodex", "custom-modex", 0),
            (("help", "__mcp-jsonl-bridge", "extra"), "prodex", "modex", 2),
            (("__mcp-jsonl-bridge", "--help=bad"), "prodex", "modex", 2),
        )
        for arguments, oracle_argv0, modex_argv0, expected_status in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-mcp-bridge-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-mcp-bridge-modex"
                )
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(baseline.returncode, expected_status)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (expected_status, expected_stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_run_help_routes_match_release_without_starting_runtime(self):
        cases = (
            (("run", "--help"), "prodex", "modex"),
            (("run", "-h"), "prodex", "modex"),
            (("run", "--help", "--unknown"), "prodex", "modex"),
            (("run", "--full-access", "--help"), "prodex", "modex"),
            (("help", "run"), "prodex", "modex"),
            (("run", "--help"), "custom-prodex", "custom-modex"),
        )
        for arguments, oracle_argv0, modex_argv0 in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-run-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-run-help-modex"
                )
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" run",
                    b"Usage: " + modex_argv0.encode() + b" run", 1,
                )
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, expected_stdout, b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

        baseline, baseline_created = isolated_run(
            ORACLE, ["run", "--help=bad"], "prodex", "01660-run-help-value-oracle"
        )
        modex, modex_created = isolated_run(
            MODEX, ["run", "--help=bad"], "modex", "01660-run-help-value-modex"
        )
        expected_stderr = baseline.stderr.replace(
            b"Usage: prodex run", b"Usage: modex run", 1
        )
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (2, b"", expected_stderr))
        self.assertEqual((baseline_created, modex_created), ([], []))

        baseline, baseline_created = isolated_run(
            ORACLE, ["help", "run", "--help"], "prodex", "01660-run-help-error-oracle"
        )
        modex, modex_created = isolated_run(
            MODEX, ["help", "run", "--help"], "modex", "01660-run-help-error-modex"
        )
        expected_stderr = baseline.stderr.replace(
            b"Usage: prodex run", b"Usage: modex run", 1
        )
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (2, b"", expected_stderr))
        self.assertEqual((baseline_created, modex_created), ([], []))

        modex, created = isolated_run(MODEX, ["run"], "modex", "01660-run-guard")
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
        )
        self.assertEqual(created, [])

        modex, created = isolated_run(
            MODEX, ["run", "-hfoo"], "modex", "01660-run-help-short-cluster-guard"
        )
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
        )
        self.assertEqual(created, [])

    def test_ping_group_help_matches_without_mutations(self):
        cases = (
            (("ping", "--help"), "prodex", "modex", 0),
            (("ping", "-h"), "prodex", "modex", 0),
            (("ping", "-hfoo"), "prodex", "modex", 0),
            (("ping", "-h=bad"), "prodex", "modex", 0),
            (("ping", "-hV"), "prodex", "modex", 0),
            (("ping", "help"), "prodex", "modex", 0),
            (("help", "ping"), "prodex", "modex", 0),
            (("ping", "--help", "ignored"), "prodex", "modex", 0),
            (("help", "ping"), "custom-prodex", "custom-modex", 0),
            (("ping", "help", "openai"), "prodex", "modex", 0),
            (("help", "ping", "openai"), "prodex", "modex", 0),
            (("ping", "openai", "--help"), "prodex", "modex", 0),
            (("ping", "openai", "-h=bad"), "prodex", "modex", 0),
            (("ping", "--help=bad"), "prodex", "modex", 2),
            (("ping", "help", "extra"), "prodex", "modex", 2),
            (("ping", "help", "--help"), "prodex", "modex", 2),
            (("help", "ping", "--help"), "prodex", "modex", 2),
            (("ping", "openai", "--help=bad"), "prodex", "modex", 2),
            (("help", "ping", "openai", "--help"), "prodex", "modex", 2),
        )
        for arguments, oracle_argv0, modex_argv0, expected_status in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-ping-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-ping-help-modex"
                )
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(baseline.returncode, expected_status)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (expected_status, expected_stdout, expected_stderr))
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

    def test_quota_help_matches_release_without_quota_execution(self):
        valid_cases = (
            (("quota", "--help"), "prodex", "modex"),
            (("quota", "-h"), "prodex", "modex"),
            (("quota", "-hfoo"), "prodex", "modex"),
            (("help", "quota"), "prodex", "modex"),
            (("quota", "--profile", "synthetic-profile", "--help"), "prodex", "modex"),
            (("quota", "--profile=synthetic-profile", "--help"), "prodex", "modex"),
            (("quota", "--profile", "", "--help"), "prodex", "modex"),
            (("quota", "--profile=", "--help"), "prodex", "modex"),
            (("quota", "--base-url=", "--help"), "prodex", "modex"),
            (("quota", "-psynthetic-profile", "--help"), "prodex", "modex"),
            (("quota", "--watch", "--help"), "prodex", "modex"),
            (("quota", "--profile", "main", "--all", "--help"), "prodex", "modex"),
            (("quota", "--all", "--provider", "deepseek", "--once", "--help"), "prodex", "modex"),
            (("quota", "--help", "--unknown"), "prodex", "modex"),
            (("quota", "--help"), "custom-prodex", "custom-modex"),
        )
        for arguments, oracle_argv0, modex_argv0 in valid_cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01660-quota-help-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01660-quota-help-modex"
                )
                expected_stdout = baseline.stdout.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                ).replace(b"prodex quota", b"modex quota")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, expected_stdout, b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

        invalid_cases = (
            ("quota", "--profile", "--help"),
            ("quota", "--all=yes", "--help"),
            ("quota", "--base-url", "--help"),
            ("quota", "--auth", "--help"),
            ("quota", "--profile", "--unknown", "--help"),
            ("quota", "--auth", "--unknown", "--help"),
            ("quota", "--provider", "--unknown", "--help"),
            ("quota", "--base-url", "--unknown", "--help"),
            ("quota", "-p", "--unknown", "--help"),
            ("quota", "--profile", "-z", "--help"),
            ("quota", "--profile", "--prfile", "--help"),
            ("quota", "--profile", "main", "--profile", "--unknown", "--help"),
            ("quota", "--profile", "--", "--help"),
            ("quota", "--", "--help"),
            ("quota", "--", "synthetic"),
            ("quota", "--all", "--unknown", "--help"),
            ("quota", "--profile", "main", "--profile", "other", "--help"),
            ("quota", "--prfile", "main", "--help"),
            ("quota", "--help=bad"),
            ("help", "quota", "extra"),
            ("help", "quota", "--help"),
        )
        for arguments in invalid_cases:
            with self.subTest(invalid_arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01660-quota-error-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-quota-error-modex"
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: prodex ", b"Usage: modex ", 1
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

        for arguments in (
            ("quota", "--profile", "synthetic-profile"),
            ("quota", "--all", "--provider", "deepseek", "--detail", "--once"),
            ("quota", "--raw", "--profile", "synthetic-profile"),
            ("quota", "--all", "--provider", "local", "--base-url", "http://127.0.0.1:8131/v1", "--once"),
        ):
            with self.subTest(valid_runtime_options=arguments):
                modex, created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-quota-runtime-guard",
                )
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])

    def test_quota_invalid_options_fail_before_execution(self):
        cases = (
            ("quota", "--unknown"),
            ("quota", "--all=yes"),
            ("quota", "--profile"),
            ("quota", "--profile", "--all"),
            ("quota", "--watch=false"),
            ("quota", "--base-url"),
            ("quota", "--profile", "synthetic", "--profile", "other"),
            ("quota", "--profile", "synthetic", "--unknown"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01660-quota-invalid-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01660-quota-invalid-modex"
                )
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ", 1)
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
