"""Differential DeepSeek request projection checks for Prodex 0.166.2."""

import hashlib
import json
import unittest

from manual_real_codex_01660_route_comparison import require_isolated_environment
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class ProviderRequestProjection01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_malformed_primary_tool_name_does_not_select_a_later_alias(self):
        cases = (
            ("null name with tool_name", "function_call", None, "lookup", None, None),
            ("number name with tool_name", "function_call", 7, "lookup", None, None),
            ("object name with tool_name", "function_call", {"bad": "synthetic"}, "lookup", None, None),
            ("array name with tool_name", "function_call", ["synthetic"], "lookup", None, None),
            ("boolean name with tool_name", "function_call", False, "lookup", None, None),
            ("invalid name with nested function", "function_call", None, None, {"name": "nested"}, None),
            ("invalid custom name", "custom_tool_call", None, "shell", None, "raw synthetic input"),
            ("invalid MCP name with result", "mcp_call", None, "lookup", None, None),
            ("missing name uses tool_name", "function_call", "__missing__", "lookup", None, None),
            ("missing name uses nested function", "function_call", "__missing__", None, {"name": "nested"}, None),
        )
        for index, (label, kind, name, tool_name, function, input_value) in enumerate(cases):
            with self.subTest(case=label):
                item = {"type": kind, "call_id": f"call_synthetic_{index}", "arguments": "{}"}
                if name != "__missing__":
                    item["name"] = name
                if tool_name is not None:
                    item["tool_name"] = tool_name
                if function is not None:
                    item["function"] = function
                if input_value is not None:
                    item["input"] = input_value
                if kind == "mcp_call":
                    item["output"] = {"ok": True, "source": "synthetic"}
                request = {"model": "deepseek-chat", "input": [item]}
                bodies = []
                for binary in (ORACLE, MODEX):
                    upstream, responses = observe_turns(
                        binary, [request], [buffered_reply(index)], latest_version="0.166.2",
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    bodies.append(upstream[0]["body"])
                self.assertEqual(bodies[1], bodies[0])
                messages = json.loads(bodies[0])["messages"]
                if name == "__missing__":
                    expected_name = tool_name if tool_name is not None else function["name"]
                    self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], expected_name)
                else:
                    self.assertEqual(messages, [{"content": "", "role": "assistant"}])

    def test_empty_primary_tool_name_still_fails_before_dispatch(self):
        request = {"model": "deepseek-chat", "input": [{
            "type": "function_call", "call_id": "call_synthetic_empty",
            "name": "", "tool_name": "lookup", "arguments": "{}",
        }]}
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, [request], [buffered_reply()], latest_version="0.166.2",
            )
            self.assertEqual([response["status"] for response in responses], [502])
            self.assertEqual(upstream, [])
            observations.append(responses[0]["body"])
        self.assertEqual(observations[1], observations[0])

    def test_custom_nested_name_matches_reference(self):
        request = {"model": "deepseek-chat", "input": [{
            "type": "custom_tool_call", "call_id": "call_synthetic_nested",
            "function": {"name": "shell"}, "input": "synthetic",
        }]}
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, [request], [buffered_reply()], latest_version="0.166.2",
            )
            observations.append(([row["status"] for row in responses],
                                 [row["body"] for row in upstream]))
        self.assertEqual(observations[1], observations[0])

    def test_function_call_argument_alias_precedence(self):
        cases = (
            {"arguments": None, "input": "fallback"},
            {"arguments": 7, "input": "fallback"},
            {"arguments": {}, "input": "fallback"},
            {"input": None, "function": {"arguments": "nested"}},
            {"function": {"arguments": "nested"}},
            {"arguments": "", "input": "fallback"},
        )
        for index, fields in enumerate(cases):
            with self.subTest(fields=fields):
                request = {"model": "deepseek-chat", "input": [{
                    "type": "function_call", "call_id": "call_synthetic",
                    "name": "lookup", **fields,
                }]}
                observations = []
                for binary in (ORACLE, MODEX):
                    upstream, responses = observe_turns(
                        binary, [request], [buffered_reply(index)], latest_version="0.166.2",
                    )
                    observations.append(([row["status"] for row in responses],
                                         [row["body"] for row in upstream]))
                self.assertEqual(observations[1], observations[0])


if __name__ == "__main__":
    unittest.main()
