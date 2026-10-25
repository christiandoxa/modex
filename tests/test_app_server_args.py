"""Compare native projection with actual frozen child argv captures."""

import json
import subprocess
import unittest

from capture_app_server_args import FIXTURES
from test_cli import ROOT


class AppServerArgumentTests(unittest.TestCase):
    def test_actual_runtime_arguments_project_to_captured_preflight_arguments(self):
        catalog = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
        for case in catalog["cases"]:
            with self.subTest(case=case["name"]):
                result = subprocess.run([str(ROOT / "build/tests/app_server_args_driver"), "1", *case["runtime_args"]], capture_output=True, timeout=5, check=False)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(json.loads(result.stdout), case["app_server_args"])


if __name__ == "__main__":
    unittest.main()
