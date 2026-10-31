"""Compare root help routes with the frozen release in isolated homes."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def map_executable(output):
    return output.replace(b"Usage: prodex ", b"Usage: modex ", 1)


def isolated_run(binary, arguments, argv0, label):
    with tempfile.TemporaryDirectory(prefix="modex-root-help-" + label + "-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        result = subprocess.run(sandbox_command(binary, root, arguments, argv0=argv0),
                                capture_output=True, timeout=10, check=False)
        created = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                         if path not in (root / "home", root / "workspace"))
        return result, created


class RootHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_help_forms_match_release_and_do_not_mutate_home(self):
        for arguments in (["--help"], ["-h"], ["help"], ["--help", "ignored"], ["-h", "ignored"]):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(ORACLE, arguments, "prodex", "oracle")
                modex, modex_created = isolated_run(MODEX, arguments, "modex", "modex")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (0, map_executable(baseline.stdout), b""))
                self.assertEqual(baseline_created, [])
                self.assertEqual(modex_created, [])

    def test_custom_argv0_matches_release(self):
        baseline, baseline_created = isolated_run(ORACLE, ["--help"], "custom-modex", "oracle-custom")
        modex, modex_created = isolated_run(MODEX, ["--help"], "custom-modex", "modex-custom")
        self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                         (0, map_executable(baseline.stdout), b""))
        self.assertEqual(baseline_created, [])
        self.assertEqual(modex_created, [])


if __name__ == "__main__":
    unittest.main()
