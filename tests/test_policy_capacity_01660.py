"""0.166.0 DeepSeek API-key 503 behavior; profile runtime remains unimplemented."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_deepseek_key_rotation_01651_04392 import KEY_A, KEY_B, KEYS


class PolicyCapacityUnavailable01660ApiKeyPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_policy_capacity_still_uses_the_status_based_api_key_retry_path(self):
        request = [{"model": "deepseek-chat", "input": "synthetic policy capacity"}]
        body = b'{"error":{"code":"policy_capacity_unavailable","message":"synthetic policy"}}'
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    request,
                    [
                        {"status": 503, "content_type": "application/json", "body": body},
                        buffered_reply(9),
                    ],
                    api_keys=KEYS,
                    latest_version="0.166.0",
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in upstream],
                    [KEY_A, KEY_B],
                )
                self.assertEqual(upstream[1]["body"], upstream[0]["body"])
                self.assertEqual([response["status"] for response in responses], [200])

    def test_single_api_key_forwards_policy_503_unchanged(self):
        request = [{"model": "deepseek-chat", "input": "synthetic single-key capacity"}]
        body = b'{"error":{"code":"policy_capacity_unavailable","message":"synthetic policy"}}'
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    request,
                    [
                        {"status": 503, "content_type": "application/json", "body": body},
                        buffered_reply(9),
                    ],
                    api_keys="synthetic-key-a",
                    latest_version="0.166.0",
                )
                self.assertEqual(len(upstream), 1)
                self.assertEqual(upstream[0]["headers"]["authorization"], KEY_A)
                self.assertEqual([response["status"] for response in responses], [503])
                self.assertEqual(bytes.fromhex(responses[0]["body"]), body)

    def test_unrelated_metadata_does_not_suppress_server_overload_rotation(self):
        request = [{"model": "deepseek-chat", "input": "synthetic overload control"}]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    request,
                    [
                        {"status": 503, "content_type": "application/json",
                         "body": b'{"metadata":{"code":"policy_capacity_unavailable"},"error":{"code":"server_is_overloaded"}}'},
                        buffered_reply(10),
                    ],
                    api_keys=KEYS,
                    latest_version="0.166.0",
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in upstream],
                    [KEY_A, KEY_B],
                )
                self.assertEqual([response["status"] for response in responses], [200])
