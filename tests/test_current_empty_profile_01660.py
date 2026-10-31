"""Compare the no-active-profile inspection slice with Prodex 0.166.0."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


EXPECTED = (
    b"[ Active Profile ] ===========================================================================================\n"
    b"Status:    No active profile.\n"
)
UNIMPLEMENTED = b"Error: this Modex development build has not implemented the requested command\n"
REQUIRED_ORACLE_EFFECTS = {
    "home/.prodex/profile-lifecycle.json.lock",
    "home/.prodex/update-check.lock",
}
OPTIONAL_ORACLE_EFFECTS = {
    "home/.prodex/runtime-housekeeping.last-run",
    "home/.prodex/runtime-housekeeping.lock",
}


def run(binary, root, argv0, environment=None, arguments=("current",)):
    return subprocess.run(
        sandbox_command(
            binary, root, list(arguments), argv0=argv0, environment=environment,
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )


def effects(root):
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path not in (root / "home", root / "workspace")
    }


class CurrentEmptyProfile01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.0 oracle: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.0 oracle checksum is wrong")

    def test_absent_profile_root_matches_oracle_without_modex_state_writes(self):
        observations = []
        for binary, argv0 in ((ORACLE, "custom-prodex"), (MODEX, "custom-modex")):
            with tempfile.TemporaryDirectory(prefix="modex-current-empty-01660-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir(mode=0o700)
                result = run(binary, root, argv0)
                observed = effects(root)
                observations.append((result.returncode, result.stdout, result.stderr))
                if binary == ORACLE:
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, EXPECTED, b""))
                    self.assertTrue(REQUIRED_ORACLE_EFFECTS <= observed)
                    self.assertLessEqual(observed, REQUIRED_ORACLE_EFFECTS | OPTIONAL_ORACLE_EFFECTS | {"home/.prodex"})
                else:
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, EXPECTED, b""))
                    self.assertEqual(observed, set())
        self.assertEqual(observations[0], observations[1])

    def test_custom_argv0_is_preserved_by_current_parser(self):
        observations = []
        for binary, argv0 in ((ORACLE, "custom-prodex"), (MODEX, "custom-modex")):
            with tempfile.TemporaryDirectory(prefix="modex-current-argv0-01660-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir(mode=0o700)
                result = run(binary, root, argv0, arguments=("current", "--unknown"))
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertIn(f"Usage: {argv0} current".encode(), result.stderr)
                self.assertEqual(effects(root), set())
                observations.append(result.stderr)
        self.assertEqual(
            observations[1], observations[0].replace(b"custom-prodex", b"custom-modex")
        )

    def test_custom_root_existing_dangling_and_unwritable_parent_stay_fail_closed(self):
        for kind in ("existing", "dangling", "unwritable-parent"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(
                prefix="modex-current-root-01660-"
            ) as directory:
                root = Path(directory)
                home = root / "home"
                home.mkdir(mode=0o700)
                (root / "workspace").mkdir(mode=0o700)
                configured_root = home / ".prodex"
                if kind == "existing":
                    configured_root.mkdir(mode=0o700)
                    state = configured_root / "profile-lifecycle.json"
                    state.write_bytes(b'{"active_profile":"synthetic","profiles":[]}\n')
                    before = state.read_bytes()
                    expected_effects = {
                        "home/.prodex",
                        "home/.prodex/profile-lifecycle.json",
                    }
                elif kind == "dangling":
                    configured_root.symlink_to("missing-prodex-root")
                    expected_effects = {"home/.prodex"}
                else:
                    home.chmod(0o555)
                    expected_effects = set()
                try:
                    result = run(
                        MODEX, root, "modex",
                        environment={"PRODEX_HOME": str(configured_root)},
                    )
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b"", UNIMPLEMENTED))
                    self.assertEqual(effects(root), expected_effects)
                    if kind == "existing":
                        self.assertEqual(state.read_bytes(), before)
                finally:
                    home.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
