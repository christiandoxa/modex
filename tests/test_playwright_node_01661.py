"""Compare Super's Playwright Node preflight with Prodex 0.166.1."""

import hashlib
import os
from pathlib import Path
import unittest

from test_super_dry_run_01651 import OPTIONAL_TOOL_FIXTURE, run_dry_run, write_optional_tool


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "d9c3232ca504548c473ad06e4be001bb307256e00d35f888676e9512c62e4c3a"


class PlaywrightNode01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file() or not OPTIONAL_TOOL_FIXTURE.is_file():
            raise AssertionError("Build Modex and the native optional-tool fixture first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.1 Linux release")

    def test_node_version_is_checked_before_the_package_probe(self):
        cases = (
            ("v17.9.1", True, "skipped (Node.js 18+ is required; found v17.9.1)", False),
            ("v17.9.1", False, "skipped (Node.js 18+ is required; found v17.9.1)", False),
            ("nonsense", True, "skipped (Node.js 18+ is required; found nonsense)", False),
            ("empty", True, "skipped (Node.js 18+ is required; found available)", False),
            ("exit:7", True, "skipped (Node.js version check exited with exit status: 7)", False),
            ("invalid-stdout", True, "skipped (probe stdout was not UTF-8)", False),
            ("invalid-stderr", True, "skipped (probe stderr was not UTF-8)", False),
            ("v18.0.0", False, "skipped (npx was not found on PATH)", False),
            ("v18.0.0", True, "resolved (activation deferred until launch)", True),
            ("stderr:v20.0.0", True, "resolved (activation deferred until launch)", True),
        )
        for version, with_npx, expected, invoked in cases:
            for binary, argv0 in ((ORACLE, "prodex"), (MODEX, "modex")):
                with self.subTest(version=version, with_npx=with_npx, binary=argv0):
                    def prepare(root):
                        write_optional_tool(root / "bin/node")
                        if with_npx:
                            write_optional_tool(root / "bin/npx")
                        (root / "home/.rtk-version-fixture").write_text(version)
                        (root / "home/.npx-version-fixture").write_text("0.0.83")
                        (root / "home/.npx-probe-marker-enabled").touch()

                    result, before, after = run_dry_run(
                        binary, argv0, prepare, extra_binaries=(OPTIONAL_TOOL_FIXTURE,),
                    )
                    self.assertEqual((result.returncode, result.stderr), (0, b""))
                    rows = [line.strip() for line in result.stdout.decode().splitlines()
                            if "playwright-mcp:" in line]
                    self.assertEqual(rows, ["playwright-mcp: " + expected])
                    marker = after.pop("home/.npx-probe-invoked", None)
                    self.assertEqual(marker is not None, invoked)
                    self.assertEqual(after, before)

    def test_node_diagnostic_redacts_secrets_and_escapes_terminal_controls(self):
        def prepare(root):
            write_optional_tool(root / "bin/node")
            write_optional_tool(root / "bin/npx")
            (root / "home/.rtk-version-fixture").write_text("Bearer synthetic-secret-token\x1b[31m")
            (root / "home/.npx-probe-marker-enabled").touch()

        result, before, after = run_dry_run(
            MODEX, "modex", prepare, extra_binaries=(OPTIONAL_TOOL_FIXTURE,),
        )
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertNotIn(b"synthetic-secret-token", result.stdout)
        self.assertNotIn(b"\x1b", result.stdout)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
