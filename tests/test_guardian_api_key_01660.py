"""Keep Guardian profile affinity separate from the DeepSeek API-key route."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


KEYS = "synthetic-key-a,synthetic-key-b"
KEY_A = "Bearer synthetic-key-a"
KEY_B = "Bearer synthetic-key-b"
GUARDIAN_TURNS = [
    {"model": "deepseek-chat", "input": "synthetic parent"},
    {
        "model": "deepseek-chat",
        "input": "synthetic reviewer",
        "use_guardian_parent": True,
        "_headers": {"x-codex-guardian": "reviewer"},
    },
]


class GuardianApiKey01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def test_guardian_parent_metadata_does_not_pin_the_api_key_route(self):
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    GUARDIAN_TURNS,
                    [buffered_reply(1), buffered_reply(2)],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in upstream],
                    [KEY_A, KEY_B],
                )
                self.assertEqual([response["status"] for response in responses], [200, 200])

    def test_guardian_metadata_does_not_change_api_key_quota_retry(self):
        quota = {
            "status": 429,
            "content_type": "application/json",
            "body": b'{"error":{"code":"insufficient_quota","message":"synthetic quota"}}',
        }
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    GUARDIAN_TURNS,
                    [buffered_reply(1), quota, buffered_reply(3)],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in upstream],
                    [KEY_A, KEY_B, KEY_A],
                )
                self.assertEqual([response["status"] for response in responses], [200, 200])


if __name__ == "__main__":
    unittest.main()
