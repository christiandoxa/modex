"""Characterize clean-home info/status behavior against Prodex 0.166.2."""

import hashlib
import json
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
UNIMPLEMENTED = (
    b"Error: this Modex development build has not implemented the requested command\n"
)
INFO_HELP = ROOT / "docs/evidence/baseline-0.166.2/help/info.txt"
STATUS_HELP = ROOT / "docs/evidence/baseline-0.166.2/help/status.txt"


def observe(binary, executable, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-info-status-01662-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        (root / "workspace").mkdir(mode=0o700)
        result = subprocess.run(
            sandbox_command(
                binary,
                root,
                arguments,
                argv0=executable,
                environment={"TZ": "UTC"},
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=20,
            check=False,
        )
        effects = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path not in (home, root / "workspace")
        }
        return result, effects


class InfoStatusOffline01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.2 binary: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.2 oracle checksum is wrong")

    def test_help_controls_remain_read_only(self):
        for command, expected_path in (("info", INFO_HELP), ("status", STATUS_HELP)):
            expected = expected_path.read_bytes()
            modex_expected = expected.replace(
                b"prodex " + command.encode(), b"modex " + command.encode()
            )
            baseline, baseline_effects = observe(ORACLE, "prodex", [command, "--help"])
            modex, modex_effects = observe(MODEX, "modex", [command, "--help"])
            self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (0, expected, b""))
            self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, modex_expected, b""))
            self.assertEqual(baseline_effects, set())
            self.assertEqual(modex_effects, set())

    def test_clean_home_info_requires_live_dashboard_inputs(self):
        baseline, baseline_effects = observe(ORACLE, "prodex", ["info", "--json"])
        modex, modex_effects = observe(MODEX, "modex", ["info", "--json"])

        self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
        report = json.loads(baseline.stdout)
        self.assertEqual((report["version"], report["profile_count"], report["active_profile"]),
                         ("0.166.2", 0, None))
        self.assertEqual((report["providers"], report["provider_routes"]), ("none", "none"))
        self.assertEqual(report["runtime_policy"], None)
        self.assertEqual(report["secret_backend"]["backend"], "file")
        self.assertGreater(report["process_count"], 0)
        self.assertIn("Prodex processes", report["fields"])
        self.assertIn("Recent load", report["fields"])
        self.assertEqual(baseline_effects, {
            "home/.prodex",
            "home/.prodex/update-check.lock",
        })

        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (1, b"", UNIMPLEMENTED))
        self.assertEqual(modex_effects, set())

    def test_empty_pool_status_crash_is_not_reproduced(self):
        baseline, baseline_effects = observe(ORACLE, "prodex", ["status", "--once"])
        modex, modex_effects = observe(MODEX, "modex", ["status", "--once"])

        self.assertEqual(baseline.returncode, 101)
        self.assertIn(b"Mojo status runway renderer returned invalid output: InvalidInput", baseline.stderr)
        self.assertGreaterEqual(baseline_effects, {
            "home/.prodex",
            "home/.prodex/profile-lifecycle.json.lock",
            "home/.prodex/runtime-housekeeping.lock",
            "home/.prodex/update-check.lock",
        })
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (1, b"", UNIMPLEMENTED))
        self.assertEqual(modex_effects, set())


if __name__ == "__main__":
    unittest.main()
