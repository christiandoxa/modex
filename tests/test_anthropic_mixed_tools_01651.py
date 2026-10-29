"""Synthetic production comparisons for mixed Anthropic function and web tools."""

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY
from test_provider_tools_04392_characterization import CODEX_REQUEST, _codex_with_request, _normalized_events, _run
import test_super_launch
import test_anthropic_message_arrays_04392 as message_arrays


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


def _codex_with_raw_request(raw_request):
    source = test_super_launch.CODEX
    if source.count(CODEX_REQUEST) != 1:
        raise AssertionError("Expected one synthetic Codex request body")
    replacement = 'body = b"\\x00synthetic\\xff" if passthrough else ' + repr(raw_request)
    return source.replace(CODEX_REQUEST, replacement)


def _run_mode(binary, request, scenario, mode=None, strict_tools=False, raw_request=None):
    codex = (
        _codex_with_raw_request(raw_request)
        if raw_request is not None else _codex_with_request(request)
    )
    with patch.object(test_super_launch, "CODEX", codex):
        original_run = test_super_launch.subprocess.run

        def run_with_mode(*args, **kwargs):
            if strict_tools:
                command = args[0] if args else kwargs["args"]
                base_url = command[command.index("--base-url") + 1]
                base = urlsplit(base_url)
                kwargs["env"] = {
                    **kwargs["env"],
                    "PRODEX_DEEPSEEK_STRICT_TOOLS": "true",
                    "PRODEX_DEEPSEEK_BETA_BASE_URL": f"{base.scheme}://{base.netloc}/beta",
                }
            if mode is not None:
                kwargs["env"] = {
                    **kwargs["env"],
                    "PRODEX_DEEPSEEK_WEB_SEARCH_MODE": mode,
                }
            return original_run(*args, **kwargs)

        with patch.object(test_super_launch.subprocess, "run", side_effect=run_with_mode):
            result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                binary=binary, scenario=scenario, model="deepseek-chat",
            )
    response = next((record for record in records if record["kind"] == "response"), None)
    return result, response, upstream, state


def _observe_mode_turns(binary, turns, replies, mode):
    original_run = test_super_launch.subprocess.run

    def run_with_mode(*args, **kwargs):
        kwargs["env"] = {
            **kwargs["env"],
            "PRODEX_DEEPSEEK_WEB_SEARCH_MODE": mode,
        }
        return original_run(*args, **kwargs)

    with patch.object(test_super_launch.subprocess, "run", side_effect=run_with_mode):
        return observe_turns(binary, turns, replies)


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
    if isinstance(value, str) and value.startswith(("resp_deepseek_", "msg_deepseek_", "call_deepseek_")):
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
    def test_responses_instructions_map_to_anthropic_system_for_both_releases(self):
        cases = [
            ({"input": "synthetic query", "instructions": "outer instruction"},
             "outer instruction"),
            ({"input": [
                {"role": "system", "content": "input system"},
                {"role": "developer", "content": "input developer"},
                {"role": "user", "content": "query"},
            ], "instructions": "outer instruction"},
             "outer instruction\n\ninput system\n\ninput developer"),
            ({"input": "synthetic query", "instructions": " \t\n "}, None),
            ({"input": "synthetic query", "instructions": "\u00a0\u3000"}, None),
            ({"input": "synthetic query", "instructions": "\u00a0\u200b\u3000"},
             "\u00a0\u200b\u3000"),
        ]
        for request_fields, expected_system in cases:
            with self.subTest(instructions=request_fields["instructions"]):
                request = {
                    "model": "deepseek-chat",
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                    **request_fields,
                }
                results = [_run(binary, request, scenario="anthropic-buffered")
                           for binary in (ORACLE_01651, ORACLE, MODEX)]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(result["state"]["leftovers"], [])
                    if expected_system is None:
                        self.assertNotIn("system", result["upstream_body"])
                    else:
                        self.assertEqual(result["upstream_body"]["system"], expected_system)
                self.assertEqual(results[0]["upstream"][0]["body"], results[1]["upstream"][0]["body"])
                self.assertEqual(results[1]["upstream"][0]["body"], results[2]["upstream"][0]["body"])
                self.assertEqual(results[0]["upstream_body"], results[1]["upstream_body"])
                self.assertEqual(results[1]["upstream_body"], results[2]["upstream_body"])

    def test_nonstring_responses_instructions_fail_before_provider_post(self):
        for instructions in (None, 7, []):
            with self.subTest(instructions=instructions):
                request = {
                    "model": "deepseek-chat",
                    "input": "synthetic query",
                    "instructions": instructions,
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                }
                results = [_run(binary, request, scenario="anthropic-buffered")
                           for binary in (ORACLE_01651, ORACLE, MODEX)]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])
                self.assertEqual(results[0]["response_body"], results[1]["response_body"])
                self.assertEqual(results[1]["response_body"], results[2]["response_body"])

    def test_responses_metadata_and_include_match_routes(self):
        base = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = (
            ("standard metadata and include", {
                "metadata": {"user_id": "synthetic-user"},
                "include": ["reasoning.encrypted_content"],
            }, ("auto", "anthropic", "openai_chat")),
            ("container types only", {"metadata": {"user_id": 7}, "include": [7]}, ("auto", "anthropic")),
        )

        def run(binary, request, scenario, mode):
            if mode == "auto":
                return _run(binary, request, scenario=scenario)
            process, response, upstream, state = _run_mode(
                binary, request, scenario, mode=mode,
            )
            return {
                "exit_code": process.returncode,
                "status": response["status"] if response else None,
                "response_body": bytes.fromhex(response["body"]) if response else b"",
                "upstream": upstream,
                "upstream_body": json.loads(bytes.fromhex(upstream[0]["body"])) if upstream else None,
                "state": state,
            }

        for label, fields, modes in cases:
            with self.subTest(case=label):
                request = {**base, **fields}
                for mode in modes:
                    captures = [run(binary, request, "anthropic-buffered", mode) for binary in (ORACLE_01651, ORACLE, MODEX)]
                    expected_path = "/v1/chat/completions" if mode == "openai_chat" else "/anthropic/v1/messages"
                    for capture in captures:
                        self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
                        self.assertEqual(len(capture["upstream"]), 1)
                        self.assertEqual(capture["upstream"][0]["path"], expected_path)
                        self.assertNotIn("metadata", capture["upstream_body"])
                        self.assertNotIn("include", capture["upstream_body"])
                        self.assertEqual(capture["state"]["leftovers"], [])
                    self.assertEqual(captures[1]["upstream_body"], captures[0]["upstream_body"])
                    self.assertEqual(captures[2]["upstream_body"], captures[0]["upstream_body"])
                    expected = _normalize(json.loads(captures[0]["response_body"]))
                    self.assertEqual(_normalize(json.loads(captures[1]["response_body"])), expected)
                    self.assertEqual(_normalize(json.loads(captures[2]["response_body"])), expected)

        request = {**base, "stream": True, **cases[0][1]}
        captures = [run(binary, request, "anthropic-stream", mode) for mode in ("auto", "anthropic") for binary in (ORACLE_01651, ORACLE, MODEX)]
        for capture in captures:
            self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
            self.assertEqual(len(capture["upstream"]), 1)
            self.assertEqual(capture["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertNotIn("metadata", json.loads(bytes.fromhex(capture["upstream"][0]["body"])))
            self.assertNotIn("include", json.loads(bytes.fromhex(capture["upstream"][0]["body"])))
            self.assertEqual(capture["state"]["leftovers"], [])
            self.assertEqual(capture["upstream_body"], captures[0]["upstream_body"])
            self.assertEqual(_events(capture["response_body"]), _events(captures[0]["response_body"]))

        invalid = ({"metadata": None}, {"metadata": "synthetic"}, {"include": None}, {"include": "reasoning.encrypted_content"})
        for mode in ("auto", "anthropic", "openai_chat"):
            for fields in invalid:
                with self.subTest(mode=mode, fields=fields):
                    responses = [run(binary, {**base, **fields}, "anthropic-buffered", mode) for binary in (ORACLE_01651, ORACLE, MODEX)]
                    for response in responses:
                        self.assertEqual((response["exit_code"], response["status"]), (1, 502))
                        self.assertEqual(response["upstream"], [])
                        self.assertEqual(response["state"]["leftovers"], [])
                    self.assertEqual(responses[1]["response_body"], responses[0]["response_body"])
                    self.assertEqual(responses[2]["response_body"], responses[0]["response_body"])

    def test_store_defaults_are_ignored_on_anthropic_provider_requests(self):
        values = ("missing", False, True, None, "false")
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for mode in ("auto", "anthropic", "openai_chat"):
            for streaming in (False, True):
                with self.subTest(mode=mode, stream=streaming):
                    turns = []
                    for value in values:
                        turn = {
                            "model": "deepseek-chat",
                            "input": "synthetic store control",
                            "stream": streaming,
                            "tools": [{"type": "web_search_preview"}],
                        }
                        if value != "missing":
                            turn["store"] = value
                        turns.append(turn)

                    if mode == "openai_chat":
                        if streaming:
                            chunks = [
                                {"id": "chat_store", "created": 42, "model": "deepseek-chat",
                                 "choices": [{"index": 0, "delta": {"role": "assistant", "content": "ok"},
                                              "finish_reason": None}]},
                                {"id": "chat_store", "created": 42, "model": "deepseek-chat",
                                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                            ]
                            reply = {
                                "status": 200,
                                "content_type": "text/event-stream",
                                "body": b"".join(
                                    b"data: " + json.dumps(chunk, separators=(",", ":")).encode() + b"\n\n"
                                    for chunk in chunks
                                ) + b"data: [DONE]\n\n",
                            }
                        else:
                            reply = {
                                "status": 200,
                                "content_type": "application/json",
                                "body": json.dumps({
                                    "id": "chat_store", "model": "deepseek-chat",
                                    "choices": [{"index": 0,
                                                  "message": {"role": "assistant", "content": "ok"},
                                                  "finish_reason": "stop"}],
                                }, separators=(",", ":")).encode(),
                            }
                    elif streaming:
                        reply = _stream([
                            {"type": "message_start", "message": {
                                "id": "msg_store", "role": "assistant", "model": "deepseek-chat",
                                "usage": {"input_tokens": 1, "output_tokens": 0},
                            }},
                            {"type": "content_block_start", "index": 0,
                             "content_block": {"type": "text", "text": ""}},
                            {"type": "content_block_delta", "index": 0,
                             "delta": {"type": "text_delta", "text": "ok"}},
                            {"type": "content_block_stop", "index": 0},
                            {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                             "usage": {"output_tokens": 1}},
                            {"type": "message_stop"},
                        ])
                    else:
                        reply = _buffered_reply(
                            content=[{"type": "text", "text": "ok"}],
                            stop_reason="end_turn",
                        )

                    captures = [
                        _observe_mode_turns(binary, turns, [reply] * len(turns), mode)
                        for binary in binaries
                    ]
                    expected_path = "/v1/chat/completions" if mode == "openai_chat" else "/anthropic/v1/messages"
                    for posts, responses in captures:
                        self.assertEqual([response["status"] for response in responses], [200, 200, 200, 502, 502])
                        self.assertEqual(len(posts), 3)
                        self.assertEqual([post["path"] for post in posts], [expected_path] * 3)
                        bodies = [json.loads(post["body"]) for post in posts]
                        self.assertTrue(all("store" not in body for body in bodies))
                        self.assertEqual([post["body"] for post in posts], [posts[0]["body"]] * 3)

                    expected_posts = [post["body"] for post in captures[0][0]]
                    self.assertEqual([post["body"] for post in captures[1][0]], expected_posts)
                    self.assertEqual([post["body"] for post in captures[2][0]], expected_posts)
                    for response_index in range(3):
                        if streaming:
                            normalized = [
                                _normalized_events(bytes.fromhex(responses[response_index]["body"]))
                                for _, responses in captures
                            ]
                        else:
                            normalized = [
                                _normalize(json.loads(bytes.fromhex(responses[response_index]["body"])))
                                for _, responses in captures
                            ]
                        self.assertEqual(normalized[1:], normalized[:1] * 2)
                    for response_index in (3, 4):
                        errors = [
                            bytes.fromhex(responses[response_index]["body"])
                            for _, responses in captures
                        ]
                        self.assertEqual(errors[1:], errors[:1] * 2)

    def test_native_anthropic_unsupported_chat_fields_fallback_safely(self):
        base = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "tools": [SEARCH, FUNCTION],
        }

        def run(binary, request, scenario, mode):
            if mode == "auto":
                return _run(binary, request, scenario=scenario)
            process, response, upstream, state = _run_mode(
                binary, request, scenario, mode=mode,
            )
            return {
                "exit_code": process.returncode,
                "status": response["status"] if response else None,
                "response_body": bytes.fromhex(response["body"]) if response else b"",
                "upstream": upstream,
                "upstream_body": json.loads(bytes.fromhex(upstream[0]["body"])) if upstream else None,
                "state": state,
            }

        cases = (
            ("logprobs", {"logprobs": True}, {"logprobs": True}),
            ("reasoning", {"reasoning": {"effort": "high"}}, {
                "reasoning_effort": "high", "thinking": {"type": "enabled"},
            }),
        )
        for label, fields, expected_fields in cases:
            request = {**base, **fields}
            with self.subTest(case=label):
                for mode in ("auto", "openai_chat"):
                    captures = [run(binary, request, "anthropic-buffered", mode) for binary in (ORACLE_01651, ORACLE, MODEX)]
                    for capture in captures:
                        self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
                        self.assertEqual(len(capture["upstream"]), 1)
                        self.assertEqual(capture["upstream"][0]["path"], "/v1/chat/completions")
                        for key, value in expected_fields.items():
                            self.assertEqual(capture["upstream_body"].get(key), value)
                        self.assertTrue(all(tool.get("type") == "function" for tool in capture["upstream_body"].get("tools", [])))
                        self.assertEqual(capture["state"]["leftovers"], [])
                    self.assertEqual(captures[1]["upstream_body"], captures[0]["upstream_body"])
                    self.assertEqual(captures[2]["upstream_body"], captures[0]["upstream_body"])
                    expected = _normalize(json.loads(captures[0]["response_body"]))
                    self.assertEqual(_normalize(json.loads(captures[1]["response_body"])), expected)
                    self.assertEqual(_normalize(json.loads(captures[2]["response_body"])), expected)

                rejected = [run(binary, request, "anthropic-buffered", "anthropic") for binary in (ORACLE_01651, ORACLE, MODEX)]
                for capture in rejected:
                    self.assertEqual((capture["exit_code"], capture["status"]), (1, 400))
                    self.assertEqual(capture["upstream"], [])
                    self.assertEqual(capture["state"]["leftovers"], [])
                self.assertEqual(rejected[1]["response_body"], rejected[0]["response_body"])
                self.assertEqual(rejected[2]["response_body"], rejected[0]["response_body"])

        streaming = {**base, "stream": True, "logprobs": True, "reasoning": {"effort": "high"}}
        for mode in ("auto", "openai_chat"):
            captures = [run(binary, streaming, "stream", mode) for binary in (ORACLE_01651, ORACLE, MODEX)]
            for capture in captures:
                self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
                self.assertEqual(len(capture["upstream"]), 1)
                self.assertEqual(capture["upstream"][0]["path"], "/v1/chat/completions")
                self.assertEqual(capture["upstream_body"].get("logprobs"), True)
                self.assertEqual(capture["upstream_body"].get("reasoning_effort"), "high")
                self.assertEqual(capture["upstream_body"].get("thinking"), {"type": "enabled"})
                self.assertEqual(capture["state"]["leftovers"], [])
            self.assertEqual(captures[1]["upstream_body"], captures[0]["upstream_body"])
            self.assertEqual(captures[2]["upstream_body"], captures[0]["upstream_body"])
            expected = _normalized_events(captures[0]["response_body"])
            self.assertEqual(_normalized_events(captures[1]["response_body"]), expected)
            self.assertEqual(_normalized_events(captures[2]["response_body"]), expected)

        invalid = (
            {"logprobs": "true"},
            {"reasoning": {"effort": 7}},
            {"reasoning": []},
            {"service_tier": "priority"},
        )
        for mode in ("auto", "anthropic", "openai_chat"):
            for fields in invalid:
                with self.subTest(mode=mode, fields=fields):
                    captures = [run(binary, {**base, **fields}, "anthropic-buffered", mode) for binary in (ORACLE_01651, ORACLE, MODEX)]
                    for capture in captures:
                        self.assertEqual((capture["exit_code"], capture["status"]), (1, 502))
                        self.assertEqual(capture["upstream"], [])
                        self.assertEqual(capture["state"]["leftovers"], [])
                    self.assertEqual(captures[1]["response_body"], captures[0]["response_body"])
                    self.assertEqual(captures[2]["response_body"], captures[0]["response_body"])

    def test_empty_and_whitespace_arrays_match_01651(self):
        with patch.object(message_arrays, "ORACLE", ORACLE_01651):
            message_arrays.AnthropicMessageArrayTests.test_empty_and_whitespace_arrays_match_release(self)

    def test_message_text_content_shapes_match_01651(self):
        with patch.object(message_arrays, "ORACLE", ORACLE_01651):
            message_arrays.AnthropicMessageArrayTests.test_message_text_content_shapes_match_release(self)

    def test_message_roles_and_metadata_match_01651(self):
        with patch.object(message_arrays, "ORACLE", ORACLE_01651):
            message_arrays.AnthropicMessageArrayTests.test_unknown_roles_and_message_metadata_match_release(self)

    def test_untyped_tool_message_fallback_order_matches_releases(self):
        input_items = [
            {"role": "user", "content": "before"},
            {"role": "tool", "content": "  missing ID result  "},
            {"role": "tool", "tool_call_id": None, "content": "null ID result"},
            {"role": "tool", "tool_call_id": 7, "content": "numeric ID result"},
            {"role": "tool", "tool_call_id": "", "content": "empty ID result"},
            {"role": "tool", "tool_call_id": " \t ", "content": "  whitespace content  "},
            {"role": "user", "content": "after"},
        ]
        expected_messages = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_prodex", "content": "  missing ID result  "},
            {"type": "tool_result", "tool_use_id": "call_prodex", "content": "null ID result"},
            {"type": "tool_result", "tool_use_id": "call_prodex", "content": "numeric ID result"},
            {"type": "tool_result", "tool_use_id": "call_prodex", "content": "empty ID result"},
            {"type": "tool_result", "tool_use_id": "call_prodex", "content": "  whitespace content  "},
            {"type": "text", "text": "before"},
            {"type": "text", "text": "after"},
        ]}]
        for stream, scenario in ((False, "anthropic-buffered"), (True, "anthropic-stream")):
            with self.subTest(stream=stream):
                request = {"model": "deepseek-chat", "input": input_items,
                           "stream": stream, "tools": [{"type": "web_search_preview"}]}
                results = [_run(binary, request, scenario=scenario)
                           for binary in (ORACLE_01651, ORACLE, MODEX)]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(result["upstream_body"]["messages"], expected_messages)
                    self.assertEqual(result["state"]["leftovers"], [])
                self.assertEqual(results[0]["upstream_body"], results[1]["upstream_body"])
                self.assertEqual(results[1]["upstream_body"], results[2]["upstream_body"])
                if stream:
                    self.assertEqual(_events(results[0]["response_body"]),
                                     _events(results[1]["response_body"]))
                    self.assertEqual(_events(results[1]["response_body"]),
                                     _events(results[2]["response_body"]))
                else:
                    expected = json.loads(results[0]["response_body"])
                    for result in results[1:]:
                        self.assertEqual(_normalize(json.loads(result["response_body"])),
                                         _normalize(expected))

        typed_tool = {"model": "deepseek-chat", "input": [
            {"type": "message", "role": "tool", "content": "typed result"},
        ], "stream": False, "tools": [{"type": "web_search_preview"}]}
        for binary in (ORACLE_01651, ORACLE, MODEX):
            result = _run(binary, typed_tool, scenario="anthropic-buffered")
            self.assertEqual((result["exit_code"], result["status"]), (1, 502))
            self.assertEqual(result["upstream"], [])

    def test_function_output_id_is_retained_with_grouped_tool_results(self):
        request = {"model": "deepseek-chat", "input": "synthetic web query",
                   "stream": False, "tools": [{"type": "web_search_preview"}]}
        results = [_run(binary, request, scenario="anthropic-buffered-tool-history-array-output")
                   for binary in (ORACLE_01651, ORACLE, MODEX)]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(len(result["upstream"]), 2)
            self.assertEqual(result["state"]["leftovers"], [])
        second_bodies = [json.loads(bytes.fromhex(result["upstream"][1]["body"]))
                         for result in results]
        self.assertEqual(second_bodies[1:], second_bodies[:1] * 2)
        user = next(message for message in second_bodies[0]["messages"]
                    if message["role"] == "user" and any(
                        block["type"] == "tool_result" for block in message["content"]))
        result = next(block for block in user["content"] if block["type"] == "tool_result")
        self.assertEqual((result["tool_use_id"], result["content"]),
                         ("call_tool_use", "first\nsecond\nthird"))

    def test_function_call_history_items_match_both_releases(self):
        base = {
            "model": "deepseek-chat",
            "stream": False,
            "tools": [
                {"type": "web_search_preview"},
                {"type": "function", "name": "lookup", "parameters": {"type": "object"}},
                {"type": "function", "name": "count", "parameters": {"type": "object"}},
            ],
        }
        cases = (
            ("orphan call", [
                {"type": "message", "role": "user", "content": "question"},
                {"type": "function_call", "call_id": "call_orphan", "name": "lookup",
                 "arguments": "{malformed"},
            ], [{"role": "user", "content": [{"type": "text", "text": "question"}]}]),
            ("matched call and output", [
                {"type": "message", "role": "user", "content": "question"},
                {"type": "function_call", "call_id": "call_lookup", "name": "lookup",
                 "arguments": "{\"query\":\"release\"}"},
                {"type": "function_call_output", "call_id": "call_lookup", "output": "result"},
            ], [
                {"role": "user", "content": [{"type": "text", "text": "question"}]},
                {"role": "assistant", "content": [{"type": "tool_use", "id": "call_lookup",
                 "name": "lookup", "input": {"query": "release"}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_lookup",
                 "content": "result"}]},
            ]),
            ("partial tool results", [
                {"type": "message", "role": "user", "content": "question"},
                {"type": "function_call", "call_id": "call_orphan", "name": "lookup",
                 "arguments": "{malformed"},
                {"type": "function_call", "call_id": "call_count", "name": "count",
                 "arguments": "{\"prefix\":\"rel\"}"},
                {"type": "function_call_output", "call_id": "call_count", "output": "1"},
            ], [
                {"role": "user", "content": [{"type": "text", "text": "question"}]},
                {"role": "assistant", "content": [{"type": "tool_use", "id": "call_count",
                 "name": "count", "input": {"prefix": "rel"}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_count",
                 "content": "1"}]},
            ]),
        )
        for label, items, expected_messages in cases:
            request = {**base, "input": items}
            with self.subTest(case=label):
                captures = [_run(binary, request, scenario="anthropic-buffered")
                            for binary in (ORACLE_01651, ORACLE, MODEX)]
                for capture in captures:
                    self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
                    self.assertEqual(len(capture["upstream"]), 1)
                    self.assertEqual(capture["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(capture["upstream_body"]["messages"], expected_messages)
                    self.assertEqual(capture["state"]["leftovers"], [])
                self.assertEqual(captures[0]["upstream_body"], captures[1]["upstream_body"])
                self.assertEqual(captures[1]["upstream_body"], captures[2]["upstream_body"])

    def test_function_output_aliases_and_extra_fields_match_modes(self):
        base = {"model": "deepseek-chat", "stream": False, "tools": [SEARCH, FUNCTION]}
        matched = [
            {"type": "message", "role": "user", "content": "question"},
            {"type": "function_call", "call_id": "call_primary", "name": "lookup", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call_primary", "tool_call_id": "conflict",
             "content": {"nested": [1, "two"]}, "future_field": {"synthetic": True}},
            {"type": "function_call", "tool_call_id": "call_tool_alias", "name": "lookup", "arguments": "{}"},
            {"type": "function_call_output", "tool_call_id": "call_tool_alias",
             "result": {"nested": [{"text": "result"}]}, "future_field": "ignored"},
            {"type": "function_call", "id": "call_id_alias", "name": "lookup", "arguments": "{}"},
            {"type": "function_call_output", "id": "call_id_alias", "error": "synthetic failure"},
            {"type": "function_call", "call_id": "call_nonstring", "name": "lookup", "arguments": "{}"},
            {"type": "function_call_output", "call_id": 7, "tool_call_id": "call_nonstring",
             "output": "baseline drops this unmatched pair"},
        ]
        orphan = [
            {"type": "message", "role": "user", "content": "question"},
            {"type": "function_call_output", "id": "orphan", "error": "synthetic failure",
             "future_field": "ignored"},
        ]
        invalid = [
            {"type": "message", "role": "user", "content": "question"},
            {"type": "function_call", "call_id": "call_blank", "name": "lookup", "arguments": "{}"},
            {"type": "function_call_output", "call_id": " ", "tool_call_id": "call_blank",
             "output": "still invalid"},
        ]
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for label, items in (("matched", matched), ("orphan", orphan)):
            for mode in ("auto", "anthropic", "openai_chat"):
                scenario = "buffered" if mode == "openai_chat" else "anthropic-buffered"
                request = {**base, "input": items}
                with self.subTest(history=label, mode=mode):
                    captures = [_run_mode(binary, request, scenario, mode) for binary in binaries]
                    requests = []
                    for result, response, upstream, state in captures:
                        self.assertEqual((result.returncode, response["status"]), (0, 200))
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(state["leftovers"], [])
                        requests.append((upstream[0]["path"], bytes.fromhex(upstream[0]["body"])))
                    expected_path = "/v1/chat/completions" if mode == "openai_chat" else "/anthropic/v1/messages"
                    self.assertEqual([path for path, _ in requests], [expected_path] * len(binaries))
                    expected_ids = ["call_primary", "call_tool_alias", "call_id_alias"] if label == "matched" else []
                    for _, request_body in requests:
                        body_text = request_body.decode()
                        self.assertNotIn("future_field", body_text)
                        messages = json.loads(request_body)["messages"]
                        if mode == "openai_chat":
                            results = [message for message in messages if message["role"] == "tool"]
                            result_ids = [message["tool_call_id"] for message in results]
                        else:
                            results = [block for message in messages for block in message.get("content", [])
                                       if block["type"] == "tool_result"]
                            result_ids = [block["tool_use_id"] for block in results]
                        self.assertEqual(result_ids, expected_ids)
                        if label == "matched":
                            self.assertNotIn("call_nonstring", body_text)
                            self.assertEqual(len(results), 3)

        for mode in ("auto", "anthropic", "openai_chat"):
            scenario = "buffered" if mode == "openai_chat" else "anthropic-buffered"
            request = {**base, "input": invalid}
            with self.subTest(history="blank primary", mode=mode):
                captures = [_run_mode(binary, request, scenario, mode) for binary in binaries]
                for result, response, upstream, state in captures:
                    self.assertEqual((result.returncode, response["status"]), (1, 502))
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                self.assertEqual(captures[1][1]["body"], captures[0][1]["body"])
                self.assertEqual(captures[2][1]["body"], captures[0][1]["body"])

    def test_malformed_matched_function_call_arguments_match_modes(self):
        request = {
            "model": "deepseek-chat",
            "stream": False,
            "tools": [SEARCH, FUNCTION],
            "input": [
                {"type": "message", "role": "user", "content": "question"},
                {"type": "function_call", "call_id": "call_lookup", "name": "lookup",
                 "arguments": "{malformed"},
                {"type": "function_call_output", "call_id": "call_lookup", "output": "result"},
            ],
        }
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for stream, scenario in ((False, "buffered"), (True, "stream")):
            streamed_request = {**request, "stream": stream}
            for mode in ("auto", "anthropic"):
                with self.subTest(stream=stream, mode=mode):
                    captures = [
                        _run_mode(binary, streamed_request, scenario, mode)
                        for binary in binaries
                    ]
                    for result, response, upstream, state in captures:
                        self.assertEqual((result.returncode, response["status"]), (1, 400))
                        self.assertEqual(upstream, [])
                        self.assertEqual(state["leftovers"], [])
                    self.assertEqual(captures[1][1]["body"], captures[0][1]["body"])
                    self.assertEqual(captures[2][1]["body"], captures[0][1]["body"])

            with self.subTest(stream=stream, mode="openai_chat"):
                captures = [
                    _run_mode(binary, streamed_request, scenario, "openai_chat")
                    for binary in binaries
                ]
                for result, response, upstream, state in captures:
                    self.assertEqual((result.returncode, response["status"]), (0, 200))
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    self.assertEqual(state["leftovers"], [])
                chat_bodies = [json.loads(bytes.fromhex(upstream[0]["body"]))
                               for _, _, upstream, _ in captures]
                self.assertEqual(chat_bodies[1:], chat_bodies[:1] * 2)
                self.assertEqual(
                    chat_bodies[0]["messages"][1]["tool_calls"][0]["function"]["arguments"],
                    "{malformed",
                )

    def test_streamed_text_parts_and_metadata_match_both_releases(self):
        request = {"model": "deepseek-chat", "input": [{
            "type": "message", "role": "user", "id": "synthetic-id",
            "content": [{"type": "input_text", "text": "alpha", "annotations": []},
                        {"type": "input_text", "text": "beta"}],
        }], "stream": True, "tools": [{"type": "web_search_preview"}]}
        results = [_run(binary, request, scenario="anthropic-stream")
                   for binary in (ORACLE_01651, ORACLE, MODEX)]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(len(result["upstream"]), 1)
            self.assertEqual(result["upstream_body"], results[0]["upstream_body"])
            self.assertEqual(_normalized_events(result["response_body"]),
                             _normalized_events(results[0]["response_body"]))
            self.assertEqual(result["state"]["leftovers"], [])

    def test_untyped_image_content_matches_both_releases(self):
        image = {"type": "input_image", "image_url": "https://example.test/synthetic-image"}
        for parts, status in (([image], 400), ([{"type": "input_text", "text": "text"}, image], 200)):
            request = {"model": "deepseek-chat", "input": [{"role": "user", "content": parts}],
                       "stream": False, "tools": [{"type": "web_search_preview"}]}
            results = [_run(binary, request, scenario="anthropic-buffered")
                       for binary in (ORACLE_01651, ORACLE, MODEX)]
            for result in results:
                self.assertEqual(result["status"], status)
                self.assertEqual(len(result["upstream"]), 1 if status == 200 else 0)
                self.assertEqual(result["state"]["leftovers"], [])
                if status == 200:
                    self.assertEqual(result["upstream_body"], results[0]["upstream_body"])
                    self.assertNotIn("synthetic-image", json.dumps(result["upstream_body"]))
                else:
                    self.assertEqual(result["response_body"], message_arrays.INVALID_REQUEST_BODY)

        request = {"model": "deepseek-chat", "input": [{"role": "user", "content": image}],
                   "stream": False, "tools": [{"type": "web_search_preview"}]}
        results = [_run(binary, request, scenario="anthropic-buffered")
                   for binary in (ORACLE_01651, ORACLE, MODEX)]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(result["upstream_body"], results[0]["upstream_body"])
            self.assertIn("synthetic-image", json.dumps(result["upstream_body"]))

    def test_blank_arrays_obey_web_search_modes(self):
        for name, items in (
            ("empty", []),
            ("mixed", [{"role": "user", "content": " "}, {"role": "user", "content": "query"}]),
        ):
            request = {"model": "deepseek-chat", "input": items, "stream": False,
                       "tools": [{"type": "web_search_preview"}]}
            for mode in ("auto", "anthropic", "openai_chat", "off"):
                with self.subTest(case=name, mode=mode):
                    expected = 502 if mode == "off" else 400 if name == "empty" and mode != "openai_chat" else 200
                    scenario = "anthropic-buffered" if mode in ("auto", "anthropic") else "buffered"
                    results = [_run_mode(binary, request, scenario, mode)
                               for binary in (ORACLE_01651, ORACLE, MODEX)]
                    for result, response, upstream, state in results:
                        self.assertEqual(response["status"], expected)
                        self.assertEqual(result.returncode, 0 if expected == 200 else 1)
                        self.assertEqual(len(upstream), 1 if expected == 200 else 0)
                        self.assertEqual(state["leftovers"], [])
                    if expected == 200:
                        bodies = [json.loads(bytes.fromhex(result[2][0]["body"])) for result in results]
                        self.assertEqual(bodies[1:], bodies[:1] * 2)
                    else:
                        bodies = [bytes.fromhex(result[1]["body"]) for result in results]
                        self.assertEqual(bodies[1:], bodies[:1] * 2)

    def test_blank_array_entries_in_streaming_requests(self):
        for items, expected in (([], 400), ([{"role": "user", "content": " "},
                                             {"role": "user", "content": "query"}], 200)):
            request = {"model": "deepseek-chat", "input": items, "stream": True,
                       "tools": [{"type": "web_search_preview"}]}
            captures = [_run_mode(binary, request, "anthropic-stream")
                        for binary in (ORACLE_01651, ORACLE, MODEX)]
            for result, response, upstream, state in captures:
                self.assertEqual(response["status"], expected)
                self.assertEqual(result.returncode, 0 if expected == 200 else 1)
                self.assertEqual(len(upstream), 1 if expected == 200 else 0)
                self.assertEqual(state["leftovers"], [])
            if expected == 200:
                bodies = [json.loads(bytes.fromhex(capture[2][0]["body"])) for capture in captures]
                self.assertEqual(bodies[1:], bodies[:1] * 2)
            else:
                bodies = [bytes.fromhex(capture[1]["body"]) for capture in captures]
                self.assertEqual(bodies[1:], bodies[:1] * 2)

    def test_blank_array_continuation_respects_binding(self):
        first = {"model": "deepseek-chat", "input": "query", "stream": False,
                 "tools": [{"type": "web_search_preview"}]}
        second = {"model": "deepseek-chat", "input": [{"role": "user", "content": " "}],
                  "stream": False, "tools": [{"type": "web_search_preview"}],
                  "use_previous": True}
        captures = [observe_turns(binary, [first, second], [_buffered_reply(), _buffered_reply()])
                    for binary in (ORACLE_01651, ORACLE, MODEX)]
        for posts, responses in captures:
            self.assertEqual([response["status"] for response in responses], [200, 503])
            self.assertEqual(len(posts), 1)
        errors = [bytes.fromhex(responses[1]["body"]) for _, responses in captures]
        self.assertEqual(errors[1:], errors[:1] * 2)

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

    def test_top_level_web_search_options_without_tool_match_both_releases(self):
        base = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "web_search_options": {
                "search_context_size": "low",
                "allowed_domains": ["example.test"],
            },
        }
        for stream, scenario in ((False, "anthropic-buffered"), (True, "anthropic-stream")):
            for tools in (None, []):
                with self.subTest(stream=stream, tools=tools):
                    request = {**base, "stream": stream}
                    if tools is not None:
                        request["tools"] = tools
                    captures = [
                        _run(binary, request, scenario=scenario)
                        for binary in (ORACLE_01651, ORACLE, MODEX)
                    ]
                    for capture in captures:
                        self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
                        self.assertEqual(len(capture["upstream"]), 1)
                        self.assertEqual(capture["upstream"][0]["path"], "/anthropic/v1/messages")
                        self.assertEqual(capture["state"]["leftovers"], [])
                    expected_body = captures[0]["upstream_body"]
                    self.assertEqual(expected_body["tools"], [{
                        "name": "web_search",
                        "type": "web_search_20250305",
                        "allowed_domains": ["example.test"],
                    }])
                    for capture in captures[1:]:
                        self.assertEqual(capture["upstream_body"], expected_body)
                        if stream:
                            self.assertEqual(_events(capture["response_body"]),
                                             _events(captures[0]["response_body"]))
                        else:
                            self.assertEqual(
                                _normalize(json.loads(capture["response_body"])),
                                _normalize(json.loads(captures[0]["response_body"])),
                            )

    def test_malformed_tools_and_top_level_web_search_options_fail_before_post(self):
        base = {"model": "deepseek-chat", "input": "synthetic query", "stream": False}
        cases = (
            ("null tools", {"tools": None, "web_search_options": {"search_context_size": "low"}}),
            ("object tools", {"tools": {}, "web_search_options": {"search_context_size": "low"}}),
            ("string tools", {"tools": "bad", "web_search_options": {"search_context_size": "low"}}),
            ("null options", {"web_search_options": None}),
            ("string options", {"web_search_options": "bad"}),
            ("invalid context", {"web_search_options": {"search_context_size": "instant"}}),
            ("invalid domain type", {"web_search_options": {"allowed_domains": "example.test"}}),
            ("false parallel calls", {"web_search_options": {"search_context_size": "low"},
                                       "parallel_tool_calls": False}),
        )
        for name, overrides in cases:
            with self.subTest(case=name):
                request = {**base, **overrides}
                captures = [
                    _run(binary, request, scenario="anthropic-buffered")
                    for binary in (ORACLE_01651, ORACLE, MODEX)
                ]
                for capture in captures:
                    self.assertEqual((capture["exit_code"], capture["status"]), (1, 502))
                    self.assertEqual(capture["upstream"], [])
                    self.assertEqual(capture["response_body"], b"upstream request failed")
                    self.assertEqual(capture["state"]["leftovers"], [])

    def test_parallel_tool_calls_true_is_accepted_and_omitted(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "parallel_tool_calls": True,
            "web_search_options": {"search_context_size": "low"},
        }
        captures = [
            _run(binary, request, scenario="anthropic-buffered")
            for binary in (ORACLE_01651, ORACLE, MODEX)
        ]
        for capture in captures:
            self.assertEqual((capture["exit_code"], capture["status"]), (0, 200))
            self.assertEqual(len(capture["upstream"]), 1)
            self.assertEqual(capture["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertNotIn("parallel_tool_calls", capture["upstream_body"])
            self.assertEqual(capture["state"]["leftovers"], [])
        self.assertEqual([capture["upstream_body"] for capture in captures[1:]],
                         [captures[0]["upstream_body"]] * 2)
        self.assertEqual([_normalize(json.loads(capture["response_body"]))
                          for capture in captures[1:]],
                         [_normalize(json.loads(captures[0]["response_body"]))] * 2)

    def test_untranslatable_web_option_falls_back_only_in_auto_mode(self):
        for stream, chat_scenario, anthropic_scenario in (
            (False, "buffered", "anthropic-buffered"),
            (True, "stream", "anthropic-stream"),
        ):
            request = {
                "model": "deepseek-chat",
                "input": "synthetic query",
                "stream": stream,
                "web_search_options": {
                    "search_context_size": "low",
                    "future_option": "synthetic ignored value",
                },
            }
            with self.subTest(stream=stream):
                auto = [
                    _run_mode(binary, request, chat_scenario, mode="auto")
                    for binary in (ORACLE_01651, ORACLE, MODEX)
                ]
                for result, response, upstream, state in auto:
                    self.assertEqual((result.returncode, response["status"]), (0, 200))
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    self.assertEqual(state["leftovers"], [])
                chat_bodies = [json.loads(bytes.fromhex(upstream[0]["body"]))
                               for _, _, upstream, _ in auto]
                self.assertEqual(chat_bodies[1:], chat_bodies[:1] * 2)
                self.assertNotIn("web_search_options", chat_bodies[0])
                self.assertNotIn("future_option", json.dumps(chat_bodies[0]))
                if stream:
                    responses = [_events(bytes.fromhex(response["body"]))
                                 for _, response, _, _ in auto]
                else:
                    responses = [_normalize(json.loads(bytes.fromhex(response["body"])))
                                 for _, response, _, _ in auto]
                self.assertEqual(responses[1:], responses[:1] * 2)

                forced = [
                    _run_mode(binary, request, anthropic_scenario, mode="anthropic")
                    for binary in (ORACLE_01651, ORACLE, MODEX)
                ]
                for result, response, upstream, state in forced:
                    self.assertEqual((result.returncode, response["status"]), (1, 400))
                    self.assertEqual(upstream, [])
                    self.assertEqual(bytes.fromhex(response["body"]), bytes.fromhex(forced[0][1]["body"]))
                    self.assertEqual(state["leftovers"], [])

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

    def test_buffered_text_only_shapes_match_both_releases(self):
        cases = (
            ("empty content", [], [], [], []),
            ("single text", [{"type": "text", "text": "previous reply"}],
             ["message"], ["previous reply"], []),
            ("empty text block", [{"type": "text", "text": ""}],
             ["message"], [""], []),
            ("multiple text blocks", [
                {"type": "text", "text": "first"},
                {"type": "text", "text": "second"},
            ], ["message"], ["first", "second"], []),
            ("thinking between text", [
                {"type": "text", "text": "before"},
                {"type": "thinking", "thinking": "synthetic reasoning"},
                {"type": "text", "text": "after"},
            ], ["message", "reasoning", "message"], ["before", "after"],
             ["synthetic reasoning"]),
        )
        for label, content, expected_types, expected_texts, expected_reasoning in cases:
            with self.subTest(case=label):
                captures = []
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    posts, responses = observe_turns(
                        binary, [_request()], [_buffered_reply(content, "end_turn")],
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(len(responses), 1)
                    self.assertEqual(responses[0]["status"], 200)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    result = _normalize(_json_body(responses[0]))
                    self.assertEqual([item["type"] for item in result["output"]], expected_types)
                    self.assertEqual([
                        part["text"]
                        for item in result["output"] if item["type"] == "message"
                        for part in item["content"]
                    ], expected_texts)
                    self.assertEqual([
                        item["summary"][0]["text"]
                        for item in result["output"] if item["type"] == "reasoning"
                    ], expected_reasoning)
                    captures.append((json.loads(posts[0]["body"]), result))
                self.assertEqual(captures[1:], captures[:1] * 2)

    def test_buffered_text_block_citations_and_extra_fields_match_both_releases(self):
        cases = (
            (
                "text-only citations and arbitrary fields",
                [
                    {"type": "text", "text": "before",
                     "citations": [{"type": "char_location", "cited_text": "before",
                                    "document_index": 0, "document_title": "Synthetic",
                                    "start_char_index": 0, "end_char_index": 6}],
                     "future_field": {"version": 2}},
                    {"type": "text", "text": " after", "citations": {"malformed": "shape"},
                     "future_field": [1, 2]},
                ],
                "end_turn",
                ["message"],
                ["before", " after"],
            ),
            (
                "web-search text with malformed citations",
                [
                    {"type": "server_tool_use", "id": "srv_citation", "name": "web_search",
                     "input": {"query": "synthetic"}},
                    {"type": "web_search_tool_result", "tool_use_id": "srv_citation",
                     "content": [{"type": "web_search_result",
                                  "url": "https://example.test/source",
                                  "title": "Synthetic source"}]},
                    {"type": "text", "text": "Search summary", "citations": "malformed",
                     "future_field": None},
                ],
                "end_turn",
                ["web_search_call", "message"],
                ["Search summary"],
            ),
            (
                "mixed tool and search blocks with unknown metadata",
                [
                    {"type": "server_tool_use", "id": "srv_metadata", "name": "web_search",
                     "input": {"query": "synthetic", "future_field": "ignored"},
                     "future_field": {"marker": "synthetic"}},
                    {"type": "web_search_tool_result", "tool_use_id": "srv_metadata",
                     "content": [{"type": "web_search_result",
                                  "url": "https://example.test/source",
                                  "title": "Synthetic source",
                                  "future_field": "ignored"}],
                     "future_field": "ignored"},
                    {"type": "text", "text": "Search summary", "future_field": "ignored"},
                    {"type": "tool_use", "id": "call_metadata", "name": "lookup",
                     "input": {"query": "synthetic"}, "future_field": "ignored"},
                ],
                "tool_use",
                ["web_search_call", "message", "function_call"],
                ["Search summary"],
            ),
            (
                "tool-use text with extra fields",
                [
                    {"type": "text", "text": "Before call", "citations": 7,
                     "future_field": "ignored"},
                    {"type": "tool_use", "id": "call_citation", "name": "lookup",
                     "input": {"query": "synthetic"}},
                ],
                "tool_use",
                ["message", "function_call"],
                ["Before call"],
            ),
        )
        for label, content, stop_reason, expected_types, expected_texts in cases:
            with self.subTest(case=label):
                captures = []
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    posts, responses = observe_turns(
                        binary, [_request()], [_buffered_reply(content, stop_reason)],
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(len(responses), 1)
                    self.assertEqual(responses[0]["status"], 200)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    headers = {name.lower(): value for name, value in posts[0]["headers"].items()}
                    self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
                    self.assertEqual(headers["anthropic-version"], "2023-06-01")
                    result = _normalize(_json_body(responses[0]))
                    self.assertEqual([item["type"] for item in result["output"]], expected_types)
                    self.assertEqual([
                        part["text"]
                        for item in result["output"] if item["type"] == "message"
                        for part in item["content"]
                    ], expected_texts)
                    self.assertNotIn("citations", json.dumps(result))
                    self.assertNotIn("future_field", json.dumps(result))
                    captures.append((json.loads(posts[0]["body"]), result))
                self.assertEqual(captures[1:], captures[:1] * 2)

    def test_buffered_search_query_shapes_match_both_releases(self):
        query_shapes = (
            ("array filters nonstrings", {"queries": ["first", 7, "", None, "last"],
                                            "future_field": "ignored"}, ["first", "", "last"]),
            ("invalid singular query falls back to array", {"query": 7,
                                                              "queries": ["fallback", False]},
             ["fallback"]),
            ("singular query takes precedence", {"query": "single", "queries": ["ignored"]},
             ["single"]),
            ("empty singular query takes precedence", {"query": "", "queries": ["ignored"]},
             [""]),
            ("missing input", None, []),
            ("missing query fields", {}, []),
        )
        content = []
        expected_queries = []
        for index, (label, search_input, expected) in enumerate(query_shapes):
            search_id = f"srv_query_{index}"
            search = {"type": "server_tool_use", "id": search_id, "name": "web_search",
                      "future_field": label}
            if search_input is not None:
                search["input"] = search_input
            content.extend((
                search,
                {"type": "web_search_tool_result", "tool_use_id": search_id,
                 "content": [], "future_field": "ignored"},
            ))
            expected_queries.append(expected)
        content.extend((
            {"type": "text", "text": "done"},
            {"type": "tool_use", "id": "call_query_shapes", "name": "lookup", "input": {}},
        ))
        captures = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [_request()], [_buffered_reply(content)])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 200)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            response = _normalize(_json_body(responses[0]))
            searches = [item for item in response["output"] if item["type"] == "web_search_call"]
            self.assertEqual([item["action"]["queries"] for item in searches], expected_queries)
            self.assertNotIn("future_field", json.dumps(response))
            captures.append((json.loads(posts[0]["body"]), response))
        self.assertEqual(captures[1:], captures[:1] * 2)

        malformed = _buffered_reply([
            {"type": "tool_use", "name": "lookup", "input": {},
             "future_field": "synthetic"},
        ])
        outcomes = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [_request()], [malformed])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 502)
            outcomes.append((posts[0]["path"], responses[0]["status"],
                             bytes.fromhex(responses[0]["body"])))
        self.assertEqual(outcomes[1:], outcomes[:1] * 2)

    def test_stream_search_query_shapes_and_metadata_match_both_releases(self):
        reply = _stream([
            {"type": "ping", "future_field": "synthetic"},
            {"type": "message_start", "message": {
                "id": "msg_stream_metadata", "model": "deepseek-chat",
                "usage": {"input_tokens": 3, "future_field": "ignored"},
                "future_field": "ignored",
            }, "future_event": "ignored"},
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "server_tool_use", "id": "srv_stream_metadata", "name": "web_search",
                "input": {"queries": ["first", 7, "", None, "last"],
                           "future_field": "ignored"},
                "future_field": "ignored",
            }, "future_event": "ignored"},
            {"type": "content_block_stop", "index": 0, "future_event": "ignored"},
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "web_search_tool_result", "tool_use_id": "srv_stream_metadata",
                "content": [{"type": "web_search_result",
                             "url": "https://example.test/source",
                             "title": "Synthetic source",
                             "future_field": "ignored"}],
                "future_field": "ignored",
            }, "future_event": "ignored"},
            {"type": "content_block_stop", "index": 1, "future_event": "ignored"},
            {"type": "content_block_start", "index": 2, "content_block": {
                "type": "text", "future_field": "ignored",
            }, "future_event": "ignored"},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "text_delta", "text": "done", "future_field": "ignored",
            }, "future_event": "ignored"},
            {"type": "content_block_stop", "index": 2, "future_event": "ignored"},
            {"type": "message_delta", "delta": {
                "stop_reason": "end_turn", "future_field": "ignored",
            }, "usage": {"output_tokens": 5, "future_field": "ignored"},
                "future_event": "ignored"},
            {"type": "message_stop", "future_event": "ignored"},
        ])
        request = _request(stream=True)
        captures = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 200)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            events = _events(bytes.fromhex(responses[0]["body"]))
            self.assertEqual(events[-1][0], "response.completed")
            searches = [item for item in events[-1][1]["response"]["output"]
                        if item["type"] == "web_search_call"]
            self.assertEqual(searches[0]["action"]["queries"], ["first", 7, "", None, "last"])
            self.assertEqual([event["delta"] for name, event in events
                              if name == "response.output_text.delta"], ["done"])
            self.assertNotIn("future_field", json.dumps(events))
            captures.append((json.loads(posts[0]["body"]), events))
        self.assertEqual(captures[1:], captures[:1] * 2)

    def test_stream_missing_function_id_uses_release_fallback(self):
        reply = _stream([
            {"type": "message_start", "message": {}},
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "tool_use", "name": "lookup", "future_field": "synthetic",
            }, "future_event": "synthetic"},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": "{}", "future_field": "synthetic",
            }, "future_event": "synthetic"},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {}},
            {"type": "message_stop", "future_event": "synthetic"},
        ])
        captures = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [_request(stream=True)], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 200)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            events = _events(bytes.fromhex(responses[0]["body"]))
            self.assertEqual(events[-1][0], "response.completed")
            call = next(item for item in events[-1][1]["response"]["output"]
                        if item["type"] == "function_call")
            self.assertEqual(call["call_id"], "<generated-id>")
            self.assertEqual(call["arguments"], "{}")
            self.assertNotIn("future_field", json.dumps(events))
            captures.append((json.loads(posts[0]["body"]), events))
        self.assertEqual(captures[1:], captures[:1] * 2)

    def test_stream_nonstring_function_argument_fragments_match_releases(self):
        request = _request(stream=True)
        cases = (
            ("number", {"partial_json": 3}),
            ("null", {"partial_json": None}),
            ("missing", {}),
            ("boolean", {"partial_json": True}),
            ("object", {"partial_json": {"synthetic": True}}),
        )
        for name, fields in cases:
            with self.subTest(fragment=name):
                reply = _stream([
                    {"type": "message_start", "message": {}},
                    {"type": "content_block_start", "index": 0, "content_block": {
                        "type": "tool_use", "id": "call_nonstring", "name": "lookup",
                    }},
                    {"type": "content_block_delta", "index": 0, "delta": {
                        "type": "input_json_delta", "future_field": "ignored", **fields,
                    }},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {}},
                    {"type": "message_stop"},
                ])
                releases = []
                for binary in (ORACLE_01651, ORACLE):
                    posts, responses = observe_turns(binary, [request], [reply])
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(responses[0]["status"], 200)
                    events = _events(bytes.fromhex(responses[0]["body"]))
                    self.assertEqual(events[-1][0], "response.completed")
                    call = next(item for item in events[-1][1]["response"]["output"]
                                if item["type"] == "function_call")
                    self.assertEqual(call["arguments"], "")
                    releases.append((json.loads(posts[0]["body"]), events))
                self.assertEqual(releases[1], releases[0])

                posts, responses = observe_turns(MODEX, [request], [reply])
                self.assertEqual(len(posts), 1)
                self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                self.assertEqual(responses[0]["status"], 200)
                events = _events(bytes.fromhex(responses[0]["body"]))
                self.assertEqual((json.loads(posts[0]["body"]), events), releases[0])
                call = next(item for item in events[-1][1]["response"]["output"]
                            if item["type"] == "function_call")
                self.assertEqual(call["arguments"], "")

    def test_buffered_envelope_extensions_and_usage_normalization_match_releases(self):
        cases = (
            (
                "envelope and usage extensions",
                {
                    "type": "future_message",
                    "role": 7,
                    "stop_sequence": None,
                    "context_management": {"applied_edits": []},
                    "tool_usage": {"web_search": {"num_requests": 99}},
                    "future_field": "ignored",
                },
                {
                    "input_tokens": 3,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 4,
                    "cache_read_input_tokens": 2,
                    "server_tool_use": {"web_search_requests": 7, "future_field": True},
                },
                (),
                {
                    "id": "msg_mixed",
                    "model": "deepseek-chat",
                    "usage": {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
                    "tool_usage": {"web_search": {"num_requests": 7}},
                    "metadata": {"anthropic": {"stop_reason": "end_turn"}},
                },
            ),
            (
                "invalid id, model, and usage counters normalize",
                {"id": 7, "model": None, "type": None, "role": "user"},
                {
                    "input_tokens": "3",
                    "output_tokens": None,
                    "server_tool_use": {"web_search_requests": "7"},
                },
                ("stop_reason",),
                {
                    "id": "resp_anthropic",
                    "model": "unknown",
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                },
            ),
            (
                "missing usage and stop reason",
                {},
                None,
                ("usage", "stop_reason"),
                {"id": "msg_mixed", "model": "deepseek-chat"},
            ),
            (
                "non-object usage is omitted",
                {},
                "future usage shape",
                (),
                {
                    "id": "msg_mixed",
                    "model": "deepseek-chat",
                    "metadata": {"anthropic": {"stop_reason": "end_turn"}},
                },
            ),
            (
                "content must remain an array",
                {},
                {"input_tokens": 3, "output_tokens": 5},
                (),
                None,
            ),
        )
        for label, envelope_fields, usage, removed, expected in cases:
            with self.subTest(case=label):
                captures = []
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    reply = _buffered_reply([{"type": "text", "text": "Synthetic response"}], "end_turn")
                    payload = json.loads(reply["body"])
                    payload.update(envelope_fields)
                    if usage is not None:
                        payload["usage"] = usage
                    for field in removed:
                        payload.pop(field)
                    if expected is None:
                        payload["content"] = "not an array"
                    reply["body"] = json.dumps(payload, separators=(",", ":")).encode()
                    posts, responses = observe_turns(binary, [_request()], [reply])
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(len(responses), 1)
                    if expected is None:
                        self.assertEqual(responses[0]["status"], 502)
                        self.assertEqual(bytes.fromhex(responses[0]["body"]),
                                         b"provider response could not be processed")
                        captures.append((json.loads(posts[0]["body"]), responses[0]["status"],
                                         bytes.fromhex(responses[0]["body"])))
                        continue
                    self.assertEqual(responses[0]["status"], 200)
                    response = _normalize(_json_body(responses[0]))
                    for key, value in expected.items():
                        self.assertEqual(response.get(key), value, key)
                    self.assertNotIn("stop_sequence", response)
                    self.assertNotIn("context_management", response)
                    self.assertNotIn("future_field", json.dumps(response))
                    captures.append((json.loads(posts[0]["body"]), response))
                self.assertEqual(captures[1:], captures[:1] * 2)

    def test_buffered_text_only_malformed_shapes_still_fail_closed(self):
        cases = (
            ("missing text", [{"type": "text"}]),
            ("missing text with citations", [{"type": "text", "citations": [{"type": "char_location"}]}]),
            ("non-string text", [{"type": "text", "text": 7}]),
            ("non-string text with citations", [{"type": "text", "text": 7, "citations": "malformed"}]),
            ("unsupported block", [{"type": "future_block"}]),
        )
        for label, content in cases:
            with self.subTest(case=label):
                captures = []
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    posts, responses = observe_turns(
                        binary, [_request()], [_buffered_reply(content, "end_turn")],
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(len(responses), 1)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(responses[0]["status"], 502)
                    self.assertEqual(bytes.fromhex(responses[0]["body"]),
                                     b"provider response could not be processed")
                    captures.append((json.loads(posts[0]["body"]), responses[0]["status"],
                                     bytes.fromhex(responses[0]["body"])))
                self.assertEqual(captures[1:], captures[:1] * 2)

    def test_buffered_thinking_blocks_match_release(self):
        cases = (
            (
                "search with UTF-8, empty, and non-string reasoning",
                [
                    {"type": "server_tool_use", "id": "srv_thinking", "name": "web_search",
                     "input": {"query": "release"}},
                    {"type": "thinking", "thinking": "Café 🧠\nSynthetic reasoning",
                     "signature": "synthetic signature"},
                    {"type": "web_search_tool_result", "tool_use_id": "srv_thinking",
                     "content": [{"type": "web_search_result",
                                  "url": "https://example.test/release"}]},
                    {"type": "thinking", "thinking": ""},
                    {"type": "thinking", "thinking": 7},
                    {"type": "text", "text": "Found it."},
                ],
                "end_turn",
                ["web_search_call", "reasoning", "reasoning", "message"],
                ["Café 🧠\nSynthetic reasoning", ""],
            ),
            (
                "repeated reasoning interleaves with search and function calls",
                [
                    {"type": "text", "text": "Before."},
                    {"type": "thinking", "thinking": "First thought."},
                    {"type": "server_tool_use", "id": "srv_first", "name": "web_search",
                     "input": {"query": "first"}},
                    {"type": "tool_use", "id": "call_first", "name": "lookup",
                     "input": {"query": "first"}},
                    {"type": "thinking", "thinking": "Second thought."},
                    {"type": "web_search_tool_result", "tool_use_id": "srv_first",
                     "content": [{"type": "web_search_result",
                                  "url": "https://example.test/first"}]},
                    {"type": "server_tool_use", "id": "srv_second", "name": "web_search",
                     "input": {"query": "second"}},
                    {"type": "thinking", "thinking": False},
                    {"type": "text", "text": "Middle."},
                    {"type": "tool_use", "id": "call_second", "name": "lookup",
                     "input": {"query": "second"}},
                    {"type": "web_search_tool_result", "tool_use_id": "srv_second",
                     "content": [{"type": "web_search_result",
                                  "url": "https://example.test/second"}]},
                    {"type": "thinking", "thinking": "Third thought."},
                    {"type": "text", "text": "After."},
                ],
                "tool_use",
                ["message", "reasoning", "web_search_call", "function_call",
                 "reasoning", "web_search_call", "message", "function_call",
                 "reasoning", "message"],
                ["First thought.", "Second thought.", "Third thought."],
            ),
            (
                "missing and non-string reasoning separate text messages",
                [
                    {"type": "text", "text": "Before."},
                    {"type": "thinking", "thinking": False},
                    {"type": "text", "text": "Middle."},
                    {"type": "thinking"},
                    {"type": "text", "text": "After."},
                    {"type": "tool_use", "id": "call_lookup", "name": "lookup",
                     "input": {"query": "release"}},
                ],
                "tool_use",
                ["message", "message", "message", "function_call"],
                [],
            ),
            (
                "ordinary response control has no reasoning",
                None,
                "tool_use",
                ["message", "web_search_call", "function_call", "message"],
                [],
            ),
        )
        for label, content, stop_reason, expected_types, expected_reasoning in cases:
            with self.subTest(case=label):
                request = _request()
                reply = _buffered_reply(content, stop_reason)
                captures = []
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    posts, responses = observe_turns(binary, [request], [reply])
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(len(responses), 1)
                    self.assertEqual(responses[0]["status"], 200)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    headers = {name.lower(): value for name, value in posts[0]["headers"].items()}
                    self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
                    self.assertEqual(headers["anthropic-version"], "2023-06-01")
                    captures.append((json.loads(posts[0]["body"]),
                                     _normalize(_json_body(responses[0]))))
                self.assertEqual(captures[1:], captures[:1] * 2)
                self.assertEqual([item["type"] for item in captures[0][1]["output"]],
                                 expected_types)
                self.assertEqual([
                    item["summary"][0]["text"]
                    for item in captures[0][1]["output"]
                    if item["type"] == "reasoning"
                ], expected_reasoning)

    def test_thinking_support_keeps_tool_use_validation(self):
        reply = _buffered_reply([
            {"type": "thinking", "thinking": "Synthetic reasoning"},
            {"type": "tool_use", "id": "call_missing_name", "input": {}},
        ])
        captures = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [_request()], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            captures.append((json.loads(posts[0]["body"]), responses[0]["status"],
                             bytes.fromhex(responses[0]["body"])))
        self.assertEqual(captures[1:], captures[:1] * 2)
        self.assertEqual(captures[0][1], 502)

    def test_reasoning_response_continuation_matches_unavailable_boundary(self):
        first = _request()
        first["input"] = "Synthetic first turn"
        second = {
            "model": "deepseek-chat",
            "input": [
                {"type": "function_call_output", "call_id": "call_lookup",
                 "output": "synthetic result"},
                {"type": "message", "role": "user", "content": "Continue synthetically."},
            ],
            "stream": False,
            "tools": _request()["tools"],
            "use_previous": True,
        }
        replies = [
            _buffered_reply([
                {"type": "thinking", "thinking": "Synthetic retained reasoning"},
                {"type": "tool_use", "id": "call_lookup", "name": "lookup",
                 "input": {"query": "first"}},
            ], "tool_use"),
            _buffered_reply([
                {"type": "server_tool_use", "id": "srv_next", "name": "web_search",
                 "input": {"query": "second"}},
                {"type": "web_search_tool_result", "tool_use_id": "srv_next", "content": []},
                {"type": "text", "text": "Second turn done."},
            ], "end_turn"),
        ]
        captures = []
        for binary in (ORACLE_01651, ORACLE, MODEX):
            posts, responses = observe_turns(binary, [first, second], replies)
            self.assertEqual([response["status"] for response in responses], [200, 503])
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            self.assertEqual(
                [item["type"] for item in _json_body(responses[0])["output"]],
                ["reasoning", "function_call"],
            )
            captures.append((json.loads(posts[0]["body"]),
                             bytes.fromhex(responses[1]["body"])))
        self.assertEqual(captures[1:], captures[:1] * 2)
        self.assertEqual(captures[0][1], b'{"error":{"code":"bound_continuation_unavailable","message":"bound continuation provider is unavailable"}}')

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

    def test_web_search_options_project_like_both_releases(self):
        cases = [
            ("missing", {}),
            ("allowed domains empty", {"allowed_domains": []}),
            ("blocked domains empty", {"blocked_domains": []}),
            ("blocked domains", {"blocked_domains": ["blocked.example"]}),
            ("max uses minimum", {"max_uses": 1}),
            ("max uses maximum", {"max_uses": 18446744073709551615}),
            ("empty location", {"user_location": {}}),
            ("location fields", {
                "user_location": {
                    "type": "approximate",
                    "city": "Jakarta",
                    "region": "Jakarta",
                    "country": "ID",
                    "timezone": "Asia/Jakarta",
                    "synthetic_extension": "preserved",
                },
            }),
            ("context low", {"search_context_size": "low"}),
            ("context medium", {"search_context_size": "medium"}),
            ("context high", {"search_context_size": "high"}),
        ]
        for name, options in cases:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic web query",
                "stream": False,
                "tools": [{"type": "web_search_preview", **options}],
            }
            with self.subTest(case=name):
                results = [
                    _run(binary, request, scenario="anthropic-buffered")
                    for binary in (ORACLE_01651, ORACLE, MODEX)
                ]
                expected = results[0]
                expected_options = {
                    key: value for key, value in options.items()
                    if key != "search_context_size"
                }
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(result["upstream_body"], expected["upstream_body"])
                    self.assertEqual(result["upstream_body"]["tools"][-1]["type"], "web_search_20250305")
                    web_search = result["upstream_body"]["tools"][-1]
                    self.assertEqual(
                        {key: web_search[key] for key in expected_options},
                        expected_options,
                    )
                    self.assertNotIn("search_context_size", web_search)
                    self.assertEqual(result["state"]["leftovers"], [])

    def test_streamed_web_search_options_match_both_releases(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic streamed web query",
            "stream": True,
            "tools": [{
                "type": "web_search_preview",
                "blocked_domains": ["blocked.example"],
                "max_uses": 2,
                "user_location": {
                    "type": "approximate",
                    "city": "Jakarta",
                    "country": "ID",
                },
                "search_context_size": "high",
            }],
        }
        results = [
            _run(binary, request, scenario="anthropic-stream")
            for binary in (ORACLE_01651, ORACLE, MODEX)
        ]
        expected = results[0]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(len(result["upstream"]), 1)
            self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
            self.assertEqual(result["upstream_body"], expected["upstream_body"])
            self.assertEqual(
                _normalized_events(result["response_body"]),
                _normalized_events(expected["response_body"]),
            )
            self.assertEqual(result["state"]["leftovers"], [])
        web_search = expected["upstream_body"]["tools"][-1]
        self.assertEqual(web_search["blocked_domains"], ["blocked.example"])
        self.assertEqual(web_search["max_uses"], 2)
        self.assertEqual(web_search["user_location"], request["tools"][0]["user_location"])
        self.assertNotIn("search_context_size", web_search)

    def test_invalid_web_search_options_fail_before_provider_post(self):
        cases = [
            ("allowed domains wrong type", {"allowed_domains": "allowed.example"}),
            ("blocked domain empty item", {"blocked_domains": [""]}),
            ("max uses zero", {"max_uses": 0}),
            ("max uses negative", {"max_uses": -1}),
            ("max uses fraction", {"max_uses": 1.5}),
            ("max uses string", {"max_uses": "2"}),
            ("max uses null", {"max_uses": None}),
            ("max uses overflow", {"max_uses": 18446744073709551616}),
            ("location wrong type", {"user_location": []}),
            ("location null", {"user_location": None}),
            ("context empty", {"search_context_size": ""}),
            ("context unknown", {"search_context_size": "extreme"}),
            ("context wrong type", {"search_context_size": 1}),
            ("context null", {"search_context_size": None}),
        ]
        for name, options in cases:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic web query",
                "stream": False,
                "tools": [{"type": "web_search_preview", **options}],
            }
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(case=name, binary=binary.name):
                    result = _run(binary, request, scenario="anthropic-buffered")
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])

    def test_conflicting_search_filters_fall_back_only_in_auto_mode(self):
        binaries = (ORACLE_01651, ORACLE, MODEX)
        requests = (
            {
                "model": "deepseek-chat",
                "input": "synthetic web query",
                "stream": False,
                "tools": [{
                    "type": "web_search_preview",
                    "allowed_domains": [],
                    "blocked_domains": [],
                }],
            },
            {
                "model": "deepseek-chat",
                "input": "synthetic web query",
                "stream": False,
                "web_search_options": {
                    "allowed_domains": [],
                    "blocked_domains": [],
                },
            },
        )
        for request in requests:
            with self.subTest(fields=tuple(key for key in request if key not in ("model", "input", "stream"))):
                for mode in ("auto", "openai_chat", "off", "anthropic"):
                    with self.subTest(mode=mode):
                        observed = [
                            _run_mode(binary, request, "buffered", mode)
                            for binary in binaries
                        ]
                        for result, response, upstream, state in observed:
                            if mode in ("auto", "openai_chat"):
                                self.assertEqual(result.returncode, 0)
                                self.assertIsNotNone(response)
                                self.assertEqual(response["status"], 200)
                                self.assertEqual(len(upstream), 1)
                                self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                                body = json.loads(bytes.fromhex(upstream[0]["body"]))
                                expected_body = {
                                    "messages": [{"content": "synthetic web query", "role": "user"}],
                                    "model": "deepseek-chat", "stream": False,
                                }
                                if mode == "openai_chat":
                                    expected_body["web_search_options"] = {
                                        "allowed_domains": [], "blocked_domains": [],
                                    }
                                self.assertEqual(body, expected_body)
                            elif mode == "off":
                                self.assertEqual(result.returncode, 1)
                                self.assertIsNotNone(response)
                                self.assertEqual(response["status"], 502)
                                self.assertEqual(bytes.fromhex(response["body"]), b"upstream request failed")
                                self.assertEqual(upstream, [])
                            else:
                                self.assertEqual(result.returncode, 1)
                                self.assertIsNotNone(response)
                                self.assertEqual(response["status"], 400)
                                self.assertEqual(
                                    bytes.fromhex(response["body"]),
                                    b'{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}',
                                )
                                self.assertEqual(upstream, [])
                            self.assertEqual(state["leftovers"], [])

    def test_conflict_fallback_preserves_input_and_option_validation(self):
        cases = (
            ("empty input", "", {}),
            ("invalid domains", "synthetic web query", {"allowed_domains": "bad"}),
            ("invalid location", "synthetic web query", {"user_location": []}),
            ("invalid max uses", "synthetic web query", {"max_uses": 0}),
            ("invalid context size", "synthetic web query", {"search_context_size": "extreme"}),
        )
        for name, content, extra in cases:
            request = {
                "model": "deepseek-chat",
                "input": content,
                "stream": False,
                "tools": [{
                    "type": "web_search_preview",
                    "allowed_domains": [],
                    "blocked_domains": [],
                    **extra,
                }],
            }
            with self.subTest(case=name):
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    result, response, upstream, state = _run_mode(binary, request, "buffered")
                    expected_status = 400 if name == "empty input" else 502
                    self.assertEqual(result.returncode, 1)
                    self.assertIsNotNone(response)
                    self.assertEqual(response["status"], expected_status)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])

    def test_conflict_fallback_preserves_history_and_strict_tools_route(self):
        request = {
            "model": "deepseek-chat",
            "input": [
                {"type": "message", "role": "user", "content": "synthetic first turn"},
                {"type": "message", "role": "assistant", "content": "synthetic prior answer"},
                {"type": "message", "role": "user", "content": "synthetic current turn"},
            ],
            "stream": False,
            "tools": [
                {"type": "web_search_preview", "allowed_domains": [], "blocked_domains": []},
                FUNCTION,
            ],
        }
        results = [
            _run_mode(binary, request, "buffered", strict_tools=True)
            for binary in (ORACLE_01651, ORACLE, MODEX)
        ]
        expected = json.loads(bytes.fromhex(results[0][2][0]["body"]))
        self.assertEqual(expected["messages"], [
            {"content": "synthetic first turn", "role": "user"},
            {"content": "synthetic prior answer", "role": "assistant"},
            {"content": "synthetic current turn", "role": "user"},
        ])
        self.assertEqual(len(expected["tools"]), 1)
        self.assertEqual(expected["tools"][0]["function"]["name"], "lookup")
        self.assertNotIn("web_search_options", expected)
        for result, response, upstream, state in results:
            self.assertEqual((result.returncode, response["status"]), (0, 200))
            self.assertEqual(len(upstream), 1)
            self.assertEqual(upstream[0]["path"], "/beta/chat/completions")
            self.assertEqual(json.loads(bytes.fromhex(upstream[0]["body"])), expected)
            self.assertEqual(state["leftovers"], [])

    def test_auto_conflict_duplicate_keys_fall_back_and_malformed_json_stops(self):
        duplicate = (
            b'{"model":"deepseek-chat","input":"synthetic web query","stream":false,'
            b'"tools":[{"type":"web_search_preview","allowed_domains":["first.example"],'
            b'"allowed_domains":[],"blocked_domains":[]}]} '
        )
        malformed = (
            b'{"model":"deepseek-chat","input":"synthetic web query","stream":false,'
            b'"tools":[{"type":"web_search_preview","allowed_domains":[],"blocked_domains":[]}'
        )
        results = [
            _run_mode(binary, {}, "buffered", "auto", raw_request=duplicate)
            for binary in (ORACLE_01651, ORACLE, MODEX)
        ]
        for result, response, upstream, state in results:
            self.assertEqual((result.returncode, response["status"]), (0, 200))
            self.assertEqual(len(upstream), 1)
            self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
            self.assertEqual(json.loads(bytes.fromhex(upstream[0]["body"])), {
                "messages": [{"content": "synthetic web query", "role": "user"}],
                "model": "deepseek-chat", "stream": False,
            })
            self.assertEqual(state["leftovers"], [])
        results = [
            _run_mode(binary, {}, "buffered", "auto", raw_request=malformed)
            for binary in (ORACLE_01651, ORACLE, MODEX)
        ]
        for result, response, upstream, state in results:
            self.assertEqual((result.returncode, response["status"]), (1, 502))
            self.assertEqual(bytes.fromhex(response["body"]), b"upstream request failed")
            self.assertEqual(upstream, [])
            self.assertEqual(state["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
