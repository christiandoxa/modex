"""DeepSeek loopback base URL scheme comparison against Prodex 0.166.0."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class ProviderBaseUrlScheme01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (not ORACLE.is_file()
                or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_http_scheme_is_case_insensitive_for_loopback_upstreams(self):
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary,
                [{"model": "deepseek-chat", "input": "synthetic uppercase scheme"}],
                [buffered_reply()],
                latest_version="0.166.0",
                base_scheme="HTTP",
            )
            self.assertEqual([response["status"] for response in responses], [200])
            self.assertEqual(len(upstream), 1)
            self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
            self.assertEqual(upstream[0]["headers"]["authorization"],
                             "Bearer synthetic-provider-key")
            observations.append(upstream[0]["body"])

        self.assertEqual(observations[0], observations[1])

    def test_spaces_in_loopback_upstream_paths_are_percent_encoded(self):
        cases = (
            ("/v1/hello world", "/v1/hello%20world/chat/completions"),
            ("/v1/ spaced /path", "/v1/%20spaced%20/path/chat/completions"),
            ("/v1/é space/", "/v1/%C3%A9%20space/chat/completions"),
            ("/v1/already%20encoded", "/v1/already%20encoded/chat/completions"),
        )
        for base_path, expected_path in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(base_path=base_path, reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic path"}],
                        [buffered_reply()], base_path=base_path, latest_version="0.166.0",
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([request["path"] for request in upstream], [expected_path])
                    self.assertEqual(upstream[0]["headers"]["authorization"],
                                     "Bearer synthetic-provider-key")
