"""Pin the synthetic DeepSeek API-key 503 retry matrix to Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_policy_capacity_01660 as historical


class ProviderPolicyCapacity01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference

    def test_policy_capacity_503_rotates_api_key(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_policy_capacity_still_uses_the_status_based_api_key_retry_path(self)

    def test_single_key_forwards_policy_capacity_503(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_single_api_key_forwards_policy_503_unchanged(self)

    def test_combo_retries_model_before_rotating_api_key(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_combo_policy_503_retries_model_before_api_key(self)

    def test_unrelated_metadata_does_not_hide_server_overload_rotation(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_unrelated_metadata_does_not_suppress_server_overload_rotation(self)

    def test_anthropic_messages_503_rotates_api_key(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_anthropic_messages_policy_capacity_503_retries_next_api_key(self)

    def test_anthropic_messages_single_key_forwards_503(self):
        historical.PolicyCapacityUnavailable01660ApiKeyPathTests.test_anthropic_messages_single_api_key_forwards_policy_503_unchanged(self)


if __name__ == "__main__":
    unittest.main()
