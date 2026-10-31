"""Compare Anthropic streaming order with the active 0.166.2 release."""

import hashlib

from manual_real_codex_01660_route_comparison import require_isolated_environment
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_anthropic_stream_01660 as historical


class AnthropicStream01662Tests(historical.AnthropicStream01660Tests):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        original_observe_turns = historical.observe_turns
        cls.original_observe_turns = staticmethod(original_observe_turns)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

        def observe_active(*args, **kwargs):
            kwargs["latest_version"] = "0.166.2"
            return original_observe_turns(*args, **kwargs)

        historical.observe_turns = observe_active

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference
        historical.observe_turns = cls.original_observe_turns
