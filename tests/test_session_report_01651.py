"""Session-report production comparisons against the active 0.165.1 release."""

import hashlib
import os
from pathlib import Path

import test_sessions


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class SessionReport01651Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 release")
        if not test_sessions.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE
        )
        self.assertEqual(modex, baseline)
        return baseline
