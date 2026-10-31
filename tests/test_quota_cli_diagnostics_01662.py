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

HELP_USAGE_FORMS = (
    (("--profile", "synthetic"), False),
    (("--profile=synthetic",), True),
    (("--profile=",), True),
    (("-p", "synthetic"), False),
    (("-psynthetic",), True),
    (("-p=synthetic",), True),
    (("--auth", "synthetic"), False),
    (("--auth=synthetic",), True),
    (("--provider", "synthetic"), False),
    (("--provider=synthetic",), True),
    (("--base-url", "http://synthetic.invalid"), False),
    (("--base-url=http://synthetic.invalid",), True),
    (("--profile",), False),
    (("-p",), False),
    (("--auth",), False),
    (("--provider",), False),
    (("--base-url",), False),
    (("--all",), True),
    (("--detail",), True),
    (("--raw",), True),
    (("--watch",), True),
    (("--once",), True),
    (("--profile", "synthetic", "--once"), True),
    (("--once", "--provider", "synthetic"), True),
)

REPEATED_SPLIT_VALUES = (
    ("--profile split", ("--profile", "first", "--profile", "second")),
    ("-p split", ("-p", "first", "-p", "second")),
    ("profile attached then split", ("--profile=first", "--profile", "second")),
    ("profile alias split", ("--profile", "first", "-p", "second")),
    ("--auth split", ("--auth", "first", "--auth", "second")),
    ("--provider split", ("--provider", "first", "--provider", "second")),
    (
        "--base-url split",
        ("--base-url", "http://first.invalid", "--base-url", "http://second.invalid"),
    ),
)

REPEATED_SPLIT_BASES = (
    ("profile", ("--profile", "first", "--profile", "second"), "--profile <NAME>"),
    ("profile alias", ("-p", "first", "-p", "second"), "--profile <NAME>"),
    ("auth", ("--auth", "first", "--auth", "second"), "--auth <AUTH>"),
    ("provider", ("--provider", "first", "--provider", "second"), "--provider <PROVIDER>"),
    ("base-url", ("--base-url", "http://first.invalid", "--base-url", "http://second.invalid"), "--base-url <URL>"),
)


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

    def test_malformed_help_usage_matches_attached_and_split_option_forms(self):
        for index, (prefix, option_group) in enumerate(HELP_USAGE_FORMS):
            arguments = ["quota", *prefix, "--help=synthetic"]
            baseline, baseline_created = isolated_run(ORACLE, arguments, "modex", f"quota-help-form-{index}-oracle")
            actual, actual_created = isolated_run(MODEX, arguments, "modex", f"quota-help-form-{index}-modex")
            usage = "Usage: modex quota --help"
            if option_group:
                usage += " " + OPTION_GROUP
            expected = (
                "error: unexpected value 'synthetic' for '--help' found; no more were expected\n\n"
                + usage
                + "\n\nFor more information, try '--help'.\n"
            ).encode()
            with self.subTest(arguments=arguments):
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (2, b"", expected))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (2, b"", expected))
                self.assertEqual((baseline_created, actual_created), ([], []))

    def test_repeated_split_value_precedence_and_separator(self):
        help_error = (
            "error: unexpected value 'synthetic' for '--help' found; no more were expected\n\n"
            "Usage: modex quota --help "
            + OPTION_GROUP
            + "\n\nFor more information, try '--help'.\n"
        ).encode()
        duplicate_profile = (
            "error: the argument '--profile <NAME>' cannot be used multiple times\n\n"
            "Usage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n"
        ).encode()
        duplicate_once = (
            "error: the argument '--once' cannot be used multiple times\n\n"
            "Usage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n"
        ).encode()
        invalid_attached_boolean = (
            "error: unexpected value 'true' for '--all' found; no more were expected\n\n"
            "Usage: modex quota "
            + OPTION_GROUP
            + "\n\nFor more information, try '--help'.\n"
        ).encode()
        unexpected_after_separator = (
            "error: unexpected argument '--help=synthetic' found\n\n"
            "Usage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n"
        ).encode()
        cases = [
            ("repeated split option before malformed help", ["quota", "--profile", "a", "--profile", "b", "--help=synthetic"], help_error),
            ("attached then repeated split option before malformed help", ["quota", "--profile=a", "--profile", "b", "--help=synthetic"], help_error),
            ("repeated split option before plain help", ["quota", "--profile", "a", "--profile", "b", "--help"], duplicate_profile),
            ("repeated split option before pending value", ["quota", "--profile", "a", "--profile", "b", "--provider", "--help=synthetic"], duplicate_profile),
            ("pending value after deferred duplicate", ["quota", "--profile", "a", "--profile", "b", "--provider", "--unknown"], duplicate_profile),
            ("attached duplicate remains immediate", ["quota", "--profile=a", "--profile=b", "--help=synthetic"], duplicate_profile),
            ("boolean duplicate remains immediate", ["quota", "--once", "--once", "--help=synthetic"], duplicate_once),
            ("attached boolean still precedes deferred duplicate", ["quota", "--profile", "a", "--profile", "b", "--all=true"], invalid_attached_boolean),
            ("unknown positional still precedes duplicate", ["quota", "--profile", "a", "--profile", "b", "extra"], "error: unexpected argument 'extra' found\n\nUsage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n".encode()),
            ("separator makes following help a positional argument", ["quota", "--profile", "a", "--profile", "b", "--", "--help=synthetic"], unexpected_after_separator),
        ]
        for label, arguments, expected_stderr in cases:
            baseline, baseline_created = isolated_run(ORACLE, arguments, "modex", f"quota-repeat-{label}-oracle")
            actual, actual_created = isolated_run(MODEX, arguments, "modex", f"quota-repeat-{label}-modex")
            with self.subTest(case=label):
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (2, b"", expected_stderr))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (2, b"", expected_stderr))
                self.assertEqual((baseline_created, actual_created), ([], []))

        for label, prefix in REPEATED_SPLIT_VALUES:
            arguments = ["quota", *prefix, "--help=synthetic"]
            baseline, baseline_created = isolated_run(ORACLE, arguments, "modex", f"quota-repeat-{label}-oracle")
            actual, actual_created = isolated_run(MODEX, arguments, "modex", f"quota-repeat-{label}-modex")
            with self.subTest(case=label):
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (2, b"", help_error))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (2, b"", help_error))
                self.assertEqual((baseline_created, actual_created), ([], []))

    def test_following_argument_precedence_after_repeated_split_values(self):
        follow_ons = (
            ("unknown attached", ("--unknown=x",), "unknown"),
            ("unknown with other suggestion", ("--watc=x",), "unknown-suggestion"),
            ("unknown suggesting seen profile", ("--profilee=x",), "profile-suggestion"),
            ("attached boolean error", ("--all=x",), "attached-boolean"),
            ("missing split value", ("--base-url",), "duplicate"),
            ("valid boolean then malformed help", ("--once", "--help=synthetic"), "duplicate"),
            ("valid value then malformed help", ("--provider", "synthetic", "--help=synthetic"), "duplicate"),
            ("later boolean duplicate", ("--once", "--once", "--help=synthetic"), "duplicate"),
            (
                "later value duplicate",
                ("--provider", "first", "--provider", "second", "--help=synthetic"),
                "duplicate",
            ),
        )
        for base_label, prefix, duplicate_label in REPEATED_SPLIT_BASES:
            duplicate_error = (
                f"error: the argument '{duplicate_label}' cannot be used multiple times\n\n"
                "Usage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n"
            ).encode()
            for index, (label, suffix, kind) in enumerate(follow_ons):
                arguments = ["quota", *prefix, *suffix]
                if kind == "duplicate":
                    expected_stderr = duplicate_error
                elif kind == "attached-boolean":
                    expected_stderr = (
                        "error: unexpected value 'x' for '--all' found; no more were expected\n\n"
                        "Usage: modex quota "
                        + OPTION_GROUP
                        + "\n\nFor more information, try '--help'.\n"
                    ).encode()
                elif kind == "profile-suggestion":
                    expected_stderr = (
                        "error: unexpected argument '--profilee' found\n\n"
                        "  tip: a similar argument exists: '--profile'\n\n"
                        "Usage: modex quota --profile <NAME>\n\nFor more information, try '--help'.\n"
                    ).encode()
                else:
                    suggestion = "\n\n  tip: a similar argument exists: '--watch'" if kind == "unknown-suggestion" else ""
                    name = "--watc" if kind == "unknown-suggestion" else "--profilee" if kind == "profile-suggestion" else "--unknown"
                    expected_stderr = (
                        f"error: unexpected argument '{name}' found{suggestion}\n\n"
                        "Usage: modex quota [OPTIONS]\n\nFor more information, try '--help'.\n"
                    ).encode()
                baseline, baseline_created = isolated_run(
                    ORACLE, arguments, "modex", f"quota-follow-{base_label}-{index}-oracle"
                )
                actual, actual_created = isolated_run(
                    MODEX, arguments, "modex", f"quota-follow-{base_label}-{index}-modex"
                )
                with self.subTest(base=base_label, suffix=label):
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (2, b"", expected_stderr))
                    self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (2, b"", expected_stderr))
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
