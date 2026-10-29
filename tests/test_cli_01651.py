"""Selected production CLI comparisons against the 0.165.1 release."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import (
    MODEX,
    SUPER_INTEGER_ACCEPT_CASES,
    SUPER_INTEGER_ERROR_CASES,
    SUPER_NEGATIVE_INTEGER_CASES,
    SUPER_POSITIONAL_VALUE_CASES,
    SUPER_REASONING_EFFORT_INVALID_VALUES,
    SUPER_SUB_AGENT_CONCURRENCY_ACCEPT_CASES,
    SUPER_SUB_AGENT_CONCURRENCY_ERROR_CASES,
    SUPER_VALUE_OPTIONS,
    isolated_run as isolated_version,
    super_integer_diagnostic,
)
from test_root_help import isolated_run, map_executable


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class Release01651CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")

    def test_version_identity_and_no_mutations(self):
        for flag in ("--version", "-V"):
            for tail in ([], ["extra"], ["session", "list"], ["--unknown"], ["--help"], ["--"]):
                with self.subTest(flag=flag, tail=tail):
                    baseline, baseline_mutations = isolated_version(ORACLE, [flag, *tail])
                    modex, modex_mutations = isolated_version(MODEX, [flag, *tail])
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (0, b"prodex 0.165.1\n", b""))
                    self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, b"modex 0.1.0-dev\n", b""))
                    self.assertEqual((baseline_mutations, modex_mutations), ([], []))

    def test_help_forms_and_custom_executable(self):
        for arguments, argv0 in ((["--help"], "prodex"), (["-h"], "prodex"), (["help"], "prodex"),
                                 (["--help", "ignored"], "prodex"), (["-h", "ignored"], "prodex"),
                                 (["--help"], "custom-modex")):
            with self.subTest(arguments=arguments, argv0=argv0):
                baseline, baseline_created = isolated_run(ORACLE, arguments, argv0, "01651")
                modex_argv0 = "modex" if argv0 == "prodex" else argv0
                modex, modex_created = isolated_run(MODEX, arguments, modex_argv0, "modex")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, map_executable(baseline.stdout), b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_update_help_routes_are_read_only(self):
        for arguments in (("update", "--help"), ("update", "-h"), ("help", "update"),
                          ("update", "--help", "ignored"), ("update", "-h", "ignored")):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, list(arguments), "prodex", "01651-update")
                modex, modex_created = isolated_run(MODEX, list(arguments), "modex", "modex-update")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, map_executable(baseline.stdout), b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_help_update_preserves_unknown_subcommand_argument(self):
        for argument in ("--unknown=synthetic-value", "--help=synthetic-value", "synthetic=value"):
            with self.subTest(argument=argument):
                baseline, baseline_created = isolated_run(
                    ORACLE, ["help", "update", argument], "prodex", "01651-update-help-error"
                )
                modex, modex_created = isolated_run(
                    MODEX, ["help", "update", argument], "modex", "modex-update-help-error"
                )
                expected_stderr = baseline.stderr.replace(
                    b"Usage: prodex update", b"Usage: modex update"
                )
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, baseline.stdout, expected_stderr))
                self.assertIn(argument.encode(), expected_stderr)
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_update_parser_errors_and_help_order_match_release(self):
        cases = (
            (["update", "--help"], 0, "prodex"),
            (["update", "-hh"], 0, "prodex"),
            (["update", "-hx"], 0, "prodex"),
            (["update", "--help", "ignored"], 0, "prodex"),
            (["update", "--bogus"], 2, "prodex"),
            (["update", "--hepl"], 2, "prodex"),
            (["update", "--help=synthetic-help-value"], 2, "prodex"),
            (["update", "--bogus=synthetic-secret"], 2, "prodex"),
            (["update", "--api-key", "synthetic-secret"], 2, "prodex"),
            (["update", "synthetic-position"], 2, "prodex"),
            (["update", "--", "--help"], 2, "prodex"),
            (["help", "update"], 0, "prodex"),
            (["help", "update", "ignored"], 2, "prodex"),
            (["update", "--hepl"], 2, "custom-prodex"),
        )
        for arguments, code, argv0 in cases:
            with self.subTest(arguments=arguments, argv0=argv0):
                executable = "modex" if argv0 == "prodex" else "custom-modex"
                baseline, baseline_created = isolated_run(ORACLE, arguments, argv0, "01651-update-parser")
                modex, modex_created = isolated_run(MODEX, arguments, executable, "modex-update-parser")
                self.assertEqual(baseline.returncode, code)
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (code,
                     baseline.stdout.replace(b"Usage: " + argv0.encode() + b" ",
                                             b"Usage: " + executable.encode() + b" "),
                     baseline.stderr.replace(b"Usage: " + argv0.encode() + b" ",
                                             b"Usage: " + executable.encode() + b" ")),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))
                self.assertNotIn(b"synthetic-secret", baseline.stderr + modex.stderr)

    def test_unknown_option_name_remains_in_diagnostic(self):
        argument = b"--synthetic-secret"
        baseline, baseline_created = isolated_run(
            ORACLE, ["update", argument.decode()], "prodex", "01651-update-option-name"
        )
        modex, modex_created = isolated_run(
            MODEX, ["update", argument.decode()], "modex", "modex-update-option-name"
        )
        self.assertEqual((baseline.returncode, modex.returncode), (2, 2))
        self.assertIn(argument, baseline.stderr)
        self.assertIn(argument, modex.stderr)
        self.assertEqual((baseline_created, modex_created), ([], []))

    def test_update_execution_stays_fail_closed(self):
        modex, created = isolated_run(MODEX, ["update"], "modex", "modex-update-unimplemented")
        self.assertEqual(modex.returncode, 1)
        self.assertEqual(modex.stdout, b"")
        self.assertIn(b"has not implemented the requested command", modex.stderr)
        self.assertEqual(created, [])


class SuperProviderCli01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")

    def test_invalid_provider_values_match_clap_errors(self):
        cases = (
            ["super", "--provider", "bad"],
            ["super", "--provider=Bad", "--help"],
            ["super", "--provider", " BAD ", "--help"],
            ["super", "--provider", "local", "--help"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-provider")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-provider")
                expected_stderr = baseline.stderr.replace(b"prodex", b"modex")
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, baseline.stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_sub_agent_reasoning_effort_matches_clap(self):
        option = "--sub-agent-model-reasoning-effort"
        cases = [(["super", "--sub-agent", option, "HIGH", "--help"], 0)]
        cases.extend(((["super", "--sub-agent", option, value], 2)
                      for value in SUPER_REASONING_EFFORT_INVALID_VALUES))
        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-effort")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-effort")
                self.assertEqual((baseline.returncode, modex.returncode), (expected_code, expected_code))
                if expected_code == 0:
                    self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                    self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                    self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                else:
                    self.assertEqual((modex.stdout, modex.stderr),
                                     (baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_positional_provider_error_keeps_runtime_diagnostic(self):
        arguments = ["super", "exec", "--provider=local", "--help"]
        expected_stderr = (
            b'Error: invalid --provider: supported values are anthropic, copilot, deepseek, '
            b'gemini, kiro, got "local"\n'
        )
        baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-provider-tail")
        modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-provider-tail")
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                         (1, b"", expected_stderr))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (baseline.returncode, baseline.stdout, baseline.stderr))
        self.assertTrue(baseline_created)
        self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                            for path in baseline_created))
        self.assertEqual(modex_created, [])

    def test_provider_aliases_and_help_order_match(self):
        cases = (
            ["super", "--provider", "claude", "--help"],
            ["super", "--provider=github-copilot", "--help"],
            ["super", "--provider=github_copilot", "--help"],
            ["super", "--provider", "DEEPSEEK", "--help"],
            ["super", "--help", "--provider=bad"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-provider-help")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-provider-help")
                self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertIn(b"Usage: prodex super", baseline.stdout)
                self.assertIn(b"Usage: modex super", modex.stdout)
                self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_missing_values_match_clap_for_all_options_and_aliases(self):
        for option in SUPER_VALUE_OPTIONS:
            with self.subTest(option=option):
                baseline, baseline_created = isolated_run(ORACLE, ["super", option], "prodex", "01651-super-missing")
                modex, modex_created = isolated_run(MODEX, ["super", option], "modex", "modex-super-missing")
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_missing_value_boundaries_preserve_empty_dash_values_and_order(self):
        for arguments in (
            ["super", "--provider="],
            ["super", "--provider", ""],
            ["super", "--provider", "-bad"],
            ["super", "--provider=-bad"],
            ["super", "--provider", "--api-key"],
            ["super", "--provider", "--help"],
            ["super", "--provider", "-h"],
            ["super", "--provider=bad", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-missing-boundary")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-missing-boundary")
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

        for arguments in (
            ["super", "--help", "--provider"],
            ["super", "--provider=deepseek", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "01651-super-help-order")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex-super-help-order")
                self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_negative_integer_values_match_release_diagnostics(self):
        for option, diagnostic_label in SUPER_NEGATIVE_INTEGER_CASES:
            with self.subTest(option=option):
                arguments = ["super", option, "-1"]
                expected_stderr = (
                    b"error: invalid value '-1' for '" + diagnostic_label.encode()
                    + b"': invalid digit found in string\n\nFor more information, try '--help'.\n"
                )
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01651-super-negative-integer"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "modex-super-negative-integer"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_integer_boundaries_and_help_order_match_release(self):
        oracle_help, oracle_help_created = isolated_run(
            ORACLE, ["super", "--help"], "prodex", "01651-super-integer-help"
        )
        modex_help, modex_help_created = isolated_run(
            MODEX, ["super", "--help"], "modex", "modex-super-integer-help"
        )
        self.assertEqual((oracle_help.returncode, oracle_help.stderr, oracle_help_created),
                         (0, b"", []))
        self.assertEqual((modex_help.returncode, modex_help.stderr, modex_help_created),
                         (0, b"", []))

        for name, arguments in SUPER_INTEGER_ACCEPT_CASES:
            with self.subTest(name=name):
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01651-super-integer-accepted"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "modex-super-integer-accepted"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (0, oracle_help.stdout, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, modex_help.stdout, b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

        for name, arguments, value, label, reason in SUPER_INTEGER_ERROR_CASES:
            with self.subTest(name=name):
                expected_stderr = super_integer_diagnostic(value, label, reason)
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01651-super-integer-invalid"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "modex-super-integer-invalid"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_sub_agent_concurrency_value_diagnostics_match_release(self):
        for name, arguments, value, reason in SUPER_SUB_AGENT_CONCURRENCY_ERROR_CASES:
            with self.subTest(name=name):
                expected_stderr = super_integer_diagnostic(
                    value, "--sub-agent-max-concurrency <VALUE>", reason
                )
                baseline, baseline_created = isolated_run(
                    ORACLE, list(arguments), "prodex", "01651-super-sub-agent-concurrency"
                )
                modex, modex_created = isolated_run(
                    MODEX, list(arguments), "modex", "modex-super-sub-agent-concurrency"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_sub_agent_concurrency_boundaries_help_order_and_tail(self):
        baseline_help, baseline_help_created = isolated_run(
            ORACLE, ["super", "--help"], "prodex", "01651-super-sub-agent-help"
        )
        modex_help, modex_help_created = isolated_run(
            MODEX, ["super", "--help"], "modex", "modex-super-sub-agent-help"
        )
        self.assertEqual((baseline_help.returncode, baseline_help.stderr, baseline_help_created),
                         (0, b"", []))
        self.assertEqual((modex_help.returncode, modex_help.stderr, modex_help_created),
                         (0, b"", []))

        for value in SUPER_SUB_AGENT_CONCURRENCY_ACCEPT_CASES:
            with self.subTest(accepted=value):
                arguments = ["super", "--sub-agent", "--sub-agent-max-concurrency", value, "--help"]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01651-super-sub-agent-accepted"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "modex-super-sub-agent-accepted"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (0, baseline_help.stdout, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, modex_help.stdout, b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

        for arguments in (
            ["super", "--help", "--sub-agent", "--sub-agent-max-concurrency", "-1"],
            ["super", "--sub-agent", "--sub-agent-max-concurrency", "-1", "--help"],
        ):
            with self.subTest(help_order=arguments):
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01651-super-sub-agent-help-order"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "modex-super-sub-agent-help-order"
                )
                if arguments[1] == "--help":
                    self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                    self.assertEqual((baseline.stdout, modex.stdout),
                                     (baseline_help.stdout, modex_help.stdout))
                    self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                else:
                    expected_stderr = super_integer_diagnostic(
                        "-1",
                        "--sub-agent-max-concurrency <VALUE>",
                        "invalid maximum active sub-agents: expected default or an integer from 1 to 64",
                    )
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                     (2, b"", expected_stderr))
                    self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                     (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

        arguments = ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "-1"]
        baseline, baseline_created = isolated_run(
            ORACLE, arguments, "prodex", "01651-super-sub-agent-post-exec"
        )
        modex, modex_created = isolated_run(
            MODEX, arguments, "modex", "modex-super-sub-agent-post-exec"
        )
        expected = (
            1,
            b"",
            b"Error: invalid maximum active sub-agents: expected default or an integer from 1 to 64\n",
        )
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), expected)
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), expected)
        self.assertTrue(baseline_created)
        self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                            for path in baseline_created))
        self.assertEqual(modex_created, [])

    def test_sub_agent_concurrency_still_requires_explicit_enablement(self):
        result, created = isolated_run(
            MODEX,
            ["super", "--sub-agent-max-concurrency", "1"],
            "modex",
            "modex-sub-agent-required",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr,
                         b"Error: sub-agent detail flags require explicit --sub-agent\n")
        self.assertEqual(created, [])

    def test_sub_agent_concurrency_dry_run_reaches_only_the_release_consumer(self):
        cases = (
            (" 1 ", b"Maximum active sub-agents: 1 (custom)\n"),
            (" default ", b"Maximum active sub-agents: 4 (Prodex default)\n"),
        )
        for value, report_line in cases:
            with self.subTest(value=value):
                arguments = [
                    "super", "--dry-run", "--provider", "deepseek", "--api-key",
                    "synthetic-provider-key", "--base-url", "http://127.0.0.1:8131/v1",
                    "--model", "deepseek-chat", "--no-presidio", "--skip-quota-check",
                    "--sub-agent", "--sub-agent-max-concurrency", value,
                ]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01651-super-sub-agent-dry-run"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "modex-super-sub-agent-dry-run"
                )
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertIn(report_line, baseline.stdout)
                self.assertIn(b"Codex/TUI not started because --dry-run was set.\n", baseline.stdout)
                self.assertNotIn(b"synthetic-provider-key", baseline.stdout + baseline.stderr)
                self.assertEqual(baseline_created, [])
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable\n"),
                )
                self.assertEqual(modex_created, [])

    def test_sub_agent_concurrency_post_tail_whitespace_reaches_startup_guard(self):
        cases = (
            (" 1 ", b"Maximum active sub-agents: 1 (custom)\n"),
            (" default ", b"Maximum active sub-agents: 4 (Prodex default)\n"),
        )
        for value, report_line in cases:
            with self.subTest(value=value):
                arguments = [
                    "super", "exec", "--dry-run", "--provider", "deepseek", "--api-key",
                    "synthetic-provider-key", "--base-url", "http://127.0.0.1:8131/v1",
                    "--model", "deepseek-chat", "--no-presidio", "--skip-quota-check",
                    "--sub-agent", "--sub-agent-max-concurrency", value,
                ]
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "prodex", "01651-super-sub-agent-post-tail-dry-run"
                )
                modex, modex_created = isolated_run(
                    MODEX, arguments, "modex", "modex-super-sub-agent-post-tail-dry-run"
                )
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertIn(report_line, baseline.stdout)
                self.assertIn(b"Codex/TUI not started because --dry-run was set.\n", baseline.stdout)
                self.assertEqual(baseline_created, [])
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (1, b"", b"Error: Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable\n"),
                )
                self.assertEqual(modex_created, [])

    def test_negative_integer_after_exec_keeps_runtime_error_path(self):
        arguments = ["super", "exec", "--context-window", "-1"]
        baseline, baseline_created = isolated_run(
            ORACLE, arguments, "prodex", "01651-super-post-exec-negative"
        )
        modex, modex_created = isolated_run(
            MODEX, arguments, "modex", "modex-super-post-exec-negative"
        )
        expected = (1, b"", b"Error: invalid digit found in string\n")
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), expected)
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), expected)
        self.assertTrue(baseline_created)
        self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                            for path in baseline_created))
        self.assertEqual(modex_created, [])

    def test_missing_values_after_positional_tail_keep_runtime_path_difference_visible(self):
        for name, arguments in SUPER_POSITIONAL_VALUE_CASES:
            with self.subTest(name=name):
                baseline, baseline_created = isolated_run(ORACLE, list(arguments), "prodex", "01651-super-tail-missing")
                modex, modex_created = isolated_run(MODEX, list(arguments), "modex", "modex-super-tail-missing")
                self.assertEqual((baseline.returncode, modex.returncode), (1, 1))
                if name == "model-help-tail":
                    self.assertIn(b"no active profile selected", baseline.stderr)
                    self.assertIn(b"Super startup is not implemented", modex.stderr)
                else:
                    expected = f"Error: --{name} requires a value".encode()
                    self.assertEqual(baseline.stderr.splitlines()[-1], expected)
                    self.assertEqual(modex.stderr, expected + b"\n")
                self.assertTrue(baseline_created)
                self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                                    for path in baseline_created))
                self.assertEqual(modex_created, [])


if __name__ == "__main__":
    unittest.main()
