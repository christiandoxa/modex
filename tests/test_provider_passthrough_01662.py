"""Qualify synthetic provider passthrough behavior against Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_provider_passthrough_01660 as historical


PARITY_METHODS = frozenset({
    "test_503_passthrough_header_names_match_active_release",
    "test_bodyless_json_and_sse_205_framing_controls_match_active_release",
    "test_bodyless_sse_connection_header_preserves_observed_reuse",
    "test_buffered_passthrough_metadata_matches_active_release",
    "test_connect_routes_use_upstream_authority_form",
    "test_connect_success_and_upgrade_responses_do_not_establish_tunnels",
    "test_duplicate_content_type_first_value_controls_sse_classification",
    "test_duplicate_content_type_uses_last_value_and_keeps_header_order",
    "test_empty_location_redirect_loop_keeps_the_existing_cap",
    "test_empty_location_redirects_reuse_current_url_only_when_header_is_present",
    "test_models_catalog_aliases_methods_queries_and_errors_match_active_release",
    "test_models_route_keeps_modex_local_client_authentication",
    "test_raw_connect_tunnel_bytes_are_discarded_and_upstream_fd_closes",
    "test_redirect_authorities_canonicalize_same_loopback_endpoint_only",
    "test_redirect_path_query_spaces_encode_without_weakening_authority_guards",
    "test_redirect_query_apostrophe_encoding_preserves_path_and_escapes",
    "test_responses_empty_204_sse_and_bodyless_controls_match_active_wire",
    "test_root_provider_aliases_match_active_route_plan",
    "test_root_responses_alias_keeps_client_auth_and_continuation_ownership",
    "test_streamed_passthrough_metadata_matches_active_release",
})
EXCLUDED_FROM_PARITY = frozenset({
    # The active provider-shapes suite checks this intentional safety divergence.
    "test_malformed_sse_oracle_gap_and_modex_failure_with_valid_controls",
})


def _flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _flatten(test)
        else:
            yield test


def load_tests(loader, tests, pattern):
    discovered = tuple(_flatten(tests))
    names = {test._testMethodName for test in discovered}
    expected = PARITY_METHODS | EXCLUDED_FROM_PARITY
    if names != expected or len(discovered) != len(expected):
        raise AssertionError(f"provider passthrough corpus changed: {sorted(names ^ expected)}")
    return unittest.TestSuite(
        test for test in discovered if test._testMethodName in PARITY_METHODS
    )


class ProviderPassthrough01662Tests(historical.ProviderBufferedMetadata01660Tests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256
        cls.original_test_version = historical.TEST_VERSION
        historical.TEST_VERSION = "0.166.2"

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference
        historical.TEST_VERSION = cls.original_test_version


if __name__ == "__main__":
    unittest.main()
