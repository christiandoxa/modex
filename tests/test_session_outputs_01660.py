"""Selected session output comparisons against the active 0.166.0 release."""

import hashlib

import test_sessions
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


class SessionOutputs01660Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        return baseline
