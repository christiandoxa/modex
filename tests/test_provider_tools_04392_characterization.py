"""Characterize known DeepSeek web-search and strict-tool path gaps."""

import hashlib
import json
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


def _run(binary, request, strict_tools=False):
    harness = test_super_launch.SuperLaunchTests()
    codex = _codex_with_request(request)
    with patch.object(test_super_launch, "CODEX", codex):
        if strict_tools:
            original_run = test_super_launch.subprocess.run

            def run_with_strict_tools(*args, **kwargs):
                command = args[0] if args else kwargs["args"]
                base_url = command[command.index("--base-url") + 1]
                base = urlsplit(base_url)
                environment = dict(kwargs["env"])
                environment["PRODEX_DEEPSEEK_STRICT_TOOLS"] = "true"
                environment["PRODEX_DEEPSEEK_BETA_BASE_URL"] = (
                    f"{base.scheme}://{base.netloc}/beta"
                )
                kwargs["env"] = environment
                return original_run(*args, **kwargs)

            with patch.object(
                test_super_launch.subprocess, "run", side_effect=run_with_strict_tools
            ):
                result, records, upstream, state = harness.run_launch(
                    binary=binary, scenario="buffered", model="deepseek-chat"
                )
        else:
            result, records, upstream, state = harness.run_launch(
                binary=binary, scenario="buffered", model="deepseek-chat"
            )

    response = next(record for record in records if record["kind"] == "response")
    return {
        "exit_code": result.returncode,
        "status": response["status"],
        "response_body": bytes.fromhex(response["body"]),
        "upstream": upstream,
        "upstream_body": (
            json.loads(bytes.fromhex(upstream[0]["body"])) if upstream else None
        ),
        "state": state,
    }


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

        self.assertEqual((modex["exit_code"], modex["status"]), (1, 501))
        self.assertEqual(modex["upstream"], [])
        self.assertEqual(
            modex["response_body"],
            b"DeepSeek native web-search routing is not implemented",
        )
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])
        reference_headers = {
            name.lower(): value
            for name, value in reference["upstream"][0]["headers"].items()
        }
        self.assertEqual(reference_headers["x-api-key"], "synthetic-provider-key")

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

    def test_strict_tool_config_gap_and_invalid_tool_control(self):
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
        self.assertEqual(modex["upstream"][0]["path"], "/v1/chat/completions")
        modex_tool = modex["upstream_body"]["tools"][0]
        self.assertNotIn("strict", modex_tool["function"])
        self.assertNotIn("required", modex_tool["function"]["parameters"])
        self.assertNotIn("additionalProperties", modex_tool["function"]["parameters"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

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


if __name__ == "__main__":
    unittest.main()
