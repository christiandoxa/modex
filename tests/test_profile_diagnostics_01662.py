"""Compare profile parser usage diagnostics with Prodex 0.166.2."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01662",
    os.environ.get(
        "PRODEX_ORACLE",
        Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
        / "oracles/0.166.2/prodex-x86_64-unknown-linux-gnu",
    ),
))
ORACLE_SHA256 = "e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00"


def observe(binary, arguments, executable):
    with tempfile.TemporaryDirectory(prefix="modex-profile-diagnostics-01662-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir(mode=0o700)
        result = subprocess.run(
            sandbox_command(binary, root, arguments, argv0=executable),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        effects = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
        return result, effects


class ProfileDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.2 binary: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.2 oracle checksum is wrong")

    def test_unexpected_flags_show_parsed_profile_arguments(self):
        cases = (
            ("add", "--activate", "--bad"),
            ("add", "name", "--activate", "--bad"),
            ("add", "--codex-home", "/synthetic/home", "--bad"),
            ("add", "--codex-home", "--bad"),
            ("export", "--profile", "synthetic", "--bad"),
            ("export", "--profile", "one", "-p", "two", "--bad"),
            ("export", "-p", "--bad"),
            ("import", "--name", "synthetic", "--bad"),
            ("import", "--name", "--bad"),
            ("import", "source", "--name", "synthetic", "--bad"),
            ("remove", "--all", "--bad"),
            ("remove", "name", "--delete-home", "--bad"),
            ("use", "--profile", "synthetic", "--bad"),
            ("use", "-p", "--bad"),
            # Extra positional values retain Clap's command-level usage.
            ("import", "source", "extra"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                command = ["profile", *arguments]
                baseline, baseline_effects = observe(ORACLE, command, "prodex")
                modex, modex_effects = observe(MODEX, command, "modex")
                mapped_stderr = baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ")
                self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (2, b"", mapped_stderr))
                self.assertEqual(baseline_effects, ["home", "workspace"])
                self.assertEqual(modex_effects, baseline_effects)


if __name__ == "__main__":
    unittest.main()
