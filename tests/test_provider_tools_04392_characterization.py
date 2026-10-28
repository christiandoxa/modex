"""Characterize known DeepSeek web-search and config gaps plus env routing."""

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
    beta_override=None,
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
                    binary=binary, scenario=scenario, model="deepseek-chat"
                )
        else:
            result, records, upstream, state = harness.run_launch(
                binary=binary, scenario=scenario, model="deepseek-chat"
            )

    response = next((record for record in records if record["kind"] == "response"), None)
    upstream_body = None
    if upstream:
        try:
            upstream_body = json.loads(bytes.fromhex(upstream[0]["body"]))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return {
        "exit_code": result.returncode,
        "status": response["status"] if response else None,
        "response_body": bytes.fromhex(response["body"]) if response else b"",
        "upstream": upstream,
        "upstream_body": upstream_body,
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
        beta_url = "https://api.deepseek.com/beta"
        reference = _run(ORACLE_04392, request, beta_override=beta_url)
        modex = _run(MODEX, request, beta_override=beta_url)
        self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(reference["upstream"][0]["path"], "/v1/chat/completions")
        self.assertEqual(modex["upstream"][0]["path"], "/v1/chat/completions")
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(modex["state"]["leftovers"], [])

    def test_non_strict_invalid_beta_url_is_a_known_validation_gap(self):
        request = {"model": "deepseek-chat", "input": "synthetic invalid beta control"}
        invalid_beta_url = "not a URL"
        reference = _run(ORACLE_04392, request, beta_override=invalid_beta_url)
        modex = _run(MODEX, request, beta_override=invalid_beta_url)
        self.assertEqual((reference["exit_code"], reference["status"]), (1, None))
        self.assertEqual(reference["upstream"], [])
        self.assertEqual((modex["exit_code"], modex["status"]), (0, 200))
        self.assertEqual(modex["upstream"][0]["path"], "/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
