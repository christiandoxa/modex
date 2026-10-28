"""Pinned-release checks for invalid UTF-8 during DeepSeek SSE precommit."""

import hashlib
import unittest

import test_cli
from test_deepseek_precommit_boundaries_04392 import (
    observe_gated,
    response_summary,
)
from test_local_rewrite import json_bytes


HEAD = (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
        b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")


def chunk(body):
    return f"{len(body):X}\r\n".encode() + body + b"\r\n"


def chat_event(content):
    event = {
        "id": "synthetic-invalid-utf8",
        "created": 42,
        "model": "deepseek-chat",
        "choices": [{
            "index": 0,
            "delta": {"content": content},
            "finish_reason": "stop",
        }],
    }
    return b"data: " + json_bytes(event) + b"\n\n"


class DeepSeekPrecommitInvalidUTF8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(test_cli.ORACLE.read_bytes()).hexdigest() != test_cli.ORACLE_SHA256:
            raise AssertionError("oracle does not match pinned Prodex 0.439.2")

    def assert_waits_for_later_progress(self, parts, gate_before):
        observations = []
        for binary in (test_cli.ORACLE, test_cli.MODEX):
            upstream, responses = observe_gated(
                binary,
                [(part, 0) for part in parts],
                gate_before,
                idle_timeout_ms=10000,
                lookahead_timeout_ms=10000,
                response_signal="headers",
                expect_signal_before_release=False,
            )
            self.assertEqual(len(upstream), 1)
            self.assertEqual(len(responses), 1)
            summary = response_summary(responses[0])
            self.assertEqual(summary[0], 200)
            self.assertEqual(summary[1][-1], (
                "response.failed", None,
                ("provider_stream_error", "stream did not contain valid UTF-8"),
            ))
            observations.append(summary)
        self.assertEqual(observations[0], observations[1])

    def test_invalid_comment_is_ignored_until_a_later_event(self):
        parts = [
            HEAD,
            chunk(b": comment contains invalid byte \xff\n\n"),
            chunk(chat_event("recovered after comment")),
            b"0\r\n\r\n",
        ]
        self.assert_waits_for_later_progress(parts, gate_before=2)

    def test_invalid_data_poisoning_ignores_later_data_until_blank(self):
        poisoned = (
            b"data: \xff\n"
            b'data: {"type":"response.output_text.delta","delta":"must-not-commit"}\n\n'
        )
        parts = [
            HEAD,
            chunk(poisoned),
            chunk(chat_event("recovered after poisoned event")),
            b"0\r\n\r\n",
        ]
        self.assert_waits_for_later_progress(parts, gate_before=2)

    def test_poisoned_event_resets_before_hold_and_next_progress_events(self):
        poisoned = b"data: \xff\n\n"
        hold = b'data: {"type":"response.created"}\n\n'
        parts = [
            HEAD,
            chunk(poisoned),
            chunk(hold),
            chunk(chat_event("recovered after the next event")),
            b"0\r\n\r\n",
        ]
        self.assert_waits_for_later_progress(parts, gate_before=3)


if __name__ == "__main__":
    unittest.main()
