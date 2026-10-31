"""Session parser duplicate precedence against the pinned 0.166.2 release."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


CASES = (
    ("attached switch value", ["session", "list", "--profile", "a", "--profile", "b", "--json=bad"]),
    ("attached parent switch value", ["session", "list", "--profile", "a", "--profile", "b", "--parent-only=x"]),
    ("attached help value", ["session", "list", "--profile", "a", "--profile", "b", "--help=x"]),
    ("unknown flag", ["session", "list", "--profile", "a", "--profile", "b", "--unknown"]),
    ("unknown flag suggestion", ["session", "list", "--profile", "a", "--profile", "b", "--jso"]),
    ("positional", ["session", "list", "--profile", "a", "--profile", "b", "extra"]),
    ("valid switch before malformed value", ["session", "list", "--profile", "a", "--profile", "b", "--parent-only", "--json=x"]),
    ("typed value error", ["session", "list", "--profile", "a", "--profile", "b", "--limit=bad"]),
    ("missing split value", ["session", "list", "--profile", "a", "--profile", "b", "--query"]),
    ("repeated switch", ["session", "list", "--json", "--json", "--json=bad"]),
    ("help after duplicate", ["session", "list", "--profile", "a", "--profile", "b", "--help"]),
    ("earlier accepted switch", ["session", "list", "--json", "--profile", "a", "--profile", "b", "--json=x"]),
    ("list preserves earlier value option", ["session", "list", "--query", "synthetic", "--profile", "a", "--profile", "b", "--unknown"]),
    ("current preserves earlier value option", ["session", "current", "--query", "synthetic", "--profile", "a", "--profile", "b", "--unknown"]),
    ("current cwd duplicate omits only cwd", ["session", "current", "--query", "synthetic", "--cwd", "/first", "--cwd", "/second", "--unknown"]),
)


def observe(binary, executable, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-session-duplicate-01662-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir(mode=0o700)
        result = subprocess.run(
            sandbox_command(binary, root, arguments, argv0=executable),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            check=False,
        )
        effects = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
        return result.returncode, result.stdout, result.stderr, effects


class SessionDuplicatePrecedence01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_first_error_matches_after_repeated_value_option(self):
        for name, arguments in CASES:
            with self.subTest(case=name):
                baseline = observe(ORACLE, "prodex", arguments)
                actual = observe(MODEX, "modex", arguments)
                mapped_stderr = baseline[2].replace(
                    b"Usage: prodex session", b"Usage: modex session"
                )
                self.assertEqual(baseline[0], 2)
                self.assertEqual(baseline[1], b"")
                self.assertEqual(baseline[3], ["home", "workspace"])
                self.assertEqual(
                    actual,
                    (baseline[0], baseline[1], mapped_stderr, baseline[3]),
                )


if __name__ == "__main__":
    unittest.main()
