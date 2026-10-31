"""Process identity checks against the official 0.166.2 release."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00"


class ActiveBaseline01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")

    def test_version_identity_without_home_mutations(self):
        for binary, expected in ((ORACLE, b"prodex 0.166.2\n"), (MODEX, b"modex 0.1.0-dev\n")):
            for flag in ("--version", "-V"):
                with self.subTest(binary=str(binary), flag=flag), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    home = root / "home"
                    home.mkdir(mode=0o700)
                    result = subprocess.run(
                        [str(binary), flag], cwd=root, stdin=subprocess.DEVNULL,
                        env={"HOME": str(home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1"},
                        capture_output=True, timeout=10, check=False,
                    )
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b""))
                    self.assertEqual(list(home.iterdir()), [])
                    self.assertEqual(sorted(path.name for path in root.iterdir()), ["home"])


if __name__ == "__main__":
    unittest.main()
