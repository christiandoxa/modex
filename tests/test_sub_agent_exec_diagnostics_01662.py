"""Compare hidden sub-agent CLI diagnostics with Prodex 0.166.2."""

import hashlib
import os
from pathlib import Path
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class SubAgentExecDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 Linux release")

    def test_invalid_hidden_arguments_match_without_mutations(self):
        cases = (
            ((), "prodex", "modex", (b"error: the following required arguments were not provided:",)),
            (("--config", "synthetic-config"), "prodex", "modex", (b"error: the following required arguments were not provided:\n  --task-file <PATH>",)),
            (("--task-file", "synthetic-task"), "prodex", "modex", (b"error: the following required arguments were not provided:\n  --config <PATH>",)),
            (("--bogus",), "prodex", "modex", (b"error: unexpected argument '--bogus' found",)),
            (("-x",), "prodex", "modex", (b"error: unexpected argument '-x' found",)),
            (("-xh",), "prodex", "modex", (b"error: unexpected argument '-x' found",)),
            (("--conf", "synthetic-value"), "prodex", "modex", (
                b"error: unexpected argument '--conf' found",
                b"tip: a similar argument exists: '--config'",
            )),
            (("--config",), "prodex", "modex", (b"error: a value is required for '--config <PATH>' but none was supplied",)),
            (("--config", ""), "prodex", "modex", (b"error: a value is required for '--config <PATH>' but none was supplied",)),
            (("--task-file", ""), "prodex", "modex", (b"error: a value is required for '--task-file <PATH>' but none was supplied",)),
            (("--config", "--task-file", "synthetic-task"), "prodex", "modex", (b"error: a value is required for '--config <PATH>' but none was supplied",)),
            (("--config", "-hx"), "prodex", "modex", (b"error: a value is required for '--config <PATH>' but none was supplied",)),
            (("--config", "-xh"), "prodex", "modex", (b"error: unexpected argument '-x' found",)),
            (("--task-file=",), "prodex", "modex", (b"error: a value is required for '--task-file <PATH>' but none was supplied",)),
            (("--config", "--bogus"), "prodex", "modex", (b"error: unexpected argument '--bogus' found",)),
            (("--config", "one", "--config", "two"), "custom-prodex", "custom-modex", (b"error: the argument '--config <PATH>' cannot be used multiple times",)),
            (("--task-file", "one", "--task-file", "two"), "prodex", "modex", (b"error: the argument '--task-file <PATH>' cannot be used multiple times",)),
            (("extra",), "prodex", "modex", (b"error: unexpected argument 'extra' found",)),
            (("--", "extra"), "prodex", "modex", (b"error: unexpected argument 'extra' found",)),
            (("--help=bad",), "prodex", "modex", (b"error: unexpected value 'bad' for '--help' found; no more were expected",)),
        )
        for tail, oracle_argv0, modex_argv0, expected_messages in cases:
            with self.subTest(arguments=tail, argv0=oracle_argv0):
                arguments = ["__sub-agent-exec", *tail]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, oracle_argv0, "01662-sub-agent-diagnostics-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, modex_argv0, "01662-sub-agent-diagnostics-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertTrue(baseline.stderr.startswith(expected_messages[0]), baseline.stderr)
                for message in expected_messages[1:]:
                    self.assertIn(message, baseline.stderr)
                expected_stderr = baseline.stderr.replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_help_order_and_short_clusters_match_without_mutations(self):
        cases = (
            (("--config", "synthetic-config", "--help"), 0),
            (("-hh",), 0),
            (("-hx",), 0),
            (("-hhx",), 0),
            (("--help", "--bogus"), 0),
            (("--bogus", "--help"), 2),
        )
        for tail, status in cases:
            with self.subTest(arguments=tail):
                arguments = ["__sub-agent-exec", *tail]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01662-sub-agent-help-order-oracle"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "01662-sub-agent-help-order-modex"
                )
                expected_stdout = baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex ", 1)
                expected_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ", 1)
                self.assertEqual(baseline.returncode, status)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (status, expected_stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_valid_syntax_still_stops_at_the_existing_execution_guard(self):
        for tail in (
            ("--config", "synthetic-config", "--task-file", "synthetic-task"),
            ("--config=synthetic-config", "--task-file=synthetic-task"),
        ):
            with self.subTest(arguments=tail):
                modex, created = isolated_run(
                    MODEX, ["__sub-agent-exec", *tail], "modex", "01662-sub-agent-guard"
                )
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
