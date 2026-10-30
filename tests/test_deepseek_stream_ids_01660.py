"""Compare DeepSeek stream item IDs with the isolated 0.166.0 release."""

import hashlib
import re
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import json_bytes


def stream_reply(response_id, text):
    chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "deepseek-chat",
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant", "content": text},
            "finish_reason": None,
        }],
    }
    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b"data: " + json_bytes(chunk) + b"\n\ndata: [DONE]\n\n",
    }


def item_id(body):
    values = re.findall(rb'"id":"(msg_deepseek_[0-9]+)"', body)
    if len(values) != 2 or values[0] != values[1]:
        raise AssertionError(f"expected one item ID shared by added and done events: {values!r}")
    value = int(values[0].removeprefix(b"msg_deepseek_"))
    if value > 0xFFFFFFFFFFFFFFFF:
        raise AssertionError(f"item ID does not fit the observed UInt64 shape: {value}")
    return values[0], value


def normalize_item_id(body):
    return re.sub(rb'"id":"msg_deepseek_[0-9]+"', b'"id":"msg_deepseek_ID"', body)


class DeepSeekStreamItemIDs01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def observe(self, binary, turns, replies):
        upstream, responses = observe_turns(
            binary, turns, replies, latest_version="0.166.0",
        )
        self.assertEqual([row["status"] for row in responses], [200] * len(turns))
        self.assertEqual(len(upstream), len(turns))
        self.assertEqual([row["path"] for row in upstream], ["/v1/chat/completions"] * len(turns))
        self.assertEqual(
            [row["headers"]["authorization"] for row in upstream],
            ["Bearer synthetic-provider-key"] * len(turns),
        )
        bodies = [bytes.fromhex(row["body"]) for row in responses]
        ids = [item_id(body) for body in bodies]
        return bodies, ids

    def test_item_ids_match_active_stream_shape_and_uniqueness(self):
        turns = [
            {"model": "deepseek-chat", "input": "synthetic stream one", "stream": True},
            {"model": "deepseek-chat", "input": "synthetic stream two", "stream": True},
        ]
        replies = [stream_reply("chatcmpl_stream_1", "one"), stream_reply("chatcmpl_stream_2", "two")]
        observed = {}
        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            with self.subTest(binary=str(binary)):
                bodies, ids = self.observe(binary, turns, replies)
                self.assertEqual([value & 0xFFFFFFFF for _, value in ids], [1, 2])
                self.assertEqual(len({value for _, value in ids}), 2)
                observed[label] = bodies, ids

        for index in range(len(turns)):
            self.assertEqual(
                normalize_item_id(observed["modex"][0][index]),
                normalize_item_id(observed["oracle"][0][index]),
            )

        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            with self.subTest(binary=str(binary), process="second"):
                second_bodies, second_ids = self.observe(
                    binary,
                    [turns[0]],
                    [stream_reply("chatcmpl_stream_1", "one")],
                )
                self.assertEqual(second_ids[0][1] & 0xFFFFFFFF, 1)
                self.assertNotEqual(second_ids[0][1], observed[label][1][0][1])
                self.assertEqual(
                    normalize_item_id(second_bodies[0]),
                    normalize_item_id(observed[label][0][0]),
                )


if __name__ == "__main__":
    unittest.main()
