"""Buffered provider metadata passthrough against Prodex 0.166.0."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, serving
from test_super_launch import CODEX


REUSE_CLIENT = CODEX[:CODEX.index("passthrough = scenario")] + r'''
import socket
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + "/responses")
body = json.dumps({"model": "deepseek-chat", "messages": []}, separators=(",", ":")).encode()
def request(connection_close):
    headers = [f"Host: {target.hostname}:{target.port}", "Content-Type: application/json",
               "Authorization: " + authorization, f"Content-Length: {len(body)}"]
    if connection_close:
        headers.append("Connection: close")
    return ("POST /v1/chat/completions HTTP/1.1\r\n" + "\r\n".join(headers) +
            "\r\n\r\n").encode() + body
connection = socket.create_connection((target.hostname, target.port), timeout=5)
connection.settimeout(5)
connection.sendall(request(False))
first = bytearray()
while b"\r\n\r\n" not in first:
    chunk = connection.recv(4096)
    if not chunk: break
    first.extend(chunk)
head_end = first.find(b"\r\n\r\n") + 4
if head_end < 4: raise RuntimeError("missing first response headers")
while not first[head_end:].endswith(b"0\r\n\r\n"):
    chunk = connection.recv(4096)
    if not chunk: break
    first.extend(chunk)
connection.sendall(request(True))
tail = bytearray()
while True:
    try:
        chunk = connection.recv(65536)
    except TimeoutError:
        break
    if not chunk:
        break
    tail.extend(chunk)
connection.close()
save({"kind": "reuse-probe", "first_head": bytes(first[:head_end]).hex(),
      "tail": bytes(tail).hex()})
print("synthetic-continuation-complete")
'''


WIRE_CLIENT = CODEX[:CODEX.index("passthrough = scenario")] + r'''
import socket
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + "/responses")
body = json.dumps({"model": "deepseek-chat", "input": "synthetic empty stream", "stream": True}, separators=(",", ":")).encode()
connection_header = "Connection: close\r\n" if os.environ.get("MODEX_WIRE_CLOSE") == "1" else ""
request = (
    f"POST /v1/responses HTTP/1.1\r\nHost: {target.hostname}:{target.port}\r\n"
    f"Content-Type: application/json\r\nAuthorization: {authorization}\r\n"
    f"Content-Length: {len(body)}\r\n{connection_header}\r\n"
).encode() + body
second_body = json.dumps({"model": "deepseek-chat", "input": "synthetic pipelined request"}, separators=(",", ":")).encode()
second_request = (
    f"POST /v1/responses HTTP/1.1\r\nHost: {target.hostname}:{target.port}\r\n"
    f"Content-Type: application/json\r\nAuthorization: {authorization}\r\n"
    f"Content-Length: {len(second_body)}\r\nConnection: close\r\n\r\n"
).encode() + second_body
connection = socket.create_connection((target.hostname, target.port), timeout=10)
connection.settimeout(1.5)
connection.sendall(request + (second_request if os.environ.get("MODEX_WIRE_PIPELINE") == "1" else b""))
wire = bytearray()
eof = False
while True:
    try:
        chunk = connection.recv(65536)
    except TimeoutError:
        break
    if not chunk:
        eof = True
        break
    wire.extend(chunk)
connection.close()
save({"kind": "wire-response", "wire": bytes(wire).hex(), "eof": eof})
print("synthetic-wire-complete")
raise SystemExit(0)
'''


def observe_same_connection(binary, status):
    replies = [
        {"status": status, "content_type": "text/event-stream", "body": b"", "chunked": True},
        {"status": 200, "content_type": "application/json", "body": b'{"id":"synthetic-second"}'},
    ]
    with tempfile.TemporaryDirectory(prefix="modex-passthrough-01660-") as directory:
        root = Path(directory)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            json.dumps({"source": "GitHub", "latest_version": "0.166.0",
                        "checked_at": 4102444800}, separators=(",", ":"))
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + REUSE_CLIENT, encoding="utf-8")
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "TERM": "dumb", "NO_COLOR": "1",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        with serving(replies) as server:
            result = subprocess.run(
                [str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
                 "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", "deepseek-chat",
                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                cwd=root / "work", env=environment, capture_output=True, timeout=20,
            )
            records = server.records.copy()
        if result.returncode != 0 or b"synthetic-continuation-complete" not in result.stdout:
            raise AssertionError((result.returncode, result.stdout, result.stderr, records))
        probes = [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()]
        probes = [record for record in probes if record.get("kind") == "reuse-probe"]
        if len(probes) != 1:
            raise AssertionError(f"expected one same-connection capture, found {len(probes)}")
        return records, probes[0]


def observe_response_wire(binary, reply, *, request_close=False, pipeline_second=False):
    with tempfile.TemporaryDirectory(prefix="modex-response-wire-01660-") as directory:
        root = Path(directory)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            json.dumps({"source": "GitHub", "latest_version": "0.166.0",
                        "checked_at": 4102444800}, separators=(",", ":"))
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + WIRE_CLIENT, encoding="utf-8")
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "MODEX_WIRE_CLOSE": "1" if request_close else "0",
            "MODEX_WIRE_PIPELINE": "1" if pipeline_second else "0",
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")},
        }
        replies = [dict(reply)]
        if pipeline_second:
            replies.append({"status": 200, "content_type": "application/json", "body": b'{"id":"synthetic-second"}'})
        with serving(replies) as server:
            result = subprocess.run(
                [str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
                 "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", "deepseek-chat",
                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                cwd=root / "work", env=environment, capture_output=True, timeout=20,
            )
            upstream = server.records.copy()
        if result.returncode != 0 or b"synthetic-wire-complete" not in result.stdout:
            records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
            raise AssertionError((result.returncode, result.stdout, result.stderr, records, upstream))
        records = [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()]
        responses = [record for record in records if record.get("kind") == "wire-response"]
        if len(responses) != 1:
            raise AssertionError(f"expected one wire response, found {len(responses)}")
        return upstream, bytes.fromhex(responses[0]["wire"]), responses[0]["eof"]


def parse_raw_response(wire):
    head, separator, body = wire.partition(b"\r\n\r\n")
    if not separator:
        raise AssertionError(f"response has no header terminator: {wire!r}")
    status = int(head.split(b" ", 2)[1])
    headers = {}
    for line in head.split(b"\r\n")[1:]:
        name, value = line.split(b":", 1)
        headers[name.decode("ascii").lower()] = value.decode("ascii").strip()
    return status, headers, body


def decode_chunked_body(body):
    output = bytearray()
    while True:
        line, separator, remainder = body.partition(b"\r\n")
        if not separator:
            raise AssertionError(f"incomplete chunk size: {body!r}")
        size = int(line.split(b";", 1)[0], 16)
        if size == 0:
            if remainder != b"\r\n":
                raise AssertionError(f"incomplete terminal chunk: {remainder!r}")
            return bytes(output)
        if len(remainder) < size + 2 or remainder[size:size + 2] != b"\r\n":
            raise AssertionError(f"incomplete chunk payload: {remainder!r}")
        output.extend(remainder[:size])
        body = remainder[size + 2:]


class ProviderBufferedMetadata01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_buffered_passthrough_metadata_matches_active_release(self):
        values = ["synthetic-ascii", "synthetic\tmetadata", "synthetic-\x80",
                  "synthetic-\xff", "synthetic-\xc3\xa9"]
        payload = b"\x00synthetic metadata body\xff"
        for route, status in (("/v1/chat/completions?synthetic=metadata", 201), ("/v1/responses", 503)):
            turns = [{"model": "deepseek-chat", "_path": route,
                      **({"input": "synthetic"} if route == "/v1/responses" else {"messages": []}),
                      "_headers": {"x-codex-turn-state": f"synthetic-client-turn-{index}",
                          "x-codex-turn-metadata": json.dumps({"session_id": f"synthetic-metadata-{index}"}),
                          "x-prodex-internal-conversation-namespace": f"synthetic-namespace-{index}"}}
                     for index in range(len(values))]
            replies = [{"status": status, "content_type": "application/x-synthetic", "body": payload,
                        "response_headers": [("Content-Type", "application/x-synthetic"),
                            ("x-codex-turn-state", value), ("x-request-id", "synthetic-request"),
                            ("Connection", "X-Synthetic-Hop"), ("X-Synthetic-Hop", "strip-me")]}
                       for value in values]
            for binary in (ORACLE, MODEX):
                with self.subTest(route=route, binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary, turns, replies, latest_version="0.166.0",
                    )
                    self.assertEqual(len(upstream), len(turns), "metadata handling must never replay a POST")
                    self.assertEqual([row["status"] for row in responses], [status] * len(turns))
                    for index, response in enumerate(responses):
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertEqual(headers.get("x-codex-turn-state"), values[index] if index < 2 else None)
                        self.assertEqual(headers["x-request-id"], "synthetic-request")
                        self.assertNotIn("x-synthetic-hop", headers)
                        self.assertEqual(bytes.fromhex(response["body"]), payload)
                        sent = upstream[index]["headers"]
                        self.assertEqual(sent["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                        self.assertEqual(sent["x-codex-turn-state"], f"synthetic-client-turn-{index}")
                        self.assertFalse(any(name.startswith("x-prodex-internal-") for name in sent))

    def test_503_passthrough_header_names_match_active_release(self):
        body = b"synthetic policy capacity"
        request = [{"model": "deepseek-chat", "messages": [],
                    "_path": "/v1/chat/completions?synthetic=header-casing"}]
        reply = {"status": 503, "content_type": "application/x-synthetic", "body": body,
                 "response_headers": [("Content-Type", "application/x-synthetic"),
                                      ("X-Request-ID", "synthetic-request"),
                                      ("X-RateLimit-Remaining", "0")]}

        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, request, [reply], latest_version="0.166.0",
                )
                self.assertEqual(len(upstream), 1)
                self.assertEqual(responses[0]["status"], 503)
                self.assertEqual(bytes.fromhex(responses[0]["body"]), body)
                headers = responses[0]["headers"]
                for name in ("server", "date", "content-type", "x-request-id",
                             "x-ratelimit-remaining"):
                    self.assertIn(name, headers)
                    self.assertFalse(any(header.lower() == name and header != name
                                          for header in headers))
                self.assertEqual(headers["x-request-id"], "synthetic-request")
                self.assertEqual(headers["x-ratelimit-remaining"], "0")
                self.assertEqual(headers["Content-Length"], str(len(body)))

    def test_duplicate_content_type_uses_last_value_and_keeps_header_order(self):
        expected = [
            ["x-before", "synthetic-before"],
            ["content-type", "application/x-second"],
            ["set-cookie", "first=1"],
            ["set-cookie", "second=2"],
            ["x-repeat", "first"],
            ["x-repeat", "second"],
            ["x-keep", "synthetic-keep"],
        ]
        headers = [
            ("X-Before", "synthetic-before"),
            ("Content-Type", "application/x-first"),
            ("Set-Cookie", "first=1"),
            ("Content-Type", "application/x-second"),
            ("Set-Cookie", "second=2"),
            ("X-Repeat", "first"),
            ("X-Repeat", "second"),
            ("Connection", "X-Synthetic-Hop"),
            ("X-Synthetic-Hop", "strip-me"),
            ("X-Keep", "synthetic-keep"),
        ]
        cases = (
            ("Chat Completions", {"model": "deepseek-chat", "messages": [],
                                   "_path": "/v1/chat/completions"},
             {**buffered_reply(), "response_headers": headers}, 200),
            ("Responses error", {"model": "deepseek-chat", "input": "synthetic",
                                 "_path": "/v1/responses"},
             {"status": 503, "content_type": "application/json",
              "body": b'{"error":{"message":"synthetic failure"}}',
              "response_headers": headers}, 503),
        )
        for name, request, reply, status in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(route=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, [request], [reply], latest_version="0.166.0",
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual([response["status"] for response in responses], [status])
                    relevant = [
                        [header_name.lower(), value]
                        for header_name, value in responses[0]["header_list"]
                        if header_name.lower() in {
                            "x-before", "content-type", "set-cookie", "x-repeat",
                            "x-synthetic-hop", "x-keep",
                        }
                    ]
                    self.assertEqual(relevant, expected)

    def test_duplicate_content_type_first_value_controls_sse_classification(self):
        event = {"id": "synthetic-stream", "created": 42,
                 "model": "deepseek-chat", "choices": []}
        sse_body = b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        json_body = json.dumps({
            "id": "synthetic-json", "model": "deepseek-chat",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic"},
                         "finish_reason": "stop"}],
        }, separators=(",", ":")).encode()
        cases = (
            ("JSON then SSE", ["application/json", "text/event-stream"], sse_body,
             [["content-type", "text/event-stream"], ["content-length", str(len(sse_body))]]),
            ("SSE then JSON", ["text/event-stream", "application/json"], json_body,
             [["transfer-encoding", "chunked"], ["content-type", "text/event-stream"],
              ["content-type", "application/json"]]),
        )
        turn = {"model": "deepseek-chat", "messages": [], "stream": True,
                "_path": "/v1/chat/completions"}
        for name, content_types, body, expected_headers in cases:
            reply = {
                "status": 200,
                "content_type": content_types[0],
                "body": body,
                "chunked": True,
                "response_headers": [("Content-Type", value) for value in content_types],
            }
            for binary in (ORACLE, MODEX):
                with self.subTest(order=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, [turn], [reply], latest_version="0.166.0",
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), body)
                    relevant = [
                        [header_name.lower(), value]
                        for header_name, value in responses[0]["header_list"]
                        if header_name.lower() in {
                            "content-type", "content-length", "transfer-encoding",
                        }
                    ]
                    self.assertEqual(relevant, expected_headers)

    def test_bodyless_sse_connection_header_preserves_observed_reuse(self):
        for status in (204, 304):
            for binary in (ORACLE, MODEX):
                with self.subTest(status=status, binary=str(binary)):
                    upstream, probe = observe_same_connection(binary, status)
                    first_head = bytes.fromhex(probe["first_head"])
                    tail = bytes.fromhex(probe["tail"])
                    self.assertTrue(first_head.startswith(f"HTTP/1.1 {status} ".encode("ascii")))
                    headers = {}
                    for line in first_head.split(b"\r\n")[1:]:
                        if not line:
                            continue
                        name, value = line.split(b":", 1)
                        headers[name.decode("ascii").lower()] = value.decode("ascii").strip()
                    self.assertEqual(headers.get("connection"), "close")
                    self.assertEqual(headers.get("transfer-encoding"), "chunked")
                    self.assertNotIn("content-length", headers)
                    second_head_end = tail.find(b"\r\n\r\n") + 4
                    self.assertGreaterEqual(second_head_end, 4, "same-socket second response headers missing")
                    second_head = tail[:second_head_end]
                    self.assertTrue(second_head.startswith(b"HTTP/1.1 200 "))
                    second_headers = {}
                    for line in second_head.split(b"\r\n")[1:]:
                        if not line:
                            continue
                        name, value = line.split(b":", 1)
                        second_headers[name.decode("ascii").lower()] = value.decode("ascii").strip()
                    second_body = b'{"id":"synthetic-second"}'
                    self.assertEqual(int(second_headers["content-length"]), len(second_body))
                    self.assertEqual(tail[second_head_end:], second_body)
                    self.assertEqual(len(upstream), 2, "second same-socket request must reach the synthetic provider")

    def test_bodyless_json_and_sse_205_framing_controls_match_active_release(self):
        cases = [
            (204, "application/json", {"declared_length": 0}, "0", None, None),
            (304, "application/json", {"declared_length": 16}, "0", None, None),
            (205, "text/event-stream", {"declared_length": 0}, None, "chunked", "close"),
        ]
        for status, content_type, framing, length, transfer_encoding, connection in cases:
            reply = {"status": status, "content_type": content_type, "body": b"", **framing}
            for binary in (ORACLE, MODEX):
                with self.subTest(status=status, content_type=content_type, binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "messages": [], "_path": "/v1/chat/completions"}],
                        [reply], latest_version="0.166.0",
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(responses[0]["status"], status)
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), b"")
                    headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
                    self.assertEqual(headers.get("content-length"), length)
                    self.assertEqual(headers.get("transfer-encoding"), transfer_encoding)
                    self.assertEqual(headers.get("connection"), connection)

    def test_responses_empty_204_sse_and_bodyless_controls_match_active_wire(self):
        cases = [
            ("204-sse-length", {"status": 204, "content_type": "text/event-stream", "body": b""}, False, 204, "event"),
            ("204-sse-chunked-held-open", {"status": 204, "content_type": "text/event-stream", "body": b"", "chunked": True, "hold_open": True}, False, 204, "event"),
            ("304-sse", {"status": 304, "content_type": "text/event-stream", "body": b""}, True, 304, "empty-event"),
            ("205-sse", {"status": 205, "content_type": "text/event-stream", "body": b""}, True, 205, "event"),
            ("204-json", {"status": 204, "content_type": "application/json", "body": b""}, True, 502, "processing-error"),
            ("304-json", {"status": 304, "content_type": "application/json", "body": b""}, True, 304, "empty-json"),
        ]
        for label, reply, request_close, expected_status, expected_body in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(case=label, binary=str(binary)):
                    upstream, wire, eof = observe_response_wire(binary, reply, request_close=request_close)
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    status, headers, body = parse_raw_response(wire)
                    self.assertEqual(status, expected_status)
                    if status == 204 and binary == ORACLE:
                        self.assertFalse(eof, "the pinned release leaves its keep-alive socket open")
                    else:
                        self.assertTrue(eof, "client must observe an actual peer close")
                    if expected_body in ("event", "empty-event"):
                        self.assertEqual(headers.get("transfer-encoding"), "chunked")
                        self.assertEqual(headers.get("connection"), "close")
                        self.assertNotIn("content-length", headers)
                        self.assertTrue(body.endswith(b"0\r\n\r\n"))
                        payload = decode_chunked_body(body)
                        if expected_body == "event":
                            self.assertIn(b"event: response.failed\r\n", payload)
                            self.assertIn(b"provider_stream_error", payload)
                            self.assertIn(b"unexpected end of stream", payload)
                        else:
                            self.assertEqual(payload, b"")
                    elif expected_body == "processing-error":
                        self.assertEqual(headers.get("content-length"), "40")
                        self.assertEqual(len(body), 40)
                    else:
                        self.assertEqual(headers.get("content-length"), "0")
                        self.assertEqual(body, b"")

        upstream, wire, eof = observe_response_wire(
            MODEX,
            {"status": 204, "content_type": "text/event-stream", "body": b""},
            pipeline_second=True,
        )
        status, headers, body = parse_raw_response(wire)
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("connection"), "close")
        self.assertTrue(body.endswith(b"0\r\n\r\n"))
        self.assertIn(b"unexpected end of stream", decode_chunked_body(body))
        self.assertTrue(eof, "a pipelined request must not keep the 204 stream socket alive")
        self.assertEqual(len(upstream), 1, "the pipelined second request must not reach the provider")


if __name__ == "__main__":
    unittest.main()
