"""Compare the hidden MCP bridge help parser with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256, ROOT
from test_root_help import isolated_run


class McpJsonlBridgeHelpPrecedence01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_help_precedence_and_short_clusters_match_without_mutations(self):
        expected_help = (ROOT / "docs/evidence/baseline-0.166.2/help/__mcp-jsonl-bridge.txt").read_bytes()
        cases = (
            (("__mcp-jsonl-bridge", "-hh"), "prodex", "modex", 0),
            (("__mcp-jsonl-bridge", "-hx"), "custom-prodex", "custom-modex", 0),
            (("__mcp-jsonl-bridge", "--help", "--bogus"), "prodex", "modex", 0),
            (("__mcp-jsonl-bridge", "-xh"), "prodex", "modex", 2),
            (("__mcp-jsonl-bridge", "--bogus", "--help"), "custom-prodex", "custom-modex", 2),
            (("__mcp-jsonl-bridge", "--help=bad"), "prodex", "modex", 2),
            (("__mcp-jsonl-bridge", "--bad=foo"), "prodex", "modex", 2),
            (("__mcp-jsonl-bridge", "-☃"), "prodex", "modex", 2),
        )
        for arguments, oracle_argv0, modex_argv0, status in cases:
            with self.subTest(arguments=arguments, argv0=oracle_argv0):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), oracle_argv0, "01662-mcp-bridge-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), modex_argv0, "01662-mcp-bridge-modex"
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

    def test_post_command_help_precedence_matches_without_starting_server(self):
        expected_help = (ROOT / "docs/evidence/baseline-0.166.2/help/__mcp-jsonl-bridge.txt").read_bytes()
        cases = (
            (("__mcp-jsonl-bridge", "synthetic-command", "--help"), 0),
            (("__mcp-jsonl-bridge", "synthetic-command", "-h"), 0),
            (("__mcp-jsonl-bridge", "synthetic-command", "-hh"), 0),
            (("__mcp-jsonl-bridge", "synthetic-command", "--help", "--bogus"), 0),
            (("__mcp-jsonl-bridge", "synthetic-command", "--help=bad"), 2),
            (("__mcp-jsonl-bridge", "synthetic-command", "--help=bad", "--bogus"), 2),
        )
        for arguments, status in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01662-mcp-bridge-post-command-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "01662-mcp-bridge-post-command-modex"
                )
                expected_stdout = expected_help if status == 0 else b""
                expected_modex_stdout = expected_help.replace(
                    b"Usage: prodex ", b"Usage: modex ", 1
                ) if status == 0 else b""
                expected_stderr = baseline.stderr.replace(
                    b"Usage: prodex ", b"Usage: modex ", 1
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (status, expected_stdout))
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (status, expected_modex_stdout, expected_stderr),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_positional_bridge_command_stays_guarded(self):
        for tail in (
            ("synthetic-command",),
            ("-",),
            ("synthetic-command", "--bogus", "--help"),
            ("synthetic-command", "--", "--help"),
        ):
            with self.subTest(tail=tail):
                modex, created = isolated_run(
                    MODEX,
                    ["__mcp-jsonl-bridge", *tail],
                    "modex",
                    "01662-mcp-bridge-runtime-guard",
                )
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])

    def test_child_args_stop_help_scan_and_keep_bridge_guard(self):
        for tail in (
            ("synthetic-command", "--bogus", "--help"),
            ("synthetic-command", "--", "--help"),
            ("synthetic-command", "-hx"),
        ):
            with self.subTest(tail=tail):
                baseline, baseline_created = isolated_run(
                    ORACLE,
                    ["__mcp-jsonl-bridge", *tail],
                    "prodex",
                    "01662-mcp-bridge-child-args-oracle",
                )
                modex, modex_created = isolated_run(
                    MODEX,
                    ["__mcp-jsonl-bridge", *tail],
                    "modex",
                    "01662-mcp-bridge-child-args-modex",
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
                self.assertIn(b"failed to start MCP server synthetic-command", baseline.stderr)
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_missing_bridge_command_matches_required_argument_error(self):
        for tail in ((), ("--",)):
            with self.subTest(tail=tail):
                baseline, baseline_created = isolated_run(
                    ORACLE,
                    ["__mcp-jsonl-bridge", *tail],
                    "prodex",
                    "01662-mcp-bridge-missing-command-oracle",
                )
                modex, modex_created = isolated_run(
                    MODEX,
                    ["__mcp-jsonl-bridge", *tail],
                    "modex",
                    "01662-mcp-bridge-missing-command-modex",
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                expected_stderr = baseline.stderr.replace(
                    b"Usage: prodex ", b"Usage: modex ", 1
                )
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (baseline.returncode, b"", expected_stderr),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
