"""Compare Anthropic streams that complete without a web-search call."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_provider_tools_04392_characterization import _normalized_events


START = {"type": "message_start", "message": {
    "id": "msg_text", "role": "assistant", "model": "deepseek-chat",
    "usage": {"input_tokens": 3, "output_tokens": 0},
}}
TEXT_START = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
TEXT_DELTA = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Plain answer."}}
TEXT_STOP = {"type": "content_block_stop", "index": 0}
MESSAGE_DELTA = {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 5}}
NULL_DELTA = {"type": "message_delta", "delta": {"stop_reason": None, "stop_sequence": None}, "usage": {"output_tokens": 5}}
STOP = {"type": "message_stop"}
REQUEST = {"model": "deepseek-chat", "input": "synthetic query", "stream": True,
           "tools": [{"type": "web_search_preview"}]}


def stream(events):
    return b"".join(("data: " + json.dumps(event, separators=(",", ":")) + "\n\n").encode()
                    for event in events)


class AnthropicTextStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError("Build the Modex binary first")

    def test_text_and_empty_streams_match_release(self):
        cases = {
            "text": [START, TEXT_START, TEXT_DELTA, TEXT_STOP, MESSAGE_DELTA, STOP],
            "text without message delta": [START, TEXT_START, TEXT_DELTA, TEXT_STOP, STOP],
            "text with null reason": [START, TEXT_START, TEXT_DELTA, TEXT_STOP, NULL_DELTA, STOP],
            "empty text block": [START, TEXT_START, TEXT_STOP, MESSAGE_DELTA, STOP],
            "empty text block without delta": [START, TEXT_START, TEXT_STOP, STOP],
            "empty message": [START, MESSAGE_DELTA, STOP],
            "empty message with null reason": [START, NULL_DELTA, STOP],
            "empty message without delta": [START, STOP],
        }
        for name, events in cases.items():
            with self.subTest(case=name):
                reply = {"status": 200, "content_type": "text/event-stream", "body": stream(events)}
                reference_posts, reference = observe_turns(ORACLE, [REQUEST], [reply])
                actual_posts, actual = observe_turns(MODEX, [REQUEST], [reply])
                self.assertEqual([item["status"] for item in reference], [200])
                self.assertEqual([item["status"] for item in actual], [200])
                self.assertEqual(len(reference_posts), 1)
                self.assertEqual(len(actual_posts), 1)
                self.assertEqual(reference_posts[0]["path"], "/anthropic/v1/messages")
                self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
                self.assertEqual(actual_posts[0]["body"], reference_posts[0]["body"])
                expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
                observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
                self.assertEqual(expected[-1][0], "response.completed")
                self.assertEqual(observed, expected)

    def test_nonempty_block_start_is_ignored_like_release(self):
        initial = {"type": "content_block_start", "index": 0,
                   "content_block": {"type": "text", "text": "must not be dropped"}}
        reply = {"status": 200, "content_type": "text/event-stream",
                 "body": stream([START, initial, TEXT_DELTA, TEXT_STOP, MESSAGE_DELTA, STOP])}
        reference_posts, reference = observe_turns(ORACLE, [REQUEST], [reply])
        actual_posts, actual = observe_turns(MODEX, [REQUEST], [reply])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(expected[-1][0], "response.completed")
        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
