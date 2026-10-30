"""Numeric loopback URL normalization against Prodex 0.166.0."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes


LOOPBACK_ALIASES = (
    "127.1",
    "127.0.1",
    "127.0x.1",
    "127.0.0.01",
    "127.000.000.001",
    "0177.0.0.1",
    "0x7f000001",
    "2130706433",
    "127.0.0.1.",
    "127%2e1",
    "127.0.0.%31",
    "%31%32%37.1",
    "0x7f0000%30%31",
    "%31%32%37%2e%30%2e%30%2e%31",
)


class ProviderBaseUrlAuthority01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (not ORACLE.is_file()
                or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def assert_canonical_host(self, request):
        host, port = request["headers"]["host"].rsplit(":", 1)
        self.assertEqual(host, "127.0.0.1")
        self.assertTrue(port.isdigit())
        self.assertEqual(port, str(int(port)))

    def test_numeric_loopback_authorities_match_active_provider_route(self):
        turn = {"model": "deepseek-chat", "input": "synthetic authority normalization"}
        for host in LOOPBACK_ALIASES:
            observations = []
            for binary in (ORACLE, MODEX):
                with self.subTest(host=host, reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary, [turn], [buffered_reply()], latest_version="0.166.0",
                        base_host=host, base_port_prefix="000",
                    )
                    self.assertEqual([row["status"] for row in responses], [200])
                    self.assertEqual(len(upstream), 1)
                    request = upstream[0]
                    self.assertEqual(request["path"], "/v1/chat/completions")
                    self.assert_canonical_host(request)
                    self.assertEqual(request["headers"]["authorization"],
                                     "Bearer " + SYNTHETIC_API_KEY)
                    observations.append((request["path"], request["body"]))
            self.assertEqual(observations[0], observations[1])

    def test_anthropic_messages_uses_canonical_authority(self):
        reply = {"status": 200, "content_type": "application/json", "body": json_bytes({
            "id": "msg_synthetic", "type": "message", "role": "assistant",
            "model": "deepseek-chat", "content": [{"type": "text", "text": "synthetic reply"}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1},
        })}
        turn = {"model": "deepseek-chat", "input": "synthetic search", "stream": False,
                "tools": [{"type": "web_search_preview"}]}
        for host in ("127.1", "127%2e1"):
            observations = []
            for binary in (ORACLE, MODEX):
                with self.subTest(host=host, reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary, [turn], [reply], latest_version="0.166.0", base_host=host,
                    )
                    self.assertEqual([row["status"] for row in responses], [200])
                    self.assertEqual(len(upstream), 1)
                    request = upstream[0]
                    self.assertEqual(request["path"], "/anthropic/v1/messages")
                    self.assert_canonical_host(request)
                    self.assertEqual(request["headers"]["x-api-key"], SYNTHETIC_API_KEY)
                    observations.append((request["path"], request["body"]))
            if len(observations) == 2:
                self.assertEqual(observations[0], observations[1])

    def test_nonloopback_and_ambiguous_authorities_fail_before_request(self):
        for host in (
            "localhost", "127.1.example", "127.0.0.08", "127..1", "127.1.2.3.4",
            "0x", "0x100000000", "126.0.0.1", "128.0.0.1", "8.8.8.8",
            "0x08080808", "167772161", "128%2e0%2e0%2e1", "127.0.0.1%3a80",
            "127%2f1", "127%5c1", "127%401", "127%252e1", "127%001", "127%0d1",
            "127%7f1", "127%ff1", "127%xx1",
        ):
            with self.subTest(host=host):
                try:
                    upstream, responses = observe_turns(
                        MODEX, [{"model": "deepseek-chat", "input": "synthetic rejected authority"}],
                        [buffered_reply()], latest_version="0.166.0", base_host=host,
                    )
                except AssertionError as error:
                    status, _, stderr, _, upstream = error.args[0]
                    self.assertNotEqual(status, 0)
                    self.assertTrue(b"loopback" in stderr.lower()
                                    or b"invalid --base-url" in stderr.lower())
                    self.assertEqual(upstream, [])
                else:
                    self.fail(f"Modex accepted {host}: {len(upstream)} requests, statuses "
                              f"{[row['status'] for row in responses]}")


if __name__ == "__main__":
    unittest.main()
