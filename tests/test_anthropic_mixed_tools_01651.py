"""Synthetic production comparisons for mixed Anthropic function and web tools."""

import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
FUNCTION = {
    "type": "function",
    "name": "lookup",
    "description": "Lookup one record",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}
COUNT = {
    "type": "function",
    "name": "count",
    "description": "Count matching records",
    "parameters": {"type": "object", "properties": {"prefix": {"type": "string"}}},
}
SEARCH = {"type": "web_search_preview", "allowed_domains": ["example.test"]}


def _request(stream=False):
    return {
        "model": "deepseek-chat",
        "input": "synthetic mixed request",
        "stream": stream,
        "tools": [SEARCH, FUNCTION, COUNT],
    }


def _buffered_reply(content=None, stop_reason="tool_use"):
    if content is None:
        content = [
            {"type": "text", "text": "Before search."},
            {"type": "server_tool_use", "id": "srv_lookup", "name": "web_search",
             "input": {"query": "release"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_lookup", "content": [
                {"type": "web_search_result", "url": "https://example.test/release",
                 "title": "Release"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup",
             "input": {"query": "release"}},
            {"type": "text", "text": "After function."},
        ]
    return {
        "status": 200,
        "content_type": "application/json",
        "body": json.dumps({
            "id": "msg_mixed",
            "type": "message",
            "role": "assistant",
            "model": "deepseek-chat",
            "content": content,
            "stop_reason": stop_reason,
            "usage": {"input_tokens": 3, "output_tokens": 5},
        }, separators=(",", ":")).encode(),
    }


def _stream(events):
    body = b"".join(
        b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        for event in events
    )
    return {"status": 200, "content_type": "text/event-stream", "body": body}


def _normalize(value):
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "<time>" if key == "created_at" else _normalize(item)
            for key, item in value.items()
        }
    if isinstance(value, str) and value.startswith(("resp_deepseek_", "msg_deepseek_")):
        return "<generated-id>"
    return value


def _events(payload):
    events = []
    name = None
    for line in payload.decode().splitlines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: {"):
            events.append((name, _normalize(json.loads(line[6:]))))
    return events


def _json_body(record):
    return json.loads(bytes.fromhex(record["body"]))


class AnthropicMixedTool01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE_01651.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE_01651}")
        if hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.165.1")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def _compare(self, request, reply):
        reference_posts, reference = observe_turns(ORACLE_01651, [request], [reply])
        actual_posts, actual = observe_turns(MODEX, [request], [reply])
        self.assertEqual(len(reference), 1)
        self.assertEqual(len(actual), 1)
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(reference[0]["status"], 200)
        self.assertEqual(actual[0]["status"], 200)
        self.assertEqual(actual_posts[0]["path"], reference_posts[0]["path"])
        self.assertEqual(json.loads(actual_posts[0]["body"]), json.loads(reference_posts[0]["body"]))
        headers = {name.lower(): value for name, value in actual_posts[0]["headers"].items()}
        self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        return reference_posts[0], reference[0], actual_posts[0], actual[0]

    def test_function_search_tools_and_tool_choices_match_release(self):
        reply = _buffered_reply([
            {"type": "server_tool_use", "id": "srv_lookup", "name": "web_search",
             "input": {"query": "release"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_lookup", "content": [
                {"type": "web_search_result", "url": "https://example.test/release",
                 "title": "Release"},
            ]},
            {"type": "text", "text": "Found it."},
        ], "end_turn")
        choices = [
            ("default", None, None, ["lookup", "count", "web_search"]),
            ("auto", "auto", {"type": "auto"}, ["lookup", "count", "web_search"]),
            ("required", "required", {"type": "any"}, ["lookup", "count", "web_search"]),
            ("named", {"type": "function", "name": "lookup"},
             {"type": "tool", "name": "lookup"}, ["lookup", "count", "web_search"]),
            ("none", "none", None, []),
        ]
        for label, choice, expected_choice, expected_names in choices:
            with self.subTest(choice=label):
                request = _request()
                if choice is not None:
                    request["tool_choice"] = choice
                reference, expected, actual, observed = self._compare(request, reply)
                expected_body = json.loads(reference["body"])
                actual_body = json.loads(actual["body"])
                self.assertEqual(actual_body, expected_body)
                self.assertEqual([tool["name"] for tool in actual_body.get("tools", [])], expected_names)
                self.assertEqual(actual_body.get("tool_choice"), expected_choice)
                self.assertEqual(_normalize(_json_body(observed)), _normalize(_json_body(expected)))

    def test_function_without_schema_gets_release_default_schema(self):
        request = _request()
        request["tools"][1] = {key: value for key, value in FUNCTION.items() if key != "parameters"}
        _, _, actual_post, _ = self._compare(request, _buffered_reply([
            {"type": "server_tool_use", "id": "srv_lookup", "name": "web_search",
             "input": {"query": "release"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_lookup", "content": [
                {"type": "web_search_result", "url": "https://example.test/release",
                 "title": "Release"},
            ]},
            {"type": "text", "text": "Found it."},
        ], "end_turn"))
        body = json.loads(actual_post["body"])
        self.assertEqual(body["tools"][0]["input_schema"], {"type": "object", "properties": {}})

    def test_mixed_buffered_search_and_function_blocks_match_release(self):
        _, expected, _, observed = self._compare(_request(), _buffered_reply())
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        self.assertEqual([item["type"] for item in result["output"]], [
            "message", "web_search_call", "function_call", "message",
        ])
        self.assertEqual(result["output"][2]["call_id"], "call_lookup")

    def test_mixed_search_and_function_stream_matches_release(self):
        events = [
            {"type": "message_start", "message": {
                "id": "msg_mixed_stream", "role": "assistant", "model": "deepseek-chat",
                "usage": {"input_tokens": 3, "output_tokens": 0},
            }},
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": "srv_lookup", "name": "web_search", "input": {},
            }},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":"release"}',
            }},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "srv_lookup", "content": [
                    {"type": "web_search_result", "url": "https://example.test/release",
                     "title": "Release"},
                ],
            }},
            {"type": "content_block_stop", "index": 1},
            {"type": "content_block_start", "index": 2, "content_block": {
                "type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {},
            }},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":',
            }},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "input_json_delta", "partial_json": '"release"}',
            }},
            {"type": "content_block_stop", "index": 2},
            {"type": "content_block_start", "index": 3, "content_block": {
                "type": "text", "text": "",
            }},
            {"type": "content_block_delta", "index": 3, "delta": {
                "type": "text_delta", "text": "After function.",
            }},
            {"type": "content_block_stop", "index": 3},
            {"type": "message_delta", "delta": {
                "stop_reason": "tool_use", "stop_sequence": None,
            }, "usage": {"output_tokens": 5}},
            {"type": "message_stop"},
        ]
        _, expected, _, observed = self._compare(_request(stream=True), _stream(events))
        self.assertEqual(_events(bytes.fromhex(observed["body"])),
                         _events(bytes.fromhex(expected["body"])))
        self.assertEqual(_events(bytes.fromhex(observed["body"]))[-1][0], "response.completed")

    def test_second_mixed_search_pair_remains_fail_closed(self):
        content = [
            {"type": "server_tool_use", "id": "srv_one", "name": "web_search",
             "input": {"query": "first"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_one", "content": [
                {"type": "web_search_result", "url": "https://example.test/first"},
            ]},
            {"type": "server_tool_use", "id": "srv_two", "name": "web_search",
             "input": {"query": "second"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_two", "content": [
                {"type": "web_search_result", "url": "https://example.test/second"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup",
             "input": {"query": "second"}},
        ]
        reference_posts, reference = observe_turns(
            ORACLE_01651, [_request()], [_buffered_reply(content)],
        )
        actual_posts, actual = observe_turns(
            MODEX, [_request()], [_buffered_reply(content)],
        )
        self.assertEqual(reference[0]["status"], 200)
        self.assertEqual(actual[0]["status"], 502)
        self.assertEqual(len(reference_posts), 1)
        self.assertEqual(len(actual_posts), 1)
        self.assertEqual(json.loads(actual_posts[0]["body"]),
                         json.loads(reference_posts[0]["body"]))

    def test_invalid_function_schema_fails_before_provider_request(self):
        request = _request()
        request["tools"] = [SEARCH, {"type": "function", "name": "lookup", "parameters": []}]
        reply = _buffered_reply()
        for binary in (ORACLE_01651, MODEX):
            with self.subTest(binary=binary.name):
                posts, responses = observe_turns(binary, [request], [reply])
                self.assertEqual(posts, [])
                self.assertEqual(len(responses), 1)
                self.assertEqual(responses[0]["status"], 502)
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"upstream request failed")


if __name__ == "__main__":
    unittest.main()
