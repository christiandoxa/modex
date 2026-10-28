"""Real-process ownership checks against the pinned Prodex 0.439.2 release."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class ContinuationBinding04392Tests(unittest.TestCase):
    def test_accepted_and_unbound_ownership_matches_release(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = [
            ("previous-owned", [{}, {"use_previous": True}], None, [200, 503], 1),
            ("previous-unknown", [{}, {"previous_response_id": "synthetic-unknown"}], None, [200, 200], 2),
            ("session-owned", [{"session_id": "session-a"}, {"session_id": "session-a"}], None, [200, 503], 1),
            ("session-other", [{"session_id": "session-a"}, {"session_id": "session-b"}], None, [200, 200], 2),
            ("turn-owned", [{"_headers": {"x-codex-turn-state": "turn-a"}},
                             {"_headers": {"x-codex-turn-state": "turn-a"}}], None, [200, 503], 1),
            ("turn-other", [{"_headers": {"x-codex-turn-state": "turn-a"}},
                            {"_headers": {"x-codex-turn-state": "turn-b"}}], None, [200, 200], 2),
            ("failed-upstream", [{"session_id": "session-a"}, {"session_id": "session-a"}],
             {"status": 429, "content_type": "application/json", "body": b'{"error":"synthetic"}'},
             [429, 200], 2),
            ("accepted-invalid-body", [{"session_id": "session-a"}, {"session_id": "session-a"}],
             {"status": 200, "content_type": "application/json", "body": b"invalid"},
             [502, 503], 1),
            ("chat-session", [{"_path": "/v1/chat/completions", "messages": [], "session_id": "session-a"},
                              {"session_id": "session-a"}], None, [200, 503], 1),
            ("chat-response", [{"_path": "/v1/chat/completions", "messages": []},
                               {"use_previous": True}], None, [200, 503], 1),
            ("responses-to-chat", [{"session_id": "session-a"},
                                    {"_path": "/v1/chat/completions", "messages": [],
                                     "session_id": "session-a"}], None, [200, 503], 1),
        ]
        ownership_error = {
            "error": {
                "code": "bound_continuation_unavailable",
                "message": "bound continuation provider is unavailable",
            },
        }

        for name, additions, first_reply, statuses, post_count in cases:
            turns = [{"model": "deepseek-chat", "input": "synthetic ownership", **item}
                     for item in additions]
            replies = [first_reply or buffered_reply(0, created=42), buffered_reply(1, created=43)]
            for binary in (ORACLE, MODEX):
                with self.subTest(case=name, binary=str(binary)):
                    upstream, responses = observe_turns(binary, turns, replies)
                    self.assertEqual([row["status"] for row in responses], statuses)
                    self.assertEqual(len(upstream), post_count)
                    if statuses[-1] == 503:
                        self.assertEqual(json.loads(bytes.fromhex(responses[-1]["body"])), ownership_error)


if __name__ == "__main__":
    unittest.main()
