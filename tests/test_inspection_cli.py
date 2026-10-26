"""Compare inspection-command parsing without executing their stateful backends."""

import itertools
import random
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_root_help import isolated_run


def cases():
    result = []
    for command in ("current", "info", "status"):
        result.extend([[command, value] for value in (
            "--help", "-h", "-hh", "-h=bad", "-hx", "--help=true", "--help=", "--halp",
            "--unknown", "--unknown=x", "-x", "-xh", "extra", "--version", "--HELP", "-",
        )])
        result.extend([[command, "--help", "--unknown"], [command, "--", "--help"],
                       [command, "--", "extra"], ["help", command],
                       ["help", command, "extra"], ["help", command, "--help"]])
    for option in ("--json", "--tokens"):
        result.extend([["info", option, "--help"], ["info", option, option, "--help"],
                       ["info", option + "=true"], ["info", option + "="],
                       ["info", option, "extra"], ["info", option, "--unknown"],
                       ["info", option, "--jso"], ["info", option, "--help=true"],
                       ["info", option, option + "=true"]])
    for flags in itertools.permutations(("--json", "--tokens")):
        result.extend([["info", *flags, "--help"], ["info", *flags, "--unknown"]])
    result.extend([["info", value] for value in ("--jso", "--tokns", "-j")])
    for value in ("", "bad", "-1", "+", "0", "61", "18446744073709551616",
                  " 1", "1 ", "1_0", "0xff", "1.0", "\u0661"):
        result.append(["status", "--interval=" + value, "--help"])
    for value in ("1", "60", "+2", "0003"):
        result.extend([["status", "--interval", value, "--help"],
                       ["status", "--once", "--interval=" + value, "--help"]])
    result.extend([["status", *tail] for tail in (
        ["--interval"], ["--interval", "--help"], ["--interval", "--"],
        ["--interval", "--once"], ["--interval", "--interval"], ["--interval", "-x"],
        ["--interval", "-1"], ["--interval", "--unknown"], ["--once", "--once", "--help"],
        ["--interval", "1", "--interval=bad"], ["--once=true"], ["--once", "--once=true"],
        ["--interval", "3", "--once=true"], ["--interval", "3", "--help=true"],
        ["--once", "--help=true"], ["--interva"], ["--onc"],
        ["--interval", "3", "--once", "--interva"], ["--interval", "3", "--unknown"],
        ["--interval", "--", "--", "--help"],
        ["--interval", "--interval=2", "--help=bad", "--once", "--help"],
    )])
    return list(dict.fromkeys(tuple(arguments) for arguments in result))


class InspectionCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_matches(self, arguments, argv0=None):
        oracle_argv0 = "prodex" if argv0 is None else argv0
        modex_argv0 = "modex" if argv0 is None else argv0
        expected, expected_paths = isolated_run(
            ORACLE, arguments, oracle_argv0, "inspection-oracle")
        actual, actual_paths = isolated_run(
            MODEX, arguments, modex_argv0, "inspection-modex")
        self.assertIn(expected.returncode, (0, 2))
        expected_stdout = expected.stdout
        expected_stderr = expected.stderr
        if argv0 is None:
            expected_stdout = expected_stdout.replace(b"Usage: prodex ", b"Usage: modex ")
            expected_stderr = expected_stderr.replace(b"Usage: prodex ", b"Usage: modex ")
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                         (expected.returncode, expected_stdout, expected_stderr))
        self.assertEqual((actual_paths, expected_paths), ([], []))

    def test_empty_argv0_usage_falls_back_to_command(self):
        for arguments in (
            ["current", "--help"],
            ["info", "--json=true"],
            ["status", "--once", "--unknown"],
            ["help", "status", "extra"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_matches(arguments, argv0="")

    def test_alternate_argv0_matches_release(self):
        for arguments in (
            ["current", "--help"],
            ["info", "--json=true"],
            ["status", "--once", "--unknown"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_matches(arguments, argv0="alternate-modex")

    def test_help_and_diagnostics_match_release_without_mutations(self):
        for arguments in cases():
            with self.subTest(arguments=arguments):
                self.assert_matches(arguments)

    def test_seeded_argument_ordering_matches_release(self):
        source = random.Random(307_819)
        tokens = ("--json", "--tokens", "--once", "--interval", "--interval=2",
                  "--json=true", "--tokens=", "--once=true", "--help=bad", "--unknown=x",
                  "--jso", "--interva", "--halp", "-xh", "-hh", "-", "--", "1", "bad")
        for command in ("current", "info", "status"):
            for _ in range(128):
                arguments = [command, *source.choices(tokens, k=source.randint(1, 5)), "--help"]
                with self.subTest(arguments=arguments):
                    self.assert_matches(arguments)


if __name__ == "__main__":
    unittest.main()
