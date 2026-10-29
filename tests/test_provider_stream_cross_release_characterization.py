"""Synthetic provider stream comparisons across pinned Prodex releases."""

import copy
import hashlib
import json
import os
from pathlib import Path
import uuid
import unittest

from test_cli import MODEX
from test_provider_tools_04392_characterization import _normalized_events, _run


ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


def _require_oracle(environment_name, release, expected_sha256):
    value = os.environ.get(environment_name)
    if value is None:
        oracle = Path.home() / ".cache/modex/oracles" / release / "prodex-x86_64-unknown-linux-gnu"
    elif value:
        oracle = Path(value)
    else:
        raise AssertionError(f"{environment_name} must identify its pinned Prodex release")
    if not oracle.is_file():
        raise AssertionError(f"{environment_name} is missing: {oracle}")
    if hashlib.sha256(oracle.read_bytes()).hexdigest() != expected_sha256:
        raise AssertionError(f"{environment_name} does not match its pinned Prodex release")
    return oracle


def require_oracle_01651():
    return _require_oracle("PRODEX_ORACLE_01651", "0.165.1", ORACLE_01651_SHA256)


def require_oracle_04392():
    return _require_oracle("PRODEX_ORACLE_04392", "0.439.2", ORACLE_04392_SHA256)


def _normalize_fallback_tool_call_ids(events):
    normalized = copy.deepcopy(events)
    generated_ids = set()
    for event_name, payload in normalized:
        if event_name != "response.output_item.added":
            continue
        item = payload.get("item", {})
        call_id = item.get("call_id") if item.get("type") == "function_call" else None
        if not isinstance(call_id, str) or not call_id.startswith("call_deepseek_"):
            continue
        try:
            parsed = uuid.UUID(call_id.removeprefix("call_deepseek_"))
        except ValueError as error:
            raise AssertionError("fallback tool call ID is not a UUID") from error
        if parsed.version != 7:
            raise AssertionError("fallback tool call ID is not UUIDv7")
        generated_ids.add(call_id)
    if not generated_ids:
        return normalized

    def replace(value):
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, tuple):
            return tuple(replace(item) for item in value)
        if isinstance(value, dict):
            return {
                key: "<generated-call-id>"
                if key == "call_id" and isinstance(item, str) and item in generated_ids
                else replace(item)
                for key, item in value.items()
            }
        return value

    return replace(normalized)


class ProviderStreamCrossReleaseCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle_01651 = require_oracle_01651()
        cls.oracle_04392 = require_oracle_04392()
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_anthropic_tool_use_index_and_stop_boundaries(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = (
            "anthropic-tool-use-duplicate-index",
            "anthropic-tool-use-missing-stop",
            "anthropic-tool-use-orphan-delta",
            "anthropic-tool-use-mismatched-index",
            "anthropic-tool-use-duplicate-stop",
            "anthropic-tool-use-orphan-stop",
            "anthropic-tool-use-mismatched-stop",
            "anthropic-tool-use-delta-after-stop",
            "anthropic-tool-use-reopened-index",
        )
        for scenario in cases:
            with self.subTest(scenario=scenario):
                observations = [
                    _run(binary, request, scenario=scenario)
                    for binary in (self.oracle_01651, self.oracle_04392, MODEX)
                ]
                for observed in observations:
                    self.assertEqual((observed["exit_code"], observed["status"]), (0, 200))
                    self.assertEqual(len(observed["upstream"]), 1)
                    self.assertEqual(observed["upstream"][0]["path"], observations[0]["upstream"][0]["path"])
                    self.assertEqual(observed["upstream"][0]["body"], observations[0]["upstream"][0]["body"])
                    self.assertEqual(observed["state"]["leftovers"], [])
                reference_events = _normalize_fallback_tool_call_ids(
                    _normalized_events(observations[0]["response_body"])
                )
                for observed in observations[1:]:
                    events = _normalize_fallback_tool_call_ids(_normalized_events(observed["response_body"]))
                    self.assertEqual(events, reference_events)

    def test_anthropic_message_delta_before_message_start_is_ignored(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        events = [
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 5},
            },
            {"type": "message_stop"},
        ]
        observations = [
            _run(binary, request, scenario="anthropic-custom-events", anthropic_events=events)
            for binary in (self.oracle_01651, self.oracle_04392, MODEX)
        ]
        for observed in observations:
            self.assertEqual((observed["exit_code"], observed["status"]), (0, 200))
            self.assertEqual(len(observed["upstream"]), 1)
            self.assertEqual(observed["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertEqual(observed["state"]["leftovers"], [])

        reference_events = _normalized_events(observations[0]["response_body"])
        self.assertEqual([name for name, _ in reference_events], ["response.completed"])
        self.assertNotIn("metadata", reference_events[0][1]["response"])
        self.assertNotIn("usage", reference_events[0][1]["response"])
        for observed in observations[1:]:
            self.assertEqual(_normalized_events(observed["response_body"]), reference_events)
            self.assertEqual(observed["upstream"][0]["body"], observations[0]["upstream"][0]["body"])

    def test_anthropic_out_of_order_stream_matrix_and_start_metadata(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        start = lambda ident, tokens: {
            "type": "message_start",
            "message": {
                "id": ident,
                "role": "assistant",
                "model": "model-" + ident,
                "usage": {"input_tokens": tokens, "output_tokens": 0},
            },
        }
        text_block = {"type": "content_block_start", "index": 0,
                      "content_block": {"type": "text", "text": ""}}
        text_delta = {"type": "content_block_delta", "index": 0,
                      "delta": {"type": "text_delta", "text": "synthetic delta"}}
        message_delta = {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        }
        message_stop = {"type": "message_stop"}
        cases = (
            (
                "canonical control",
                [start("msg_canonical", 3), text_block, text_delta, message_delta, message_stop],
                None,
            ),
            (
                "pre-start text delta without message_start",
                [text_block, text_delta, message_delta, message_stop],
                None,
            ),
            (
                "pre-start function arguments fail without a name",
                [
                    {"type": "content_block_start", "index": 0, "content_block": {
                        "type": "tool_use", "id": "toolu_pre", "name": "lookup", "input": {},
                    }},
                    {"type": "content_block_delta", "index": 0, "delta": {
                        "type": "input_json_delta", "partial_json": "{\"q\":1}",
                    }},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use"},
                     "usage": {"output_tokens": 5}},
                    message_stop,
                ],
                None,
            ),
            (
                "late start after text",
                [text_block, text_delta, start("msg_late", 3), message_delta, message_stop],
                ("msg_late", "model-msg_late", {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}),
            ),
            (
                "late start after message_delta",
                [text_block, text_delta, message_delta, start("msg_late", 3), message_stop],
                ("msg_late", "model-msg_late", {"input_tokens": 3, "output_tokens": 0, "total_tokens": 3}),
            ),
            (
                "duplicate starts before content",
                [start("msg_a", 3), start("msg_b", 9), text_block, text_delta, message_delta, message_stop],
                ("msg_b", "model-msg_b", {"input_tokens": 9, "output_tokens": 5, "total_tokens": 14}),
            ),
            (
                "duplicate starts after content",
                [text_block, text_delta, start("msg_a", 3), start("msg_b", 9), message_delta, message_stop],
                ("msg_a", "model-msg_b", {"input_tokens": 9, "output_tokens": 5, "total_tokens": 14}),
            ),
            (
                "empty block before start",
                [text_block, start("msg_empty", 3), message_delta, message_stop],
                ("msg_empty", "model-msg_empty", {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}),
            ),
            (
                "custom generated-prefix ID followed by another start",
                [text_block, text_delta, start("resp_deepseek_custom", 3), start("msg_next", 9), message_delta, message_stop],
                ("msg_next", "model-msg_next", {"input_tokens": 9, "output_tokens": 5, "total_tokens": 14}),
            ),
        )
        for label, events, release_final in cases:
            with self.subTest(case=label):
                observations = [
                    _run(binary, request, scenario="anthropic-custom-events", anthropic_events=events)
                    for binary in (self.oracle_01651, self.oracle_04392, MODEX)
                ]
                for observed in observations:
                    self.assertEqual((observed["exit_code"], observed["status"]), (0, 200))
                    self.assertEqual(len(observed["upstream"]), 1)
                    self.assertEqual(observed["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(observed["state"]["leftovers"], [])

                normalized = [
                    _normalize_fallback_tool_call_ids(_normalized_events(item["response_body"]))
                    for item in observations
                ]
                self.assertEqual(normalized[0], normalized[1])
                self.assertEqual(observations[1]["upstream"][0]["body"], observations[0]["upstream"][0]["body"])
                self.assertEqual(normalized[2], normalized[0])
                if release_final is not None:
                    release_response = normalized[0][-1][1]["response"]
                    self.assertEqual(
                        (release_response["id"], release_response["model"], release_response["usage"]),
                        release_final,
                    )

    def test_anthropic_native_prefetch_consumes_exact_prefix(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        start = lambda ident, tokens: {
            "type": "message_start",
            "message": {
                "id": ident,
                "role": "assistant",
                "model": "model-" + ident,
                "usage": {"input_tokens": tokens, "output_tokens": 0},
            },
        }
        text_block = {"type": "content_block_start", "index": 0,
                      "content_block": {"type": "text", "text": ""}}
        text_delta = lambda text: {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": text},
        }
        message_delta = {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        }
        message_stop = {"type": "message_stop"}

        def exact_size_ping(size):
            base = json.dumps({"type": "ping", "padding": ""}, separators=(",", ":")).encode()
            padding = size - len(base) - len(b"data: \n\n")
            self.assertGreaterEqual(padding, 0)
            event = {"type": "ping", "padding": "x" * padding}
            frame = b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
            self.assertEqual(len(frame), size)
            return event

        scenarios = (
            (
                "first message_start",
                [start("msg_dropped", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "first text delta",
                [text_delta("dropped"), text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "first non-retryable error",
                [{"type": "error", "error": {"type": "synthetic_error", "message": "synthetic first error"}},
                 start("msg_after_error", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "first retryable error without a fallback",
                [{"type": "error", "error": {"type": "rate_limit_error", "message": "synthetic first error"}},
                 start("msg_after_error", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "event label ping with message_start JSON type",
                [{"event": "ping", "data": start("msg_label_ignored", 3)},
                 text_block, text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "JSON ping with message_start event label",
                [{"event": "message_start", "data": {"type": "ping"}},
                 start("msg_after_ping", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {},
            ),
            (
                "fragmented first frame",
                [start("msg_fragmented", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {"anthropic_fragment_at": 17},
            ),
            (
                "timeout after partial first frame",
                [start("msg_timeout", 3), text_block, text_delta("retained"), message_delta, message_stop],
                {
                    "anthropic_fragment_at": 17,
                    "anthropic_fragment_delay_ms": 100,
                    "environment_overrides": {"PRODEX_RUNTIME_PROXY_SSE_LOOKAHEAD_TIMEOUT_MS": "25"},
                },
            ),
            (
                "EOF inside first frame",
                [start("msg_truncated", 3), text_block, text_delta("not reached"), message_delta, message_stop],
                {"anthropic_truncate_at": 17},
            ),
            (
                "8 KiB boundary after ping",
                [exact_size_ping(8192), start("msg_after_boundary", 3), text_block,
                 text_delta("retained"), message_delta, message_stop],
                {"anthropic_fragment_at": 8192},
            ),
            (
                "8 KiB boundary inside next frame",
                [exact_size_ping(8191), start("msg_inside_boundary", 3), text_block,
                 text_delta("retained"), message_delta, message_stop],
                {"anthropic_fragment_at": 8192},
            ),
        )

        for label, events, options in scenarios:
            with self.subTest(case=label):
                observations = [
                    _run(binary, request, scenario="anthropic-custom-events", anthropic_events=events, **options)
                    for binary in (self.oracle_01651, self.oracle_04392, MODEX)
                ]
                for observed in observations:
                    self.assertEqual((observed["exit_code"], observed["status"]), (0, 200))
                    self.assertEqual(len(observed["upstream"]), 1)
                    self.assertEqual(observed["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(observed["state"]["leftovers"], [])
                normalized = [_normalized_events(item["response_body"]) for item in observations]
                self.assertEqual(normalized[0], normalized[1])
                self.assertEqual(normalized[2], normalized[0])
                self.assertEqual(observations[1]["upstream"][0]["body"], observations[0]["upstream"][0]["body"])

    def test_anthropic_tool_use_name_validation_matches_both_releases(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        start = {
            "type": "message_start",
            "message": {
                "id": "msg_tool_name",
                "role": "assistant",
                "model": "deepseek-chat",
                "usage": {"input_tokens": 3, "output_tokens": 0},
            },
        }
        cases = (
            ("missing", False, None),
            ("null", True, None),
            ("number", True, 5),
            ("empty", True, ""),
            ("whitespace", True, "  "),
            ("valid", True, "lookup"),
        )
        binaries = (self.oracle_01651, self.oracle_04392, MODEX)
        for case, include_name, name in cases:
            with self.subTest(case=case):
                block = {"type": "tool_use", "id": "toolu_name_probe", "input": {}}
                if include_name:
                    block["name"] = name
                events = [
                    start,
                    {"type": "content_block_start", "index": 0, "content_block": block},
                    {"type": "content_block_delta", "index": 0,
                     "delta": {"type": "input_json_delta", "partial_json": "{}"}},
                    {"type": "content_block_stop", "index": 0},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use"},
                     "usage": {"output_tokens": 1}},
                    {"type": "message_stop"},
                ]
                observations = [
                    _run(binary, request, scenario="anthropic-custom-events", anthropic_events=events)
                    for binary in binaries
                ]
                for observed in observations:
                    self.assertEqual((observed["exit_code"], observed["status"]), (0, 200))
                    self.assertEqual(observed["state"]["leftovers"], [])
                    self.assertEqual(observed["upstream"][0]["path"], "/anthropic/v1/messages")
                expected = _normalized_events(observations[0]["response_body"])
                expected_item_name = name if isinstance(name, str) and include_name else "tool_call"
                self.assertEqual(expected[1][1]["item"]["name"], expected_item_name)
                if case == "valid":
                    self.assertEqual([name for name, _ in expected], [
                        "response.created",
                        "response.output_item.added",
                        "response.function_call_arguments.delta",
                        "response.output_item.done",
                        "response.completed",
                    ])
                    self.assertEqual(expected[-1][1]["response"]["output"][0]["name"], "lookup")
                else:
                    self.assertEqual([name for name, _ in expected], [
                        "response.created",
                        "response.output_item.added",
                        "response.function_call_arguments.delta",
                        "response.failed",
                    ])
                    self.assertEqual(expected[-1][1]["response"]["error"]["code"], "invalid_tool_call_arguments")
                    self.assertEqual(
                        expected[-1][1]["response"]["error"]["message"],
                        "DeepSeek streamed a tool call without a function name at index 0",
                    )
                for observed in observations[1:]:
                    self.assertEqual(_normalized_events(observed["response_body"]), expected)
                    self.assertEqual(observed["upstream"][0]["path"], observations[0]["upstream"][0]["path"])
                    self.assertEqual(observed["upstream"][0]["body"], observations[0]["upstream"][0]["body"])



if __name__ == "__main__":
    unittest.main()
