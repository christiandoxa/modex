"""Compare token event selection with both pinned release processes."""

import unittest

import test_log_stream
import test_log_stream_escaped_event_01651_04392 as escaped_test
import test_log_upstream_selection_01651_04392 as upstream_test
from test_log_stream import run_trace, runtime_record


def token_record(event, profile, *, note=None, escaped=False):
    fields = {
        "input_tokens": "12",
        "output_tokens": "4",
        "profile": profile,
        "source": "synthetic",
        "transport": "synthetic",
    }
    if note is not None:
        fields["note"] = note
    line = runtime_record(event, fields, "2026-10-24T01:02:03Z")
    if escaped:
        line = line.replace(b'"event":"token_usage"', b'"event":"token\\u005fusage"')
    return line


class TokenEventSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        escaped_test.LogStreamEscapedEventTests.setUpClass()
        cls.binaries = escaped_test.LogStreamEscapedEventTests.binaries
        cls.oracle_binaries = cls.binaries[:2]

    def stream_trace(self, binary, mode, contents, scenario, *, arguments=None):
        previous_oracle = test_log_stream.ORACLE
        test_log_stream.ORACLE = (
            binary if binary in self.oracle_binaries else self.oracle_binaries[-1]
        )
        try:
            return run_trace(binary, mode, b"", contents, scenario, arguments=arguments)
        finally:
            test_log_stream.ORACLE = previous_oracle

    def test_snapshot_selection_matches_both_releases(self):
        rejected = token_record(
            "synthetic_event", "wrong-token-profile", note="token_usage",
        )
        accepted = token_record("token_usage", "escaped-token-profile", escaped=True)
        self.assertIn(b"token_usage", rejected)
        self.assertNotIn(b"token_usage", accepted)

        for mode in ("json", "plain"):
            for contents, profile, should_emit in (
                (rejected, b"wrong-token-profile", False),
                (accepted, b"escaped-token-profile", True),
            ):
                with self.subTest(mode=mode, profile=profile):
                    last_results = [
                        upstream_test.last(binary, mode, contents)
                        for binary in self.binaries
                    ]
                    self.assertEqual(last_results[1:], last_results[:1] * 2)
                    last_output = last_results[0][1] + last_results[0][2]
                    self.assertEqual(profile in last_output, should_emit)

                    def collect(follower):
                        follower.collect(0.2)

                    arguments = ["log", "stream"] + (["--json"] if mode == "json" else [])
                    traces = [
                        self.stream_trace(
                            binary, mode, contents, collect, arguments=arguments,
                        )
                        for binary in self.binaries
                    ]
                    self.assertEqual(traces[1:], traces[:1] * 2)
                    stream_output = traces[0]["stdout"] + traces[0]["stderr"]
                    self.assertEqual(profile in stream_output, should_emit)

    def test_follow_ignores_token_fields_on_other_events(self):
        rejected = token_record(
            "synthetic_event", "wrong-token-profile", note="token_usage",
        )
        accepted = token_record("token_usage", "escaped-token-profile", escaped=True)

        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                traces = []
                arguments = ["log", "stream"] + (["--json"] if mode == "json" else [])
                for binary in self.binaries:
                    def follow(follower):
                        follower.collect(0.2)
                        follower.require_quiet(2.2)
                        with follower.log.open("ab") as stream:
                            stream.write(rejected)
                        follower.collect(0.5)
                        with follower.log.open("ab") as stream:
                            stream.write(accepted)
                        follower.require_marker("escaped-token-profile")
                        follower.require_quiet(0.2)

                    traces.append(self.stream_trace(
                        binary, mode, b"invalid runtime line\n", follow,
                        arguments=arguments,
                    ))

                self.assertEqual(traces[1:], traces[:1] * 2)
                output = traces[0]["stdout"] + traces[0]["stderr"]
                self.assertIn(b"escaped-token-profile", output)
                token_event_marker = b'"event":"token_usage"' if mode == "json" else b"] TOKENS "
                self.assertEqual(output.count(token_event_marker), 1)


if __name__ == "__main__":
    unittest.main()
