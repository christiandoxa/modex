"""Real-process characterization of the still-unimplemented multi-key path."""

import hashlib
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256
import test_super_launch


KEYS = "synthetic-key-a,synthetic-key-b"
KEY_A = "Bearer synthetic-key-a"
KEY_B = "Bearer synthetic-key-b"


class DeepSeekKeyRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_releases_rotate_unbound_requests_and_constrain_continuations(self):
        turns = [{"model": "deepseek-chat", "input": "synthetic first"},
                 {"model": "deepseek-chat", "input": "synthetic second"}]
        for binary in (ORACLE_01651, ORACLE):
            with self.subTest(binary=str(binary), scenario="unbound"):
                posts, responses = observe_turns(binary, turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
                self.assertEqual([response["status"] for response in responses], [200, 200])
            with self.subTest(binary=str(binary), scenario="previous_response"):
                bound_turns = [turns[0], {**turns[1], "use_previous": True}]
                posts, responses = observe_turns(binary, bound_turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))

        result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
            binary=MODEX, api_key=None, scenario="buffered", environment_overrides={"DEEPSEEK_API_KEYS": KEYS},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"multiple DEEPSEEK_API_KEYS values require key rotation", result.stderr)
        self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))
        self.assertNotIn(KEYS.encode(), result.stdout + result.stderr)

    def test_release_retry_depends_on_error_class_before_commit(self):
        request = [{"model": "deepseek-chat", "input": "synthetic retry"}]
        body = b'{"error":{"message":"synthetic failure","type":"synthetic"}}'
        for status in (400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503):
            retry = status in (401, 403, 500, 502, 503)
            for binary in (ORACLE_01651, ORACLE):
                with self.subTest(status=status, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, request,
                        [{"status": status, "content_type": "application/json", "body": body}, buffered_reply(1)],
                        api_keys=KEYS,
                    )
                    self.assertEqual([post["headers"]["authorization"] for post in posts],
                                     [KEY_A, KEY_B] if retry else [KEY_A])
                    self.assertEqual(responses[0]["status"], 200 if retry else status)
