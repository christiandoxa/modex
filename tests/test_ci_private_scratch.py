"""Clean up CI-private scratch even when directory setup fails partway through."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCRATCH_HELPER = ROOT / "scripts/ci/private-scratch.sh"


class PrivateScratchSetupTests(unittest.TestCase):
    def test_partial_directory_setup_failure_removes_private_root(self):
        with tempfile.TemporaryDirectory(prefix="modex-ci-scratch-failure-") as temporary:
            temp = Path(temporary)
            fake_bin = temp / "fake-bin"
            fake_bin.mkdir()
            root_file = temp / "scratch-root"
            fake_mkdir = fake_bin / "mkdir"
            fake_mkdir.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"${4%/home}\" >\"$MODEX_TEST_SCRATCH_ROOT_FILE\"\n"
                "/usr/bin/mkdir -m 700 -- \"$4\" || exit $?\n"
                "printf '%s\\n' \"$4\" >\"$MODEX_TEST_PARTIAL_DIR_FILE\"\n"
                "echo 'synthetic partial scratch setup failure' >&2\n"
                "exit 73\n",
                encoding="utf-8",
            )
            fake_mkdir.chmod(0o755)
            environment = {
                "PATH": os.pathsep.join((str(fake_bin), "/usr/bin", "/bin")),
                "HOME": str(temp / "home"),
                "TMPDIR": str(temp / "tmp"),
                "MODEX_PRIVATE_SCRATCH_HELPER": str(PRIVATE_SCRATCH_HELPER),
                "MODEX_TEST_SCRATCH_ROOT_FILE": str(root_file),
                "MODEX_TEST_PARTIAL_DIR_FILE": str(temp / "partial-dir"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", 'source "$MODEX_PRIVATE_SCRATCH_HELPER"'],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("synthetic partial scratch setup failure", result.stderr)
            scratch_root = Path(root_file.read_text(encoding="utf-8").strip())
            partial_dir = Path((temp / "partial-dir").read_text(encoding="utf-8").strip())
            self.assertEqual(partial_dir, scratch_root / "home")
            self.assertFalse(scratch_root.exists(), "partial CI scratch must be removed on setup failure")


if __name__ == "__main__":
    unittest.main()
