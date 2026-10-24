"""Run the explicit-environment spawn foundation without implementation helpers."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_cli import ROOT


class ProcessRuntimeTests(unittest.TestCase):
    def test_explicit_environment_spawn_with_only_mojo_and_platform_libraries(self):
        with tempfile.TemporaryDirectory(prefix="modex-process-runtime-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            child = root / "synthetic-child"
            shutil.copyfile(ROOT / "build/tests/process_child", child)
            child.chmod(0o700)
            command = sandbox_command(ROOT / "build/tests/test_process_spawn", root, [str(child)])
            result = subprocess.run(command, capture_output=True, timeout=10, check=False)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (0, b"synthetic-child-ok\nexplicit environment spawn checks: PASS\n", b""))


if __name__ == "__main__":
    unittest.main()
