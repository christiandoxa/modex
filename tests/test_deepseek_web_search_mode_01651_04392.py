"""Compare mode-only TOML configuration with both pinned release processes."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
import test_deepseek_web_search_mode_04392 as mode_tests
import test_provider_tools_04392_characterization as tool_tests

ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class DeepSeekWebSearchModeCrossReleaseTests(unittest.TestCase):
    binaries = (ORACLE_01651, ORACLE, MODEX)
    test_toml_mode_overrides_environment = mode_tests.DeepSeekWebSearchModeTests.test_toml_mode_overrides_environment
    test_invalid_toml_mode_fails_before_child_or_upstream = mode_tests.DeepSeekWebSearchModeTests.test_invalid_toml_mode_fails_before_child_or_upstream
    test_toml_strict_beta_and_search_settings_override_environment = tool_tests.ProviderTool04392CharacterizationTests.test_toml_strict_beta_and_search_settings_override_environment
    test_invalid_toml_strict_and_beta_settings_stop_before_launch = tool_tests.ProviderTool04392CharacterizationTests.test_invalid_toml_strict_and_beta_settings_stop_before_launch
    test_blank_or_nonstring_toml_beta_falls_back_to_environment = tool_tests.ProviderTool04392CharacterizationTests.test_blank_or_nonstring_toml_beta_falls_back_to_environment

    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build the Modex binary first")
