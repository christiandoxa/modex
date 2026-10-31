"""Profile-bound session listing against the active Prodex release."""

import hashlib

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_cli
import test_session_profile_04392 as historical


class SessionProfile01662Tests(historical.SessionProfile04392Tests):
    @classmethod
    def release_oracles(cls):
        return (ORACLE,)

    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file() or test_cli.MODEX != MODEX:
            raise AssertionError("Build the configured production Modex binary first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")


if __name__ == "__main__":
    import unittest

    unittest.main()
