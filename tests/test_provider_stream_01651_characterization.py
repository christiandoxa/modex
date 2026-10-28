"""Synthetic production-path checks against the pinned Prodex 0.165.1 oracle."""

import hashlib
import copy
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
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
