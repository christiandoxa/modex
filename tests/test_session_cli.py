"""Compare session help and argument errors with official-release fixtures."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE_SHA256, ROOT


class SessionCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_release_help_and_argument_diagnostics(self):
        captured = json.loads((ROOT / "docs/evidence/baseline/session-cli.json").read_text())
        self.assertEqual(captured["oracle_sha256"], ORACLE_SHA256)
        with tempfile.TemporaryDirectory(prefix="modex-session-cli-check-") as directory:
            for index, case in enumerate(captured["cases"]):
                with self.subTest(arguments=case["arguments"]):
                    root = Path(directory) / str(index)
                    root.mkdir()
                    (root / "home").mkdir(mode=0o700)
                    (root / "workspace").mkdir()
                    result = subprocess.run(sandbox_command(MODEX, root, case["arguments"], argv0="modex"),
                                            capture_output=True, timeout=10, check=False)
                    expected_stdout = case["stdout"].replace("prodex session", "modex session").encode()
                    expected_stderr = case["stderr"].replace("prodex session", "modex session").encode()
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (case["exit_code"], expected_stdout, expected_stderr))
                    if not case["new_paths"]:
                        created = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                                         if path not in (root / "home", root / "workspace"))
                        self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
