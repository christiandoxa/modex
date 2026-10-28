"""Compare embedded DeepSeek message tool calls with the frozen release."""

import hashlib
import json
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_provider_catalog_04395 import _codex_with_request


def call(name="lookup", call_id="synthetic-call", arguments="{}"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


class EmbeddedToolCalls04395Tests(unittest.TestCase):
    def test_generic_tool_calls_match_release_in_simple_and_non_simple_requests(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        regular = call()
        cases = [
            ("valid", "assistant", [regular], [regular], False),
            ("empty", "assistant", [], [], False),
            ("null", "assistant", None, None, False),
            ("non-array", "assistant", "synthetic", None, False),
            ("invalid-entries", "assistant", [False, {}, {"function": {"name": ""}}], [], False),
            ("missing-id", "assistant", [{"function": {"name": "lookup"}}],
             [{"type": "function", "function": {"name": "lookup", "arguments": "{}"}}], False),
            ("null-id-and-args", "assistant", [call(call_id=None, arguments=None)],
             [call(call_id=None, arguments="null")], False),
            ("object-args", "assistant", [{"id": 7, "type": "custom", "function": {"name": "lookup", "arguments": {"z": 1, "a": 2}}}],
             [call(call_id=7, arguments='{"a":2,"z":1}')], False),
            ("array-args", "assistant", [call(arguments=[1, 2])], [call(arguments="[1,2]")], False),
            ("space-name", "assistant", [{"function": {"name": " "}}],
             [{"type": "function", "function": {"name": " ", "arguments": "{}"}}], False),
            ("user-role", "user", [regular], [regular], False),
            ("tool-role", "tool", [regular], [regular], False),
            ("non-simple", "assistant", [regular], None, True),
        ]
        harness = test_super_launch.SuperLaunchTests()
        for name, role, supplied, expected, non_simple in cases:
            request = {"model": "deepseek-chat", "input": [{"role": role, "content": "hi", "tool_calls": supplied}], "stream": False}
            if non_simple:
                request["safety_identifier"] = "synthetic-user"
            message = {"role": role, "content": "hi"}
            if expected is not None:
                message["tool_calls"] = expected
            with self.subTest(case=name):
                captures = []
                for binary in (ORACLE, MODEX):
                    with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                        result, records, upstream, state = harness.run_launch(
                            binary=binary, scenario="buffered", model="deepseek-chat"
                        )
                    response = next(record for record in records if record["kind"] == "response")
                    self.assertEqual((result.returncode, response["status"], len(upstream)), (0, 200, 1), result.stderr)
                    self.assertEqual(state["leftovers"], [])
                    body = json.loads(bytes.fromhex(upstream[0]["body"]))
                    self.assertEqual(body["messages"], [message])
                    captures.append(body)
                self.assertEqual(captures[1], captures[0])

    def test_paired_output_keeps_embedded_call(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        harness = test_super_launch.SuperLaunchTests()
        for typed in (False, True):
            item = {"role": "assistant", "content": "hi", "tool_calls": [call()]}
            if typed:
                item["type"] = "message"
            request = {"model": "deepseek-chat", "input": [item, {
                "type": "function_call_output", "call_id": "synthetic-call", "output": "answer"
            }], "stream": False}
            expected = [
                {"role": "assistant", "content": "hi", "tool_calls": [call()]},
                {"role": "tool", "tool_call_id": "synthetic-call", "content": "answer"},
            ]
            with self.subTest(typed=typed):
                captures = []
                for binary in (ORACLE, MODEX):
                    with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                        result, records, upstream, state = harness.run_launch(
                            binary=binary, scenario="buffered", model="deepseek-chat"
                        )
                    response = next(record for record in records if record["kind"] == "response")
                    self.assertEqual((result.returncode, response["status"], len(upstream)), (0, 200, 1), result.stderr)
                    self.assertEqual(state["leftovers"], [])
                    body = json.loads(bytes.fromhex(upstream[0]["body"]))
                    self.assertEqual(body["messages"], expected)
                    captures.append(body)
                self.assertEqual(captures[1], captures[0])


if __name__ == "__main__":
    unittest.main()
