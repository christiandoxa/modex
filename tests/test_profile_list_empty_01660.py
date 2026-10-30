"""Characterize the active 0.166.0 empty-profile-list gap and side effects."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


UNIMPLEMENTED = b"Error: this Modex development build has not implemented the requested command\n"
REQUIRED_REFERENCE_FILES = {
    "home/.prodex/profile-lifecycle.json.lock",
    "home/.prodex/update-check.lock",
}
OPTIONAL_HOUSEKEEPING_EFFECTS = {
    "home/.prodex/runtime-housekeeping.last-run",
    "home/.prodex/runtime-housekeeping.lock",
}
ALLOWED_REFERENCE_EFFECTS = (
    REQUIRED_REFERENCE_FILES
    | OPTIONAL_HOUSEKEEPING_EFFECTS
    | {"home/.prodex"}
)


def observe(binary, argv0):
    temporary = tempfile.TemporaryDirectory(prefix="modex-profile-list-empty-01660-")
    root = Path(temporary.name)
    (root / "home").mkdir(mode=0o700)
    (root / "workspace").mkdir(mode=0o700)
    store_absent_before = not (root / "home/.prodex").exists()
    command = sandbox_command(binary, root, ["profile", "list"], argv0=argv0)
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    effects = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path not in (root / "home", root / "workspace")
    }
    return temporary, root, command, result, effects, store_absent_before


class ProfileListEmpty01660GapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use an absolute pinned 0.166.0 binary: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError(f"The 0.166.0 oracle checksum is wrong: {ORACLE}")

    def test_empty_store_panel_and_required_locks_expose_profile_list_gap(self):
        (
            reference_temporary, reference_root, reference_command,
            reference, reference_effects, reference_store_absent,
        ) = observe(ORACLE, "prodex")
        (
            modex_temporary, modex_root, modex_command,
            modex, modex_effects, modex_store_absent,
        ) = observe(MODEX, "modex")
        try:
            for command, root in (
                (reference_command, reference_root),
                (modex_command, modex_root),
            ):
                self.assertIn("--unshare-all", command)
                self.assertIn("--clearenv", command)
                self.assertIn("--tmpfs", command)
                home_setting = command.index("HOME", command.index("--setenv"))
                self.assertEqual(command[home_setting + 1], str(root / "home"))

            self.assertTrue(reference_store_absent)
            self.assertTrue(modex_store_absent)

            self.assertEqual((reference.returncode, reference.stderr), (0, b""))
            self.assertEqual(
                reference.stdout,
                b"[ Profiles ] =================================================================================================\n"
                b"Status:         No profiles configured.\n"
                b"Create:         prodex profile add <name>\n"
                b"Import:         prodex profile import-current\n"
                b"Import Copilot: prodex profile import copilot\n",
            )
            self.assertLessEqual(REQUIRED_REFERENCE_FILES, reference_effects)
            self.assertLessEqual(reference_effects, ALLOWED_REFERENCE_EFFECTS)

            self.assertEqual(
                (modex.returncode, modex.stdout, modex.stderr, modex_effects),
                (1, b"", UNIMPLEMENTED, set()),
            )
        finally:
            reference_temporary.cleanup()
            modex_temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
