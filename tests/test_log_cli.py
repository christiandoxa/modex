"""Compare bounded log argument behavior with the pinned Prodex binary."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from capture_session_cli import map_executable
from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


CASES = [
    ["log", "--help"], ["log", "-h"], ["log", "-hh"], ["help", "log"],
    ["help", "log", "extra"], ["log", "last", "-h"],
    ["log", "last"], ["log", "--json", "last"],
    ["log", "bad"], ["log", "wat"], ["log", "stram"], ["log", "upstram"],
    ["log", "--json", "wat"], ["log", "--json", "--json"],
    ["log", "--json=true"], ["log", "--json="], ["log", "--json", "--json=bad"],
    ["log", "--verbose"], ["log", "last", "--verbose"],
    ["log", "--jso"], ["log", "--jso", "last"], ["log", "-j"],
    ["log", "last", "stream"], ["log", "wat", "extra"],
    ["log", "--", "last"], ["log", "--", "--help"], ["log", "--", "--json"],
    ["log", "--help", "--verbose"], ["log", "--help", "--json=bad"],
    ["log", "last", "--help", "extra"], ["log", "--json", "--help", "--json"],
    ["log", "--help", "-h"], ["log", "-h", "--help"],
    ["log", "--json=bad", "--help"], ["log", "--help=bad"],
    ["log", "--json", "--help=bad"],
]

# Fixed, bounded argv coverage for option ordering and clap's short-help parsing.
for prefix in ([], ["last"], ["bad"], ["--json"], ["--json", "--json"], ["--"]):
    for help_flag in ("-h", "-hh", "-hhh", "-hj", "-jh", "--help"):
        CASES.append(["log", *prefix, help_flag])
CASES.extend([
    ["log", "--json", "--json=bad"], ["log", "--json=bad", "--json"],
    ["log", "--json", "last", "--json"], ["log", "last", "--json", "--json"],
    ["log", "--json", "--", "last"], ["log", "--", "last", "--json"],
    ["log", "--", "last", "extra"], ["log", "last", "--", "extra"],
    ["log", "bad", "--json", "extra"], ["log", "--json", "bad", "extra"],
    ["log", "-", "last"], ["log", "last", "--json=x"],
])


class LogCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_log_help_and_argument_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="modex-log-cli-check-") as directory:
            parent = Path(directory)
            for index, arguments in enumerate(CASES):
                with self.subTest(arguments=arguments):
                    outputs = []
                    for label, binary, argv0 in (("baseline", ORACLE, "prodex"), ("modex", MODEX, "modex")):
                        root = parent / f"{index}-{label}"
                        root.mkdir()
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir()
                        result = subprocess.run(sandbox_command(binary, root, arguments, argv0=argv0),
                                                capture_output=True, timeout=10, check=False)
                        outputs.append((result.returncode,
                                        map_executable(result.stdout.decode()),
                                        map_executable(result.stderr.decode())))
                    self.assertEqual(outputs[1], outputs[0])


if __name__ == "__main__":
    unittest.main()
