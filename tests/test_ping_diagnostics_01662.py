"""Compare offline ping group diagnostics with the 0.166.2 release."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class PingDiagnostics01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_missing_command_and_unknown_flags_match_without_mutation(self):
        for arguments in (("ping",), ("ping", "--"), ("ping", "--bogus"),
                          ("ping", "--bogus=value"), ("ping", "-xyz")):
            with self.subTest(arguments=arguments):
                reference, reference_changes = isolated_run(ORACLE, list(arguments), "modex", "ping-oracle")
                actual, actual_changes = isolated_run(MODEX, list(arguments), "modex", "ping-modex")
                self.assertEqual((reference.returncode, reference.stdout), (2, b""))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                 (reference.returncode, reference.stdout, reference.stderr))
                self.assertEqual((reference_changes, actual_changes), ([], []))


if __name__ == "__main__":
    unittest.main()
