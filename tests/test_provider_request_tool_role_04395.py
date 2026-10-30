"""Compare bare tool-role Responses input mapping with 0.439.2 and historical 0.439.5."""

import hashlib
import json
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import (MODEX, ORACLE as ACTIVE_ORACLE, ORACLE_SHA256 as ACTIVE_ORACLE_SHA256,
                      HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)
from test_provider_catalog_04395 import _codex_with_request


TOOL_CONTENT = "synthetic tool output"
TOOL_CALL_ID = "synthetic-call"


def _tool(content=TOOL_CONTENT, call_id="absent"):
    item = {"role": "tool", "content": content}
    if call_id != "absent":
        item["tool_call_id"] = call_id
    return item


CASES = (
    ("simple_absent_id", [_tool()], False, [{"role": "tool", "content": TOOL_CONTENT}]),
    ("simple_empty_id", [_tool(call_id="")], False, [{"role": "tool", "tool_call_id": "", "content": TOOL_CONTENT}]),
    ("simple_non_string_id", [_tool(call_id=7)], False, [{"role": "tool", "tool_call_id": "call_1", "content": TOOL_CONTENT}]),
    ("simple_orphan_id", [_tool(call_id=TOOL_CALL_ID)], False,
     [{"role": "tool", "tool_call_id": TOOL_CALL_ID, "content": TOOL_CONTENT}]),
    ("simple_call_id", [{**_tool(), "call_id": "primary"}], False,
     [{"role": "tool", "tool_call_id": "primary", "content": TOOL_CONTENT}]),
    ("simple_fallback_id", [{**_tool(), "id": "fallback"}], False,
     [{"role": "tool", "tool_call_id": "fallback", "content": TOOL_CONTENT}]),
    ("simple_id_precedence", [{**_tool(call_id="secondary"), "call_id": "primary", "id": "fallback"}], False,
     [{"role": "tool", "tool_call_id": "primary", "content": TOOL_CONTENT}]),
    ("simple_secondary_precedence", [{**_tool(call_id="secondary"), "id": "fallback"}], False,
     [{"role": "tool", "tool_call_id": "secondary", "content": TOOL_CONTENT}]),
    ("simple_null_primary", [{**_tool(call_id="secondary"), "call_id": None}], False,
     [{"role": "tool", "tool_call_id": "call_1", "content": TOOL_CONTENT}]),
    ("simple_empty_primary", [{**_tool(call_id="secondary"), "call_id": ""}], False,
     [{"role": "tool", "tool_call_id": "", "content": TOOL_CONTENT}]),
    ("simple_number_primary", [{**_tool(call_id="secondary"), "call_id": 7}], False,
     [{"role": "tool", "tool_call_id": "call_1", "content": TOOL_CONTENT}]),
    ("simple_paired_id", [
        {"type": "function_call", "call_id": TOOL_CALL_ID, "name": "lookup", "arguments": "{}"},
        _tool(call_id=TOOL_CALL_ID),
    ], False, [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": TOOL_CALL_ID, "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }]},
        {"role": "tool", "tool_call_id": TOOL_CALL_ID, "content": TOOL_CONTENT},
    ]),
    ("non_simple_absent_id", [_tool()], True, [{"role": "tool", "content": TOOL_CONTENT}]),
    ("non_simple_empty_id", [_tool(call_id="")], True, [{"role": "tool", "content": TOOL_CONTENT}]),
    ("non_simple_non_string_id", [_tool(call_id=7)], True, [{"role": "tool", "content": TOOL_CONTENT}]),
    ("non_simple_string_id", [_tool(call_id=TOOL_CALL_ID)], True, [{"role": "tool", "content": TOOL_CONTENT}]),
    ("non_simple_id_precedence", [{**_tool(call_id="secondary"), "call_id": "primary", "id": "fallback"}], True,
     [{"role": "tool", "content": TOOL_CONTENT}]),
    ("typed_tool_role_rejected", [{"type": "message", **_tool()}], False, None),
    ("typed_invalid_role_rejected", [{"type": "message", "role": "critic", "content": "synthetic"}], False, None),
)


class ProviderRequestToolRole04395Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ACTIVE_ORACLE.read_bytes()).hexdigest() != ACTIVE_ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match historical release 0.439.2")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match the pinned release checksum")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_bare_tool_role_mapping_matches_release(self):
        harness = test_super_launch.SuperLaunchTests()
        for name, items, non_simple, expected_messages in CASES:
            request = {"model": "deepseek-chat", "input": items, "stream": False}
            if non_simple:
                request["safety_identifier"] = "synthetic-user"
            with self.subTest(case=name):
                captures = []
                for binary in (ACTIVE_ORACLE, ORACLE, MODEX):
                    with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                        result, records, upstream, state = harness.run_launch(
                            binary=binary, scenario="buffered", model="deepseek-chat"
                        )
                    response = next(record for record in records if record["kind"] == "response")
                    self.assertEqual(state["leftovers"], [])
                    if expected_messages is None:
                        self.assertEqual(result.returncode, 1)
                        self.assertEqual((response["status"], upstream), (502, []))
                        captures.append(None)
                        continue
                    self.assertEqual((result.returncode, result.stdout), (0, b"synthetic-client-complete\n"), result.stderr)
                    self.assertEqual(response["status"], 200)
                    self.assertEqual(len(upstream), 1)
                    body = json.loads(bytes.fromhex(upstream[0]["body"]))
                    self.assertEqual(body["messages"], expected_messages)
                    if non_simple:
                        self.assertEqual(body["user_id"], "synthetic-user")
                    else:
                        self.assertNotIn("user_id", body)
                    captures.append(body)
                self.assertEqual(captures[1:], [captures[0], captures[0]])


if __name__ == "__main__":
    unittest.main()
