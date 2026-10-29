"""Compare file-backed plain runtime log parsing with pinned releases."""

import unittest

from test_log_stream import run_trace
import test_log_stream_escaped_event_01651_04392 as oracle_setup
from test_log_upstream_selection_01651_04392 import last


class PlainRuntimeLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        oracle_setup.LogStreamEscapedEventTests.setUpClass()
        cls.binaries = oracle_setup.LogStreamEscapedEventTests.binaries

    def test_plain_runtime_records_match_last(self):
        prefix = b"[2026-10-24T01:02:03Z] "
        lines = (
            b'request=7 upstream_payload profile="hello world" payload_b64=aGVsbG8=',
            b'empty= upstream_payload profile="quote \\\" and \\\\ slash" payload_b64=aGVsbG8=',
            b'upstream_payload profile="unterminated value payload_b64=aGVsbG8=',
            b'upstream_payload profile=one profile="two words" payload_b64=aGVsbG8=',
            b'request=7 token_usage profile="alpha beta" input_tokens=10 output_tokens=2',
            b'token_usage profile="escaped \\\"value\\\"" input_tokens=1 output_tokens=2',
            b'token_usage input_tokens=1 output_tokens=2 profile= first= unknown',
        )
        for mode in ("json", "plain"):
            for line in lines:
                with self.subTest(mode=mode, line=line):
                    results = [last(binary, mode, prefix + line + b"\n") for binary in self.binaries]
                    self.assertEqual(results[1:], results[:1] * 2)

    def test_plain_runtime_followers_match(self):
        prefix = b"[2026-10-24T01:02:03Z] "
        for mode in ("json", "plain"):
            for command in ("stream", "upstream"):
                line = prefix + b'request=7 upstream_payload profile="hello world" payload_b64=cGxhaW4tbWFya2Vy\n'
                if command == "stream":
                    line += prefix + b'source="fixture space" stream_payload stream="stream marker"\n'
                    line += prefix + b'profile="token profile" token_usage input_tokens=71 output_tokens=2\n'
                args = ["log", command] + (["--json"] if mode == "json" else [])
                def follow(follower):
                    follower.require_marker("Waiting for")
                    follower.require_quiet(2.2)
                    with follower.log.open("ab") as stream:
                        stream.write(line)
                    if command == "stream":
                        follower.require_markers(("plain-marker", "stream marker", "token profile"))
                    else:
                        follower.require_marker("plain-marker")
                traces = [run_trace(binary, mode, b"", b"", follow, arguments=args) for binary in self.binaries]
                with self.subTest(mode=mode, command=command):
                    self.assertEqual(traces[1:], traces[:1] * 2)


if __name__ == "__main__":
    unittest.main()
