"""Historical 0.439.2 black-box tests; Python is never a product dependency."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
HISTORICAL_04395_ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04395",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.439.5/prodex-x86_64-unknown-linux-gnu",
))
HISTORICAL_04395_ORACLE_SHA256 = "96cef1bfea9cfd90b769d1d7854e88400beed151ad05c229facdd6d52a5d59c5"
HISTORICAL_04392_ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
HISTORICAL_04391_ORACLE_SHA256 = "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a"
SUPER_VALUE_OPTIONS = (
    "--profile", "-p", "--base-url", "--sub-agent-provider", "--sub-agent-model",
    "--sub-agent-model-reasoning-effort", "--sub-agent-url", "--sub-agent-max-concurrency",
    "--tool", "--require-tool", "--url", "--provider", "--cli", "--api-key", "--model",
    "--local-model", "--context-window", "--local-context-window", "--auto-compact-token-limit",
    "--local-auto-compact-token-limit", "--web-search", "--rollout-budget-tokens",
    "--rollout-budget-reminders", "--rollout-budget-sampling-weight",
    "--rollout-budget-prefill-weight", "--current-time-reminder-interval",
    "--current-time-clock-source",
)
SUPER_REASONING_EFFORT_INVALID_VALUES = (
    " INSTANT ", "instant", "İNSTANT", 'bad"quote', "bad\\quote", "bad💡quote",
    "bad\x1b[31mquote\x1b[0m",
    "bad\x1b]2;title\x07quote", "bad\x1b]2;title\x1b\\quote",
    "bad\x1b]incomplete", "bad\x1bPdata\x1b\\quote",
    "bad\x1b_data\x1b\\quote", "bad\x1b^data\x1b\\quote",
    "bad\x1bXdata\x1b\\quote", "bad\x1b]data\x18quote",
    "bad\x1b]data\x1aquote", "bad\x1b]data\x1b[31mquote",
    "bad\x1b]one\x1b]two\x07quote", "bad\x1bPdata\x07quote",
    "bad\x1b\x07quote", "bad\x1b\tquote", "bad\x1b\rquote",
    "bad\x1b[\tquote", "bad\x1b \nquote", "bad\x1b[\x07quote",
    "bad\x1b ééquote", "bad\x1bébquote",
) + tuple("bad" + chr(code) + "quote" for code in range(1, 32)) + tuple(
    "bad" + chr(code) + "quote" for code in range(127, 160)
)
SUPER_POSITIONAL_VALUE_CASES = (
    ("provider", ("super", "exec", "--provider")),
    ("api-key", ("super", "exec", "--api-key")),
    ("model", ("super", "exec", "--model")),
    ("context-window", ("super", "exec", "--context-window")),
    ("model-help-tail", ("super", "exec", "--model", "--help")),
)
SUPER_NEGATIVE_INTEGER_CASES = (
    ("--context-window", "--context-window <TOKENS>"),
    ("--local-context-window", "--context-window <TOKENS>"),
    ("--auto-compact-token-limit", "--auto-compact-token-limit <TOKENS>"),
    ("--local-auto-compact-token-limit", "--auto-compact-token-limit <TOKENS>"),
    ("--rollout-budget-tokens", "--rollout-budget-tokens <TOKENS>"),
    ("--rollout-budget-reminders", "--rollout-budget-reminders <TOKENS>"),
    ("--current-time-reminder-interval", "--current-time-reminder-interval <REQUESTS>"),
)
SUPER_INTEGER_ACCEPT_CASES = (
    ("zero", ("super", "--context-window", "0", "--help")),
    ("u64 max", ("super", "--context-window", "18446744073709551615", "--help")),
    ("plus sign", ("super", "--context-window", "+1", "--help")),
    ("attached canonical", ("super", "--context-window=0", "--help")),
    ("attached context alias", ("super", "--local-context-window=0", "--help")),
    ("attached auto-compact alias", ("super", "--local-auto-compact-token-limit=0", "--help")),
    ("help before invalid value", ("super", "--help", "--context-window", "-1")),
)
SUPER_INTEGER_ERROR_CASES = (
    ("overflow", ("super", "--context-window", "18446744073709551616", "--help"),
     "18446744073709551616", "--context-window <TOKENS>", "number too large to fit in target type"),
    ("whitespace", ("super", "--context-window", " 1 ", "--help"),
     " 1 ", "--context-window <TOKENS>", "invalid digit found in string"),
    ("attached canonical", ("super", "--context-window=-1", "--help"),
     "-1", "--context-window <TOKENS>", "invalid digit found in string"),
    ("attached context alias", ("super", "--local-context-window=18446744073709551616", "--help"),
     "18446744073709551616", "--context-window <TOKENS>", "number too large to fit in target type"),
    ("attached auto-compact alias", ("super", "--local-auto-compact-token-limit=-1", "--help"),
     "-1", "--auto-compact-token-limit <TOKENS>", "invalid digit found in string"),
    ("invalid value before help", ("super", "--context-window", "-1", "--help"),
     "-1", "--context-window <TOKENS>", "invalid digit found in string"),
)
SUPER_SUB_AGENT_CONCURRENCY_ACCEPT_CASES = (
    "default", "1", "4", "8", "16", "32", "64", " 1 ",
)
SUPER_SUB_AGENT_CONCURRENCY_ERROR_CASES = (
    ("negative", ("super", "--sub-agent", "--sub-agent-max-concurrency", "-1"),
     "-1", "invalid maximum active sub-agents: expected default or an integer from 1 to 64"),
    ("plus sign", ("super", "--sub-agent", "--sub-agent-max-concurrency", "+1"),
     "+1", "invalid maximum active sub-agents: expected default or an integer from 1 to 64"),
    ("zero", ("super", "--sub-agent", "--sub-agent-max-concurrency", "0"),
     "0", "maximum active sub-agents must be between 1 and 64"),
    ("too large", ("super", "--sub-agent", "--sub-agent-max-concurrency", "65"),
     "65", "maximum active sub-agents must be between 1 and 64"),
    ("u16 overflow", ("super", "--sub-agent", "--sub-agent-max-concurrency", "65536"),
     "65536", "invalid maximum active sub-agents: expected an integer from 1 to 64"),
    ("syntax", ("super", "--sub-agent", "--sub-agent-max-concurrency", "abc"),
     "abc", "invalid maximum active sub-agents: expected default or an integer from 1 to 64"),
    ("u64 overflow", ("super", "--sub-agent", "--sub-agent-max-concurrency", "18446744073709551616"),
     "18446744073709551616", "invalid maximum active sub-agents: expected an integer from 1 to 64"),
    ("attached negative", ("super", "--sub-agent", "--sub-agent-max-concurrency=-1"),
     "-1", "invalid maximum active sub-agents: expected default or an integer from 1 to 64"),
)


def super_integer_diagnostic(value, label, reason):
    return (f"error: invalid value '{value}' for '{label}': {reason}\n\n"
            "For more information, try '--help'.\n").encode()


def isolated_run(binary, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-cli-test-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        result = subprocess.run(
            [str(binary), *arguments],
            cwd=root,
            env={"HOME": str(home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        mutations = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                           if path != home)
        return result, mutations


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file():
            raise AssertionError("Set PRODEX_ORACLE_04392 to the verified historical 0.439.2 Linux binary")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match the pinned release checksum")

    def test_version_identity_mapping_and_no_mutations(self):
        for flag in ("--version", "-V"):
            for tail in ([], ["extra"], ["session", "list"], ["--unknown"], ["--help"], ["--"]):
                arguments = [flag, *tail]
                with self.subTest(arguments=arguments):
                    baseline, baseline_mutations = isolated_run(ORACLE, arguments)
                    modex, modex_mutations = isolated_run(MODEX, arguments)
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                     (0, b"prodex 0.439.2\n", b""))
                    self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                     (0, b"modex 0.1.0-dev\n", b""))
                    self.assertEqual(baseline_mutations, [])
                    self.assertEqual(modex_mutations, baseline_mutations)

    def test_unimplemented_command_fails_without_echoing_arguments(self):
        # This checks honest development behavior, not baseline command parity.
        sentinel = "synthetic-secret-that-must-not-appear"
        result, mutations = isolated_run(MODEX, ["gateway", "--api-key", sentinel])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"has not implemented", result.stderr)
        self.assertNotIn(sentinel.encode(), result.stderr)
        self.assertEqual(mutations, [])


class HistoricalSuperProviderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CliTests.setUpClass()

    def _run(self, binary, arguments, executable, label):
        from test_root_help import isolated_run

        return isolated_run(binary, arguments, executable, label)

    def test_invalid_provider_values_match_clap_errors(self):
        for arguments in (
            ["super", "--provider", "bad"],
            ["super", "--provider=Bad", "--help"],
            ["super", "--provider", " BAD ", "--help"],
            ["super", "--provider", "local", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider")
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
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-effort")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-effort")
                self.assertEqual((baseline.returncode, modex.returncode), (expected_code, expected_code))
                if expected_code == 0:
                    self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                    self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                    self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                else:
                    self.assertEqual((modex.stdout, modex.stderr),
                                     (baseline.stdout, baseline.stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_missing_values_match_clap_for_all_options_and_aliases(self):
        for option in SUPER_VALUE_OPTIONS:
            with self.subTest(option=option):
                baseline, baseline_created = self._run(ORACLE, ["super", option], "prodex", "04392-super-missing")
                modex, modex_created = self._run(MODEX, ["super", option], "modex", "modex-super-missing")
                expected_stderr = baseline.stderr.replace(b"prodex", b"modex")
                self.assertEqual(baseline.returncode, 2)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, baseline.stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_missing_value_boundaries_keep_empty_dash_values_and_help_order(self):
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
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-missing-boundary")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-missing-boundary")
                expected_stderr = baseline.stderr.replace(b"prodex", b"modex")
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_negative_integer_values_match_release_diagnostics(self):
        for option, diagnostic_label in SUPER_NEGATIVE_INTEGER_CASES:
            with self.subTest(option=option):
                arguments = ["super", option, "-1"]
                expected_stderr = (
                    b"error: invalid value '-1' for '" + diagnostic_label.encode()
                    + b"': invalid digit found in string\n\nFor more information, try '--help'.\n"
                )
                baseline, baseline_created = self._run(
                    ORACLE, arguments, "prodex", "04392-super-negative-integer"
                )
                modex, modex_created = self._run(
                    MODEX, arguments, "modex", "modex-super-negative-integer"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_integer_boundaries_and_help_order_match_release(self):
        oracle_help, oracle_help_created = self._run(
            ORACLE, ["super", "--help"], "prodex", "04392-super-integer-help"
        )
        modex_help, modex_help_created = self._run(
            MODEX, ["super", "--help"], "modex", "modex-super-integer-help"
        )
        self.assertEqual((oracle_help.returncode, oracle_help.stderr, oracle_help_created),
                         (0, b"", []))
        self.assertEqual((modex_help.returncode, modex_help.stderr, modex_help_created),
                         (0, b"", []))

        for name, arguments in SUPER_INTEGER_ACCEPT_CASES:
            with self.subTest(name=name):
                baseline, baseline_created = self._run(
                    ORACLE, list(arguments), "prodex", "04392-super-integer-accepted"
                )
                modex, modex_created = self._run(
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
                baseline, baseline_created = self._run(
                    ORACLE, list(arguments), "prodex", "04392-super-integer-invalid"
                )
                modex, modex_created = self._run(
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
                baseline, baseline_created = self._run(
                    ORACLE, list(arguments), "prodex", "04392-super-sub-agent-concurrency"
                )
                modex, modex_created = self._run(
                    MODEX, list(arguments), "modex", "modex-super-sub-agent-concurrency"
                )
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", expected_stderr))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_sub_agent_concurrency_boundaries_help_order_and_tail(self):
        baseline_help, baseline_help_created = self._run(
            ORACLE, ["super", "--help"], "prodex", "04392-super-sub-agent-help"
        )
        modex_help, modex_help_created = self._run(
            MODEX, ["super", "--help"], "modex", "modex-super-sub-agent-help"
        )
        self.assertEqual((baseline_help.returncode, baseline_help.stderr, baseline_help_created),
                         (0, b"", []))
        self.assertEqual((modex_help.returncode, modex_help.stderr, modex_help_created),
                         (0, b"", []))

        for value in SUPER_SUB_AGENT_CONCURRENCY_ACCEPT_CASES:
            with self.subTest(accepted=value):
                arguments = ["super", "--sub-agent", "--sub-agent-max-concurrency", value, "--help"]
                baseline, baseline_created = self._run(
                    ORACLE, arguments, "prodex", "04392-super-sub-agent-accepted"
                )
                modex, modex_created = self._run(
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
                baseline, baseline_created = self._run(
                    ORACLE, arguments, "prodex", "04392-super-sub-agent-help-order"
                )
                modex, modex_created = self._run(
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
        baseline, baseline_created = self._run(
            ORACLE, arguments, "prodex", "04392-super-sub-agent-post-exec"
        )
        modex, modex_created = self._run(
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

    def test_missing_values_after_positional_tail_keep_runtime_path_difference_visible(self):
        for name, arguments in SUPER_POSITIONAL_VALUE_CASES:
            with self.subTest(name=name):
                baseline, baseline_created = self._run(ORACLE, list(arguments), "prodex", "04392-super-tail-missing")
                modex, modex_created = self._run(MODEX, list(arguments), "modex", "modex-super-tail-missing")
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

        for arguments in (
            ["super", "--help", "--provider"],
            ["super", "--provider=deepseek", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-help-order")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-help-order")
                self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_positional_provider_error_keeps_runtime_diagnostic(self):
        arguments = ["super", "exec", "--provider=local", "--help"]
        expected_stderr = (
            b'Error: invalid --provider: supported values are anthropic, copilot, deepseek, '
            b'gemini, kiro, got "local"\n'
        )
        baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider-tail")
        modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider-tail")
        self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                         (1, b"", expected_stderr))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (baseline.returncode, baseline.stdout, baseline.stderr))
        self.assertTrue(baseline_created)
        self.assertTrue(all(path == "home/.prodex" or path.startswith("home/.prodex/")
                            for path in baseline_created))
        self.assertEqual(modex_created, [])

    def test_provider_aliases_and_help_order_match(self):
        for arguments in (
            ["super", "--provider", "claude", "--help"],
            ["super", "--provider=github-copilot", "--help"],
            ["super", "--provider=github_copilot", "--help"],
            ["super", "--provider", "DEEPSEEK", "--help"],
            ["super", "--help", "--provider=bad"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = self._run(ORACLE, arguments, "prodex", "04392-super-provider-help")
                modex, modex_created = self._run(MODEX, arguments, "modex", "modex-super-provider-help")
                self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
                self.assertTrue(baseline.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertTrue(modex.stdout.startswith(b"YOLO shortcut for the Super tool stack"))
                self.assertIn(b"Usage: prodex super", baseline.stdout)
                self.assertIn(b"Usage: modex super", modex.stdout)
                self.assertEqual((baseline.stderr, modex.stderr), (b"", b""))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
