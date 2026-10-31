"""Run the synthetic provider-shape corpus against Prodex 0.166.2."""

import hashlib

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_provider_passthrough_01660 as passthrough
import test_provider_shapes_01660 as historical


class ProviderShapes01662Tests(historical.ProviderShapes01660Tests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256
        cls.original_passthrough_reference = (passthrough.MODEX, passthrough.ORACLE, passthrough.ORACLE_SHA256)
        passthrough.MODEX, passthrough.ORACLE, passthrough.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference
        passthrough.MODEX, passthrough.ORACLE, passthrough.ORACLE_SHA256 = cls.original_passthrough_reference

    def _observe_stream(self, binary, body):
        upstream, responses = historical.observe_turns(
            binary,
            [{"model": "deepseek-chat", "input": "synthetic bounded stream"}],
            [{"status": 200, "content_type": "text/event-stream", "body": body,
              "chunked": True, "chunk_size": 8192}],
            latest_version="0.166.2",
        )
        self.assertEqual(len(upstream), 1)
        self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["status"], 200)
        return historical._stream_events(bytes.fromhex(responses[0]["body"]))

    def test_chunked_sse_can_exceed_four_mib_total_with_bounded_frames(self):
        limit = 4 * 1024 * 1024
        comments = (b":" + b"x" * (64 * 1024 - 1) + b"\n\n") * 65
        terminal = (
            b'data: {"id":"chatcmpl_synthetic","model":"deepseek-chat",'
            b'"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            b"data: [DONE]\n\n"
        )
        body = comments + terminal
        self.assertGreater(len(body), limit)
        results = []
        for binary in (ORACLE, MODEX):
            events = self._observe_stream(binary, body)
            self.assertEqual([event["type"] for event in events],
                             ["response.created", "response.completed"])
            self.assertEqual(events[-1]["response"]["output"], [])
            results.append((events[-1]["type"], events[-1]["response"]["output"]))
        self.assertEqual(results[0], results[1])

    def test_stream_line_and_event_limits_match_at_exact_and_over_boundaries(self):
        limit = 4 * 1024 * 1024
        terminal = (
            b'data: {"id":"chatcmpl_synthetic","model":"deepseek-chat",'
            b'"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            b"data: [DONE]\n\n"
        )
        line_at_limit = b":" + b"x" * (limit - 2) + b"\n"
        line_one_over = b":" + b"x" * (limit - 1) + b"\n"
        self.assertEqual((len(line_at_limit), len(line_one_over)), (limit, limit + 1))
        line_exact = line_at_limit + b"\n" + terminal
        line_over = line_one_over + b"\n" + terminal
        prefix = b'{"choices":'

        def event_body(second_value_bytes):
            suffix = b" " * (second_value_bytes - 3) + b"[]}"
            return (b"data: " + prefix + b"\n" + b"data: " + suffix + b"\n\n"
                    + b"data: [DONE]\n\n")

        event_exact = event_body(limit - len(prefix) - 2)
        event_over = event_body(limit - len(prefix) - 1)
        self.assertEqual((len(prefix) + 1 + (limit - len(prefix) - 2) + 1,
                          len(prefix) + 1 + (limit - len(prefix) - 1) + 1),
                         (limit, limit + 1))
        cases = (
            ("line exact", line_exact, None),
            ("line one byte over", line_over,
             "provider SSE line exceeded safe size limit (4194304)"),
            ("event exact", event_exact, None),
            ("event one byte over", event_over,
             "provider SSE event exceeded safe size limit (4194304)"),
        )
        for name, body, expected_error in cases:
            with self.subTest(case=name):
                self.assertGreater(len(body), limit)
                observed = []
                for binary in (ORACLE, MODEX):
                    events = self._observe_stream(binary, body)
                    if expected_error is None:
                        self.assertEqual([event["type"] for event in events],
                                         ["response.created", "response.completed"])
                        actual = None
                    else:
                        self.assertEqual([event["type"] for event in events], ["response.failed"])
                        actual = events[0]["response"]["error"]["message"]
                        self.assertEqual(actual, expected_error)
                    observed.append(actual)
                self.assertEqual(observed[0], observed[1])

    def test_malformed_stream_control_keeps_failure_and_known_oracle_difference_visible(self):
        passthrough.ProviderBufferedMetadata01660Tests.test_malformed_sse_oracle_gap_and_modex_failure_with_valid_controls(self)
