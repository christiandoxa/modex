"""Compare the real Super hook preflight identity with Prodex 0.166.2."""

import hashlib
import os
from pathlib import Path
import unittest

from test_super_launch import run_private_launch


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00"


class HookIdentity01662Tests(unittest.TestCase):
    def test_hook_initialize_uses_the_active_release_identity(self):
        self.assertTrue(MODEX.is_file(), "Build Modex first")
        self.assertTrue(ORACLE.is_file(), "Set PRODEX_ORACLE to the 0.166.2 release")
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=binary.name):
                result, records, upstream, state = run_private_launch(binary, scenario="buffered")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((len(upstream), state["leftovers"]), (1, []))
                identities = [record["params"]["clientInfo"] for record in records
                              if record.get("kind") == "request" and record.get("method") == "initialize"]
                self.assertEqual(identities, [{"name": "prodex-hook-trust", "version": "0.166.2"}])


if __name__ == "__main__":
    unittest.main()
