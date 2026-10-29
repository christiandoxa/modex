"""Compare malformed buffered DeepSeek choices through all three processes."""

import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_deepseek_continuation import observe_turns
from test_local_rewrite import json_bytes


REFERENCE_CACHE = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    REFERENCE_CACHE / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"


def _reply(index, choices):
    return {
        "status": 200,
        "content_type": "application/json",
        "body": json_bytes({
            "id": f"synthetic-choice-{index}",
            "model": "deepseek-chat",
            "choices": choices,
        }),
    }


class ProviderBufferedChoiceTests(unittest.TestCase):
    def test_nonobject_first_choice_fails_and_empty_or_later_choices_match(self):
        for binary, digest in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), digest)
        self.assertTrue(MODEX.is_file(), "Build the Modex binary first")

        turns = [
            {"model": "deepseek-chat", "input": "synthetic malformed choice"},
            {"model": "deepseek-chat", "input": "synthetic empty choices"},
            {"model": "deepseek-chat", "input": "synthetic later malformed choice"},
        ]
        replies = [
            _reply(0, [None, {"message": {"content": "must be ignored"}}]),
            _reply(1, []),
            _reply(2, [{"message": {"content": "first choice wins"}}, None]),
        ]
        observed = []
        for binary in (ORACLE_01651, ORACLE_04392, MODEX):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), 3)
            self.assertEqual([post["path"] for post in posts], ["/v1/chat/completions"] * 3)
            self.assertEqual([response["status"] for response in responses], [500, 200, 200])
            self.assertEqual(bytes.fromhex(responses[0]["body"]), b"")
            bodies = [json.loads(bytes.fromhex(response["body"])) for response in responses[1:]]
            self.assertEqual(bodies[0]["output"], [])
            self.assertEqual(bodies[1]["output"][0]["content"][0]["text"], "first choice wins")
            observed.append([response["status"] for response in responses])
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[1], observed[2])


if __name__ == "__main__":
    unittest.main()
