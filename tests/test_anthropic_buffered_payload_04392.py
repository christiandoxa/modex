"""Compare complete supported web-search payloads with the frozen release."""

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_super_launch
import test_provider_tools_04392_characterization as characterization


class AnthropicBufferedPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        oracle = characterization.ORACLE_04392
        if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != characterization.ORACLE_04392_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        if not characterization.MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {characterization.MODEX}")

    def test_complete_payload_and_empty_values_match_release(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic web query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        original_dumps = json.dumps
        for case in ("normal", "empty_text", "empty_id"):
            with self.subTest(case=case):
                def encode(value, *args, **kwargs):
                    if isinstance(value, dict) and value.get("id") == "msg_search" and "content" in value:
                        value = copy.deepcopy(value)
                        if case == "empty_text":
                            value["content"][2]["text"] = ""
                        elif case == "empty_id":
                            value["id"] = ""
                    return original_dumps(value, *args, **kwargs)

                with patch.object(test_super_launch.json, "dumps", side_effect=encode):
                    reference = characterization._run(characterization.ORACLE_04392, request, scenario="anthropic-buffered")
                    actual = characterization._run(characterization.MODEX, request, scenario="anthropic-buffered")
                self.assertEqual((reference["status"], actual["status"]), (200, 200))
                self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                expected_payload = json.loads(reference["response_body"])
                actual_payload = json.loads(actual["response_body"])
                for payload in (expected_payload, actual_payload):
                    self.assertIsInstance(payload.pop("created_at"), int)
                self.assertEqual(actual_payload, expected_payload)
                self.assertEqual(actual_payload["metadata"], {"anthropic": {"stop_reason": "end_turn"}})
                if case == "empty_text":
                    self.assertEqual(actual_payload["output"][-1]["content"][0]["text"], "")
                elif case == "empty_id":
                    self.assertEqual(actual_payload["id"], "")


if __name__ == "__main__":
    unittest.main()
