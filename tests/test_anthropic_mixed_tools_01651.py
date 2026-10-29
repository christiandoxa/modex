"""Synthetic production comparisons for mixed Anthropic function and web tools."""

import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY
from test_provider_tools_04392_characterization import _run


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
FUNCTION_RESPONSE_BLOCK = b'{"type":"tool_use","id":"x","name":"f"}'
TEXT_RESPONSE_BLOCK = b'{"type":"text","text":"x"}'


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


def _counted_buffered_reply(function_blocks, search_pairs=0, text_blocks=0):
    prefix = []
    for index in range(search_pairs):
        search_id = f"srv_bulk_{index}"
        query = f"query-{index}"
        url = f"https://example.test/result-{index}"
        prefix.extend((
            json.dumps({"type": "server_tool_use", "id": search_id, "name": "web_search",
                        "input": {"query": query}}, separators=(",", ":")).encode(),
            json.dumps({"type": "web_search_tool_result", "tool_use_id": search_id,
                        "content": [{"type": "web_search_result", "url": url}]},
                       separators=(",", ":")).encode(),
        ))
    content = b",".join(prefix)
    if function_blocks:
        repeated_functions = (FUNCTION_RESPONSE_BLOCK + b",") * function_blocks
        content += (b"," if content else b"") + repeated_functions[:-1]
    if text_blocks:
        repeated_text = (TEXT_RESPONSE_BLOCK + b",") * text_blocks
        content += (b"," if content else b"") + repeated_text[:-1]
    return {
        "status": 200,
        "content_type": "application/json",
        "body": (
            b'{"id":"msg_bulk","type":"message","role":"assistant",'
            b'"model":"deepseek-chat","content":[' + content +
            b'],"stop_reason":"tool_use","usage":{"input_tokens":3,"output_tokens":5}}'
        ),
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
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
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

    def _assert_content_limit_boundary(self, exact_function_blocks, over_function_blocks,
                                       exact_text_blocks, over_text_blocks, search_pairs,
                                       exact_output_items):
        request = _request()
        replies = [
            _counted_buffered_reply(exact_function_blocks, search_pairs, exact_text_blocks),
            _counted_buffered_reply(over_function_blocks, search_pairs, over_text_blocks),
        ]
        observed = []
        for binary in (ORACLE_01651, MODEX):
            posts, responses = observe_turns(binary, [request, request], replies)
            self.assertEqual(len(posts), 2)
            self.assertEqual(len(responses), 2)
            self.assertEqual([record["status"] for record in responses], [200, 502])
            self.assertEqual(bytes.fromhex(responses[1]["body"]),
                             b"provider response could not be processed")
            for post in posts:
                headers = {name.lower(): value for name, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
                self.assertEqual(headers["anthropic-version"], "2023-06-01")
            output = _json_body(responses[0])["output"]
            self.assertEqual(len(output), exact_output_items)
            observed.append((posts, responses, output))
        reference_posts, reference_responses, reference_output = observed[0]
        actual_posts, actual_responses, actual_output = observed[1]
        self.assertEqual([post["path"] for post in actual_posts], [post["path"] for post in reference_posts])
        self.assertEqual([json.loads(post["body"]) for post in actual_posts],
                         [json.loads(post["body"]) for post in reference_posts])
        self.assertEqual(len(reference_output), len(actual_output))
        self.assertEqual([record["status"] for record in actual_responses],
                         [record["status"] for record in reference_responses])
        if search_pairs:
            self.assertEqual([item["type"] for item in actual_output[:search_pairs]],
                             ["web_search_call"] * search_pairs)
        self.assertEqual(_normalize(_json_body(actual_responses[0])),
                         _normalize(_json_body(reference_responses[0])))
        self.assertEqual([item["type"] for item in actual_output],
                         [item["type"] for item in reference_output])
        self.assertIn("function_call", [item["type"] for item in actual_output])

    def test_buffered_content_block_limit_for_function_only_replies(self):
        self._assert_content_limit_boundary(1, 1, 65_535, 65_536, 0, 2)

    def test_buffered_content_block_limit_for_mixed_replies(self):
        self._assert_content_limit_boundary(1, 1, 65_531, 65_532, 2, 4)

    def test_many_buffered_search_pairs_and_function_match_release(self):
        for search_pairs in (3, 64, 1024):
            with self.subTest(search_pairs=search_pairs):
                _, expected, _, observed = self._compare(
                    _request(), _counted_buffered_reply(1, search_pairs)
                )
                expected_body = _normalize(_json_body(expected))
                actual_body = _normalize(_json_body(observed))
                self.assertEqual(actual_body, expected_body)
                self.assertEqual(len(actual_body["output"]), search_pairs + 1)
                self.assertEqual(actual_body["output"][-1]["type"], "function_call")

    def test_strict_mixed_tools_use_anthropic_route_like_release(self):
        captures = [
            _run(binary, _request(), strict_tools=True, scenario="anthropic-buffered")
            for binary in (ORACLE_01651, MODEX)
        ]
        for capture in captures:
            self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
            self.assertEqual(len(capture["upstream"]), 1)
            self.assertEqual(capture["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertEqual(capture["state"]["leftovers"], [])
        self.assertEqual(captures[0]["upstream_body"], captures[1]["upstream_body"])
        self.assertEqual(_normalize(json.loads(captures[0]["response_body"])),
                         _normalize(json.loads(captures[1]["response_body"])))

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

    def test_two_mixed_search_pairs_match_release(self):
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
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        self.assertEqual([item["type"] for item in result["output"]], [
            "web_search_call", "web_search_call", "function_call",
        ])

    def test_text_on_both_sides_of_search_result_keeps_message_boundary(self):
        content = [
            {"type": "server_tool_use", "id": "srv_boundary", "name": "web_search",
             "input": {"query": "boundary"}},
            {"type": "text", "text": "Before result."},
            {"type": "web_search_tool_result", "tool_use_id": "srv_boundary", "content": [
                {"type": "web_search_result", "url": "https://example.test/boundary"},
            ]},
            {"type": "text", "text": "After result."},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        self.assertEqual([item["type"] for item in result["output"]], [
            "web_search_call", "message", "message", "function_call",
        ])
        self.assertEqual(result["output"][1]["content"][0]["text"], "Before result.")
        self.assertEqual(result["output"][2]["content"][0]["text"], "After result.")

    def test_search_result_sources_project_release_fields(self):
        sources = [
            {"url": "https://example.test/one", "title": "One", "page_age": "today",
             "type": "future_result"},
            {"url": "https://example.test/no-title", "title": 17},
            {"url": 7, "title": "invalid URL"},
            {"title": "missing URL"},
            {"url": "https://example.test/no-type"},
            "not an object",
        ]
        result_block = {
            "type": "web_search_tool_result", "tool_use_id": "search_sources",
            "content": sources,
        }
        expected_sources = [
            {"type": "url", "url": "https://example.test/one", "title": "One"},
            {"type": "url", "url": "https://example.test/no-title"},
            {"type": "url", "url": "https://example.test/no-type"},
        ]

        for stream in (False, True):
            request = _request(stream=stream)
            if stream:
                reply = _stream([
                    {"type": "message_start", "message": {
                        "id": "msg_sources", "model": "deepseek-chat",
                        "usage": {"input_tokens": 1},
                    }},
                    {"type": "content_block_start", "index": 0, "content_block": {
                        "type": "server_tool_use", "id": "search_sources", "name": "web_search",
                        "input": {"query": "synthetic"},
                    }},
                    {"type": "content_block_start", "index": 1, "content_block": result_block},
                    {"type": "content_block_stop", "index": 1},
                    {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                     "usage": {"output_tokens": 1}},
                    {"type": "message_stop"},
                ])
            else:
                reply = _buffered_reply([
                    {"type": "server_tool_use", "id": "search_sources", "name": "web_search",
                     "input": {"query": "synthetic"}},
                    result_block,
                    {"type": "text", "text": "done"},
                ], stop_reason="end_turn")
            normalized = []
            request_bodies = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                posts, responses = observe_turns(binary, [request], [reply])
                self.assertEqual(len(posts), 1)
                self.assertEqual(len(responses), 1)
                self.assertEqual(responses[0]["status"], 200)
                self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                request_bodies.append(json.loads(posts[0]["body"]))
                if stream:
                    events = _events(bytes.fromhex(responses[0]["body"]))
                    self.assertEqual(events[-1][0], "response.completed")
                    response = events[-1][1]["response"]
                    normalized.append(events)
                else:
                    response = _normalize(_json_body(responses[0]))
                    normalized.append(response)
                search = next(item for item in response["output"]
                              if item["type"] == "web_search_call")
                self.assertEqual(search["action"]["sources"], expected_sources)
            self.assertEqual(normalized[1:], normalized[:1] * 2)
            self.assertEqual(request_bodies[1:], request_bodies[:1] * 2)

    def test_search_result_content_shapes_match_both_releases(self):
        cases = (
            ("missing", False, None),
            ("empty array", True, []),
            ("null", True, None),
            ("string", True, "synthetic result"),
            ("object", True, {"url": "https://example.test/ignored"}),
        )
        search_id = "search_content_shape"
        for label, include_content, content in cases:
            result = {"type": "web_search_tool_result", "tool_use_id": search_id}
            if include_content:
                result["content"] = content
            for stream in (False, True):
                with self.subTest(content=label, stream=stream):
                    request = _request(stream=stream)
                    if stream:
                        reply = _stream([
                            {"type": "message_start", "message": {
                                "id": "msg_content_shape", "model": "deepseek-chat",
                                "usage": {"input_tokens": 1},
                            }},
                            {"type": "content_block_start", "index": 0, "content_block": {
                                "type": "server_tool_use", "id": search_id, "name": "web_search",
                                "input": {"query": "synthetic"},
                            }},
                            {"type": "content_block_start", "index": 1, "content_block": result},
                            {"type": "content_block_stop", "index": 1},
                            {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                             "usage": {"output_tokens": 1}},
                            {"type": "message_stop"},
                        ])
                    else:
                        reply = _buffered_reply([
                            {"type": "server_tool_use", "id": search_id, "name": "web_search",
                             "input": {"query": "synthetic"}},
                            result,
                            {"type": "text", "text": "done"},
                        ], stop_reason="end_turn")
                    normalized = []
                    request_bodies = []
                    for binary in (ORACLE_01651, ORACLE, MODEX):
                        posts, responses = observe_turns(binary, [request], [reply])
                        self.assertEqual(len(posts), 1)
                        self.assertEqual(len(responses), 1)
                        self.assertEqual(responses[0]["status"], 200)
                        self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                        request_bodies.append(json.loads(posts[0]["body"]))
                        if stream:
                            events = _events(bytes.fromhex(responses[0]["body"]))
                            self.assertEqual(events[-1][0], "response.completed")
                            response = events[-1][1]["response"]
                            normalized.append(events)
                        else:
                            response = _normalize(_json_body(responses[0]))
                            normalized.append(response)
                        search = next(item for item in response["output"]
                                      if item["type"] == "web_search_call")
                        self.assertEqual(search["action"]["sources"], [])
                    self.assertEqual(normalized[1:], normalized[:1] * 2)
                    self.assertEqual(request_bodies[1:], request_bodies[:1] * 2)

    def test_mixed_tool_search_result_without_content_matches_both_releases(self):
        content = [
            {"type": "server_tool_use", "id": "search_mixed_content", "name": "web_search",
             "input": {"query": "synthetic"}},
            {"type": "web_search_tool_result", "tool_use_id": "search_mixed_content",
             "content": None},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        request = _request()
        reply = _buffered_reply(content)
        outcomes = []
        request_bodies = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 200)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            request_bodies.append(json.loads(posts[0]["body"]))
            response = _normalize(_json_body(responses[0]))
            search = next(item for item in response["output"]
                          if item["type"] == "web_search_call")
            self.assertEqual(search["action"]["sources"], [])
            outcomes.append(response)
        self.assertEqual(outcomes[1:], outcomes[:1] * 2)
        self.assertEqual(request_bodies[1:], request_bodies[:1] * 2)

    def test_invalid_utf8_search_result_matches_both_releases(self):
        search_id = "search_invalid_utf8"
        result = {"type": "web_search_tool_result", "tool_use_id": search_id,
                  "content": [{"type": "web_search_result", "url": "https://example.test/one",
                               "title": "invalid-utf8-marker"}]}
        events = [
            {"type": "message_start", "message": {
                "id": "msg_invalid_utf8", "model": "deepseek-chat", "usage": {"input_tokens": 1},
            }},
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": search_id, "name": "web_search",
                "input": {"query": "synthetic"},
            }},
            {"type": "content_block_start", "index": 1, "content_block": result},
            {"type": "message_stop"},
        ]

        for stream in (False, True):
            request = _request(stream=stream)
            if stream:
                reply = _stream(events)
            else:
                reply = _buffered_reply([
                    {"type": "server_tool_use", "id": search_id, "name": "web_search",
                     "input": {"query": "synthetic"}},
                    result,
                    {"type": "text", "text": "done"},
                ], stop_reason="end_turn")
            reply["body"] = reply["body"].replace(b'"invalid-utf8-marker"', b'"\xff"')
            outcomes = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                posts, responses = observe_turns(binary, [request], [reply])
                self.assertEqual(len(posts), 1)
                self.assertEqual(len(responses), 1)
                if stream:
                    self.assertEqual(responses[0]["status"], 200)
                    events = _events(bytes.fromhex(responses[0]["body"]))
                    self.assertEqual(events[-1][0], "response.failed")
                    self.assertEqual(events[-1][1]["response"]["error"], {
                        "code": "provider_stream_error", "message": "stream did not contain valid UTF-8",
                    })
                    outcomes.append(events)
                else:
                    self.assertEqual(responses[0]["status"], 502)
                    self.assertEqual(bytes.fromhex(responses[0]["body"]),
                                     b"provider response could not be processed")
                    outcomes.append((responses[0]["status"], responses[0]["body"]))
            self.assertEqual(outcomes[1:], outcomes[:1] * 2)

    def test_two_mixed_search_pairs_with_reused_id_keep_individual_queries_and_sources(self):
        content = [
            {"type": "server_tool_use", "id": "srv_reused", "name": "web_search",
             "input": {"query": "first query"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_reused", "content": [
                {"type": "web_search_result", "url": "https://example.test/first"},
            ]},
            {"type": "server_tool_use", "id": "srv_reused", "name": "web_search",
             "input": {"query": "second query"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_reused", "content": [
                {"type": "web_search_result", "url": "https://example.test/second"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        searches = [item for item in result["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["queries"] for item in searches], [
            ["first query"], ["second query"],
        ])
        self.assertEqual([item["action"]["sources"][0]["url"] for item in searches], [
            "https://example.test/first", "https://example.test/second",
        ])

    def test_repeated_result_overwrites_latest_matching_search_sources(self):
        content = [
            {"type": "server_tool_use", "id": "srv_repeat", "name": "web_search",
             "input": {"query": "repeat"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_repeat", "content": [
                {"type": "web_search_result", "url": "https://example.test/first"},
            ]},
            {"type": "web_search_tool_result", "tool_use_id": "srv_repeat", "content": [
                {"type": "web_search_result", "url": "https://example.test/last"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        search = next(item for item in result["output"] if item["type"] == "web_search_call")
        self.assertEqual(search["action"]["sources"][0]["url"], "https://example.test/last")

    def test_one_result_targets_latest_preceding_reused_search_id(self):
        content = [
            {"type": "server_tool_use", "id": "srv_shared", "name": "web_search",
             "input": {"query": "first query"}},
            {"type": "server_tool_use", "id": "srv_shared", "name": "web_search",
             "input": {"query": "second query"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_shared", "content": [
                {"type": "web_search_result", "url": "https://example.test/latest"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        searches = [item for item in result["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["queries"] for item in searches], [
            ["first query"], ["second query"],
        ])
        self.assertEqual([item["action"]["sources"] for item in searches], [
            [], [{"type": "url", "url": "https://example.test/latest"}],
        ])

    def test_distinct_search_results_match_ids_when_results_are_reversed(self):
        content = [
            {"type": "server_tool_use", "id": "srv_first", "name": "web_search",
             "input": {"query": "first query"}},
            {"type": "server_tool_use", "id": "srv_second", "name": "web_search",
             "input": {"query": "second query"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv_second", "content": [
                {"type": "web_search_result", "url": "https://example.test/second"},
            ]},
            {"type": "web_search_tool_result", "tool_use_id": "srv_first", "content": [
                {"type": "web_search_result", "url": "https://example.test/first"},
            ]},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        searches = [item for item in result["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"][0]["url"] for item in searches], [
            "https://example.test/first", "https://example.test/second",
        ])

    def test_search_result_before_use_is_ignored_and_unmatched_search_stays_empty(self):
        content = [
            {"type": "web_search_tool_result", "tool_use_id": "srv_future", "content": [
                {"type": "web_search_result", "url": "https://example.test/before"},
            ]},
            {"type": "server_tool_use", "id": "srv_future", "name": "web_search",
             "input": {"query": "future"}},
            {"type": "server_tool_use", "id": "srv_empty", "name": "web_search",
             "input": {"query": "no result"}},
            {"type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {}},
        ]
        _, expected, _, observed = self._compare(_request(), _buffered_reply(content))
        result = _json_body(observed)
        self.assertEqual(_normalize(result), _normalize(_json_body(expected)))
        searches = [item for item in result["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"] for item in searches], [[], []])

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
