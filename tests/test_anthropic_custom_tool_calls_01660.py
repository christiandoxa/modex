"""Compare custom Responses tool-call translation with Prodex 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_provider_tools_04392_characterization import _run


class AnthropicCustomToolCalls01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def _assert_request_matches(self, request, expected_body, mode):
        reference = _run(
            ORACLE, request, scenario="anthropic-buffered", mode_override=mode,
        )
        actual = _run(
            MODEX, request, scenario="anthropic-buffered", mode_override=mode,
        )
        for result in (reference, actual):
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(len(result["upstream"]), 1)
            self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertEqual(result["upstream_body"], expected_body)
            self.assertEqual(result["state"]["leftovers"], [])
        self.assertEqual(actual["upstream_body"], reference["upstream_body"])

    def test_custom_tool_pair_maps_to_anthropic_tool_use(self):
        base = {
            "model": "deepseek-chat",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = (
            (
                "custom call",
                {
                    **base,
                    "input": [
                        {"type": "custom_tool_call", "call_id": "call_custom",
                         "name": "custom", "input": {"q": "synthetic"}},
                        {"type": "custom_tool_call_output", "call_id": "call_custom",
                         "output": "synthetic result"},
                    ],
                },
                [{"role": "assistant", "content": [{
                    "type": "tool_use", "id": "call_custom", "name": "custom",
                    "input": {"input": json.dumps({"q": "synthetic"}, separators=(",", ":"))},
                }]}, {"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": "call_custom",
                    "content": "synthetic result",
                }]}],
            ),
            (
                "ordinary function call control",
                {
                    **base,
                    "input": [
                        {"type": "function_call", "call_id": "call_function",
                         "name": "lookup", "arguments": "{\"q\":\"synthetic\"}"},
                        {"type": "function_call_output", "call_id": "call_function",
                         "output": "synthetic result"},
                    ],
                },
                [{"role": "assistant", "content": [{
                    "type": "tool_use", "id": "call_function", "name": "lookup",
                    "input": {"q": "synthetic"},
                }]}, {"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": "call_function",
                    "content": "synthetic result",
                }]}],
            ),
        )
        for label, request, messages in cases:
            expected_body = {
                "max_tokens": 4096,
                "messages": messages,
                "model": "deepseek-chat",
                "stream": False,
                "tools": [{"name": "web_search", "type": "web_search_20250305"}],
            }
            for mode in ("auto", "anthropic"):
                with self.subTest(case=label, mode=mode):
                    self._assert_request_matches(request, expected_body, mode)

    def test_malformed_custom_items_and_unknown_types_stay_rejected(self):
        base = {
            "model": "deepseek-chat",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        invalid_inputs = (
            [{"type": "custom_tool_call", "name": "custom", "input": "synthetic"}],
            [{"type": "custom_tool_call", "call_id": "call_custom", "input": "synthetic"}],
            [{"type": "custom_tool_call_output", "call_id": "call_custom"}],
            [{"type": "synthetic_extension", "role": "user", "content": "synthetic"}],
        )
        for items in invalid_inputs:
            request = {**base, "input": items}
            with self.subTest(items=items):
                reference = _run(
                    ORACLE, request, scenario="anthropic-buffered", mode_override="anthropic",
                )
                actual = _run(
                    MODEX, request, scenario="anthropic-buffered", mode_override="anthropic",
                )
                for result in (reference, actual):
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                self.assertEqual(actual["response_body"], reference["response_body"])


if __name__ == "__main__":
    unittest.main()
