"""Pinned-release observations through real Super and isolated synthetic peers."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes, serving
from test_super_launch import CODEX


CLIENT = CODEX[:CODEX.index('passthrough = scenario')]
CLIENT += r'''
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + "/responses")
previous = None
for turn in json.loads(os.environ["MODEX_CONTINUATION_TURNS"]):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer synthetic-client-key",
               **turn.pop("_headers", {})}
    if turn.pop("use_previous", False):
        turn["previous_response_id"] = previous
    started = int(time.time())
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
    connection.request("POST", target.path, json.dumps(turn, separators=(",", ":")).encode(),
                       headers)
    response = connection.getresponse()
    payload = response.read()
    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),
          "body": payload.hex(), "started": started, "finished": int(time.time())})
    connection.close()
    if response.status == 200:
        previous = json.loads(payload)["id"]
print("synthetic-continuation-complete")
'''


def observe_turns(binary, turns, responses):
    with tempfile.TemporaryDirectory(prefix="modex-continuation-") as temporary:
        root = Path(temporary)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            '{"source":"GitHub","latest_version":"0.439.1","checked_at":4102444800}'
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + CLIENT)
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "MODEX_CONTINUATION_TURNS": json.dumps(turns),
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        with serving(responses) as server:
            result = subprocess.run(
                [str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
                 "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", "deepseek-chat",
                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                cwd=root / "work", env=environment, capture_output=True, timeout=45,
            )
            if result.returncode != 0 or b"synthetic-continuation-complete" not in result.stdout:
                records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
                records = [record for record in records if record["kind"] == "response"]
                raise AssertionError((result.returncode, result.stdout, result.stderr, records, server.records))
        records = [json.loads(line) for line in capture.read_text().splitlines()]
        return server.records, [record for record in records if record["kind"] == "response"]


def buffered_reply(index=0, **fields):
    return {"status": 200, "content_type": "application/json", "body": json_bytes({
        "id": f"synthetic-chat-{index}", "model": "deepseek-chat",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic reply"},
                     "finish_reason": "stop"}], **fields,
    })}


class DeepSeekContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("oracle does not match pinned Prodex 0.439.1")

    def test_invalid_continuation_identities_fail_before_provider_side_effects(self):
        invalid = ["a\0b", "a\x1fb", "a\x7fb", "a\x80b", "a\x9fb", "x" * 1025, "é" * 513]
        variants = [{"previous_response_id": value} for value in invalid]
        variants += [{"session_id": "a\x80b"}, {"client_metadata": {"session_id": "x" * 1025}},
                     {"_headers": {"session_id": "x" * 1025}},
                     {"_headers": {"x-codex-turn-state": "x" * 1025}},
                     {"_headers": {"x-codex-turn-metadata": json.dumps({"session_id": "a\0b"})}}]
        turns = [{"model": "deepseek-chat", "input": "synthetic invalid identity", **value}
                 for value in variants]
        error = {"error": {"code": "bound_continuation_unavailable",
                           "message": "bound continuation provider is unavailable"}}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [buffered_reply()] * len(turns))
                self.assertEqual(len(responses), len(turns))
                self.assertEqual(upstream, [])
                for response in responses:
                    self.assertEqual(response["status"], 503)
                    self.assertEqual(json.loads(bytes.fromhex(response["body"])), error)
                    headers = {name.lower(): value for name, value in response["headers"].items()}
                    self.assertEqual(headers["cache-control"], "no-store")
                    self.assertEqual(headers["x-content-type-options"], "nosniff")

    def test_valid_identity_boundaries_and_header_precedence_match_release(self):
        variants = [{"previous_response_id": "é" * 512}, {"session_id": "s" * 1024},
                    {"previous_response_id": " \t \n "},
                    {"_headers": {"session_id": "valid-first", "x-session-id": "x" * 1025}},
                    {"_headers": {"x-codex-turn-state": "t" * 1024}}]
        turns = [{"model": "deepseek-chat", "input": "synthetic valid identity", **value}
                 for value in variants]
        replies = [buffered_reply(index, created=42) for index in range(len(turns))]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual([response["status"] for response in responses], [200] * len(turns))
            for record in upstream:
                self.assertEqual(record["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                self.assertEqual(record["path"], "/v1/chat/completions")
            observed.append([json.loads(record["body"]) for record in upstream])
        self.assertEqual(*observed)

    def test_created_fallback_and_unsigned_values_match_release(self):
        fields = [{}, {"created": None}, {"created": -1}, {"created": False},
                  {"created": "42"}, {"created": 0}, {"created": 42}]
        turns = [{"model": "deepseek-chat", "input": "synthetic timestamp"} for _ in fields]
        replies = [buffered_reply(index, **value) for index, value in enumerate(fields)]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual(len(responses), len(turns))
            bodies = []
            for index, response in enumerate(responses):
                self.assertEqual(response["status"], 200)
                body = json.loads(bytes.fromhex(response["body"]))
                created = body.pop("created_at")
                if index < 5:
                    self.assertGreaterEqual(created, response["started"])
                    self.assertLessEqual(created, response["finished"])
                else:
                    self.assertEqual(created, fields[index]["created"])
                bodies.append(body)
            observed.append(bodies)
        self.assertEqual(*observed)

    def test_delayed_created_fallback_matches_release(self):
        reply = buffered_reply(ignored="x" * 80)
        reply.update(chunk_size=(len(reply["body"]) + 1) // 2, delay=1.2)
        turns = [{"model": "deepseek-chat", "input": "synthetic delayed timestamp"}]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [reply])
                self.assertEqual(len(upstream), 1)
                response = responses[0]
                created = json.loads(bytes.fromhex(response["body"]))["created_at"]
                self.assertGreater(created, response["started"])
                self.assertLessEqual(created, response["finished"])


if __name__ == "__main__":
    unittest.main()
