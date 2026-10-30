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
