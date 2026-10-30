"""Real-process regression for bounded SSE continuation ownership observation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes, serving
from test_deepseek_continuation import buffered_reply, observe_turns
from test_super_launch import CODEX
from test_cli import MODEX, ORACLE, ORACLE_SHA256


CLIENT = CODEX[:CODEX.index("passthrough = scenario")]
CLIENT += r'''
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
for turn in json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text()):
    path = turn.pop("_path", "/v1/responses")
    headers = {"Content-Type": "application/json", "Authorization": authorization,
               **turn.pop("_headers", {})}
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=15)
    connection.request("POST", path, json.dumps(turn, separators=(",", ":")).encode(), headers)
    response = connection.getresponse()
    payload = response.read()
    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),
          "body": payload.hex()})
    connection.close()
print("runtime-observer-complete")
'''


def observe_case(binary, event_body, followup_id, *, chunk_size=8191):
    with tempfile.TemporaryDirectory(prefix="modex-runtime-observer-") as temporary:
        root = Path(temporary)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            '{"source":"GitHub","latest_version":"0.439.2","checked_at":4102444800}'
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + CLIENT)
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        turns_file = root / "turns.json"
        turns_file.write_text(json.dumps([
            {"model": "deepseek-chat", "input": "synthetic first", "messages": [],
             "stream": True, "_path": "/v1/chat/completions"},
            {"model": "deepseek-chat", "input": "synthetic followup", "messages": [],
             "previous_response_id": followup_id},
        ]))
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "MODEX_CONTINUATION_TURNS_FILE": str(turns_file),
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        first = {"status": 200, "content_type": "text/event-stream", "body": event_body,
                 "chunked": True, "chunk_size": chunk_size}
        second = {"status": 200, "content_type": "application/json", "body": json_bytes({
            "id": "synthetic-chat-followup", "model": "deepseek-chat",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic reply"},
                         "finish_reason": "stop"}],
        })}
        with serving([first, second]) as server:
            result = subprocess.run(
                [str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
                 "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", "deepseek-chat",
                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                cwd=root / "work", env=environment, capture_output=True, timeout=45,
            )
            records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
            if result.returncode != 0 or b"runtime-observer-complete" not in result.stdout:
                raise AssertionError((result.returncode, result.stdout, result.stderr, records, server.records))
        return server.records, [record for record in records if record["kind"] == "response"]


def completed_event(data):
    return b"event: response.completed\ndata: " + data + b"\n\n"


def nested_response(arrays):
    return ('{"response":{"id":"resp_depth"},"deep":' + "[" * arrays + "0" + "]" * arrays + "}").encode()


class RuntimeObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("oracle does not match the pinned Prodex 0.439.2 release")

    def test_large_valid_sse_event_binds_before_followup_dispatch(self):
        response_id = "synthetic-large-response"
        data = (
            b'{"response":{"id":"' + response_id.encode() + b'"},"filler":"'
            + b"x" * (4 * 1024 * 1024)
            + b'"}'
        )
        first_response = {
            "status": 200,
            "content_type": "text/event-stream",
            "body": b"event: response.completed\ndata: " + data + b"\n\n",
            "chunked": True,
            "chunk_size": 8191,
        }
        turns = [
            {
                "model": "deepseek-chat",
                "input": "first synthetic turn",
                "_path": "/v1/chat/completions",
                "messages": [],
                "stream": True,
            },
            {"model": "deepseek-chat", "input": "follow the response", "use_previous": True},
        ]
        error = {
            "error": {
                "code": "bound_continuation_unavailable",
                "message": "bound continuation provider is unavailable",
            }
        }

        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [first_response, buffered_reply(1, created=43)]
                )
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertEqual(len(upstream), 1)
                self.assertEqual(json.loads(bytes.fromhex(responses[1]["body"])), error)
                self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_bounded_sse_json_controls_match_release_before_followup_dispatch(self):
        cases = [
            ("ordinary", completed_event(b'{"response":{"id":"resp_ordinary"}}'), "resp_ordinary", 17, 503, 1),
            ("incomplete-json", completed_event(b'{"response":{"id":"resp_incomplete"},"tail":'), "resp_incomplete", 13, 200, 2),
            ("trailing-json", completed_event(b'{"response":{"id":"resp_trailing"}}x'), "resp_trailing", 13, 200, 2),
            ("bad-number-after-id", completed_event(b'{"response":{"id":"resp_bad_number"},"n":1e9999}'), "resp_bad_number", 9, 200, 2),
            ("valid-long-number", completed_event(("{\"response\":{\"id\":\"resp_long_number\"},\"n\":0." + "0" * 300 + "1}").encode()), "resp_long_number", 3, 503, 1),
            ("duplicate-id-last-wins", completed_event(b'{"response":{"id":"resp_old","id":"resp_new"}}'), "resp_new", 1, 503, 1),
            ("duplicate-id-old-not-bound", completed_event(b'{"response":{"id":"resp_old","id":"resp_new"}}'), "resp_old", 5, 200, 2),
            ("non-string-inner-id-fallback", completed_event(b'{"response":{"id":12},"id":"resp_fallback"}'), "resp_fallback", 7, 503, 1),
            ("escaped-key-and-value", completed_event(b'{"res\\u0070onse":{"id":"resp_\\u0065scaped"}}'), "resp_escaped", 1, 503, 1),
            ("multiline-data", b'event: response.completed\ndata: {"response":\ndata: {"id":"resp_multiline"}}\n\n', "resp_multiline", 3, 503, 1),
            ("valid-json-at-eof", b'data: {"response":{"id":"resp_eof"}}', "resp_eof", 2, 503, 1),
            ("utf8-split", completed_event('{"response":{"id":"resp_é_東京"}}'.encode()), "resp_é_東京", 1, 503, 1),
            ("unicode-data-prefix-whitespace", b'event: response.completed\ndata:' + "\u00a0".encode() + b'{"response":{"id":"resp_nbsp"}}\n\n', "resp_nbsp", 1, 503, 1),
            ("identifier-1024-bytes", completed_event(("{\"response\":{\"id\":\"" + "r" * 1024 + "\"}}").encode()), "r" * 1024, 997, 503, 1),
            ("identifier-1025-bytes-rejected-before-dispatch", completed_event(("{\"response\":{\"id\":\"" + "r" * 1025 + "\"}}").encode()), "r" * 1025, 997, 503, 1),
            ("invalid-utf8", completed_event(b'{"response":{"id":"resp_invalid_utf8"},"value":"\xff"}'), "resp_invalid_utf8", 2, 200, 2),
            ("valid-before-invalid-utf8-same-chunk", completed_event(b'{"response":{"id":"resp_before_invalid"}}') + completed_event(b'{"response":{"id":"resp_invalid_utf8"},"value":"' + bytes([255]) + b'"}'), "resp_before_invalid", 128, 503, 1),
            ("depth-125", completed_event(nested_response(125)), "resp_depth", 31, 503, 1),
            ("depth-126-valid", completed_event(nested_response(126)), "resp_depth", 19, 503, 1),
            ("depth-127-invalid", completed_event(nested_response(127)), "resp_depth", 11, 200, 2),
        ]
        for name, body, previous_id, chunk_size, expected_status, expected_posts in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(case=name, binary=str(binary)):
                    upstream, responses = observe_case(binary, body, previous_id, chunk_size=chunk_size)
                    self.assertEqual(len(responses), 2)
                    self.assertEqual([item["status"] for item in responses], [200, expected_status])
                    self.assertEqual(len(upstream), expected_posts)
                    self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)

    def test_oversized_valid_event_binds_with_one_post(self):
        data = b'{"response":{"id":"resp_oversized"},"filler":"' + b"x" * (4 * 1024 * 1024) + b'"}'
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_case(binary, completed_event(data), "resp_oversized", chunk_size=8191)
                self.assertEqual([item["status"] for item in responses], [200, 503])
                self.assertEqual(len(upstream), 1)

    def test_unicode_whitespace_before_event_json_matches_release(self):
        codepoints = (0x0B, 0x0C, 0x85, 0x1680, *range(0x2000, 0x200B),
                      0x2028, 0x2029, 0x202F, 0x205F, 0x3000)
        for codepoint in codepoints:
            response_id = f"resp_whitespace_{codepoint:x}"
            event = (b'event: response.completed\ndata:' + chr(codepoint).encode()
                     + b'{"response":{"id":"' + response_id.encode() + b'"}}\n\n')
            for binary in (ORACLE, MODEX):
                with self.subTest(codepoint=hex(codepoint), binary=str(binary)):
                    upstream, responses = observe_case(binary, event, response_id, chunk_size=1)
                    self.assertEqual([item["status"] for item in responses], [200, 503])
                    self.assertEqual(len(upstream), 1)


if __name__ == "__main__":
    unittest.main()
