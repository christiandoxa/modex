"""Current-release production checks for rejected worker changes."""

import hashlib
import json
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY


class Release04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_specific_replacement_retains_its_later_tool_position(self):
        turn = {"model": "deepseek-chat", "input": "synthetic", "tools": [
            {"type": "mcp", "server_label": "s", "allowed_tools": ["run"]},
            {"type": "function", "name": "middle"},
            {"type": "function", "name": "mcp__s__run", "parameters": {
                "type": "object", "properties": {"q": {"type": "string"}}}},
            {"type": "function", "name": "tail"},
        ]}
        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, [turn], [buffered_reply(created=42)])
                self.assertEqual([row["status"] for row in responses], [200])
                self.assertEqual(len(upstream), 1)
                self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                tools = json.loads(upstream[0]["body"])["tools"]
                self.assertEqual([tool["function"]["name"] for tool in tools],
                                 ["middle", "mcp__s__run", "tail"])
                self.assertEqual(tools[1]["function"]["parameters"]["properties"],
                                 {"q": {"type": "string"}})
                observations.append(tools)
        self.assertEqual(*observations)

    def test_merged_response_metadata_can_exceed_four_mib(self):
        turn = {"model": "deepseek-chat", "input": "synthetic",
                "metadata": {"trace": "x" * 2_100_000}}
        reply = buffered_reply(created=42, choices=[{"index": 0, "message": {
            "role": "assistant", "content": "synthetic", "reasoning_content": "y" * 2_100_000},
            "finish_reason": "stop"}])
        digests = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, [turn], [reply])
                self.assertEqual([row["status"] for row in responses], [200])
                self.assertEqual(len(upstream), 1)
                self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                metadata = json.loads(bytes.fromhex(responses[0]["body"]))["metadata"]
                self.assertTrue(metadata["trace"] == turn["metadata"]["trace"])
                self.assertTrue(metadata["deepseek"]["reasoning_content"] ==
                                "y" * 2_100_000)
                encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
                self.assertGreater(len(encoded), 4 * 1024 * 1024)
                digests.append(hashlib.sha256(encoded).hexdigest())
        self.assertEqual(*digests)


if __name__ == "__main__":
    unittest.main()
