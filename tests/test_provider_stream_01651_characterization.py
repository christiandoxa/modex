"""Synthetic production-path checks against the pinned Prodex 0.165.1 oracle."""

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import (
    MODEX,
    ORACLE as ORACLE_04392,
    ORACLE_SHA256 as ORACLE_04392_SHA256,
)
from test_provider_tools_04392_characterization import _normalized_events, _run
from test_anthropic_text_stream_04392 import START, TEXT_START, TEXT_DELTA, TEXT_STOP, MESSAGE_DELTA, STOP, REQUEST, stream
from test_deepseek_continuation import observe_turns


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


class ProviderStream01651CharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE_01651.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE_01651}")
        if hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.165.1")
        if not ORACLE_04392.is_file():
            raise AssertionError(f"Historical Prodex 0.439.2 oracle is missing: {ORACLE_04392}")
        if hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256:
            raise AssertionError("The historical Prodex oracle does not match release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_anthropic_text_start_payload_is_ignored(self):
        for value in ("synthetic initial text", "", None, 42):
            with self.subTest(value=value):
                start = copy.deepcopy(TEXT_START)
                if value is None:
                    del start["content_block"]["text"]
                else:
                    start["content_block"]["text"] = value
                reply = {"status": 200, "content_type": "text/event-stream", "body": stream([
                    START, start, TEXT_DELTA, TEXT_STOP, MESSAGE_DELTA, STOP,
                ])}
                reference_posts, reference = observe_turns(ORACLE_01651, [REQUEST], [reply])
                actual_posts, actual = observe_turns(MODEX, [REQUEST], [reply])
                self.assertEqual(len(reference_posts), 1)
                self.assertEqual(len(actual_posts), 1)
                self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
                self.assertEqual(actual_posts[0]["body"], reference_posts[0]["body"])
                expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
                observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
                self.assertEqual(expected[-1][0], "response.completed")
                self.assertEqual(observed, expected)
                self.assertNotIn("synthetic initial text", json.dumps(observed, ensure_ascii=False))

    def test_anthropic_message_delta_stop_fields_match_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "anthropic-stop-end-turn-sequence": "stop",
            "anthropic-stop-tool-use": "tool_calls",
            "anthropic-stop-max-tokens": "length",
            "anthropic-stop-missing-message-delta": None,
            "anthropic-stop-null-reason": None,
            "anthropic-stop-missing-reason": None,
            "anthropic-stop-invalid-reason": None,
            "anthropic-stop-invalid-sequence": "stop",
            "anthropic-stop-unknown-event": "stop",
        }
        for scenario, expected_finish_reason in cases.items():
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(modex["upstream"]), 1)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                reference_events = _normalized_events(reference["response_body"])
                modex_events = _normalized_events(modex["response_body"])
                self.assertEqual(modex_events, reference_events)
                self.assertIn("response.completed", [name for name, _ in reference_events])
                completed = reference_events[-1][1]["response"]
                if expected_finish_reason is None:
                    self.assertNotIn("metadata", completed)
                else:
                    self.assertEqual(
                        completed["metadata"]["deepseek"]["finish_reason"],
                        expected_finish_reason,
                    )
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_repeated_server_search_results_match_releases(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        events = [
            START,
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {},
            }},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":"first"}',
            }},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "search_1", "content": [
                    {"type": "web_search_result", "url": "https://one.example.test", "title": "One"},
                ],
            }},
            {"type": "content_block_stop", "index": 1},
            {"type": "content_block_start", "index": 2, "content_block": {
                "type": "server_tool_use", "id": "search_2", "name": "web_search", "input": {},
            }},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":"second"}',
            }},
            {"type": "content_block_stop", "index": 2},
            {"type": "content_block_start", "index": 3, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "search_2", "content": [
                    {"type": "web_search_result", "url": "https://two.example.test", "title": "Two"},
                ],
            }},
            {"type": "content_block_stop", "index": 3},
            {"type": "content_block_start", "index": 4, "content_block": {
                "type": "text", "text": "",
            }},
            {"type": "content_block_delta", "index": 4, "delta": {
                "type": "text_delta", "text": "Found both.",
            }},
            {"type": "content_block_stop", "index": 4},
            MESSAGE_DELTA,
            STOP,
        ]
        reply = {
            "status": 200,
            "content_type": "text/event-stream",
            "body": stream(events),
        }
        captures = []
        for binary in (ORACLE_01651, ORACLE_04392, MODEX):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            self.assertEqual(responses[0]["status"], 200)
            captures.append((posts, _normalized_events(bytes.fromhex(responses[0]["body"]))))

        expected_posts, expected_events = captures[0]
        historical_posts, historical_events = captures[1]
        actual_posts, actual_events = captures[2]
        self.assertEqual(historical_posts[0]["body"], expected_posts[0]["body"])
        self.assertEqual(actual_posts[0]["body"], expected_posts[0]["body"])
        self.assertEqual(historical_events, expected_events)
        self.assertEqual(actual_events, expected_events)
        self.assertEqual(expected_events[-1][0], "response.completed")
        output = expected_events[-1][1]["response"]["output"]
        self.assertEqual([item["id"] for item in output[:2]], ["search_1", "search_2"])
        self.assertEqual(
            [item["action"]["queries"] for item in output[:2]],
            [["first"], ["second"]],
        )
        self.assertEqual(
            [item["action"]["sources"][0]["url"] for item in output[:2]],
            ["https://one.example.test", "https://two.example.test"],
        )
        self.assertEqual(output[2]["content"][0]["text"], "Found both.")

    def test_anthropic_repeated_search_id_matches_release_completion_policy(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        events = [
            START,
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": "shared_search", "name": "web_search", "input": {},
            }},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":"first"}',
            }},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "shared_search", "content": [
                    {"type": "web_search_result", "url": "https://one.example.test", "title": "One"},
                ],
            }},
            {"type": "content_block_stop", "index": 1},
            {"type": "content_block_start", "index": 2, "content_block": {
                "type": "server_tool_use", "id": "shared_search", "name": "web_search", "input": {},
            }},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":"second"}',
            }},
            {"type": "content_block_stop", "index": 2},
            {"type": "content_block_start", "index": 3, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "shared_search", "content": [
                    {"type": "web_search_result", "url": "https://two.example.test", "title": "Two"},
                ],
            }},
            {"type": "content_block_stop", "index": 3},
            {"type": "content_block_start", "index": 4, "content_block": {
                "type": "text", "text": "",
            }},
            {"type": "content_block_delta", "index": 4, "delta": {
                "type": "text_delta", "text": "Found both.",
            }},
            {"type": "content_block_stop", "index": 4},
            MESSAGE_DELTA,
            STOP,
        ]
        reply = {
            "status": 200,
            "content_type": "text/event-stream",
            "body": stream(events),
        }
        captures = []
        for binary in (ORACLE_01651, ORACLE_04392, MODEX):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            self.assertEqual(responses[0]["status"], 200)
            captures.append((posts, _normalized_events(bytes.fromhex(responses[0]["body"]))))

        expected_posts, expected_events = captures[0]
        historical_posts, historical_events = captures[1]
        actual_posts, actual_events = captures[2]
        self.assertEqual(historical_posts[0]["body"], expected_posts[0]["body"])
        self.assertEqual(actual_posts[0]["body"], expected_posts[0]["body"])
        self.assertEqual(historical_events, expected_events)
        self.assertEqual(actual_events, expected_events)
        completed = [
            event[1] for event in expected_events
            if event[0] == "response.output_item.done"
            and event[1].get("item", {}).get("type") == "web_search_call"
        ]
        self.assertEqual([event["output_index"] for event in completed], [0, 2])
        self.assertEqual([event["item"]["id"] for event in completed], ["shared_search"] * 2)
        self.assertEqual(completed[0]["item"]["action"]["queries"], ["first"])
        self.assertEqual(
            completed[0]["item"]["action"]["sources"][0]["url"],
            "https://one.example.test",
        )
        self.assertEqual(completed[1]["item"]["action"]["queries"], ["second"])
        self.assertEqual(completed[1]["item"]["action"]["sources"], [])
        response = expected_events[-1][1]["response"]
        searches = [item for item in response["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"] for item in searches], [
            [{"type": "url", "url": "https://one.example.test", "title": "One"}],
            [],
        ])

    def test_anthropic_buffered_function_tool_use_matches_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "anthropic-buffered-tool-use": '{"query":"release"}',
            "anthropic-buffered-tool-use-missing-input": "{}",
            "anthropic-buffered-tool-use-scalar": "7",
            "anthropic-buffered-tool-use-array": '[1,"two"]',
        }
        for scenario, expected_arguments in cases.items():
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)

                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(modex["upstream"]), 1)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])

                expected = json.loads(reference["response_body"])
                actual = json.loads(modex["response_body"])
                self.assertEqual(actual["id"], expected["id"])
                self.assertEqual(actual["model"], expected["model"])
                self.assertEqual(actual["output"], expected["output"])
                self.assertEqual(actual["metadata"], expected["metadata"])
                self.assertEqual(actual["usage"], expected["usage"])
                self.assertEqual(actual["output"][1]["arguments"], expected_arguments)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_text_runs_split_at_tool_calls(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-tool-use-mixed")
        modex = _run(MODEX, request, scenario="anthropic-buffered-tool-use-mixed")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        self.assertEqual(actual["output"], expected["output"])
        self.assertEqual(
            [
                (
                    item["type"],
                    [part["text"] for part in item.get("content", [])],
                    item.get("name"),
                    item.get("arguments"),
                )
                for item in actual["output"]
            ],
            [
                ("message", ["Found ", "it."], None, None),
                ("function_call", [], "lookup", '{"query":"release"}'),
                ("message", ["Next ", "step."], None, None),
                ("function_call", [], "count", '[1,"two"]'),
                ("message", ["Done."], None, None),
            ],
        )
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_tool_use_preserves_stop_reason_presence_and_type(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        for scenario in (
            "anthropic-buffered-tool-use-stop-missing",
            "anthropic-buffered-tool-use-stop-null",
            "anthropic-buffered-tool-use-stop-numeric",
        ):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                expected = json.loads(reference["response_body"])
                actual = json.loads(modex["response_body"])
                for key in ("id", "object", "model", "output", "usage"):
                    self.assertEqual(actual[key], expected[key], key)
                if "metadata" in expected:
                    self.assertEqual(actual["metadata"], expected["metadata"])
                else:
                    self.assertNotIn("metadata", actual)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_function_call_is_retained_for_next_request(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-tool-history")
        modex = _run(MODEX, request, scenario="anthropic-buffered-tool-history")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["responses"]), 2)
        self.assertEqual(len(modex["responses"]), 2)
        self.assertEqual(len(reference["upstream"]), 2)
        self.assertEqual(len(modex["upstream"]), 2)
        self.assertEqual(modex["upstream"][1]["path"], reference["upstream"][1]["path"])
        reference_second = json.loads(bytes.fromhex(reference["upstream"][1]["body"]))
        modex_second = json.loads(bytes.fromhex(modex["upstream"][1]["body"]))
        self.assertEqual(modex_second, reference_second)
        assistant = next(message for message in modex_second["messages"] if message["role"] == "assistant")
        self.assertEqual(assistant["content"][1], {
            "type": "tool_use",
            "id": "call_tool_use",
            "name": "functions--lookup",
            "input": {"query": "release"},
        })
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_mixed_tool_history_matches_release_order(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-tool-history-mixed")
        modex = _run(MODEX, request, scenario="anthropic-buffered-tool-history-mixed")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 2)
        self.assertEqual(len(modex["upstream"]), 2)
        reference_second = json.loads(bytes.fromhex(reference["upstream"][1]["body"]))
        modex_second = json.loads(bytes.fromhex(modex["upstream"][1]["body"]))
        self.assertEqual(modex_second, reference_second)
        assistant = next(message for message in modex_second["messages"] if message["role"] == "assistant")
        self.assertEqual(assistant["content"], [
            {"type": "text", "text": "Found it.Next step.Done."},
            {"type": "tool_use", "id": "call_lookup", "name": "functions--lookup", "input": {"query": "release"}},
        ])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_function_output_array_matches_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-tool-history-array-output")
        modex = _run(MODEX, request, scenario="anthropic-buffered-tool-history-array-output")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 2)
        self.assertEqual(len(modex["upstream"]), 2)
        reference_second = json.loads(bytes.fromhex(reference["upstream"][1]["body"]))
        modex_second = json.loads(bytes.fromhex(modex["upstream"][1]["body"]))
        self.assertEqual(modex_second, reference_second)
        user = next(
            message for message in modex_second["messages"]
            if message["role"] == "user" and any(part["type"] == "tool_result" for part in message["content"])
        )
        result = next(part for part in user["content"] if part["type"] == "tool_result")
        self.assertEqual(result["content"], "first\nsecond\nthird")
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_unmatched_function_output_matches_release_repair(self):
        request = {
            "model": "deepseek-chat",
            "input": [
                {"type": "function_call_output", "call_id": "call_orphan", "output": "orphan result"},
                {"type": "message", "role": "user", "content": "Continue."},
            ],
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-tool-use")
        modex = _run(MODEX, request, scenario="anthropic-buffered-tool-use")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        reference_body = json.loads(bytes.fromhex(reference["upstream"][0]["body"]))
        modex_body = json.loads(bytes.fromhex(modex["upstream"][0]["body"]))
        self.assertEqual(modex_body, reference_body)
        self.assertEqual(reference_body["messages"], [{
            "role": "user",
            "content": [{"type": "text", "text": "Continue."}],
        }])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_search_shape_remains_release_compatible(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered")
        modex = _run(MODEX, request, scenario="anthropic-buffered")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        for key in ("id", "model", "output", "metadata", "usage"):
            self.assertEqual(actual[key], expected[key], key)

    def test_anthropic_function_tool_use_stream_matches_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-tool-use")
        modex = _run(MODEX, request, scenario="anthropic-tool-use")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])

        reference_events = _normalized_events(reference["response_body"])
        modex_events = _normalized_events(modex["response_body"])
        self.assertEqual(modex_events, reference_events)
        completed = reference_events[-1][1]["response"]
        self.assertEqual(completed["output"][0]["name"], "lookup")
        self.assertEqual(completed["output"][0]["arguments"], '{"query":"current release"}')
        self.assertEqual(completed["metadata"]["deepseek"]["finish_reason"], "tool_calls")
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_multiple_tools_can_share_a_text_response(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        for scenario in ("anthropic-tool-use-mixed", "anthropic-tool-use-text-after"):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(modex["upstream"]), 1)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                reference_events = _normalized_events(reference["response_body"])
                modex_events = _normalized_events(modex["response_body"])
                self.assertEqual(modex_events, reference_events)
                completed = reference_events[-1][1]["response"]
                self.assertEqual(completed["output"][0]["content"][0]["text"], "Found ")
                self.assertEqual(
                    [(item["name"], item["arguments"]) for item in completed["output"][1:]],
                    [("lookup", '{"query":"release"}'), ("count", '{"n":1}')],
                )
                tool_indexes = [
                    payload["output_index"]
                    for name, payload in reference_events
                    if name == "response.output_item.added" and "output_index" in payload
                ]
                self.assertEqual(tool_indexes, [1, 2] if scenario == "anthropic-tool-use-mixed" else [0, 2])
                self.assertEqual(len(tool_indexes), len(set(tool_indexes)))
                self.assertEqual(completed["metadata"]["deepseek"]["finish_reason"], "tool_calls")
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_tool_events_during_text_and_after_message_delta_match_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        for scenario in (
            "anthropic-tool-use-open-text",
            "anthropic-tool-use-after-message-delta",
            "anthropic-tool-use-after-message-stop",
        ):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                reference_events = _normalized_events(reference["response_body"])
                modex_events = _normalized_events(modex["response_body"])
                self.assertEqual(modex_events, reference_events)
                names = [name for name, _ in reference_events]
                self.assertIn("response.completed", names)
                if scenario == "anthropic-tool-use-after-message-delta":
                    done = names.index("response.output_item.done")
                    deltas = [index for index, name in enumerate(names) if name == "response.function_call_arguments.delta"]
                    self.assertEqual(len(deltas), 2)
                    self.assertGreater(deltas[-1], done)
                if scenario == "anthropic-tool-use-after-message-stop":
                    completed = reference_events[-1][1]["response"]
                    self.assertEqual(completed["output"][0]["arguments"], "{} ")
                    self.assertEqual(names.count("response.function_call_arguments.delta"), 2)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_unsupported_anthropic_image_block_difference_stays_visible(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-stream-unknown-content")
        modex = _run(MODEX, request, scenario="anthropic-stream-unknown-content")
        reference_events = [name for name, _ in _normalized_events(reference["response_body"])]
        modex_events = [name for name, _ in _normalized_events(modex["response_body"])]

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertIn("response.completed", reference_events)
        self.assertIn("response.failed", modex_events)
        self.assertNotIn("response.completed", modex_events)
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_tool_use_index_and_stop_boundaries(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "anthropic-tool-use-duplicate-index": True,
            "anthropic-tool-use-missing-stop": True,
            "anthropic-tool-use-orphan-delta": False,
            "anthropic-tool-use-mismatched-index": False,
            "anthropic-tool-use-duplicate-stop": False,
            "anthropic-tool-use-orphan-stop": False,
            "anthropic-tool-use-mismatched-stop": False,
            "anthropic-tool-use-delta-after-stop": False,
            "anthropic-tool-use-reopened-index": False,
        }
        release_completes = {
            "anthropic-tool-use-duplicate-stop",
            "anthropic-tool-use-orphan-stop",
            "anthropic-tool-use-mismatched-stop",
            "anthropic-tool-use-reopened-index",
        }
        for scenario, exact_match in cases.items():
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(modex["upstream"]), 1)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                reference_events = _normalized_events(reference["response_body"])
                modex_events = _normalized_events(modex["response_body"])
                if exact_match:
                    self.assertEqual(modex_events, reference_events)
                else:
                    if scenario in release_completes:
                        self.assertIn("response.completed", [name for name, _ in reference_events])
                    else:
                        self.assertIn("response.failed", [name for name, _ in reference_events])
                    modex_names = [name for name, _ in modex_events]
                    self.assertIn("response.failed", modex_names)
                    self.assertNotIn("response.output_item.done", modex_names)
                    self.assertNotIn("response.completed", modex_names)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
