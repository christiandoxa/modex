"""Compare quota parser failures with the pinned 0.166.2 release."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


OPTION_GROUP = (
    "<--profile <NAME>|--all|--auth <AUTH>|--provider <PROVIDER>|--detail|"
    "--raw|--watch|--once|--base-url <URL>>"
)

CASES = (
    (
        ["quota", "--provider", "--help=bad"],
        "error: unexpected value 'bad' for '--help' found; no more were expected\n\n"
        "Usage: prodex quota --help\n\nFor more information, try '--help'.\n",
    ),
    (
        ["quota", "--profile", "main", "--provider", "--help=bad"],
        "error: unexpected value 'bad' for '--help' found; no more were expected\n\n"
        f"Usage: prodex quota --help {OPTION_GROUP}\n\nFor more information, try '--help'.\n",
    ),
    (
        ["quota", "--once", "--detail", "--help=bad"],
        "error: unexpected value 'bad' for '--help' found; no more were expected\n\n"
        f"Usage: prodex quota --help {OPTION_GROUP}\n\nFor more information, try '--help'.\n",
    ),
    (
        ["quota", "--once", "--detail=true", "--help=bad"],
        "error: unexpected value 'true' for '--detail' found; no more were expected\n\n"
        f"Usage: prodex quota {OPTION_GROUP}\n\nFor more information, try '--help'.\n",
    ),
    (
        ["quota", "--detail=true", "--help=bad"],
        "error: unexpected value 'true' for '--detail' found; no more were expected\n\n"
        "Usage: prodex quota --detail\n\nFor more information, try '--help'.\n",
    ),
    (
        ["quota", "--provider", "--help"],
        "error: a value is required for '--provider <PROVIDER>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
)

HELP_CONTROLS = (["quota", "--help"], ["quota", "-h"], ["help", "quota"])


class QuotaCliDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")

    def test_malformed_help_precedence_and_option_usage_are_offline(self):
        with tempfile.TemporaryDirectory(prefix="modex-quota-cli-01662-") as directory:
            base = Path(directory)
            for index, (arguments, expected_stderr) in enumerate(CASES):
                outputs = []
                for label, binary in (("prodex", ORACLE), ("modex", MODEX)):
                    root = base / f"{index}-{label}"
                    root.mkdir()
                    (root / "home").mkdir(mode=0o700)
                    (root / "workspace").mkdir()
                    result = subprocess.run(
                        sandbox_command(binary, root, arguments, argv0="prodex"),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    outputs.append((result.returncode, result.stdout, result.stderr))
                    self.assertEqual(
                        sorted(path.relative_to(root).as_posix() for path in root.rglob("*")),
                        ["home", "workspace"],
                    )
                with self.subTest(arguments=arguments):
                    self.assertEqual(outputs[0], (2, b"", expected_stderr.encode()))
                    self.assertEqual(outputs[1], outputs[0])

    def test_attached_boolean_values_outrank_pending_value_options(self):
        value_options = ("--profile", "-p", "--auth", "--provider", "--base-url")
        boolean_options = (
            "--all=true", "--detail=true", "--raw=true", "--watch=true", "--once=true", "--all=",
        )
        for prefix in ((), ("--once",)):
            for value_option in value_options:
                for boolean_option in boolean_options:
                    arguments = ["quota", *prefix, value_option, boolean_option]
                    with self.subTest(arguments=arguments):
                        baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "quota-oracle")
                        actual, actual_created = isolated_run(MODEX, arguments, "prodex", "quota-modex")
                        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                        self.assertIn(b"unexpected value '", baseline.stderr)
                        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                         (baseline.returncode, baseline.stdout, baseline.stderr))
                        self.assertEqual((baseline_created, actual_created), ([], []))

        for arguments in (
            ["quota", "--profile", "--detail"],
            ["quota", "--profile", "--detail", "--help"],
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "quota-control-oracle")
                actual, actual_created = isolated_run(MODEX, arguments, "prodex", "quota-control-modex")
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr),
                                 (actual.returncode, actual.stdout, actual.stderr))
                self.assertIn(b"a value is required for '--profile <NAME>'", baseline.stderr)
                self.assertEqual((baseline_created, actual_created), ([], []))

    def test_valid_quota_options_stay_behind_the_no_state_guard(self):
        for arguments in (
            ["quota", "--all"],
            ["quota", "--profile", "synthetic", "--once"],
            ["quota", "--provider", "deepseek"],
        ):
            with self.subTest(arguments=arguments):
                actual, created = isolated_run(MODEX, arguments, "prodex", "quota-execution-guard")
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr),
                    (1, b"", b"Error: this Modex development build has not implemented the requested command\n"),
                )
                self.assertEqual(created, [])

    def test_release_help_controls_stay_outside_quota_execution(self):
        with tempfile.TemporaryDirectory(prefix="modex-quota-help-control-01662-") as directory:
            base = Path(directory)
            for index, arguments in enumerate(HELP_CONTROLS):
                outputs = []
                for label, binary in (("prodex", ORACLE), ("modex", MODEX)):
                    root = base / f"{index}-{label}"
                    root.mkdir()
                    (root / "home").mkdir(mode=0o700)
                    (root / "workspace").mkdir()
                    result = subprocess.run(
                        sandbox_command(binary, root, arguments, argv0="prodex"),
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    outputs.append((result.returncode, result.stdout, result.stderr))
                    self.assertEqual(
                        sorted(path.relative_to(root).as_posix() for path in root.rglob("*")),
                        ["home", "workspace"],
                    )
                with self.subTest(arguments=arguments):
                    self.assertEqual(outputs[0][0], 0)
                    self.assertEqual(outputs[0][2], b"")
                    self.assertEqual(outputs[1], outputs[0])


if __name__ == "__main__":
    unittest.main()
