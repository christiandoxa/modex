"""Characterize active-release repair of an existing insecure app root."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


class SecureAppRootPermissions01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")

    def observe(self, binary, executable):
        with tempfile.TemporaryDirectory(prefix="modex-app-root-mode-01662-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            app_root = root / "home/.prodex"
            app_root.mkdir(mode=0o755)
            app_root.chmod(0o755)
            sentinel = app_root / "existing-marker"
            sentinel.write_bytes(b"preserve this file")

            result = subprocess.run(
                sandbox_command(binary, root, ["log", "last", "--json"], argv0=executable),
                capture_output=True,
                timeout=10,
                check=False,
            )
            return (
                result.returncode,
                result.stdout,
                result.stderr,
                app_root.stat().st_mode & 0o777,
                sentinel.read_bytes(),
                sorted(path.name for path in app_root.iterdir()),
            )

    def test_log_last_repairs_only_the_owned_root_mode_in_the_reference(self):
        self.assertEqual(
            self.observe(ORACLE, "prodex"),
            (0, b"", b"", 0o700, b"preserve this file", ["existing-marker"]),
        )
        # Modex keeps the root private by failing closed when stdlib chmod is unavailable.
        self.assertEqual(
            self.observe(MODEX, "modex"),
            (
                1,
                b"",
                b"Error: secure application-directory permission repair is not implemented\n",
                0o755,
                b"preserve this file",
                ["existing-marker"],
            ),
        )


if __name__ == "__main__":
    unittest.main()
