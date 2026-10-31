"""Pin selected provider relay routes and bodyless framing to Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
import test_provider_passthrough_01660 as historical


class ProviderRelay01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference

    def test_models_catalog_aliases_methods_queries_and_errors_match_active_release(self):
        historical.ProviderBufferedMetadata01660Tests.test_models_catalog_aliases_methods_queries_and_errors_match_active_release(self)

    def test_bodyless_sse_connection_header_preserves_observed_reuse(self):
        historical.ProviderBufferedMetadata01660Tests.test_bodyless_sse_connection_header_preserves_observed_reuse(self)

    def test_responses_empty_204_sse_and_bodyless_controls_match_active_wire(self):
        historical.ProviderBufferedMetadata01660Tests.test_responses_empty_204_sse_and_bodyless_controls_match_active_wire(self)

    def test_model_catalog_forwarding_preserves_custom_base_path_and_query(self):
        body = b'{"synthetic":true}'
        turn = [{"_method": "POST", "_path": "/models?trace=synthetic",
                 "_raw_body": body.decode("ascii")}]
        reply = [{"status": 200, "content_type": "application/json", "body": body}]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, turn, reply, base_path="/tenant/api/v9", latest_version="0.166.2",
            )
            self.assertEqual([(row["method"], row["path"], row["body"]) for row in upstream], [
                ("POST", "/tenant/api/v9/models?trace=synthetic", body),
            ])
            self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer synthetic-provider-key")
            self.assertEqual([(row["status"], bytes.fromhex(row["body"])) for row in responses], [(200, body)])
            observed.append((upstream[0]["path"], upstream[0]["body"], responses[0]["body"]))
        self.assertEqual(observed[0], observed[1])


if __name__ == "__main__":
    unittest.main()
