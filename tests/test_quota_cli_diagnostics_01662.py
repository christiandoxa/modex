"""Compare quota parser failures with the pinned 0.166.2 release."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


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
