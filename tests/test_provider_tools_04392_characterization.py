"""Compare DeepSeek web-search and config behavior with the pinned release."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256


CODEX_REQUEST = r'body = b"\x00synthetic\xff" if passthrough else json.dumps({"model":"deepseek-chat","input":"synthetic prompt","stream":scenario == "stream"},separators=(",",":")).encode()'


def _codex_with_request(request):
    source = test_super_launch.CODEX
    if source.count(CODEX_REQUEST) != 1:
        raise AssertionError("Expected one synthetic Codex request body")
    replacement = (
        'body = b"\\x00synthetic\\xff" if passthrough else json.dumps('
        + repr(request)
        + ',separators=(",",":")).encode()'
    )
    return source.replace(CODEX_REQUEST, replacement)


def _run(
    binary, request, strict_tools=False, strict_config=False, scenario="buffered",
    beta_override=None, base_path="/v1",
):
    harness = test_super_launch.SuperLaunchTests()
    codex = _codex_with_request(request)
    with patch.object(test_super_launch, "CODEX", codex):
        if strict_tools or strict_config or beta_override is not None:
            original_run = test_super_launch.subprocess.run

            def run_with_strict_settings(*args, **kwargs):
                command = args[0] if args else kwargs["args"]
                base_url = command[command.index("--base-url") + 1]
                base = urlsplit(base_url)
                environment = dict(kwargs["env"])
                if strict_config:
                    config = (
                        "[deepseek]\n"
                        "strict_tools = true\n"
                        f'beta_base_url = "{base.scheme}://{base.netloc}/beta/"\n'
                    )
                    Path(environment["PRODEX_SHARED_CODEX_HOME"], "config.toml").write_text(
                        config, encoding="utf-8",
                    )
                    codex_home = Path(environment["HOME"], ".codex")
                    codex_home.mkdir(mode=0o700)
                    (codex_home / "config.toml").write_text(config, encoding="utf-8")
                if strict_tools:
                    environment["PRODEX_DEEPSEEK_STRICT_TOOLS"] = "true"
                    environment["PRODEX_DEEPSEEK_BETA_BASE_URL"] = (
                        f"{base.scheme}://{base.netloc}/beta"
                    )
                if beta_override is not None:
                    environment["PRODEX_DEEPSEEK_BETA_BASE_URL"] = beta_override
                kwargs["env"] = environment
                return original_run(*args, **kwargs)

            with patch.object(
                test_super_launch.subprocess, "run", side_effect=run_with_strict_settings
            ):
                result, records, upstream, state = harness.run_launch(
                    binary=binary, scenario=scenario, model="deepseek-chat", base_path=base_path
                )
        else:
            result, records, upstream, state = harness.run_launch(
                binary=binary, scenario=scenario, model="deepseek-chat", base_path=base_path
            )

    response = next((record for record in records if record["kind"] == "response"), None)
    responses = [record for record in records if record["kind"] == "response"]
    upstream_body = None
    if upstream:
        try:
            upstream_body = json.loads(bytes.fromhex(upstream[0]["body"]))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return {
        "exit_code": result.returncode,
        "stderr": result.stderr,
        "status": response["status"] if response else None,
        "response_body": bytes.fromhex(response["body"]) if response else b"",
        "responses": [bytes.fromhex(record["body"]) for record in responses],
        "records": records,
        "upstream": upstream,
        "upstream_body": upstream_body,
        "state": state,
    }


def _normalized_events(payload):
    def normalize(value):
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == "created_at":
                    result[key] = "<time>"
                else:
                    result[key] = normalize(item)
            return result
        if isinstance(value, str) and value.startswith(("resp_deepseek_", "msg_deepseek_")):
            return "<generated-id>"
        return value

    events = []
    event = None
    for line in payload.decode().splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: {"):
            events.append((event, normalize(json.loads(line[6:]))))
    return events


class ProviderTool04392CharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE_04392.is_file():
            raise AssertionError(f"Pinned Prodex 0.439.2 oracle is missing: {ORACLE_04392}")
        if hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_web_search_native_route_gap_and_invalid_context_control(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{
                "type": "web_search_preview",
                "allowed_domains": ["example.test"],
            }],
        }
        reference = _run(ORACLE_04392, request)
        modex = _run(MODEX, request)

        self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(reference["upstream"][0]["path"], "/anthropic/v1/messages")
        self.assertEqual(reference["upstream_body"]["tools"], [{
            "name": "web_search",
            "type": "web_search_20250305",
            "allowed_domains": ["example.test"],
        }])

        self.assertEqual((modex["exit_code"], modex["status"]), (1, 502))
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream_body"], reference["upstream_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])
        reference_headers = {
            name.lower(): value
            for name, value in reference["upstream"][0]["headers"].items()
        }
        self.assertEqual(reference_headers["x-api-key"], "synthetic-provider-key")
        modex_headers = {
            name.lower(): value
            for name, value in modex["upstream"][0]["headers"].items()
        }
        self.assertEqual(modex_headers["x-api-key"], "synthetic-provider-key")
        self.assertEqual(modex_headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("authorization", modex_headers)

        invalid_request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview", "context_size": 7}],
        }
        reference_invalid = _run(ORACLE_04392, invalid_request)
        modex_invalid = _run(MODEX, invalid_request)
        self.assertEqual((reference_invalid["exit_code"], reference_invalid["status"]), (1, 502))
        self.assertEqual((modex_invalid["exit_code"], modex_invalid["status"]), (1, 502))
        self.assertEqual(reference_invalid["upstream"], [])
        self.assertEqual(modex_invalid["upstream"], [])
        self.assertEqual(reference_invalid["response_body"], modex_invalid["response_body"])


    def test_web_search_anthropic_path_preserves_prefix_suffix_and_dot_segments(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = [
            ("/prefix/v1", "/prefix/anthropic/v1/messages"),
            ("/prefix/beta", "/prefix/anthropic/v1/messages"),
            ("/prefix/anthropic", "/prefix/anthropic/v1/messages"),
            ("/prefix/anthropic/v1", "/prefix/anthropic/v1/messages"),
            ("/prefix", "/prefix/anthropic/v1/messages"),
            ("/tenant/../evil/v1", "/evil/anthropic/v1/messages"),
            ("/prefix\\v1", "/prefix/v1/anthropic/v1/messages"),
            ("/tenant\\..\\evil\\v1", "/evil/v1/anthropic/v1/messages"),
        ]
        for base_path, expected_path in cases:
            with self.subTest(base_path=base_path):
                reference = _run(ORACLE_04392, request, scenario="anthropic-buffered", base_path=base_path)
                modex = _run(MODEX, request, scenario="anthropic-buffered", base_path=base_path)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(reference["upstream"][0]["path"], expected_path)
                self.assertEqual(modex["upstream"][0]["path"], expected_path)

    def test_anthropic_messages_buffered_web_search_translation_matches_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview", "allowed_domains": ["example.test"]}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered")
        modex = _run(MODEX, request, scenario="anthropic-buffered")
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        for key in ("id", "model", "output", "usage"):
            self.assertEqual(actual.get(key), expected.get(key), key)
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_empty_input_matches_release_before_upstream(self):
        request = {
            "model": "deepseek-chat",
            "input": "",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered")
        modex = _run(MODEX, request, scenario="anthropic-buffered")
        self.assertEqual((reference["exit_code"], reference["status"]), (1, 400))
        self.assertEqual((modex["exit_code"], modex["status"]), (1, 400))
        self.assertEqual(reference["upstream"], [])
        self.assertEqual(modex["upstream"], [])
        self.assertEqual(modex["response_body"], reference["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_messages_sse_events_and_failure_match_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview", "allowed_domains": ["example.test"]}],
        }
        for scenario in ("anthropic-stream", "anthropic-stream-error"):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_04392, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((modex["exit_code"], modex["status"]), (reference["exit_code"], reference["status"]))
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                self.assertEqual(
                    _normalized_events(modex["response_body"]),
                    _normalized_events(reference["response_body"]),
                )
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_stream_stop_variants_match_release_with_untyped_fields(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "anthropic-stop-sequence": "stop",
            "anthropic-stop-null-reason": None,
            "anthropic-stop-end-turn-sequence": "stop",
            "anthropic-stop-missing-message-delta": None,
            "anthropic-stop-tool-use": "tool_calls",
            "anthropic-stop-max-tokens": "length",
            "anthropic-stop-unknown-reason": "stop",
            "anthropic-stop-missing-reason": None,
            "anthropic-stop-invalid-reason": None,
            "anthropic-stop-invalid-sequence": "stop",
        }
        for scenario, expected_finish_reason in cases.items():
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_04392, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(modex["upstream"]), 1)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                reference_events = _normalized_events(reference["response_body"])
                modex_events = _normalized_events(modex["response_body"])
                self.assertIn("response.completed", [name for name, _ in reference_events])
                self.assertNotIn("response.failed", [name for name, _ in reference_events])
                reference_response = reference_events[-1][1]["response"]
                if expected_finish_reason is None:
                    self.assertNotIn("metadata", reference_response)
                else:
                    self.assertEqual(
                        reference_response["metadata"]["deepseek"]["finish_reason"],
                        expected_finish_reason,
                    )
                self.assertEqual(modex_events, reference_events)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_unsupported_anthropic_request_shapes_fail_before_upstream(self):
        cases = [
            (
                "untyped_role",
                {
                    "model": "deepseek-chat",
                    "input": [{"role": "critic", "content": "preserve this role content"}],
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                },
            ),
            (
                "typed_text_content",
                {
                    "model": "deepseek-chat",
                    "input": [{
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "preserve typed text"}],
                    }],
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                },
            ),
        ]
        for name, request in cases:
            with self.subTest(name=name):
                reference = _run(ORACLE_04392, request, scenario="anthropic-buffered")
                modex = _run(MODEX, request, scenario="anthropic-buffered")
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                if name == "untyped_role":
                    self.assertEqual(reference["upstream_body"]["messages"][0]["role"], "user")
                    self.assertEqual(reference["upstream_body"]["messages"][0]["content"][0]["text"], "preserve this role content")
                elif name == "typed_text_content":
                    self.assertEqual(
                        reference["upstream_body"]["messages"][0]["content"][0]["text"],
                        "preserve typed text",
                    )
                self.assertEqual((modex["exit_code"], modex["status"]), (1, 502))
                self.assertEqual(modex["upstream"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_mixed_function_and_web_tools_match_historical_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "preserve every tool",
            "stream": False,
            "tools": [
                {"type": "function", "name": "lookup", "parameters": {
                    "type": "object", "properties": {"query": {"type": "string"}},
                }},
                {"type": "web_search_preview"},
            ],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered")
        modex = _run(MODEX, request, scenario="anthropic-buffered")
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream_body"], reference["upstream_body"])
        expected = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        for key in ("id", "model", "output", "usage"):
            self.assertEqual(actual.get(key), expected.get(key), key)
        self.assertEqual((reference["state"]["leftovers"], modex["state"]["leftovers"]), ([], []))

    def test_anthropic_buffered_citations_match_04392_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered-citations")
        modex = _run(MODEX, request, scenario="anthropic-buffered-citations")
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        for response in (expected, actual):
            self.assertIsInstance(response.pop("created_at"), int)
            self.assertNotIn("citations", json.dumps(response["output"]))
            self.assertEqual([
                part["text"]
                for item in response["output"] if item["type"] == "message"
                for part in item["content"]
            ], ["Found it."])
        self.assertEqual(actual, expected)
        self.assertEqual((reference["state"]["leftovers"], modex["state"]["leftovers"]), ([], []))

    def test_anthropic_buffered_thinking_matches_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered-thinking")
        modex = _run(MODEX, request, scenario="anthropic-buffered-thinking")
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        released = json.loads(reference["response_body"])
        actual = json.loads(modex["response_body"])
        for key in ("id", "model", "output", "usage"):
            self.assertEqual(actual.get(key), released.get(key), key)
        self.assertIn("additional content", json.dumps(released["output"], ensure_ascii=False))
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_image_sse_content_is_dropped_like_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-stream-unknown-content")
        modex = _run(MODEX, request, scenario="anthropic-stream-unknown-content")
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        expected = _normalized_events(reference["response_body"])
        observed = _normalized_events(modex["response_body"])
        self.assertEqual(observed, expected)
        self.assertIn("response.completed", [name for name, _ in expected])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", reference["response_body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", modex["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_image_index_and_text_order_match_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        for scenario in ("anthropic-stream-image-interleaved", "anthropic-stream-image-missing-index"):
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_04392, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                expected = _normalized_events(reference["response_body"])
                observed = _normalized_events(modex["response_body"])
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(observed, expected)
                deltas = [body["delta"] for name, body in observed if name == "response.output_text.delta"]
                self.assertEqual(deltas, ["before image", " after image"])
                for payload in (reference["response_body"], modex["response_body"]):
                    self.assertNotIn(b"U1lOVEhFVElDX0lNQUdFX0JZVEVT", payload)
                    self.assertNotIn(b"SYNTHETIC_IMAGE_DELTA_SECRET", payload)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_image_stop_collisions_match_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        cases = {
            "anthropic-image-stop-text-collision": ["before image", " after image"],
            "anthropic-image-stop-text-repeated": ["before image", " after image"],
            "anthropic-image-stop-text-delta-before-stop": [
                "before image", " between blocks", " after image stop",
            ],
            "anthropic-image-stop-tool-collision": [],
            "anthropic-image-stop-tool-delta-before-stop": [],
            "anthropic-image-stop-search-delta-before-stop": ["Found it."],
            "anthropic-image-stop-result-collision": ["visible after result stop", "Found it."],
            "anthropic-image-stop-string-index": ["before image", " after image"],
            "anthropic-image-stop-fractional-index": ["before image", " after image"],
        }
        for scenario, expected_deltas in cases.items():
            with self.subTest(scenario=scenario):
                reference = _run(ORACLE_04392, request, scenario=scenario)
                modex = _run(MODEX, request, scenario=scenario)
                expected = _normalized_events(reference["response_body"])
                observed = _normalized_events(modex["response_body"])
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertIn("response.completed", [name for name, _ in expected])
                deltas = [body["delta"] for name, body in expected if name == "response.output_text.delta"]
                self.assertEqual(deltas, expected_deltas)
                self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                self.assertEqual(observed, expected)
                for payload in (reference["response_body"], modex["response_body"]):
                    self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", payload)
                    self.assertNotIn(b"SYNTHETIC_IMAGE_DELTA_SECRET", payload)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_buffered_image_response_is_rejected_like_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request, scenario="anthropic-buffered-image")
        modex = _run(MODEX, request, scenario="anthropic-buffered-image")
        self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
        self.assertEqual((modex["exit_code"], modex["status"]), (1, 502))
        self.assertEqual(len(reference["upstream"]), 1)
        self.assertEqual(len(modex["upstream"]), 1)
        self.assertEqual(modex["upstream"][0]["path"], reference["upstream"][0]["path"])
        self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", reference["response_body"])
        self.assertNotIn(b"SYNTHETIC_IMAGE_BLOCK_DATA", modex["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_anthropic_input_image_is_rejected_before_provider_post(self):
        marker = "U1lOVEhFVElDX0lNQUdFX0JZVEVT"
        request = {
            "model": "deepseek-chat",
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "synthetic prompt"},
                    {"type": "input_image", "image_url": "data:image/png;base64," + marker},
                ],
            }],
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE_04392, request)
        modex = _run(MODEX, request)
        self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
        self.assertEqual((modex["exit_code"], modex["status"]), (1, 502))
        self.assertEqual(reference["upstream"], [])
        self.assertEqual(modex["upstream"], [])
        self.assertNotIn(marker.encode(), reference["response_body"])
        self.assertNotIn(marker.encode(), modex["response_body"])
        self.assertNotIn(marker.encode(), reference["stderr"])
        self.assertNotIn(marker.encode(), modex["stderr"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_strict_tools_environment_routes_and_normalizes_like_pinned_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic tool request",
            "stream": False,
            "tools": [{
                "type": "function",
                "name": "lookup",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }],
        }
        reference = _run(ORACLE_04392, request, strict_tools=True)
        modex = _run(MODEX, request, strict_tools=True)

        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual(reference["upstream"][0]["path"], "/beta/chat/completions")
        reference_tool = reference["upstream_body"]["tools"][0]
        self.assertEqual(reference_tool["function"]["strict"], True)
        self.assertEqual(reference_tool["function"]["parameters"], {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        })

        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(modex["upstream"][0]["path"], "/beta/chat/completions")
        modex_tool = modex["upstream_body"]["tools"][0]
        self.assertEqual(modex_tool["function"], reference_tool["function"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

        disabled_request = dict(request)
        disabled_request["tools"] = [dict(request["tools"][0])]
        disabled_request["tools"][0].pop("strict")
        disabled = _run(MODEX, disabled_request, strict_tools=False)
        self.assertEqual((disabled["exit_code"], disabled["status"]), (0, 200))
        self.assertEqual(disabled["upstream"][0]["path"], "/v1/chat/completions")
        disabled_tool = disabled["upstream_body"]["tools"][0]
        self.assertNotIn("strict", disabled_tool["function"])
        self.assertNotIn("required", disabled_tool["function"]["parameters"])
        self.assertNotIn("additionalProperties", disabled_tool["function"]["parameters"])
        self.assertEqual(disabled["state"]["leftovers"], [])

    def test_nested_function_tools_match_simple_and_non_simple_release_paths(self):
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }
        for simple in (True, False):
            for explicit_strict in (False, True):
                with self.subTest(simple=simple, explicit_strict=explicit_strict):
                    function = {"name": "lookup", "parameters": schema}
                    if explicit_strict:
                        function["strict"] = True
                    request = {
                        "model": "deepseek-chat",
                        "input": "synthetic nested tool request",
                        "stream": False,
                        "tools": [{"type": "function", "function": function}],
                    }
                    if not simple:
                        request["safety_identifier"] = "synthetic-user"
                    reference = _run(ORACLE_04392, request, strict_tools=True)
                    modex = _run(MODEX, request, strict_tools=True)
                    self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                    self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                    self.assertEqual(reference["upstream"][0]["path"], "/beta/chat/completions")
                    self.assertEqual(modex["upstream"][0]["path"], "/beta/chat/completions")
                    self.assertEqual(modex["upstream"][0]["body"], reference["upstream"][0]["body"])
                    reference_tool = reference["upstream_body"]["tools"][0]
                    modex_tool = modex["upstream_body"]["tools"][0]
                    self.assertEqual(modex_tool, reference_tool)
                    if simple:
                        self.assertEqual(reference_tool["function"]["parameters"], schema)
                        self.assertEqual("strict" in reference_tool["function"], explicit_strict)
                    else:
                        self.assertIs(reference_tool["function"]["strict"], True)
                        self.assertEqual(reference_tool["function"]["parameters"], {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                            "additionalProperties": False,
                        })
                    self.assertEqual(reference["state"]["leftovers"], [])
                    self.assertEqual(modex["state"]["leftovers"], [])

    def test_config_only_strict_tools_gap_remains_fail_closed(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic tool request",
            "stream": False,
            "tools": [{
                "type": "function",
                "name": "lookup",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }],
        }
        reference = _run(ORACLE_04392, request, strict_config=True)
        modex = _run(MODEX, request, strict_config=True)
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual(reference["upstream"][0]["path"], "/beta/chat/completions")
        reference_tool = reference["upstream_body"]["tools"][0]["function"]
        self.assertTrue(reference_tool["strict"])
        self.assertEqual((modex["exit_code"], modex["status"]), (1, None))
        self.assertEqual(modex["upstream"], [])
        self.assertEqual(modex["state"]["leftovers"], [])
        self.assertIn("strict_tools = true", modex["state"]["config"])
        self.assertIn("/beta/", modex["state"]["config"])

        invalid_request = {
            "model": "deepseek-chat",
            "input": "synthetic tool request",
            "stream": False,
            "tools": [{"type": "file_search"}],
        }
        reference_invalid = _run(ORACLE_04392, invalid_request, strict_tools=True)
        modex_invalid = _run(MODEX, invalid_request, strict_tools=True)
        self.assertEqual((reference_invalid["exit_code"], reference_invalid["status"]), (1, 502))
        self.assertEqual((modex_invalid["exit_code"], modex_invalid["status"]), (1, 502))
        self.assertEqual(reference_invalid["upstream"], [])
        self.assertEqual(modex_invalid["upstream"], [])
        self.assertEqual(reference_invalid["response_body"], modex_invalid["response_body"])

    def test_strict_tools_raw_chat_passthrough_keeps_original_route(self):
        request = {"model": "deepseek-chat", "input": "unused passthrough control"}
        reference = _run(
            ORACLE_04392, request, strict_tools=True, scenario="passthrough",
        )
        modex = _run(
            MODEX, request, strict_tools=True, scenario="passthrough",
        )
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(reference["upstream"][0]["path"], "/v1/chat/completions?synthetic=1")
        self.assertEqual(modex["upstream"][0]["path"], "/v1/chat/completions?synthetic=1")
        self.assertEqual(bytes.fromhex(reference["upstream"][0]["body"]), b"\x00synthetic\xff")
        self.assertEqual(bytes.fromhex(modex["upstream"][0]["body"]), b"\x00synthetic\xff")
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_non_strict_launch_does_not_resolve_unused_public_beta_url(self):
        request = {"model": "deepseek-chat", "input": "synthetic beta fallback control"}
        for beta_url in (
            "https://api.deepseek.com/beta",
            "https://a%41b/beta",
            "https://a%2eb/beta",
            "https://127.0.0.%39/beta",
            "https://例え.テスト/beta",
            "https://%E4%BE%8B%E3%81%88.%E3%83%86%E3%82%B9%E3%83%88/beta",
            "https://xn--r8jz45g.xn--zckzah/beta",
        ):
            with self.subTest(beta_url=beta_url):
                reference = _run(ORACLE_04392, request, beta_override=beta_url)
                modex = _run(MODEX, request, beta_override=beta_url)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
                self.assertEqual(reference["upstream"][0]["path"], "/v1/chat/completions")
                self.assertEqual(modex["upstream"][0]["path"], "/v1/chat/completions")
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(modex["state"]["leftovers"], [])

    def test_toml_beta_url_precedes_invalid_environment_override(self):
        request = {"model": "deepseek-chat", "input": "synthetic config precedence control"}
        reference = _run(
            ORACLE_04392, request, strict_config=True, beta_override="not-a-url",
        )
        modex = _run(
            MODEX, request, strict_config=True, beta_override="not-a-url",
        )
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual(reference["upstream"][0]["path"], "/beta/chat/completions")
        self.assertEqual((modex["exit_code"], modex["status"]), (1, None))
        self.assertEqual(modex["upstream"], [])
        self.assertEqual(modex["state"]["leftovers"], [])
        self.assertIn("beta_base_url =", modex["state"]["config"])

    def test_non_strict_invalid_beta_urls_fail_before_codex_or_provider(self):
        request = {"model": "deepseek-chat", "input": "synthetic invalid beta control"}
        invalid_beta_urls = (
            ("", b"PRODEX_DEEPSEEK_BETA_BASE_URL cannot be empty"),
            ("not-a-url", b"PRODEX_DEEPSEEK_BETA_BASE_URL must be an http(s) URL"),
            ("ftp://example.test/beta", b"must be an http(s) URL"),
            ("https://a|b/beta", b"must be an http(s) URL"),
            ("https://a^b/beta", b"must be an http(s) URL"),
            ("https://a<b/beta", b"must be an http(s) URL"),
            ("https://a>b/beta", b"must be an http(s) URL"),
            ("https://a[b/beta", b"must be an http(s) URL"),
            ("https://a]b/beta", b"must be an http(s) URL"),
            ("https://a%40b/beta", b"must be an http(s) URL"),
            ("https://a%7Cb/beta", b"must be an http(s) URL"),
            ("https://a%25b/beta", b"must be an http(s) URL"),
            ("https://a%b/beta", b"must be an http(s) URL"),
            ("https://a%20b/beta", b"must be an http(s) URL"),
            ("https://a%FFb/beta", b"must be an http(s) URL"),
            ("https://a%C3%28b/beta", b"must be an http(s) URL"),
            ("https://a%80b/beta", b"must be an http(s) URL"),
            ("https://127.0.0.%32%35%36/beta", b"must be an http(s) URL"),
            ("https://synthetic-user:synthetic-secret@example.test/beta", b"must be an http(s) URL"),
            ("https://example.test/beta?token=synthetic-secret", b"must be an http(s) URL"),
            ("https://example.test/beta#token=synthetic-secret", b"must be an http(s) URL"),
            ("https://example.test/beta path", b"PRODEX_DEEPSEEK_BETA_BASE_URL must not contain whitespace"),
        )
        for invalid_beta_url, expected_diagnostic in invalid_beta_urls:
            with self.subTest(beta_url=invalid_beta_url):
                reference = _run(ORACLE_04392, request, beta_override=invalid_beta_url)
                modex = _run(MODEX, request, beta_override=invalid_beta_url)
                self.assertEqual((reference["exit_code"], reference["status"]), (1, None))
                self.assertEqual((modex["exit_code"], modex["status"]), (1, None))
                for result in (reference, modex):
                    self.assertNotIn("launch", [record.get("kind") for record in result["records"]])
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])
                    self.assertNotIn(b"synthetic-secret", result["stderr"])
                self.assertIn(
                    expected_diagnostic,
                    modex["stderr"],
                )

    def test_fullwidth_beta_hosts_reject_mapped_forbidden_host_chars(self):
        request = {"model": "deepseek-chat", "input": "synthetic IDNA host control"}
        beta_urls = (
            "https://a＃b/beta",
            "https://a％b/beta",
            "https://a／b/beta",
            "https://a：b/beta",
            "https://a＜b/beta",
            "https://a＞b/beta",
            "https://a？b/beta",
            "https://a＠b/beta",
            "https://a［b/beta",
            "https://a＼b/beta",
            "https://a］b/beta",
            "https://a＾b/beta",
            "https://a｜b/beta",
            "https://a%EF%BC%A0b/beta",
        )
        for beta_url in beta_urls:
            with self.subTest(beta_url=beta_url):
                reference = _run(ORACLE_04392, request, beta_override=beta_url)
                modex = _run(MODEX, request, beta_override=beta_url)
                self.assertEqual((reference["exit_code"], reference["status"]), (1, None))
                self.assertEqual(reference["upstream"], [])
                self.assertEqual((modex["exit_code"], modex["status"]), (1, None))
                for result in (reference, modex):
                    self.assertNotIn("launch", [record.get("kind") for record in result["records"]])
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
