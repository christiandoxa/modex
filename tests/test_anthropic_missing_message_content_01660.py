"""Compare missing-content Responses messages with Prodex 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE as ORACLE_01660, ORACLE_SHA256
from test_provider_tools_04392_characterization import _run


class AnthropicMissingMessageContent01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE_01660.is_file():
            raise AssertionError(f"Pinned Prodex 0.166.0 oracle is missing: {ORACLE_01660}")
        if hashlib.sha256(ORACLE_01660.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.166.0")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_namespace_tools_reach_anthropic_with_validation(self):
        base = {"model": "deepseek-chat", "input": "synthetic query", "stream": False}
        namespace = {"type": "namespace", "name": "agents", "tools": [
            {"type": "function", "name": "run", "description": "Run a task",
             "parameters": {"type": "object"}},
        ]}
        request = {**base, "tools": [{"type": "web_search_preview"}, namespace]}
        for mode in ("auto", "anthropic"):
            with self.subTest(mode=mode):
                reference = _run(ORACLE_01660, request, scenario="anthropic-buffered", mode_override=mode)
                actual = _run(MODEX, request, scenario="anthropic-buffered", mode_override=mode)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(actual["upstream"]), 1)
                self.assertEqual(actual["upstream"][0]["path"], "/anthropic/v1/messages")
                self.assertEqual(actual["upstream_body"], reference["upstream_body"])

        for child in ({"type": "function", "name": "run", "description": 7},
                      {"type": "function", "name": "run", "strict": "true"},
                      {"type": "function"}, {"type": "other", "name": "run"}):
            invalid = {**base, "tools": [{"type": "web_search_preview"},
                       {**namespace, "tools": [child]}]}
            with self.subTest(invalid=child):
                reference = _run(ORACLE_01660, invalid, scenario="anthropic-buffered", mode_override="anthropic")
                actual = _run(MODEX, invalid, scenario="anthropic-buffered", mode_override="anthropic")
                self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
                self.assertEqual((actual["exit_code"], actual["status"]), (1, 502))
                self.assertEqual(reference["upstream"], [])
                self.assertEqual(actual["upstream"], [])
                self.assertEqual(actual["response_body"], reference["response_body"])

    def test_missing_content_messages_are_skipped_in_native_anthropic_mode(self):
        cases = {
            "assistant before user": [
                {"role": "assistant"},
                {"role": "user", "content": "synthetic query"},
            ],
            "system before user": [
                {"role": "system"},
                {"role": "user", "content": "synthetic query"},
            ],
            "user before assistant": [
                {"role": "user"},
                {"role": "assistant", "content": "synthetic answer"},
            ],
            "empty assistant control": [
                {"role": "assistant", "content": ""},
                {"role": "user", "content": "synthetic query"},
            ],
            "null system control": [
                {"role": "system", "content": None},
                {"role": "user", "content": "synthetic query"},
            ],
            "numeric developer control": [
                {"role": "developer", "content": False},
                {"role": "user", "content": "synthetic query"},
            ],
        }
        for label, messages in cases.items():
            request = {
                "model": "deepseek-chat",
                "input": messages,
                "stream": False,
                "tools": [{"type": "web_search_preview"}],
            }
            for mode in ("auto", "anthropic"):
                with self.subTest(case=label, mode=mode):
                    reference = _run(
                        ORACLE_01660, request, scenario="anthropic-buffered", mode_override=mode,
                    )
                    actual = _run(
                        MODEX, request, scenario="anthropic-buffered", mode_override=mode,
                    )
                    self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                    self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                    self.assertEqual(len(reference["upstream"]), 1)
                    self.assertEqual(len(actual["upstream"]), 1)
                    self.assertEqual(reference["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(actual["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(actual["upstream"][0]["body"], reference["upstream"][0]["body"])
                    self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                    self.assertEqual(reference["state"]["leftovers"], [])
                    self.assertEqual(actual["state"]["leftovers"], [])

                    expected = json.loads(reference["response_body"])
                    observed = json.loads(actual["response_body"])
                    expected.pop("created_at")
                    observed.pop("created_at")
                    self.assertEqual(observed, expected)

    def test_mixed_message_order_keeps_function_call_and_output(self):
        request = {
            "model": "deepseek-chat",
            "input": [
                {"type": "message", "role": "user", "content": "before"},
                {"type": "function_call", "call_id": "call_lookup", "name": "lookup",
                 "arguments": '{"query":"release"}'},
                {"type": "function_call_output", "call_id": "call_lookup", "output": "result"},
                {"type": "message", "role": "user", "content": "after"},
            ],
            "stream": False,
            "tools": [
                {"type": "web_search_preview"},
                {"type": "function", "name": "lookup", "parameters": {"type": "object"}},
            ],
        }
        for mode in ("auto", "anthropic"):
            with self.subTest(mode=mode):
                reference = _run(
                    ORACLE_01660, request, scenario="anthropic-buffered", mode_override=mode,
                )
                actual = _run(
                    MODEX, request, scenario="anthropic-buffered", mode_override=mode,
                )
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(actual["upstream"]), 1)
                self.assertEqual(actual["upstream"][0]["path"], "/anthropic/v1/messages")
                self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                self.assertEqual(
                    actual["upstream_body"]["messages"],
                    [
                        {"role": "user", "content": [{"type": "text", "text": "before"}]},
                        {"role": "assistant", "content": [{"type": "tool_use", "id": "call_lookup",
                         "name": "lookup", "input": {"query": "release"}}]},
                        {"role": "user", "content": [
                            {"type": "tool_result", "tool_use_id": "call_lookup", "content": "result"},
                            {"type": "text", "text": "after"},
                        ]},
                    ],
                )
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(actual["state"]["leftovers"], [])

    def test_invalid_typed_content_is_rejected_before_provider_post(self):
        base = {
            "model": "deepseek-chat",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "typed numeric message content": [
                {"type": "message", "role": "user", "content": 7},
            ],
            "unsupported typed input item": [
                {"type": "synthetic_extension", "role": "user", "content": "synthetic"},
            ],
        }
        for label, items in cases.items():
            request = {**base, "input": items}
            for mode in ("auto", "anthropic"):
                with self.subTest(case=label, mode=mode):
                    reference = _run(
                        ORACLE_01660, request, scenario="anthropic-buffered", mode_override=mode,
                    )
                    actual = _run(
                        MODEX, request, scenario="anthropic-buffered", mode_override=mode,
                    )
                    self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
                    self.assertEqual((actual["exit_code"], actual["status"]), (1, 502))
                    self.assertEqual(reference["upstream"], [])
                    self.assertEqual(actual["upstream"], [])
                    self.assertEqual(actual["response_body"], reference["response_body"])
                    self.assertEqual(reference["state"]["leftovers"], [])
                    self.assertEqual(actual["state"]["leftovers"], [])
