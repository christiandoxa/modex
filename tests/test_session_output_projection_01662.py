"""Run the stateless session report suite against the active Prodex release."""

import hashlib
import unittest

import test_sessions
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256


class SessionOutputProjection01662Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")
        if test_sessions.MODEX != MODEX:
            raise AssertionError("the session report suite must use the configured Modex binary")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        return baseline


if __name__ == "__main__":
    unittest.main()
