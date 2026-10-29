"""Compare orphan Anthropic web-search results with both pinned releases."""

import hashlib
import json
import unittest

import test_cli as active_release
import test_cli_01651 as historical_release
from test_provider_tools_04392_characterization import _run


REQUEST = {
    "model": "deepseek-chat",
    "input": "synthetic web query",
    "stream": False,
    "tools": [{"type": "web_search_preview"}],
}


class AnthropicOrphanResultParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (historical_release.ORACLE, historical_release.ORACLE_SHA256),
            (active_release.ORACLE, active_release.ORACLE_SHA256),
        ):
            if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Pinned oracle is missing or changed: {oracle}")
        if not active_release.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_orphan_result_is_ignored_while_text_response_completes(self):
        binaries = (
            historical_release.ORACLE,
            active_release.ORACLE,
            active_release.MODEX,
        )
        text_output = [{
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": "Before orphan result.",
            }],
        }]
        for scenario, expected_output in (
            ("anthropic-buffered-orphan-result", text_output),
            ("anthropic-buffered-orphan-result-only", []),
        ):
            payloads = []
            for binary in binaries:
                with self.subTest(scenario=scenario, binary=binary.name):
                    result = _run(binary, REQUEST, scenario=scenario)
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertNotIn(b"synthetic-provider-key", result["stderr"])
                    self.assertNotIn(b"synthetic-codex-key", result["stderr"])
                    payload = json.loads(result["response_body"])
                    self.assertIsInstance(payload["created_at"], int)
                    payload["created_at"] = "<time>"
                    payloads.append(payload)

            self.assertEqual(payloads[0], payloads[1])
            self.assertEqual(payloads[1], payloads[2])
            self.assertEqual(payloads[2]["output"], expected_output)


if __name__ == "__main__":
    unittest.main()
