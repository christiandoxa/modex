"""Current-release production checks for rejected worker changes."""

import hashlib
import json
import unittest

import test_cli
from test_cli import MODEX, HISTORICAL_04395_ORACLE as ORACLE
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY
import test_super_launch


class Release04395Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != test_cli.HISTORICAL_04395_ORACLE_SHA256:
            raise AssertionError("oracle does not match historical Prodex 0.439.5")

    def test_hook_initialize_reports_pinned_release_and_current_modex_versions(self):
        probe = test_super_launch.SuperLaunchTests('runTest')
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                result, records, upstream, _ = probe.run_launch(binary=binary, scenario='buffered')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(upstream), 1)
                initialize = next(record for record in records
                                  if record['kind'] == 'request' and record['method'] == 'initialize')
                self.assertEqual(initialize['params'], {
                    'capabilities': {'experimentalApi': True},
                    'clientInfo': {'name': 'prodex-hook-trust',
                                   'version': '0.439.5' if binary == ORACLE else '0.166.2'},
                })

    def test_bodyless_chat_and_ordinary_response_lengths(self):
        for status, content_type, body in (
            (204, 'application/json', b''),
            (204, 'text/event-stream', b''),
            (200, 'application/json', b'{"id":"synthetic-body"}'),
        ):
            for binary in (ORACLE, MODEX):
                with self.subTest(status=status, content_type=content_type, binary=str(binary)):
                    upstream, responses = observe_turns(binary, [{
                        'model': 'deepseek-chat', 'messages': [],
                        '_path': '/v1/chat/completions?synthetic=%2B',
                    }], [{'status': status, 'content_type': content_type, 'body': body}])
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(responses[0]['status'], status)
                    self.assertEqual(bytes.fromhex(responses[0]['body']), body)
                    headers = {key.lower(): value for key, value in responses[0]['headers'].items()}
                    self.assertEqual(headers.get('content-length'),
                                     None if content_type == 'text/event-stream' else str(len(body)))
                    # Retain the known SSE framing difference; it is not a parity PASS.
                    self.assertEqual(headers.get('transfer-encoding'),
                                     'chunked' if content_type == 'text/event-stream' else None)
                    self.assertEqual(upstream[0]['headers']['authorization'], 'Bearer ' + SYNTHETIC_API_KEY)

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
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0], observations[1])

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
        self.assertEqual(len(digests), 2)
        self.assertEqual(digests[0], digests[1])


if __name__ == "__main__":
    unittest.main()
