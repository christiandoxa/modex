"""Supplementary 0.439.5 production regression for bounded SSE ID observation."""

import hashlib
import json
import unittest

from test_cli import (MODEX, HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)
from test_deepseek_continuation import buffered_reply, observe_turns


class RuntimeBindingEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("oracle does not match pinned Prodex 0.439.5")

    def test_large_valid_sse_event_is_bound_before_followup_dispatch(self):
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

        error = {"error": {"code": "bound_continuation_unavailable",
                           "message": "bound continuation provider is unavailable"}}
        self.assertEqual([response["status"] for response in oracle_responses], [200, 503])
        self.assertEqual(len(oracle_upstream), 1)
        self.assertEqual(json.loads(bytes.fromhex(oracle_responses[1]["body"])), error)
        self.assertEqual([response["status"] for response in modex_responses], [200, 503])
        self.assertEqual(len(modex_upstream), 1)
        self.assertEqual(json.loads(bytes.fromhex(modex_responses[1]["body"])), error)


if __name__ == "__main__":
    unittest.main()
