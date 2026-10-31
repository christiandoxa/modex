"""Compare empty split --cwd diagnostics with the pinned Prodex 0.166.2 CLI."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


CASES = (
    (
        "unknown option after accepted json",
        ["session", "current", "--json", "--cwd", "", "--unknown"],
        "error: unexpected argument '--unknown' found\n\n"
        "Usage: modex session current --json\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "unknown option after empty cwd",
        ["session", "current", "--cwd", "", "--unknown"],
        "error: unexpected argument '--unknown' found\n\n"
        "Usage: modex session current [OPTIONS]\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "unknown positional after empty cwd",
        ["session", "current", "--cwd", "", "extra"],
        "error: unexpected argument 'extra' found\n\n"
        "Usage: modex session current [OPTIONS]\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "malformed attached flag after empty cwd",
        ["session", "current", "--cwd", "", "--json=bad"],
        "error: unexpected value 'bad' for '--json' found; no more were expected\n\n"
        "Usage: modex session current --json\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "valid option keeps missing cwd error first",
        ["session", "current", "--cwd", "", "--json"],
        "error: a value is required for '--cwd <PATH>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "recognized invalid option keeps missing cwd error first",
        ["session", "current", "--cwd", "", "--limit=bad"],
        "error: a value is required for '--cwd <PATH>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "help keeps missing cwd error first",
        ["session", "current", "--cwd", "", "--help"],
        "error: a value is required for '--cwd <PATH>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "short help alias keeps missing cwd error first",
        ["session", "current", "--cwd", "", "-h=bad"],
        "error: a value is required for '--cwd <PATH>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "attached empty cwd stays an immediate error",
        ["session", "current", "--cwd=", "--unknown"],
        "error: a value is required for '--cwd <PATH>' but none was supplied\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "missing cwd value before unknown option stays unknown",
        ["session", "current", "--cwd", "--unknown"],
        "error: unexpected argument '--unknown' found\n\n"
        "Usage: modex session current [OPTIONS]\n\n"
        "For more information, try '--help'.\n",
    ),
    (
        "delimiter keeps following extra positional visible",
        ["session", "current", "--cwd", "", "--", "extra"],
        "error: unexpected argument 'extra' found\n\n"
        "Usage: modex session current [OPTIONS]\n\n"
        "For more information, try '--help'.\n",
    ),
)


def observe(binary, executable, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-session-cwd-01662-") as directory:
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
        return result, effects


class SessionCwdPrecedence01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_empty_split_cwd_preserves_clap_error_precedence(self):
        for name, arguments, expected_stderr in CASES:
            with self.subTest(case=name):
                baseline, baseline_effects = observe(ORACLE, "prodex", arguments)
                modex, modex_effects = observe(MODEX, "modex", arguments)
                mapped = baseline.stderr.replace(b"Usage: prodex session", b"Usage: modex session")
                self.assertEqual((baseline.returncode, baseline.stdout, mapped), (2, b"", expected_stderr.encode()))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, mapped))
                self.assertEqual(baseline_effects, ["home", "workspace"])
                self.assertEqual(modex_effects, baseline_effects)


if __name__ == "__main__":
    unittest.main()
