"""Compare DeepSeek web-search mode routing through real Super processes."""

import hashlib
import json
import unittest
from unittest.mock import patch

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_provider_tools_04392_characterization import _codex_with_request, _run
import test_super_launch


def observe(binary, mode, request, scenario, extra_environment=None):
    with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
        result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
            binary=binary,
            scenario=scenario,
            model="deepseek-chat",
            environment_overrides={
                "PRODEX_DEEPSEEK_WEB_SEARCH_MODE": mode,
                **(extra_environment or {}),
            },
        )
    response = next((item for item in records if item["kind"] == "response"), None)
    return result, response, upstream, state


class DeepSeekWebSearchModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError("Build the Modex binary first")

    def assert_mode_matches(self, mode, request, scenario, status, path):
        reference = observe(ORACLE, mode, request, scenario)
        actual = observe(MODEX, mode, request, scenario)
        for result, response, upstream, state in (reference, actual):
            self.assertEqual(result.returncode, 0 if status == 200 else 1)
            self.assertEqual(response["status"] if response else None, status)
            self.assertEqual(len(upstream), 1 if path else 0)
            self.assertEqual(state["leftovers"], [])
        if path:
            self.assertEqual(reference[2][0]["path"], path)
            self.assertEqual(actual[2][0]["path"], path)
            self.assertEqual(
                json.loads(bytes.fromhex(reference[2][0]["body"])),
                json.loads(bytes.fromhex(actual[2][0]["body"])),
            )
            expected = json.loads(bytes.fromhex(reference[1]["body"]))
            observed = json.loads(bytes.fromhex(actual[1]["body"]))
            expected.pop("created_at", None)
            observed.pop("created_at", None)
            self.assertEqual(observed, expected)
        else:
            self.assertEqual(actual[1]["body"], reference[1]["body"])

    def test_mode_selects_or_rejects_the_web_search_route(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        for mode, scenario, status, path in (
            ("off", "buffered", 502, None),
            ("DISABLED", "buffered", 502, None),
            ("disable", "buffered", 502, None),
            ("openai_chat", "buffered", 200, "/v1/chat/completions"),
            ("openai-chat", "buffered", 200, "/v1/chat/completions"),
            ("CHAT", "buffered", 200, "/v1/chat/completions"),
            ("anthropic", "anthropic-buffered", 200, "/anthropic/v1/messages"),
            ("AUTO", "anthropic-buffered", 200, "/anthropic/v1/messages"),
        ):
            with self.subTest(mode=mode):
                self.assert_mode_matches(mode, request, scenario, status, path)

    def test_modes_preserve_non_search_and_empty_input_behavior(self):
        plain = {"model": "deepseek-chat", "input": "synthetic query", "stream": False}
        search = {**plain, "input": "", "tools": [{"type": "web_search_preview"}]}
        for mode in ("off", "anthropic", "chat"):
            with self.subTest(mode=mode, case="plain"):
                self.assert_mode_matches(mode, plain, "buffered", 200, "/v1/chat/completions")
        self.assert_mode_matches("off", search, "buffered", 502, None)
        self.assert_mode_matches("openai_chat", search, "buffered", 200, "/v1/chat/completions")

    def test_invalid_modes_fail_before_provider_requests(self):
        request = {"model": "deepseek-chat", "input": "synthetic query", "stream": False}
        for mode in ("", "unknown", " off ", "\u00a0auto"):
            for binary in (ORACLE, MODEX):
                with self.subTest(mode=mode, binary=str(binary)):
                    result, response, upstream, state = observe(binary, mode, request, "buffered")
                    self.assertEqual(result.returncode, 1)
                    self.assertIsNone(response)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                    self.assertIn(b"PRODEX_DEEPSEEK_WEB_SEARCH_MODE", result.stderr)
        for binary in (ORACLE, MODEX):
            with self.subTest(mode="unknown", strict=True, binary=str(binary)):
                result, response, upstream, state = observe(binary, "unknown", request, "buffered", {
                    "PRODEX_DEEPSEEK_STRICT_TOOLS": "true",
                    "PRODEX_DEEPSEEK_BETA_BASE_URL": "http://127.0.0.1:1/beta",
                })
                self.assertEqual(result.returncode, 1)
                self.assertIsNone(response)
                self.assertEqual(upstream, [])
                self.assertEqual(state["leftovers"], [])
                self.assertIn(b"PRODEX_DEEPSEEK_WEB_SEARCH_MODE", result.stderr)

    def test_strict_tools_and_mode_use_the_beta_route(self):
        request = {
            "model": "deepseek-chat", "input": "synthetic query", "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        original_run = test_super_launch.subprocess.run
        for mode, expected_status in (("off", 502), ("openai_chat", 200)):
            def run_with_mode(*args, **kwargs):
                kwargs["env"] = {**kwargs["env"], "PRODEX_DEEPSEEK_WEB_SEARCH_MODE": mode}
                return original_run(*args, **kwargs)

            with self.subTest(mode=mode), patch.object(test_super_launch.subprocess, "run", side_effect=run_with_mode):
                reference = _run(ORACLE, request, strict_tools=True)
                actual = _run(MODEX, request, strict_tools=True)
            for result in (reference, actual):
                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["exit_code"], 0 if expected_status == 200 else 1)
                self.assertEqual(len(result["upstream"]), 1 if expected_status == 200 else 0)
                self.assertEqual(result["state"]["leftovers"], [])
            if expected_status == 200:
                self.assertEqual(reference["upstream"][0]["path"], "/beta/chat/completions")
                self.assertEqual(actual["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(actual["upstream_body"], reference["upstream_body"])
            else:
                self.assertEqual(actual["response_body"], reference["response_body"])

    def test_raw_chat_passthrough_ignores_mode(self):
        request = {"model": "deepseek-chat", "input": "unused", "stream": False}
        for mode in ("off", "openai_chat", "anthropic"):
            with self.subTest(mode=mode):
                reference = observe(ORACLE, mode, request, "passthrough")
                actual = observe(MODEX, mode, request, "passthrough")
                for result, response, upstream, state in (reference, actual):
                    self.assertEqual((result.returncode, response["status"]), (0, 200))
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions?synthetic=1")
                    self.assertEqual(bytes.fromhex(upstream[0]["body"]), b"\x00synthetic\xff")
                    self.assertEqual(state["leftovers"], [])
                self.assertEqual(actual[1]["body"], reference[1]["body"])


if __name__ == "__main__":
    unittest.main()
