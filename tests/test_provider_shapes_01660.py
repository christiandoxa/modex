"""Synthetic provider request and stream shape comparisons with Prodex 0.166.0."""

import hashlib
import json
import re
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes


def _stream_reply(chunks):
    body = b"".join(b"data: " + json_bytes(chunk) + b"\n\n" for chunk in chunks)
    return {"status": 200, "content_type": "text/event-stream",
            "body": body + b"data: [DONE]\n\n"}


def _stream_events(body):
    events = []
    for line in body.splitlines():
        if not line.startswith(b"data: "):
            continue
        event = json.loads(line[6:])
        events.append(_normalize_generated_item_ids(event))
    return events


def _normalize_generated_item_ids(value):
    if isinstance(value, list):
        return [_normalize_generated_item_ids(item) for item in value]
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if (key == "id" and isinstance(item, str)
                    and re.fullmatch(r"msg_deepseek_[0-9]+", item)):
                normalized[key] = "msg_deepseek_ID"
            else:
                normalized[key] = _normalize_generated_item_ids(item)
        return normalized
    return value


REQUEST_TURNS = [
    {"model": "deepseek-chat", "input": ""},
    {"model": "deepseek-chat", "input": [
        {"role": "developer", "content": "synthetic policy"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "synthetic question"},
    ]},
    {"model": "deepseek-chat", "input": [{
        "type": "message", "role": "user",
        "content": [{"type": "input_text", "text": "synthetic rich input"}],
    }]},
    {"model": "deepseek-chat", "input": [{
        "type": "function_call_output", "call_id": "call_synthetic",
        "output": "synthetic result",
    }]},
    {"model": "deepseek-chat", "input": "synthetic optional",
     "temperature": 0.25, "top_p": 0.75, "max_output_tokens": 37,
     "logprobs": True, "top_logprobs": 2, "stop": ["END", "STOP"],
     "user_id": "synthetic-user"},
    {"model": "deepseek-chat", "input": "synthetic schema",
     "text": {"format": {"type": "json_schema", "name": "synthetic",
                           "schema": {"type": "object", "properties": {
                               "ok": {"type": "boolean"}}}}}},
    {"model": "deepseek-chat", "input": "synthetic metadata",
     "metadata": {"local_tag": "synthetic-tag",
                  "deepseek": {"trace": "synthetic-trace"}}},
    {"model": "deepseek-chat", "input": "synthetic function",
     "tools": [{"type": "function", "name": "lookup",
                "description": "synthetic description",
                "parameters": {"type": "object", "properties": {
                    "q": {"type": "string"}}}}],
     "tool_choice": {"type": "function", "name": "lookup"}},
]


STREAM_CHUNKS = [
    ("empty choices", [{"id": "chatcmpl_fixed_0", "model": "deepseek-chat",
                        "created": 42, "choices": []}]),
    ("two choices", [{"id": "chatcmpl_fixed_1", "model": "deepseek-chat",
                       "created": 42, "choices": [
                           {"index": 0, "delta": {"content": "first"},
                            "finish_reason": None},
                           {"index": 1, "delta": {"content": "second"},
                            "finish_reason": "stop"},
                       ]}]),
    ("wrong-type content", [
        {"id": "chatcmpl_fixed_2", "model": "deepseek-chat", "created": 42,
         "choices": [{"index": 0, "delta": {"content": 7}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]),
    ("reasoning then text", [
        {"id": "chatcmpl_fixed_3", "model": "deepseek-chat", "created": 42,
         "choices": [{"index": 0, "delta": {"reasoning_content": "think"},
                      "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": "answer"},
                      "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]),
    ("finish without content", [{"id": "chatcmpl_fixed_4", "model": "deepseek-chat",
                                 "created": 42,
                                 "choices": [{"index": 0, "delta": {},
                                              "finish_reason": "stop"}]}]),
    ("missing choices", [{"id": "chatcmpl_fixed_5", "model": "deepseek-chat",
                          "created": 42}]),
    ("usage after finish", [
        {"id": "chatcmpl_fixed_6", "model": "deepseek-chat", "created": 42,
         "choices": [{"index": 0, "delta": {"content": "x"},
                      "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 1,
                                   "completion_tokens": 2, "total_tokens": 3}},
    ]),
]


class ProviderShapes01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (not ORACLE.is_file()
                or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_responses_requests_match_active_provider_bodies(self):
        replies = [buffered_reply(index) for index in range(len(REQUEST_TURNS))]
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, REQUEST_TURNS, replies, latest_version="0.166.0",
            )
            self.assertEqual([row["status"] for row in responses], [200] * len(REQUEST_TURNS))
            self.assertEqual(len(upstream), len(REQUEST_TURNS))
            self.assertEqual([row["path"] for row in upstream],
                             ["/v1/chat/completions"] * len(REQUEST_TURNS))
            self.assertEqual([row["headers"]["authorization"] for row in upstream],
                             ["Bearer " + SYNTHETIC_API_KEY] * len(REQUEST_TURNS))
            provider_responses = [
                json.loads(bytes.fromhex(row["body"])) for row in responses
            ]
            for response in provider_responses:
                response.pop("created_at", None)
            metadata = provider_responses[6].get("metadata", {})
            self.assertEqual(metadata.get("local_tag"), "synthetic-tag")
            self.assertEqual(metadata.get("deepseek", {}).get("trace"), "synthetic-trace")
            observations.append((
                [row["body"] for row in upstream],
                provider_responses,
            ))
        self.assertEqual(observations[1], observations[0])

    def test_chat_stream_response_shapes_match_active_release(self):
        turns = [{"model": "deepseek-chat", "input": "synthetic stream matrix",
                  "stream": True} for _ in STREAM_CHUNKS]
        replies = [_stream_reply(chunks) for _, chunks in STREAM_CHUNKS]
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, turns, replies, latest_version="0.166.0",
            )
            self.assertEqual([row["status"] for row in responses], [200] * len(turns))
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual([row["path"] for row in upstream],
                             ["/v1/chat/completions"] * len(turns))
            self.assertEqual([row["headers"]["authorization"] for row in upstream],
                             ["Bearer " + SYNTHETIC_API_KEY] * len(turns))
            events = [
                _stream_events(bytes.fromhex(row["body"]))
                for row in responses
            ]
            for (label, _), sequence in zip(STREAM_CHUNKS, events):
                self.assertEqual(sequence[-1]["type"], "response.completed", label)
            observations.append(events)
        self.assertEqual(observations[1], observations[0])

    def test_flash_aliases_and_combo_retries_match_active_release(self):
        unsupported = {"status": 404, "content_type": "application/json",
                       "body": b'{"error":{"code":"model_not_supported"}}'}
        rate_limited = {"status": 429, "content_type": "application/json",
                        "body": b'{"error":{"code":"rate_limit_error"}}'}
        cases = (
            ("direct alias", "flash", [buffered_reply()], ["deepseek-flash"], [200]),
            ("explicit current ID", "deepseek-flash", [buffered_reply()],
             ["deepseek-flash"], [200]),
            ("explicit compatibility ID", "deepseek-v4-flash", [buffered_reply()],
             ["deepseek-v4-flash"], [200]),
            ("404 combo retry", "combo:flash,pro", [unsupported, buffered_reply(1)],
             ["deepseek-flash", "deepseek-v4-pro"], [200]),
            ("429 combo retry", "combo:flash,pro", [rate_limited, buffered_reply(1)],
             ["deepseek-flash", "deepseek-v4-pro"], [200]),
            ("empty combo", "combo:,,,", [unsupported], ["combo:,,,"], [404]),
            ("empty suffix", "combo:", [unsupported], ["combo:"], [404]),
        )
        for label, model, replies, expected_models, expected_statuses in cases:
            turns = [{"model": model, "input": "synthetic model fallback"}]
            observations = []
            for binary in (ORACLE, MODEX):
                with self.subTest(case=label, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, turns, replies, latest_version="0.166.0",
                    )
                    self.assertEqual([response["status"] for response in responses], expected_statuses)
                    self.assertEqual(
                        [post["path"] for post in posts],
                        ["/v1/chat/completions"] * len(expected_models),
                    )
                    self.assertEqual(
                        [post["headers"]["authorization"] for post in posts],
                        ["Bearer " + SYNTHETIC_API_KEY] * len(expected_models),
                    )
                    self.assertEqual(
                        [json.loads(post["body"])["model"] for post in posts], expected_models,
                    )
                    observations.append([post["body"] for post in posts])
            self.assertEqual(observations[1], observations[0], label)


if __name__ == "__main__":
    unittest.main()
