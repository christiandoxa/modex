"""Run the synthetic local-compaction corpus against Prodex 0.166.2."""

import hashlib

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_local_compact_gap_01660 as historical


class LocalCompact01662Tests(historical.LocalCompactGap01660Tests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference
