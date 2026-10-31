"""Buffered provider metadata passthrough against Prodex 0.166.0."""

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, UpstreamHandler, serving
from test_super_launch import CODEX


WIRE_READ_TIMEOUT_SECONDS = 1.5


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
connection.settimeout(float(os.environ["MODEX_WIRE_READ_TIMEOUT_SECONDS"]))
connection.sendall(request + (second_request if os.environ.get("MODEX_WIRE_PIPELINE") == "1" else b""))
wire = bytearray()
eof = False
timed_out = False
while True:
    try:
        chunk = connection.recv(65536)
    except TimeoutError:
        timed_out = True
        break
    if not chunk:
        eof = True
        break
    wire.extend(chunk)
connection.close()
save({"kind": "wire-response", "wire": bytes(wire).hex(), "eof": eof,
      "timed_out": timed_out})
print("synthetic-wire-complete")
raise SystemExit(0)
'''


CONNECT_WIRE_CLIENT = CODEX[:CODEX.index("passthrough = scenario")] + r'''
import socket
target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
request = (
    f"CONNECT /models HTTP/1.1\r\nHost: {target.hostname}:{target.port}\r\n"
    f"Authorization: {authorization}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
).encode()
connection = socket.create_connection((target.hostname, target.port), timeout=10)
connection.settimeout(float(os.environ["MODEX_WIRE_READ_TIMEOUT_SECONDS"]))
connection.sendall(request)
wire = bytearray()
eof = False
timed_out = False
while True:
    try:
        chunk = connection.recv(65536)
    except TimeoutError:
        timed_out = True
        break
    if not chunk:
        eof = True
        break
    wire.extend(chunk)
connection.close()
save({"kind": "wire-response", "wire": bytes(wire).hex(), "eof": eof,
      "timed_out": timed_out})
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


def observe_response_wire(binary, reply, *, request_close=False, pipeline_second=False,
                          client_script=WIRE_CLIENT):
    with tempfile.TemporaryDirectory(prefix="modex-response-wire-01660-") as directory:
        root = Path(directory)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            json.dumps({"source": "GitHub", "latest_version": "0.166.0",
                        "checked_at": 4102444800}, separators=(",", ":"))
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + client_script, encoding="utf-8")
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered", "MODEX_WIRE_CLOSE": "1" if request_close else "0",
            "MODEX_WIRE_PIPELINE": "1" if pipeline_second else "0",
            "MODEX_WIRE_READ_TIMEOUT_SECONDS": str(WIRE_READ_TIMEOUT_SECONDS),
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
        return (upstream, bytes.fromhex(responses[0]["wire"]),
                responses[0]["eof"], responses[0]["timed_out"])


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


def parse_sse_events(body):
    events = []
    event_name = None
    data_lines = []
    for line in body.splitlines() + [b""]:
        if line.startswith(b"event: "):
            event_name = line[7:].decode("ascii")
        elif line.startswith(b"data: "):
            data_lines.append(line[6:])
        elif not line and data_lines:
            events.append((event_name, json.loads(b"\n".join(data_lines))))
            event_name = None
            data_lines = []
    return events


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

    def test_redirect_authorities_canonicalize_same_loopback_endpoint_only(self):
        request = [{"model": "deepseek-chat", "input": "synthetic canonical redirect"}]
        final = buffered_reply(88)
        equivalent_origins = (
            ("127.0.0.1", False, "http://127.1:{upstream_port}/v1/short", "/v1/short"),
            ("127.0.0.1", False, "http://127%2e0%2e0%2e1:{upstream_port}/v1/encoded-dotted", "/v1/encoded-dotted"),
            ("127.0.0.1", False, "http://127%2e1:{upstream_port}/v1/encoded-short", "/v1/encoded-short"),
            ("[::1]", True, "http://[0:0:0:0:0:0:0:1]:{upstream_port}/v1/expanded", "/v1/expanded"),
        )
        for base_host, ipv6, location, final_path in equivalent_origins:
            redirect = {"status": 302, "content_type": "text/plain", "body": b"discarded",
                        "response_headers": [("Location", location), ("Content-Type", "text/plain")]}
            for binary in (ORACLE, MODEX):
                with self.subTest(binary=str(binary), base_host=base_host):
                    upstream, responses = observe_turns(
                        binary, request, [redirect, final], latest_version="0.166.0",
                        base_host=base_host, upstream_ipv6=ipv6,
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                        ("POST", "/v1/chat/completions"), ("GET", final_path),
                    ])
                    self.assertEqual(upstream[0]["headers"]["host"], upstream[1]["headers"]["host"])
                    self.assertEqual(upstream[1]["headers"]["authorization"],
                                     "Bearer " + SYNTHETIC_API_KEY)
                    self.assertEqual(json.loads(bytes.fromhex(responses[0]["body"]))["id"],
                                     "synthetic-chat-88")

        rejected_origins = (
            "http://[::2]:{upstream_port}/v1/other-ip",
            "http://[::]:{upstream_port}/v1/unspecified-ip",
            "http://[::0]:{upstream_port}/v1/zero-ip",
            "http://[::0000]:{upstream_port}/v1/zero-ip-padded",
            "http://[::1]:1/v1/other-port",
            "http://synthetic@[::1]:{upstream_port}/v1/userinfo",
            "https://[::1]:{upstream_port}/v1/https",
            "http://[::1]%3A{upstream_port}/v1/encoded-authority-delimiter",
            "http://[::g]:{upstream_port}/v1/malformed-ip",
        )
        for location in rejected_origins:
            redirect = {"status": 302, "content_type": "text/plain", "body": b"not followed",
                        "response_headers": [("Location", location), ("Content-Type", "text/plain")]}
            with self.subTest(rejected_location=location):
                upstream, responses = observe_turns(
                    MODEX, request, [redirect], latest_version="0.166.0",
                    base_host="[::1]", upstream_ipv6=True,
                )
                self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                    ("POST", "/v1/chat/completions"),
                ])
                self.assertEqual(responses[0]["status"], 302)
                headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
                self.assertEqual(headers["location"], location.replace("{upstream_port}", upstream[0]["headers"]["host"].split(":")[-1]))
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"not followed")

        encoded_rejected_origins = (
            "http://127%2e0%2e0%2e1:1/v1/other-port",
            "http://127%2e0%2e0%2e1%3a{upstream_port}/v1/encoded-port-delimiter",
            "http://127%2e0%2e0%2e1%2f@127.0.0.1:{upstream_port}/v1/encoded-path-delimiter",
            "http://127%2e0%2e0%2e1%5c@127.0.0.1:{upstream_port}/v1/encoded-backslash",
            "http://127%2e0%2e0%2e1%40attacker:{upstream_port}/v1/encoded-userinfo",
            "http://127%2e0%2e0%2e1%ZZ:{upstream_port}/v1/malformed-host-escape",
            "http://127%252e0%252e0%252e1:{upstream_port}/v1/double-encoded-host",
            "http://8%2e8%2e8%2e8:{upstream_port}/v1/encoded-non-loopback",
        )
        for location in encoded_rejected_origins:
            redirect = {"status": 302, "content_type": "text/plain", "body": b"not followed",
                        "response_headers": [("Location", location), ("Content-Type", "text/plain")]}
            with self.subTest(rejected_encoded_location=location):
                upstream, responses = observe_turns(
                    MODEX, request, [redirect], latest_version="0.166.0",
                    base_host="127.0.0.1",
                )
                self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                    ("POST", "/v1/chat/completions"),
                ])
                self.assertEqual(responses[0]["status"], 302)
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"not followed")

        expanded_origin = "http://[0:0:0:0:0:0:0:1]:{upstream_port}/v1/redirect-cycle"
        redirects = [{"status": 307, "content_type": "text/plain", "body": b"",
                      "response_headers": [("Location", expanded_origin), ("Content-Type", "text/plain")]}
                     for _ in range(11)]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary), bounded=True):
                upstream, responses = observe_turns(
                    binary, request, redirects, latest_version="0.166.0",
                    base_host="[::1]", upstream_ipv6=True,
                )
                self.assertEqual(len(upstream), 11)
                self.assertEqual([response["status"] for response in responses], [502])
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"upstream request failed")

    def test_empty_location_redirects_reuse_current_url_only_when_header_is_present(self):
        turn = [{"model": "deepseek-chat", "input": "synthetic relative redirect"}]
        current = "/v1/chat/completions"
        cases = (
            ("missing", None, [("POST", current)], 302),
            ("empty", "", [("POST", current), ("GET", current)], 200),
            ("query", "?synthetic=query", [("POST", current), ("GET", current + "?synthetic=query")], 200),
            ("fragment", "#synthetic-fragment", [("POST", current), ("GET", current)], 200),
        )
        for label, location, expected_requests, expected_status in cases:
            redirect = {"status": 302, "content_type": "text/plain", "body": b"discarded"}
            if location is not None:
                redirect["response_headers"] = [("Location", location)]
            observations = []
            for binary in (ORACLE, MODEX):
                with self.subTest(case=label, binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary, turn, [redirect, buffered_reply(91)], latest_version="0.166.0",
                    )
                    requests = [(row["method"], row["path"]) for row in upstream]
                    self.assertEqual(requests, expected_requests)
                    self.assertEqual([row["status"] for row in responses], [expected_status])
                    self.assertEqual([row["headers"]["authorization"] for row in upstream],
                                     ["Bearer synthetic-provider-key"] * len(expected_requests))
                    observations.append((requests, [row["status"] for row in responses]))
            self.assertEqual(observations[0], observations[1])

    def test_empty_location_redirect_loop_keeps_the_existing_cap(self):
        current = "/v1/chat/completions"
        redirects = [
            {"status": 302, "content_type": "text/plain", "body": b"discarded",
             "response_headers": [("Location", "")]}
            for _ in range(11)
        ]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [{"model": "deepseek-chat", "input": "synthetic bounded redirect"}],
                    redirects, latest_version="0.166.0",
                )
                self.assertEqual([(row["method"], row["path"]) for row in upstream],
                                 [("POST", current)] + [("GET", current)] * 10)
                self.assertEqual([row["headers"]["authorization"] for row in upstream],
                                 ["Bearer synthetic-provider-key"] * 11)
                self.assertEqual([row["status"] for row in responses], [502])
                self.assertEqual(bytes.fromhex(responses[0]["body"]), b"upstream request failed")

    def test_redirect_path_query_spaces_encode_without_weakening_authority_guards(self):
        request = [{"model": "deepseek-chat", "messages": [],
                    "_path": "/v1/chat/completions"}]
        redirect = {"status": 302, "content_type": "text/plain", "body": b"discarded",
                    "response_headers": [("Location", "http://127.0.0.1:{upstream_port}/v1/redirect path?label=two words")]}
        reply = {"status": 200, "content_type": "application/json",
                 "body": b'{"id":"synthetic-redirect"}'}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, request, [redirect, reply], latest_version="0.166.0",
                )
                self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                    ("POST", "/v1/chat/completions"),
                    ("GET", "/v1/redirect%20path?label=two%20words"),
                ])
                self.assertEqual([row["headers"]["authorization"] for row in upstream],
                                 ["Bearer " + SYNTHETIC_API_KEY] * 2)
                self.assertEqual([response["status"] for response in responses], [200])

        rejected_locations = (
            ("authority-space", "http://127.0.0.1 :{upstream_port}/v1/unsafe", (ORACLE, MODEX), 302),
            ("scheme-space", "http ://127.0.0.1:{upstream_port}/v1/unsafe", (MODEX,), 302),
            ("userinfo-space", "http://synthetic user@127.0.0.1:{upstream_port}/v1/unsafe", (MODEX,), 302),
            ("control-tab", "/v1/redirect\tpath", (MODEX,), 302),
            ("control-cr", "/v1/redirect\rpath", (MODEX,), 502),
            ("control-lf", "/v1/redirect\npath", (MODEX,), 502),
        )
        for label, location, binaries, expected_status in rejected_locations:
            reply = {"status": 302, "content_type": "text/plain", "body": b"discarded",
                     "response_headers": [("Location", location)]}
            for binary in binaries:
                with self.subTest(binary=str(binary), rejected_location=label):
                    upstream, responses = observe_turns(
                        binary, request, [reply], latest_version="0.166.0",
                    )
                    self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                        ("POST", "/v1/chat/completions"),
                    ])
                    self.assertEqual([response["status"] for response in responses], [expected_status])

    def test_redirect_query_apostrophe_encoding_preserves_path_and_escapes(self):
        request = [{"model": "deepseek-chat", "input": "synthetic query encoding"}]
        redirect = {"status": 302, "content_type": "text/plain", "body": b"discarded",
                    "response_headers": [
                        ("Location", "http://127.0.0.1:{upstream_port}/v1/part'one%20two?label=three'four%20five"),
                    ]}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, request, [redirect, buffered_reply(97)], latest_version="0.166.0",
                )
                self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                    ("POST", "/v1/chat/completions"),
                    ("GET", "/v1/part'one%20two?label=three%27four%20five"),
                ])
                self.assertEqual([row["headers"]["authorization"] for row in upstream],
                                 ["Bearer " + SYNTHETIC_API_KEY] * 2)
                self.assertEqual([response["status"] for response in responses], [200])

    def test_root_provider_aliases_match_active_route_plan(self):
        turns = [
            {"model": "deepseek-chat", "input": "synthetic root responses POST",
             "_path": "/responses"},
            {"model": "deepseek-chat", "input": "synthetic root responses GET",
             "_method": "GET", "_path": "/responses?trace=synthetic"},
            {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic root chat POST"}],
             "_path": "/chat/completions?trace=synthetic"},
            {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic root chat GET"}],
             "_method": "GET", "_path": "/chat/completions"},
            {"model": "deepseek-chat", "input": "synthetic trailing slash",
             "_path": "/responses/"},
            {"model": "deepseek-chat", "input": "synthetic tenant prefix",
             "_path": "/tenant/responses"},
            {"model": "deepseek-chat", "input": "synthetic malformed path",
             "_path": "/v1//responses"},
        ]
        replies = [buffered_reply(index, created=42 + index) for index in range(4)]
        observed = {}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, replies, latest_version="0.166.0",
                )
                self.assertEqual(len(upstream), 4)
                self.assertEqual([row["status"] for row in responses], [200, 200, 200, 200, 404, 404, 400])
                observed[binary] = (
                    [(row["method"], row["path"], row["body"]) for row in upstream],
                    [(row["status"], bytes.fromhex(row["body"])) for row in responses],
                )

        expected = [
            ("POST", "/v1/chat/completions"),
            ("GET", "/v1/chat/completions"),
            ("POST", "/v1/chat/completions?trace=synthetic"),
            ("GET", "/v1/chat/completions"),
        ]
        for binary in (ORACLE, MODEX):
            upstream, responses = observed[binary]
            self.assertEqual([(method, path) for method, path, _ in upstream], expected)
            self.assertEqual([status for status, _ in responses], [200, 200, 200, 200, 404, 404, 400])
        self.assertEqual(observed[ORACLE][0], observed[MODEX][0])
        self.assertEqual(observed[ORACLE][1][:4], observed[MODEX][1][:4])

    def test_models_catalog_aliases_methods_queries_and_errors_match_active_release(self):
        post_body = b'{ "synthetic": true }'
        post_error = b'{"error":{"message":"synthetic quota","type":"rate_limit_error"}}'
        head_error = b'{"error":{"message":"synthetic unavailable","type":"server_error"}}'
        turns = [
            {"_method": "GET", "_path": "/models?trace=root"},
            {"_method": "GET", "_path": "/v1/models?trace=v1"},
            {"_method": "GET", "_path": "/models/auto?trace=alias"},
            {"_method": "GET", "_path": "/v1/models/deepseek-v4-flash?trace=valid"},
            {"_method": "GET", "_path": "/v1/models/no-such-model?trace=missing"},
            {"_method": "POST", "_path": "/models?trace=post", "_raw_body": post_body.decode()},
            {"_method": "HEAD", "_path": "/v1/models?trace=head"},
            {"_method": "HEAD", "_path": "/models?trace=success"},
        ]
        replies = [
            {"status": 429, "content_type": "application/json", "body": post_error},
            {"status": 503, "content_type": "application/json", "body": head_error},
            {"status": 200, "content_type": "application/json", "body": b""},
        ]
        observed = {}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [dict(turn) for turn in turns], replies, latest_version="0.166.0",
                )
                self.assertEqual([row["status"] for row in responses], [200, 200, 200, 200, 404, 429, 503, 200])
                self.assertEqual([(row["method"], row["path"]) for row in upstream], [
                    ("POST", "/v1/models?trace=post"),
                    ("HEAD", "/v1/models?trace=head"),
                    ("HEAD", "/v1/models?trace=success"),
                ])
                self.assertEqual(upstream[0]["body"], post_body)
                self.assertEqual(upstream[1]["body"], b"")
                self.assertEqual(upstream[2]["body"], b"")
                for request in upstream:
                    self.assertEqual(request["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                self.assertEqual(bytes.fromhex(responses[5]["body"]), post_error)
                self.assertEqual(bytes.fromhex(responses[6]["body"]), b"")
                self.assertEqual(bytes.fromhex(responses[7]["body"]), b"")
                list_body = json.loads(bytes.fromhex(responses[0]["body"]))
                versioned_list_body = json.loads(bytes.fromhex(responses[1]["body"]))
                self.assertEqual(list_body, versioned_list_body)
                self.assertEqual([model["id"] for model in list_body["data"]], [
                    "deepseek-v4-pro", "deepseek-flash", "deepseek-v4-flash",
                ])
                alias = json.loads(bytes.fromhex(responses[2]["body"]))
                self.assertEqual(alias, list_body["data"][0])
                valid = json.loads(bytes.fromhex(responses[3]["body"]))
                self.assertEqual(valid, list_body["data"][2])
                missing = json.loads(bytes.fromhex(responses[4]["body"]))
                self.assertEqual(missing["error"]["code"], "model_not_found")
                observed[binary] = (
                    [request["path"] for request in upstream],
                    [json.loads(bytes.fromhex(row["body"])) if row["status"] < 400 and row["body"] else bytes.fromhex(row["body"])
                     for row in responses],
                )
        self.assertEqual(observed[ORACLE], observed[MODEX])

    def test_models_route_keeps_modex_local_client_authentication(self):
        turn = [{"_method": "GET", "_path": "/models",
                 "_headers": {"Authorization": "Bearer synthetic-invalid-token"}}]
        oracle_upstream, oracle_responses = observe_turns(
            ORACLE, turn, [], latest_version="0.166.0",
        )
        modex_upstream, modex_responses = observe_turns(
            MODEX, turn, [], latest_version="0.166.0",
        )
        self.assertEqual(oracle_upstream, [])
        self.assertEqual(modex_upstream, [])
        self.assertEqual(oracle_responses[0]["status"], 200)
        self.assertEqual(modex_responses[0]["status"], 401)
        self.assertEqual(bytes.fromhex(modex_responses[0]["body"]), b"")

    def test_connect_routes_use_upstream_authority_form(self):
        reply = {"status": 418, "content_type": "application/json",
                 "body": b'{"error":"synthetic CONNECT control"}'}
        turns = (
            {"_method": "CONNECT", "_path": "/models", "_raw_body": ""},
            {"_method": "CONNECT", "_path": "/v1/chat/completions", "_raw_body":
             '{"model":"deepseek-chat","messages":[]}'},
            {"_method": "CONNECT", "_path": "/v1/messages", "_raw_body":
             '{"model":"deepseek-chat","messages":[]}'},
            {"_method": "CONNECT", "_path": "/v1/responses", "_raw_body":
             '{"model":"deepseek-chat","input":"synthetic"}'},
        )
        for binary in (ORACLE, MODEX):
            for turn in turns:
                with self.subTest(binary=str(binary), route=turn["_path"]):
                    with patch.object(UpstreamHandler, "do_CONNECT", UpstreamHandler.do_POST, create=True):
                        upstream, responses = observe_turns(
                            binary, [turn], [reply], latest_version="0.166.0",
                        )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["method"], "CONNECT")
                    self.assertEqual(upstream[0]["path"], upstream[0]["headers"]["host"])
                    self.assertTrue(upstream[0]["path"].startswith("127.0.0.1:"))
                    self.assertEqual(responses[0]["status"], 418)
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), reply["body"])

        denied_upstream, denied_responses = observe_turns(
            MODEX,
            [{"_method": "CONNECT", "_path": "/models", "_raw_body": "",
              "_headers": {"Authorization": "Bearer synthetic-invalid-token"}}],
            [], latest_version="0.166.0",
        )
        self.assertEqual(denied_upstream, [])
        self.assertEqual(denied_responses[0]["status"], 401)

    def test_connect_success_and_upgrade_responses_do_not_establish_tunnels(self):
        success = {"status": 200, "content_type": "application/octet-stream",
                   "body": b"synthetic tunnel bytes"}
        turns = (
            {"_method": "CONNECT", "_path": "/models", "_raw_body": ""},
            {"_method": "CONNECT", "_path": "/v1/responses", "_raw_body":
             '{"model":"deepseek-chat","input":"synthetic"}'},
        )
        expected = {
            (ORACLE, "/models"): (200, b""),
            (MODEX, "/models"): (502, b"upstream request failed"),
            (ORACLE, "/v1/responses"): (502, b"provider response could not be processed"),
            (MODEX, "/v1/responses"): (502, b"upstream request failed"),
        }
        for binary in (ORACLE, MODEX):
            for turn in turns:
                with self.subTest(binary=str(binary), route=turn["_path"]):
                    with patch.object(UpstreamHandler, "do_CONNECT", UpstreamHandler.do_POST, create=True):
                        upstream, responses = observe_turns(
                            binary, [turn], [success], latest_version="0.166.0",
                        )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["method"], "CONNECT")
                    self.assertEqual(upstream[0]["path"], upstream[0]["headers"]["host"])
                    self.assertEqual(
                        (responses[0]["status"], bytes.fromhex(responses[0]["body"])),
                        expected[(binary, turn["_path"])]
                    )

        upgrade = {"status": 101, "content_type": "application/octet-stream",
                   "body": b"synthetic upgrade bytes"}
        turn = [{"_method": "CONNECT", "_path": "/models", "_raw_body": ""}]
        with patch.object(UpstreamHandler, "do_CONNECT", UpstreamHandler.do_POST, create=True):
            upgrade_upstream, upgrade_responses = observe_turns(
                MODEX, turn, [upgrade], latest_version="0.166.0",
            )
        self.assertEqual(len(upgrade_upstream), 1)
        self.assertEqual(upgrade_responses[0]["status"], 502)
        self.assertEqual(bytes.fromhex(upgrade_responses[0]["body"]), b"upstream request failed")

    def test_raw_connect_tunnel_bytes_are_discarded_and_upstream_fd_closes(self):
        upstream_closed = threading.Event()
        upstream_timed_out = threading.Event()

        def raw_connect_response(handler):
            length = int(handler.headers.get("Content-Length", "0"))
            handler.server.records.append({
                "method": handler.command,
                "path": handler.path,
                "headers": {name.lower(): value for name, value in handler.headers.items()},
                "body": handler.rfile.read(length),
            })
            handler.connection.sendall(
                b"HTTP/1.1 200 Connection Established\r\n\r\n"
                b"synthetic tunnel bytes"
            )
            handler.connection.settimeout(1)
            try:
                if handler.connection.recv(1) == b"":
                    upstream_closed.set()
            except TimeoutError:
                upstream_timed_out.set()
            except OSError:
                upstream_closed.set()
            handler.close_connection = True

        with patch.object(UpstreamHandler, "do_CONNECT", raw_connect_response, create=True):
            upstream, wire, eof, timed_out = observe_response_wire(
                MODEX,
                {"status": 200, "content_type": "application/octet-stream",
                 "body": b"synthetic tunnel bytes"},
                client_script=CONNECT_WIRE_CLIENT,
            )

        self.assertTrue(upstream_closed.wait(1), "a rejected CONNECT response must close upstream")
        self.assertFalse(upstream_timed_out.is_set(), "the relay left the tunnel socket open")
        self.assertEqual(upstream[0]["method"], "CONNECT")
        self.assertEqual(upstream[0]["path"], upstream[0]["headers"]["host"])
        self.assertTrue(eof, "the downstream response must close after the CONNECT rejection")
        self.assertFalse(timed_out, "the downstream response stayed open after the CONNECT rejection")
        status, headers, body = parse_raw_response(wire)
        self.assertEqual(status, 502)
        self.assertEqual(headers["content-length"], str(len(b"upstream request failed")))
        self.assertEqual(body, b"upstream request failed")
        self.assertNotIn(b"synthetic tunnel bytes", wire)

    def test_root_responses_alias_keeps_client_auth_and_continuation_ownership(self):
        invalid = [{"model": "deepseek-chat", "input": "synthetic invalid client token",
                    "_path": "/responses",
                    "_headers": {"Authorization": "Bearer synthetic-invalid-token"}}]
        oracle_upstream, oracle_responses = observe_turns(
            ORACLE, invalid, [buffered_reply()], latest_version="0.166.0",
        )
        modex_upstream, modex_responses = observe_turns(
            MODEX, invalid, [buffered_reply()], latest_version="0.166.0",
        )
        self.assertEqual([row["status"] for row in oracle_responses], [200])
        self.assertEqual(len(oracle_upstream), 1)
        self.assertEqual([row["status"] for row in modex_responses], [401])
        self.assertEqual(modex_upstream, [])

        turns = [
            {"model": "deepseek-chat", "input": "synthetic first bound turn",
             "session_id": "synthetic-bound-session", "_path": "/v1/responses"},
            {"model": "deepseek-chat", "input": "synthetic root alias follow-up",
             "session_id": "synthetic-bound-session", "use_previous": True,
             "_path": "/responses"},
        ]
        replies = [buffered_reply(0, created=42), buffered_reply(1, created=43)]
        for binary in (ORACLE, MODEX):
            with self.subTest(binding_binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, replies, latest_version="0.166.0")
                self.assertEqual([row["status"] for row in responses], [200, 503])
                self.assertEqual(len(upstream), 1, "bound follow-up must remain blocked before provider dispatch")

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
                    upstream, wire, eof, timed_out = observe_response_wire(
                        binary, reply, request_close=request_close,
                    )
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

        upstream, wire, eof, _ = observe_response_wire(
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

    def test_malformed_sse_oracle_gap_and_modex_failure_with_valid_controls(self):
        """Record the pinned open-stream mismatch; require Modex to fail terminally."""
        cases = (
            ("non-object chunk", b"data: []\n\ndata: [DONE]\n\n"),
            ("missing choices", b"data: {}\n\ndata: [DONE]\n\n"),
            ("invalid JSON", b"data: {broken}\n\ndata: [DONE]\n\n"),
        )
        observed = {}
        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            observed[label] = {}
            for name, body in cases:
                reply = {"status": 200, "content_type": "text/event-stream", "body": body}
                upstream, wire, eof, timed_out = observe_response_wire(binary, reply)
                with self.subTest(binary=label, case=name):
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    self.assertIn(b'"stream":true', upstream[0]["body"])
                    status, headers, framed_body = parse_raw_response(wire)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers.get("transfer-encoding"), "chunked")
                    self.assertEqual(headers.get("connection"), "close")
                    observed[label][name] = (framed_body, eof, timed_out)

        # The timeout reproduces a baseline mismatch; it does not count as a
        # successful or complete stream response.
        oracle_body, oracle_eof, oracle_timed_out = observed["oracle"]["non-object chunk"]
        self.assertTrue(oracle_timed_out, "the bounded raw read must report the oracle timeout")
        self.assertFalse(oracle_eof, "the pinned oracle leaves its response socket open")
        self.assertEqual(oracle_body, b"", "known mismatch: the oracle emits no event or terminal chunk")

        modex_body, _, _ = observed["modex"]["non-object chunk"]
        modex_payload = decode_chunked_body(modex_body)
        modex_events = parse_sse_events(modex_payload)
        self.assertEqual([event for event, _ in modex_events], ["response.failed"])
        self.assertEqual(modex_events[0][1]["response"]["error"]["code"], "provider_stream_error")
        self.assertEqual(modex_events[0][1]["response"]["error"]["message"],
                         "chat stream chunk is not an object")
        self.assertTrue(modex_body.endswith(b"0\r\n\r\n"), "Modex must terminate the failed stream")
        for label in ("oracle", "modex"):
            completed_payload = decode_chunked_body(observed[label]["missing choices"][0])
            completed_events = parse_sse_events(completed_payload)
            with self.subTest(binary=label, case="missing choices"):
                self.assertEqual([event for event, _ in completed_events],
                                 ["response.created", "response.completed"])
                self.assertEqual(completed_events[-1][1]["response"]["output"], [])

            invalid_payload = decode_chunked_body(observed[label]["invalid JSON"][0])
            invalid_events = parse_sse_events(invalid_payload)
            with self.subTest(binary=label, case="invalid JSON"):
                self.assertEqual([event for event, _ in invalid_events], ["response.failed"])
                self.assertEqual(invalid_events[0][1]["response"]["error"]["code"],
                                 "provider_stream_error")
                self.assertEqual(invalid_events[0][1]["response"]["error"]["message"],
                                 "incomplete JSON segment")


if __name__ == "__main__":
    unittest.main()
