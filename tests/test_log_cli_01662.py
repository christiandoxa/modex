"""Compare connected log argument diagnostics with Prodex 0.166.2."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


CASES = (
    ("full help", ["log", "--help"], 0),
    ("short help", ["log", "-h"], 0),
    ("last help", ["log", "last", "--help"], 0),
    ("upstream JSON help", ["log", "upstream", "--json", "--help"], 0),
    ("help near-match", ["log", "--h=x"], 2),
    ("help near-match after mode", ["log", "last", "--h=x"], 2),
    ("help near-match after JSON", ["log", "--json", "--h=x"], 2),
    ("help near-match after mode and JSON", ["log", "last", "--json", "--h=x"], 2),
    ("JSON near-match control", ["log", "last", "--j=x"], 2),
    ("unknown option control", ["log", "last", "--unknown=x"], 2),
    ("unknown mode", ["log", "not-a-mode"], 2),
    ("attached help value", ["log", "--help=x"], 2),
    ("attached JSON value", ["log", "--json=x"], 2),
)


def map_executable(output):
    return output.replace(b"Usage: prodex log ", b"Usage: modex log ", 1)


def observe(binary, argv0, arguments, label):
    with tempfile.TemporaryDirectory(prefix="modex-log-cli-01662-" + label + "-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        result = subprocess.run(
            sandbox_command(binary, root, arguments, argv0=argv0),
            capture_output=True,
            timeout=10,
            check=False,
        )
        created = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path not in (root / "home", root / "workspace")
        )
        return (result.returncode, result.stdout, result.stderr), created


class LogCli01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_log_help_and_diagnostics_match_without_state_changes(self):
        for name, arguments, exit_code in CASES:
            with self.subTest(case=name):
                baseline, baseline_created = observe(ORACLE, "prodex", arguments, "oracle")
                modex, modex_created = observe(MODEX, "modex", arguments, "modex")
                self.assertEqual(baseline[0], exit_code)
                self.assertEqual(
                    modex,
                    (baseline[0], map_executable(baseline[1]), map_executable(baseline[2])),
                )
                self.assertEqual(baseline_created, [])
                self.assertEqual(modex_created, [])


if __name__ == "__main__":
    unittest.main()
