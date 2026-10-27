"""Pinned-oracle coverage for runtime continuation ID observation limits."""

import hashlib
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class RuntimeBindingEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("oracle does not match pinned Prodex 0.439.5")

    def test_large_valid_sse_event_exposes_bounded_observer_gap(self):
        response_id = "synthetic-large-response"
        data = (
            b'{"response":{"id":"' + response_id.encode() + b'"},"filler":"'
            + b"x" * (4 * 1024 * 1024)
            + b'"}'
        )
        first_response = {
            "status": 200,
            "content_type": "text/event-stream",
            "body": b"event: response.completed\ndata: " + data + b"\n\n",
            "chunked": True,
            "chunk_size": 8191,
        }
        turns = [
            {
                "model": "deepseek-chat",
                "input": "first synthetic turn",
                "_path": "/v1/chat/completions",
                "messages": [],
                "stream": True,
            },
            {"model": "deepseek-chat", "input": "follow the response", "use_previous": True},
        ]
        oracle_upstream, oracle_responses = observe_turns(
            ORACLE, turns, [first_response, buffered_reply(1, created=43)]
        )
        modex_upstream, modex_responses = observe_turns(
            MODEX, turns, [first_response, buffered_reply(1, created=43)]
        )

        self.assertEqual([response["status"] for response in oracle_responses], [200, 503])
        self.assertEqual(len(oracle_upstream), 1)
        self.assertEqual([response["status"] for response in modex_responses], [200, 200])
        self.assertEqual(len(modex_upstream), 2)


if __name__ == "__main__":
    unittest.main()
