"""Capture the 0.166.2 empty profile list result on an existing app root."""

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
EMPTY_PANEL = (
    b"[ Profiles ] " + b"=" * 97 + b"\n"
    b"Status:         No profiles configured.\n"
    b"Create:         prodex profile add <name>\n"
    b"Import:         prodex profile import-current\n"
    b"Import Copilot: prodex profile import copilot\n"
)
UNIMPLEMENTED = (
    b"Error: this Modex development build has not implemented the requested command\n"
)
REQUIRED_REFERENCE_EFFECTS = {
    "home/.prodex",
    "home/.prodex/profile-lifecycle.json.lock",
    "home/.prodex/update-check.lock",
}
OPTIONAL_HOUSEKEEPING_EFFECTS = {
    "home/.prodex/runtime-housekeeping.last-run",
    "home/.prodex/runtime-housekeeping.lock",
}


def observe(binary, executable):
    with tempfile.TemporaryDirectory(prefix="modex-profile-existing-empty-01662-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        app_root = home / ".prodex"
        app_root.mkdir(mode=0o700)
        if list(app_root.iterdir()):
            raise AssertionError("the synthetic Prodex root must start empty")

        result = subprocess.run(
            sandbox_command(
                binary,
                root,
                ["profile", "list"],
                argv0=executable,
                environment={"PRODEX_HOME": str(app_root)},
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        effects = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path not in (home, workspace)
        }
        return result, effects


class ProfileListExistingEmptyRoot01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.2 binary: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.2 oracle checksum is wrong")

    def test_release_panel_and_lifecycle_lock_effects_mismatch(self):
        baseline, baseline_effects = observe(ORACLE, "prodex")
        modex, modex_effects = observe(MODEX, "modex")

        self.assertEqual(
            (baseline.returncode, baseline.stdout, baseline.stderr),
            (0, EMPTY_PANEL, b""),
        )
        self.assertTrue(REQUIRED_REFERENCE_EFFECTS <= baseline_effects)
        self.assertLessEqual(
            baseline_effects,
            REQUIRED_REFERENCE_EFFECTS | OPTIONAL_HOUSEKEEPING_EFFECTS,
        )
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (1, b"", UNIMPLEMENTED))
        self.assertEqual(modex_effects, {"home/.prodex"})


if __name__ == "__main__":
    unittest.main()
