"""Run the synthetic provider-shape corpus against Prodex 0.166.2."""

import hashlib
import json

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

    def test_chat_stream_fingerprint_ignores_empty_and_nonstring_updates(self):
        chunks = (
            (
                {"id": "chatcmpl_empty_fingerprint", "created": 42,
                 "system_fingerprint": "", "choices": []},
                {"choices": [{"index": 0, "delta": {"content": "synthetic"},
                               "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ),
            (
                {"id": "chatcmpl_fingerprint_reset", "created": 42,
                 "system_fingerprint": "fp_synthetic", "choices": []},
                {"system_fingerprint": "", "choices": [
                    {"index": 0, "delta": {"content": "synthetic"},
                     "finish_reason": None},
                ]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ),
            (
                {"id": "chatcmpl_fingerprint_set", "created": 42,
                 "system_fingerprint": "", "choices": []},
                {"system_fingerprint": "fp_later", "choices": [
                    {"index": 0, "delta": {"content": "synthetic"},
                     "finish_reason": None},
                ]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ),
            (
                {"id": "chatcmpl_fingerprint_nonstring", "created": 42,
                 "system_fingerprint": 7, "choices": []},
                {"system_fingerprint": ["ignored"], "choices": [
                    {"index": 0, "delta": {"content": "synthetic"},
                     "finish_reason": None},
                ]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ),
            (
                {"id": "chatcmpl_fingerprint_nonstring_update", "created": 42,
                 "system_fingerprint": "fp_synthetic", "choices": []},
                {"system_fingerprint": 7, "choices": [
                    {"index": 0, "delta": {"content": "synthetic"},
                     "finish_reason": None},
                ]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ),
        )
        turns = [
            {"model": "deepseek-chat", "input": "synthetic fingerprint", "stream": True}
            for _ in chunks
        ]
        replies = [historical._stream_reply(list(case)) for case in chunks]
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = historical.observe_turns(
                binary, turns, replies, latest_version="0.166.2",
            )
            self.assertEqual([row["status"] for row in responses], [200] * len(chunks))
            self.assertEqual(len(upstream), len(chunks))
            self.assertEqual([row["path"] for row in upstream],
                             ["/v1/chat/completions"] * len(chunks))
            events = [
                historical._stream_events(bytes.fromhex(row["body"]))
                for row in responses
            ]
            observations.append(events)
        self.assertEqual(observations[1], observations[0])
        metadata = [events[-1]["response"].get("metadata", {}).get("deepseek", {})
                    for events in observations[0]]
        self.assertNotIn("system_fingerprint", metadata[0])
        self.assertEqual(metadata[1]["system_fingerprint"], "fp_synthetic")
        self.assertEqual(metadata[2]["system_fingerprint"], "fp_later")
        self.assertNotIn("system_fingerprint", metadata[3])
        self.assertEqual(metadata[4]["system_fingerprint"], "fp_synthetic")

    def test_streamed_tool_namespace_checks_only_the_last_double_hyphen(self):
        cases = (
            ("last valid pair", "left--middle--local", "left--middle", "local"),
            ("invalid last pair", "left--middle--", None, "left--middle--"),
            ("empty namespace", "--local", None, "--local"),
            ("empty local name", "namespace--", None, "namespace--"),
            ("MCP fallback", "mcp__srv__foo--bar--", "mcp__srv", "foo--bar--"),
        )
        for case_name, name, namespace, local_name in cases:
            with self.subTest(case=case_name):
                tool_call = {
                    "id": "call_synthetic_namespace",
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
                buffered_reply = {
                    "id": "chatcmpl_synthetic_namespace",
                    "model": "deepseek-chat",
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "tool_calls": [tool_call]},
                        "finish_reason": "tool_calls",
                    }],
                }
                stream_reply = historical._stream_reply([
                    {
                        "id": "chatcmpl_synthetic_namespace",
                        "created": 42,
                        "model": "deepseek-chat",
                        "choices": [{
                            "index": 0,
                            "delta": {"tool_calls": [{
                                "index": 0,
                                "id": "call_synthetic_namespace",
                                "type": "function",
                                "function": {"name": name, "arguments": "{}"},
                            }]},
                            "finish_reason": None,
                        }],
                    },
                    {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
                ])
                observations = {}
                for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
                    observed = {}
                    for mode, turn, reply in (
                        ("buffered", {"model": "deepseek-chat", "input": "synthetic namespace"}, {
                            "status": 200,
                            "content_type": "application/json",
                            "body": historical.json_bytes(buffered_reply),
                        }),
                        ("streamed", {"model": "deepseek-chat", "input": "synthetic namespace", "stream": True}, stream_reply),
                    ):
                        upstream, responses = historical.observe_turns(
                            binary, [turn], [reply], latest_version="0.166.2",
                        )
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                        self.assertEqual(
                            upstream[0]["headers"].get("authorization"),
                            "Bearer " + passthrough.SYNTHETIC_API_KEY,
                        )
                        self.assertEqual([response["status"] for response in responses], [200])
                        body = bytes.fromhex(responses[0]["body"])
                        if mode == "buffered":
                            response = json.loads(body)
                            observed[mode] = response["output"]
                        else:
                            events = historical._stream_events(body)
                            items = [
                                (event["type"], event["item"])
                                for event in events
                                if event.get("type") in (
                                    "response.output_item.added",
                                    "response.output_item.done",
                                )
                            ]
                            self.assertEqual(
                                [event_type for event_type, _ in items],
                                ["response.output_item.added", "response.output_item.done"],
                            )
                            observed[mode] = items
                    observations[label] = observed
                self.assertEqual(observations["modex"]["buffered"], observations["oracle"]["buffered"])
                self.assertEqual(observations["modex"]["streamed"], observations["oracle"]["streamed"])
                expected_stream_item = {
                    "call_id": "call_synthetic_namespace",
                    "name": local_name,
                    "type": "function_call",
                }
                if namespace is not None:
                    expected_stream_item["namespace"] = namespace
                self.assertEqual(observations["oracle"]["streamed"][0][1], expected_stream_item)
                self.assertEqual(
                    observations["oracle"]["streamed"][1][1],
                    {**expected_stream_item, "arguments": "{}"},
                )

    def test_anthropic_buffered_tool_namespace_matches_active_release(self):
        cases = (
            ("invalid final pair", "a--b--", None, "a--b--"),
            ("MCP fallback", "mcp__srv__foo--bar--", "mcp__srv", "foo--bar--"),
            ("valid split", "left--middle--local", "left--middle", "local"),
            ("whitespace valid split", " left -- right ", " left ", " right "),
            ("whitespace invalid pair", "left--middle-- ", None, "left--middle-- "),
            ("whitespace MCP fallback", "mcp__srv__foo--bar-- ", "mcp__srv", "foo--bar-- "),
        )
        request = {
            "model": "deepseek-chat",
            "input": "synthetic Anthropic namespace probe",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        for case_name, name, namespace, local_name in cases:
            with self.subTest(case=case_name):
                reply = {
                    "status": 200,
                    "content_type": "application/json",
                    "body": historical.json_bytes({
                        "id": "msg_synthetic_namespace",
                        "type": "message",
                        "role": "assistant",
                        "content": [{
                            "type": "tool_use",
                            "id": "toolu_synthetic_namespace",
                            "name": name,
                            "input": {},
                        }],
                        "model": "claude-test",
                        "stop_reason": "tool_use",
                        "usage": {"input_tokens": 2, "output_tokens": 1},
                    }),
                }
                observations = {}
                for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
                    upstream, responses = historical.observe_turns(
                        binary, [request], [reply], latest_version="0.166.2",
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(
                        upstream[0]["headers"].get("x-api-key"),
                        passthrough.SYNTHETIC_API_KEY,
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    body = json.loads(bytes.fromhex(responses[0]["body"]))
                    output = [item for item in body["output"] if item.get("type") == "function_call"]
                    self.assertEqual(len(output), 1)
                    expected = {
                        "type": "function_call",
                        "call_id": "toolu_synthetic_namespace",
                        "name": local_name,
                        "arguments": "{}",
                    }
                    if namespace is not None:
                        expected["namespace"] = namespace
                    self.assertEqual(output[0], expected)
                    observations[label] = (upstream[0]["body"], output[0])
                self.assertEqual(observations["modex"], observations["oracle"])

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
