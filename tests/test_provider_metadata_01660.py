"""Compare buffered chat metadata through real 0.166.0 and Modex processes."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns


def response_body(response_id, choices, *, fingerprint=None):
    body = {
        "id": response_id,
        "model": "deepseek-chat",
        "created": 42,
        "choices": choices,
    }
    if fingerprint is not None:
        body["system_fingerprint"] = fingerprint
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


CASES = (
    (
        "pinned_source_shape",
        response_body("chatcmpl-pinned-shape", [
            {
                "index": 0,
                "logprobs": [],
                "finish_reason": "",
                "message": {
                    "content": "synthetic answer",
                    "reasoning_content": " ",
                    "refusal": "",
                    "annotations": [False],
                },
            },
            {
                "index": 1,
                "logprobs": {"ignored": True},
                "finish_reason": "ignored",
                "message": {"reasoning_content": "ignored"},
            },
        ], fingerprint="fp"),
        {"model": "deepseek-chat", "input": "synthetic question"},
        {"deepseek": {
            "annotations": [False],
            "finish_reason": "",
            "logprobs": [],
            "system_fingerprint": "fp",
        }},
    ),
    (
        "blank_fields",
        response_body("chatcmpl-blank-fields", [{
            "index": 0,
            "finish_reason": "",
            "message": {
                "reasoning_content": " ",
                "refusal": "\t",
                "annotations": [],
            },
        }], fingerprint="\u3000"),
        {"model": "deepseek-chat", "input": "synthetic question"},
        {"deepseek": {"finish_reason": ""}},
    ),
    (
        "empty_fields",
        response_body("chatcmpl-empty-fields", [{
            "index": 0,
            "finish_reason": "",
            "message": {
                "reasoning_content": "",
                "refusal": "",
                "annotations": [],
            },
        }], fingerprint=""),
        {"model": "deepseek-chat", "input": "synthetic question"},
        {"deepseek": {"finish_reason": ""}},
    ),
    (
        "metadata_collision",
        response_body("chatcmpl-metadata-collision", [{
            "index": 0,
            "logprobs": [],
            "finish_reason": "stop",
            "message": {
                "reasoning_content": " ",
                "refusal": " ",
                "annotations": [False],
            },
        }], fingerprint="fp"),
        {
            "model": "deepseek-chat",
            "input": "synthetic question",
            "metadata": {
                "local_tag": "synthetic-local",
                "deepseek": {
                    "reasoning_content": "request-value",
                    "finish_reason": {"local_tag": "request-finish"},
                    "local_tag": "nested-local",
                },
            },
        },
        {"deepseek": {
            "annotations": [False],
            "finish_reason": {"local_tag": "request-finish"},
            "local_tag": "nested-local",
            "logprobs": [],
            "reasoning_content": "request-value",
            "system_fingerprint": "fp",
        }, "local_tag": "synthetic-local"},
    ),
)


class ProviderMetadata01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_buffered_metadata_matches_active_release_process(self):
        for name, body, turn, expected_metadata in CASES:
            with self.subTest(case=name):
                observations = []
                for binary in (ORACLE, MODEX):
                    upstream, captured = observe_turns(
                        binary,
                        [turn],
                        [{"status": 200, "content_type": "application/json", "body": body}],
                        latest_version="0.166.0",
                    )
                    self.assertEqual([row["status"] for row in captured], [200])
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    self.assertEqual(
                        upstream[0]["headers"]["authorization"],
                        "Bearer synthetic-provider-key",
                    )
                    response = json.loads(bytes.fromhex(captured[0]["body"]))
                    self.assertEqual(response.get("metadata"), expected_metadata)
                    response.pop("created_at", None)
                    observations.append((upstream[0]["body"], response))
                self.assertEqual(observations[0], observations[1])
