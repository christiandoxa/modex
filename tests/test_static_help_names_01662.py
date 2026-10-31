"""Compare static CLI help strings with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


CASES = (
    ("root", ["--help"]),
    ("root short", ["-h"]),
    ("root help command", ["help"]),
    ("session", ["session", "--help"]),
    ("session short", ["session", "-h"]),
    ("session help subcommand", ["session", "help"]),
    ("session help command", ["help", "session"]),
    ("doctor", ["doctor", "--help"]),
    ("doctor short", ["doctor", "-h"]),
    ("doctor help command", ["help", "doctor"]),
    ("quota", ["quota", "--help"]),
    ("quota short", ["quota", "-h"]),
    ("quota help command", ["help", "quota"]),
    ("super", ["super", "--help"]),
    ("super help command", ["help", "super"]),
    ("super alias", ["s", "--help"]),
    ("super alias help command", ["help", "s"]),
)


class StaticHelpNames01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_static_help_keeps_release_command_names_and_dynamic_usage(self):
        for name, arguments in CASES:
            for executable in ("modex", "custom-modex"):
                with self.subTest(route=name, executable=executable):
                    baseline, baseline_created = isolated_run(
                        ORACLE, arguments, executable, "01662-help-oracle"
                    )
                    modex, modex_created = isolated_run(
                        MODEX, arguments, executable, "01662-help-modex"
                    )
                    self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                    self.assertEqual(
                        (modex.returncode, modex.stdout, modex.stderr),
                        (baseline.returncode, baseline.stdout, baseline.stderr),
                    )
                    self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
