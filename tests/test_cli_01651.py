"""Selected production CLI comparisons against the 0.165.1 release."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import MODEX, isolated_run as isolated_version
from test_root_help import isolated_run, map_executable


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class Release01651CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")

    def test_version_identity_and_no_mutations(self):
        for flag in ("--version", "-V"):
            for tail in ([], ["extra"], ["session", "list"], ["--unknown"], ["--help"], ["--"]):
                with self.subTest(flag=flag, tail=tail):
                    baseline, baseline_mutations = isolated_version(ORACLE, [flag, *tail])
                    modex, modex_mutations = isolated_version(MODEX, [flag, *tail])
                    self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), (0, b"prodex 0.165.1\n", b""))
                    self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, b"modex 0.1.0-dev\n", b""))
                    self.assertEqual((baseline_mutations, modex_mutations), ([], []))

    def test_help_forms_and_custom_executable(self):
        for arguments, argv0 in ((["--help"], "prodex"), (["-h"], "prodex"), (["help"], "prodex"),
                                 (["--help", "ignored"], "prodex"), (["-h", "ignored"], "prodex"),
                                 (["--help"], "custom-modex")):
            with self.subTest(arguments=arguments, argv0=argv0):
                baseline, baseline_created = isolated_run(ORACLE, arguments, argv0, "01651")
                modex_argv0 = "modex" if argv0 == "prodex" else argv0
                modex, modex_created = isolated_run(MODEX, arguments, modex_argv0, "modex")
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (0, map_executable(baseline.stdout), b""))
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
