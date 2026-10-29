"""Synthetic production-path checks against the pinned Prodex 0.165.1 oracle."""

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_provider_tools_04392_characterization import _normalized_events, _run
from test_anthropic_text_stream_04392 import START, TEXT_START, TEXT_DELTA, TEXT_STOP, MESSAGE_DELTA, STOP, REQUEST, stream
from test_deepseek_continuation import observe_turns
from provider_stream_search_cases import (
    empty_search_result_case,
    interleaved_mixed_search_case,
    overlapping_search_result_case,
    repeated_search_case,
    search_started_during_result_case,
)


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

    def test_anthropic_repeated_server_search_results_match_release(self):
        request, reply = repeated_search_case()
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(reference[0]["status"], 200)
        self.assertEqual(actual[0]["status"], 200)
        self.assertEqual(reference_posts[0]["path"], "/anthropic/v1/messages")
        self.assertEqual(actual_posts[0]["body"], reference_posts[0]["body"])
        expected_events = _normalized_events(bytes.fromhex(reference[0]["body"]))
        actual_events = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(actual_events, expected_events)
        output = expected_events[-1][1]["response"]["output"]
        self.assertEqual([item["id"] for item in output[:2]], ["search_1", "search_2"])
        self.assertEqual([item["action"]["queries"] for item in output[:2]], [["first"], ["second"]])
        self.assertEqual(
            [item["action"]["sources"][0]["url"] for item in output[:2]],
            ["https://one.example.test", "https://two.example.test"],
        )
        self.assertEqual(output[2]["content"][0]["text"], "Found both.")

    def test_anthropic_result_can_finish_while_another_search_is_open(self):
        request, reply = overlapping_search_result_case()
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        searches = [item for item in expected[-1][1]["response"]["output"]
                    if item["type"] == "web_search_call"]
        self.assertEqual([item["id"] for item in searches], ["search_0", "search_1"])
        self.assertEqual([item["action"]["sources"][0]["url"] for item in searches], [
            "https://example.test/0", "https://example.test/1",
        ])

    def test_anthropic_search_can_start_while_result_is_open(self):
        request, reply = search_started_during_result_case()
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        searches = [item for item in expected[-1][1]["response"]["output"]
                    if item["type"] == "web_search_call"]
        self.assertEqual([item["id"] for item in searches], ["s0", "s1", "s2"])
        self.assertEqual([item["action"]["queries"] for item in searches], [["zero"], ["one"], ["two"]])
        self.assertEqual([item["action"]["sources"][0]["url"] for item in searches], [
            "https://example.test/s0", "https://example.test/s1", "https://example.test/s2",
        ])

    def test_anthropic_empty_search_result_matches_release(self):
        request, reply = empty_search_result_case()
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        searches = [item for item in expected[-1][1]["response"]["output"]
                    if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"] for item in searches], [[]])

    def test_anthropic_repeated_search_id_matches_release_completion_policy(self):
        request, reply = repeated_search_case(shared_id=True)
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(reference[0]["status"], 200)
        self.assertEqual(actual[0]["status"], 200)
        self.assertEqual(reference_posts[0]["path"], "/anthropic/v1/messages")
        self.assertEqual(actual_posts[0]["body"], reference_posts[0]["body"])
        expected_events = _normalized_events(bytes.fromhex(reference[0]["body"]))
        actual_events = _normalized_events(bytes.fromhex(actual[0]["body"]))
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

    def test_anthropic_interleaved_mixed_searches_and_function_match_release(self):
        request, reply = interleaved_mixed_search_case()
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(reference_posts[0]["path"], "/anthropic/v1/messages")
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        self.assertEqual(
            [payload["sequence_number"] for _, payload in observed],
            list(range(len(observed))),
        )
        output = expected[-1][1]["response"]["output"]
        searches = [item for item in output if item["type"] == "web_search_call"]
        self.assertEqual([item["id"] for item in searches], ["search_1", "search_0"])
        self.assertEqual([item["action"]["queries"] for item in searches], [["query-1"], ["query-0"]])
        self.assertEqual([item["action"]["sources"][0]["url"] for item in searches], [
            "https://example.test/1", "https://example.test/0",
        ])
        function = next(item for item in output if item["type"] == "function_call")
        self.assertEqual((function["name"], function["arguments"]), ("lookup", '{"q":"mixed"}'))

    def test_anthropic_interleaved_duplicate_search_ids_match_release(self):
        request, reply = interleaved_mixed_search_case(shared_id=True)
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        searches = [item for item in expected[-1][1]["response"]["output"]
                    if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["queries"] for item in searches], [["query-0"], ["query-1"]])
        self.assertEqual([item["action"]["sources"] for item in searches], [
            [{"type": "url", "url": "https://example.test/1", "title": "Result 1"}],
            [],
        ])

    def test_anthropic_pending_mixed_searches_complete_at_message_stop(self):
        request, reply = interleaved_mixed_search_case(include_results=False)
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        searches = [item for item in expected[-1][1]["response"]["output"]
                    if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"] for item in searches], [[], []])

    def test_anthropic_missing_malformed_and_nonstrings_search_queries_match_release(self):
        for query_case in ("missing", "malformed", "nonstring", "initial-nonstr"):
            with self.subTest(query_case=query_case):
                request, reply = interleaved_mixed_search_case(query_case=query_case)
                reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
                actual_posts, actual = observe_turns(MODEX, [request], [reply])
                self.assertEqual([response["status"] for response in reference], [200])
                self.assertEqual([response["status"] for response in actual], [200])
                self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
                expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
                observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
                self.assertEqual(observed, expected)
                searches = [item for item in expected[-1][1]["response"]["output"]
                            if item["type"] == "web_search_call"]
                first_search = next(item for item in searches if item["id"] == "search_0")
                self.assertEqual(first_search["action"]["queries"], [])
                self.assertNotIn("query-0", json.dumps(expected, ensure_ascii=False))
                self.assertIn("query-1", json.dumps(expected, ensure_ascii=False))

    def test_anthropic_provider_error_aborts_mixed_stream_without_completion(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic mixed query",
            "stream": True,
            "tools": [
                {"type": "function", "name": "lookup", "parameters": {"type": "object"}},
                {"type": "web_search_preview"},
            ],
        }
        events = [
            START,
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": "search_cancel", "name": "web_search", "input": {},
            }},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "tool_use", "id": "call_cancel", "name": "lookup", "input": {},
            }},
            {"type": "error", "error": {"type": "overloaded_error", "message": "synthetic cancellation"}},
        ]
        reply = {"status": 200, "content_type": "text/event-stream", "body": stream(events)}
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        expected = _normalized_events(bytes.fromhex(reference[0]["body"]))
        observed = _normalized_events(bytes.fromhex(actual[0]["body"]))
        self.assertEqual(observed, expected)
        self.assertEqual(observed[-1][0], "response.failed")
        self.assertNotIn("response.completed", [name for name, _ in observed])

    def test_many_interleaved_mixed_searches_match_release(self):
        request, reply = interleaved_mixed_search_case(search_count=64)
        self.assertLess(len(reply["body"]), 4 * 1024 * 1024)
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual([response["status"] for response in reference], [200])
        self.assertEqual([response["status"] for response in actual], [200])
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        self.assertEqual(
            _normalized_events(bytes.fromhex(actual[0]["body"])),
            _normalized_events(bytes.fromhex(reference[0]["body"])),
        )

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

    def test_anthropic_image_content_block_is_dropped_like_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-stream-unknown-content")
        modex = _run(MODEX, request, scenario="anthropic-stream-unknown-content")

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = _normalized_events(reference["response_body"])
        observed = _normalized_events(modex["response_body"])
        self.assertEqual(observed, expected)
        self.assertIn("response.completed", [name for name, _ in expected])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", reference["response_body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", modex["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_image_block_index_and_text_order_match_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        for scenario in ("anthropic-stream-image-interleaved", "anthropic-stream-image-missing-index"):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_01651, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                expected = _normalized_events(reference["response_body"])
                observed = _normalized_events(modex["response_body"])
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(observed, expected)
                deltas = [body["delta"] for name, body in observed if name == "response.output_text.delta"]
                self.assertEqual(deltas, ["before image", " after image"])
                for payload in (reference["response_body"], modex["response_body"]):
                    self.assertNotIn(b"U1lOVEhFVElDX0lNQUdFX0JZVEVT", payload)
                    self.assertNotIn(b"SYNTHETIC_IMAGE_DELTA_SECRET", payload)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_image_response_stays_rejected_like_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_01651, request, scenario="anthropic-buffered-image")
        modex = _run(MODEX, request, scenario="anthropic-buffered-image")

        self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
        self.assertEqual((modex["exit_code"], modex["status"]), (1, 502))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", reference["response_body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", modex["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_input_image_is_rejected_before_provider_post(self):
        marker = "U1lOVEhFVElDX0lNQUdFX0JZVEVT"
        request = {
            "model": "deepseek-chat",
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "synthetic prompt"},
                    {"type": "input_image", "image_url": "data:image/png;base64," + marker},
                ],
            }],
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        for binary in (ORACLE_01651, MODEX):
            with self.subTest(binary=binary):
                result = _run(binary, request)
                self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                self.assertEqual(result["upstream"], [])
                self.assertNotIn(marker.encode(), result["response_body"])
                self.assertNotIn(marker.encode(), result["stderr"])
                self.assertEqual(result["state"]["leftovers"], [])

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
            "anthropic-tool-use-duplicate-stop": True,
            "anthropic-tool-use-orphan-stop": True,
            "anthropic-tool-use-mismatched-stop": True,
            "anthropic-tool-use-delta-after-stop": False,
            "anthropic-tool-use-reopened-index": False,
        }
        release_completes = {"anthropic-tool-use-reopened-index"}
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
