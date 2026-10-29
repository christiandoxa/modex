"""Compare tolerant Anthropic stream metadata handling across both pinned releases."""

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
from test_deepseek_continuation import observe_turns
from test_provider_tools_04392_characterization import _normalized_events
from provider_stream_search_cases import repeated_search_case


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


def _stream(events):
    body = b"".join(
        b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        for event in events
    )
    return {"status": 200, "content_type": "text/event-stream", "body": body}


def _events():
    return [
        {"type": "message_start", "message": {
            "id": "msg_synthetic", "role": "assistant", "model": "deepseek-chat",
            "usage": {"input_tokens": 3, "output_tokens": 0},
        }},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "synthetic"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]


def _cases():
    cases = []
    for name, field, value in (
        ("start_id_missing", "id", "missing"),
        ("start_id_empty", "id", ""),
        ("start_id_wrong_type", "id", 42),
        ("start_role_missing", "role", "missing"),
        ("start_role_other", "role", "user"),
        ("start_model_missing", "model", "missing"),
        ("start_model_wrong_type", "model", None),
        ("start_type_other", "type", "future_message"),
    ):
        events = _events()
        if value == "missing":
            del events[0]["message"][field]
        elif field == "type":
            events[0]["message"][field] = value
        else:
            events[0]["message"][field] = value
        cases.append((name, events))

    extra = _events()
    extra[0]["message"]["future_field"] = {"value": "ignored"}
    extra[0]["future_event_field"] = True
    cases.append(("start_extra_fields", extra))

    for name, usage in (
        ("start_usage_missing", "missing"),
        ("start_usage_null", None),
        ("start_usage_wrong_type", "invalid"),
        ("start_usage_missing_input", {"output_tokens": 0}),
        ("start_usage_invalid_input", {"input_tokens": -1, "output_tokens": 0}),
    ):
        events = _events()
        if usage == "missing":
            del events[0]["message"]["usage"]
        else:
            events[0]["message"]["usage"] = usage
        cases.append((name, events))

    for name, usage in (
        ("delta_usage_missing", "missing"),
        ("delta_usage_null", None),
        ("delta_usage_wrong_type", 7),
        ("delta_usage_missing_output", {}),
        ("delta_usage_invalid_output", {"output_tokens": "five"}),
    ):
        events = _events()
        if usage == "missing":
            del events[4]["usage"]
        else:
            events[4]["usage"] = usage
        cases.append((name, events))

    extra = _events()
    extra[4]["future_event_field"] = True
    extra[4]["usage"]["future_usage_field"] = "ignored"
    cases.append(("delta_extra_fields", extra))

    for name, text in (
        ("text_delta_missing", "missing"),
        ("text_delta_null", None),
        ("text_delta_wrong_type", 42),
    ):
        events = _events()
        if text == "missing":
            del events[2]["delta"]["text"]
        else:
            events[2]["delta"]["text"] = text
        cases.append((name, events))

    extra = _events()
    extra[2]["future_event_field"] = True
    extra[2]["delta"]["future_delta_field"] = "ignored"
    cases.append(("text_delta_extra_fields", extra))
    return cases


class AnthropicOptionalMetadataSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not oracle.is_file():
                raise AssertionError(f"pinned Prodex oracle is missing: {oracle}")
            digest = hashlib.sha256(oracle.read_bytes()).hexdigest()
            if digest != expected:
                raise AssertionError(f"pinned Prodex oracle checksum mismatch: {oracle}: {digest}")
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")

    def test_optional_metadata_and_nonstrings_match_both_release_oracles(self):
        cases = _cases()
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, copy.deepcopy(turns), copy.deepcopy(replies))
            self.assertEqual(len(posts), len(cases), label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(row["path"] == "/anthropic/v1/messages" for row in posts), label)
            self.assertTrue(all(row["status"] == 200 for row in responses), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertEqual(headers["anthropic-version"], "2023-06-01", label)
                self.assertNotIn("authorization", headers, label)
            captures[label] = [
                (post["body"], response["status"],
                 _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]

        expected = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], expected)
        self.assertEqual(captures["Modex"], expected)
        for (name, _), (_, _, events) in zip(cases, expected):
            with self.subTest(case=name):
                self.assertEqual(events[-1][0], "response.completed")
                if name in ("text_delta_missing", "text_delta_null", "text_delta_wrong_type"):
                    self.assertNotIn("response.output_text.delta", [event for event, _ in events])
                else:
                    self.assertIn("synthetic", json.dumps(events[-1][1]["response"]["output"]))

    def test_input_json_delta_ignores_extra_root_fields_against_both_releases(self):
        request, reply = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        for event in events:
            if (
                event.get("type") == "content_block_delta"
                and event.get("delta", {}).get("type") == "input_json_delta"
            ):
                event["future_event_field"] = "ignored"
        reply = _stream(events)
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1, label)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages", label)
            headers = {key.lower(): value for key, value in posts[0]["headers"].items()}
            self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
            self.assertEqual((len(responses), responses[0]["status"]), (1, 200), label)
            captures[label] = (
                posts[0]["body"], _normalized_events(bytes.fromhex(responses[0]["body"]))
            )
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        self.assertIn(
            "Found both",
            json.dumps(captures["0.439.2"][1][-1][1]["response"]["output"]),
        )

    def test_unknown_delta_type_strings_ignore_extra_fields_against_both_releases(self):
        cases = []
        for delta_type in ("citation_delta", "signature_delta", "future_delta"):
            for extra_root_field in (False, True):
                events = _events()
                if delta_type == "citation_delta":
                    delta = {
                        "type": delta_type,
                        "citation": {
                            "type": "web_search_result_location",
                            "url": "https://example.test/source",
                            "title": "Source",
                            "cited_text": "synthetic",
                        },
                    }
                else:
                    delta = {
                        "type": delta_type, "future_payload": {"value": "ignored"},
                    }
                event = {"type": "content_block_delta", "index": 0, "delta": delta}
                if extra_root_field:
                    event["future_event_field"] = "ignored"
                events.insert(3, event)
                cases.append((f"{delta_type}_extra_{extra_root_field}", events))
        for name, index in (("missing_index", None), ("nonnumeric_index", "zero")):
            events = _events()
            event = {"type": "content_block_delta", "delta": {"type": "future_delta"}}
            if name == "nonnumeric_index":
                event["index"] = index
            events.insert(3, event)
            cases.append((f"future_delta_{name}", events))
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                self.assertEqual(events[-1][0], "response.completed")
                self.assertIn("synthetic", json.dumps(events[-1][1]["response"]["output"]))

    def test_missing_or_nonstring_delta_type_fails_closed_against_both_releases(self):
        cases = []
        for name, delta in (
            ("missing", {}),
            ("null", {"type": None}),
            ("number", {"type": 42}),
        ):
            for extra_root_field in (False, True):
                events = _events()
                events[2]["delta"] = delta.copy()
                if extra_root_field:
                    events[2]["future_event_field"] = "rejected"
                cases.append((f"{name}_extra_{extra_root_field}", events))
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                _normalized_events(bytes.fromhex(response["body"])) for response in responses
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        for label in ("0.165.1", "0.439.2", "Modex"):
            for (name, _), events in zip(cases, captures[label]):
                with self.subTest(label=label, case=name):
                    self.assertIn("response.failed", [event for event, _ in events])
                    self.assertNotIn("response.completed", [event for event, _ in events])

    def test_thinking_delta_is_a_known_release_mismatch_in_and_out_of_order(self):
        message_start = {
            "type": "message_start",
            "message": {"id": "msg_reason", "role": "assistant", "model": "claude-sonnet-4-6"},
        }
        thinking_delta = {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "thinking_delta", "thinking": "considering"},
        }
        cases = [
            ("in_order", [
                message_start,
                {"type": "content_block_start", "index": 0,
                 "content_block": {"type": "thinking", "thinking": ""}},
                thinking_delta,
                {"type": "message_stop"},
            ]),
            ("out_of_order", [message_start, thinking_delta, {"type": "message_stop"}]),
        ]
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                _normalized_events(bytes.fromhex(response["body"])) for response in responses
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        for (name, _), events in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                self.assertIn("response.reasoning_summary_text.delta", [event for event, _ in events])
                self.assertIn("considering", json.dumps(events))
                self.assertEqual(events[-1][0], "response.completed")
        expected_modex_errors = {
            "in_order": "Anthropic content block type is not supported",
            "out_of_order": "Anthropic content delta type is not supported",
        }
        for (name, _), events in zip(cases, captures["Modex"]):
            with self.subTest(modex_case=name):
                self.assertEqual(events[-1][0], "response.failed")
                self.assertEqual(events[-1][1]["response"]["error"]["message"], expected_modex_errors[name])


if __name__ == "__main__":
    unittest.main()
