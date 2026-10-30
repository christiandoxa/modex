"""Process checks against the official 0.166.0 active release."""

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
    / "oracles/0.166.0/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"


class ActiveBaseline01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_version_identity_without_state_changes(self):
        for binary, expected in ((ORACLE, b"prodex 0.166.0\n"), (MODEX, b"modex 0.1.0-dev\n")):
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

    def test_super_hook_initialize_uses_active_identity(self):
        from test_super_launch import SuperLaunchTests

        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                result, records, upstream, state = SuperLaunchTests().run_launch(
                    binary=binary, scenario="buffered",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(upstream), 1)
                self.assertEqual(state["leftovers"], [])
                identity = [record["params"]["clientInfo"] for record in records
                            if record.get("kind") == "request" and record.get("method") == "initialize"]
                self.assertEqual(identity, [{"name": "prodex-hook-trust", "version": "0.166.0"}])


if __name__ == "__main__":
    unittest.main()
