"""Compare raw DeepSeek local-proxy HTTP behavior with Prodex 0.165.1."""

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.client import HTTPResponse


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
SYNTHETIC_API_KEY = "synthetic-provider-key"
WEBSOCKET_FALLBACK = b"provider adapter requires HTTPS Responses transport fallback"
INVALID_REQUEST_TARGET_BODY = b'{"error":{"code":"invalid_request_target","message":"request target is invalid"}}'
UNSUPPORTED_ROUTE_BODY = b'{"error":{"code":"unsupported_provider_route","message":"provider route is not supported"}}'
PROVIDER_RESPONSE = json.dumps({
    "id": "chatcmpl_transport_oracle",
    "model": "deepseek-chat",
    "created": 1,
    "choices": [{"message": {"content": "synthetic response"}, "finish_reason": "stop"}],
}, separators=(",", ":")).encode()
PROVIDER_SSE_RESPONSE = base64.b64decode(next(
    case["upstream_base64"]
    for case in json.loads((ROOT / "tests/fixtures/provider-stream/cases.json").read_text(encoding="utf-8"))["cases"]
    if case["name"] == "text_done"
))
REQUEST_BODY = b'{"model":"deepseek-chat","input":"synthetic raw transport probe"}'
STREAM_REQUEST_BODY = b'{"model":"deepseek-chat","input":"synthetic raw transport probe","stream":true}'
RESPONSES_RESPONSE = b'{"created_at":1,"id":"chatcmpl_transport_oracle","metadata":{"deepseek":{"finish_reason":"stop"}},"model":"deepseek-chat","object":"response","output":[{"content":[{"text":"synthetic response","type":"output_text"}],"role":"assistant","type":"message"}]}'
TARGET_PREFIX = b"/v1/responses?x="
MAX_LENGTH_VALID_TARGET = TARGET_PREFIX + b"a" * (8192 - len(TARGET_PREFIX))
OVER_LENGTH_INVALID_TARGET = MAX_LENGTH_VALID_TARGET + b"a"


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.records = []
        self.records_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), UpstreamHandler)

    def reset_records(self):
        with self.records_lock:
            self.records.clear()

    def snapshot_records(self):
        with self.records_lock:
            return list(self.records)


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _serve_request(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        with self.server.records_lock:
            self.server.records.append({
                "method": self.command,
                "path": self.path,
                "headers": {name.lower(): value for name, value in self.headers.items()},
                "body": body,
            })
        response_kind = self.headers.get("X-Oracle-Response", "json")
        if response_kind in ("sse-204", "sse-304"):
            self.send_response(int(response_kind[-3:]))
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        response_body = PROVIDER_SSE_RESPONSE if response_kind == "sse" else PROVIDER_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream" if response_kind == "sse" else "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response_body)

    def do_GET(self):
        self._serve_request() if self.headers.get("X-Oracle-Response") else self.send_error(501)

    def do_HEAD(self):
        self._serve_request() if self.headers.get("X-Oracle-Response") else self.send_error(501)

    def do_POST(self):
        self._serve_request()

    def send_error(self, code, message=None, explain=None):
        if code == 501:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            with self.server.records_lock:
                self.server.records.append({
                    "method": self.command,
                    "path": self.path,
                    "headers": {name.lower(): value for name, value in self.headers.items()},
                    "body": body,
                })
        super().send_error(code, message, explain)

    def log_message(self, *_args):
        pass


def make_codex(path: Path):
    source = r'''import base64, http.client, json, os, re, socket, sys
from urllib.parse import urlsplit

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.153.2")
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        result = {} if request.get("method") == "initialize" else {"data": []}
        print(json.dumps({"id": request["id"], "result": result}), flush=True)
    raise SystemExit(0)

base = None
for arg in args:
    match = re.search(r"model_providers\.prodex-deepseek\.base_url=(.*)", arg)
    if match:
        base = match.group(1).strip('"')
if not base:
    raise SystemExit("synthetic Codex did not receive the local provider URL")
target = urlsplit(base)
connection = socket.create_connection((target.hostname, target.port), timeout=5)
connection.settimeout(5)
connection.sendall(bytes.fromhex(os.environ["PROBE_REQUEST_HEX"]))
if os.environ.get("PROBE_HALF_CLOSE") == "1":
    connection.shutdown(socket.SHUT_WR)
result = {"status": None, "reason": "", "headers": [], "body_base64": "", "wire_body_base64": "", "wire_body_probe_complete": False, "read_error": ""}
try:
    request_method = os.environ.get("PROBE_REQUEST_METHOD")
    response = http.client.HTTPResponse(connection, method=request_method)
    response.begin()
    wire_body = b""
    wire_body_probe_complete = False
    if request_method == "HEAD" and response.fp:
        connection.settimeout(0.25)
        try:
            wire_body = response.fp.peek(4096)
            wire_body_probe_complete = True
        except socket.timeout:
            pass
        finally:
            connection.settimeout(5)
    body = response.read()
    result.update({
        "status": response.status,
        "reason": response.reason,
        "headers": response.getheaders(),
        "body_base64": base64.b64encode(body).decode("ascii"),
        "wire_body_base64": base64.b64encode(wire_body).decode("ascii"),
        "wire_body_probe_complete": wire_body_probe_complete,
    })
except Exception as error:
    result["read_error"] = type(error).__name__
finally:
    connection.close()
followup_hex = os.environ.get("PROBE_FOLLOWUP_REQUEST_HEX", "")
if followup_hex:
    followup_connection = socket.create_connection((target.hostname, target.port), timeout=5)
    followup_connection.settimeout(5)
    followup_connection.sendall(bytes.fromhex(followup_hex))
    followup_response = http.client.HTTPResponse(followup_connection)
    followup_response.begin()
    followup_body = followup_response.read()
    result.update({
        "followup_status": followup_response.status,
        "followup_body_base64": base64.b64encode(followup_body).decode("ascii"),
    })
    followup_connection.close()
with open(os.environ["PROBE_RESULT_PATH"], "w", encoding="utf-8") as output:
    json.dump(result, output, separators=(",", ":"))
'''
    path.write_text("#!" + sys.executable + "\n" + source, encoding="utf-8")
    path.chmod(0o700)


def request_bytes(headers=(), body=REQUEST_BODY, target=b"/v1/responses", method=b"POST"):
    all_headers = [
        ("Host", "127.0.0.1"),
        *headers,
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ]
    return (
        method + b" " + target + b" HTTP/1.1\r\n"
        + b"".join(name.encode() + b": " + value.encode() + b"\r\n" for name, value in all_headers)
        + b"\r\n" + body
    )


def invalid_target_case(name, target):
    return {
        "name": name,
        "request": request_bytes(target=target),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    }


def method_case(name, method, target):
    return {
        "name": name,
        "request": request_bytes(
            headers=(("Connection", "close"),) if method == b"HEAD" else (),
            target=target,
            method=method,
        ),
        "expected_status": 501,
        "expected_reason": "Not Implemented",
        "expected_body": b"" if method == b"HEAD" else None,
        "expected_upstream_method": method.decode("ascii"),
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def success_method_case(name, method, target, response_kind="json", body=REQUEST_BODY):
    request_headers = [("X-Oracle-Response", response_kind)]
    if method == b"HEAD":
        request_headers.insert(0, ("Connection", "close"))
    if method == b"HEAD":
        expected_body = b""
        expected_headers = (
            {"content-type": "text/plain; charset=utf-8", "content-length": "40"}
            if target == b"/v1/responses"
            else {"content-type": "application/json", "content-length": "0"}
        )
    elif response_kind == "sse":
        expected_body = PROVIDER_SSE_RESPONSE if target == b"/v1/chat/completions" else None
        expected_headers = {
            "content-type": "text/event-stream" if target == b"/v1/chat/completions" else "text/event-stream; charset=utf-8",
            "transfer-encoding": "chunked",
        }
    else:
        expected_body = PROVIDER_RESPONSE if target == b"/v1/chat/completions" else RESPONSES_RESPONSE
        expected_headers = {
            "content-type": "application/json" if target == b"/v1/chat/completions" else "application/json; charset=utf-8",
            "content-length": str(len(expected_body)),
        }
    return {
        "name": name,
        "request": request_bytes(
            request_headers,
            body=body,
            target=target,
            method=method,
        ),
        "expected_status": 502 if method == b"HEAD" and target == b"/v1/responses" else 200,
        "expected_reason": "Bad Gateway" if method == b"HEAD" and target == b"/v1/responses" else "OK",
        "expected_body": expected_body,
        "expected_headers": expected_headers,
        "compare_response_body": method != b"HEAD",
        "expected_upstream_method": method.decode("ascii"),
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def head_bodyless_sse_case(status):
    return {
        "name": f"head_chat_completions_{status}_sse_framing",
        "request": request_bytes(
            (("Connection", "close"), ("X-Oracle-Response", f"sse-{status}")),
            target=b"/v1/chat/completions",
            method=b"HEAD",
        ),
        "expected_status": status,
        "expected_reason": "No Content" if status == 204 else "Not Modified",
        "expected_body": b"",
        "expected_headers": {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked",
        },
        "expected_wire_body": {"oracle": b"0\r\n\r\n", "modex": b""},
        "expected_upstream_method": "HEAD",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


CASES = (
    {
        "name": "malformed_request_line_missing_version",
        "request": b"POST /v1/responses\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "malformed_request_line_extra_token",
        "request": b"POST /v1/responses HTTP/1.1 extra\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 502,
        "expected_body": b"upstream request failed",
        "upstream": False,
    },
    {
        "name": "malformed_request_target_spacing",
        "request": b"POST /v1/responses bad HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "malformed_header",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nMalformed\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "websocket_without_connection_header",
        "request": request_bytes((("Upgrade", "websocket"),)),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    {
        "name": "websocket_duplicate_upgrade",
        "request": request_bytes((("Upgrade", "websocket"), ("Upgrade", "websocket"))),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    {
        "name": "websocket_duplicate_connection",
        "request": request_bytes((
            ("Connection", "keep-alive"), ("Connection", "Upgrade"),
            ("Upgrade", "websocket"),
        )),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    {
        "name": "truncated_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "websocket_truncated_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "oversized_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: 67108865\r\n\r\n",
        "expected_status": 413,
        "expected_reason": "Payload Too Large",
        "expected_body": b"proxied request body is too large",
        "upstream": False,
    },
    {
        "name": "valid_request_control",
        "request": request_bytes((("Connection", "close"),)),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
    {
        "name": "invalid_target_websocket_precedes_upgrade_fallback",
        "request": request_bytes((("Upgrade", "websocket"),), target=b"http://example.test/v1/responses"),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_declared_body_precedes_body_limit",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: 67108865\r\n\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_expected_body_precedes_continue",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-continue\r\nContent-Length: 67108865\r\n\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_expected_body_precedes_continue",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-continue\r\nContent-Length: 10\r\n\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_chunked_body_precedes_body_limit",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nTransfer-Encoding: chunked\r\n\r\n4000001\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_truncated_body_closes_without_response",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "invalid_target_reply_keeps_relay_accepting_requests",
        "request": request_bytes(target=b"http://example.test/v1/responses"),
        "followup_request": request_bytes((("Connection", "close"),)),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "expected_followup_status": 200,
        "upstream": True,
    },
    {
        "name": "valid_escaped_path_is_not_normalized",
        "request": request_bytes(target=b"/v1/resp%6Fnses"),
        "expected_status": 404,
        "expected_reason": "Not Found",
        "expected_body": UNSUPPORTED_ROUTE_BODY,
        "upstream": False,
    },
    {
        "name": "valid_target_length_8192",
        "request": request_bytes(target=MAX_LENGTH_VALID_TARGET),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
    *(
        invalid_target_case(name, target)
        for name, target in (
            ("absolute_form_request_target", b"http://example.test/v1/responses"),
            ("asterisk_request_target", b"*"),
            ("leading_double_slash_request_target", b"//v1/responses"),
            ("interior_double_slash_request_target", b"/v1//responses"),
            ("dot_segment_request_target", b"/v1/../responses"),
            ("encoded_dot_segment_request_target", b"/v1/%2e%2e/responses"),
            ("encoded_slash_request_target", b"/v1/%2f/responses"),
            ("fragment_request_target", b"/v1/responses#x"),
            ("malformed_query_percent_escape", b"/v1/responses?x=%GG"),
            ("request_target_length_8193", OVER_LENGTH_INVALID_TARGET),
        )
    ),
    *(
        method_case(f"method_{method.decode('ascii').lower()}_{target.rsplit(b'/', 1)[-1].decode('ascii')}", method, target)
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for method in (b"GET", b"HEAD", b"PUT", b"DELETE", b"OPTIONS", b"X-EXT")
    ),
    *(
        method_case(f"extension_method_length_{size}_{target.rsplit(b'/', 1)[-1].decode('ascii')}", b"A" * size, target)
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for size in (8192, 8193)
    ),
    *(
        success_method_case(
            f"successful_{method.decode('ascii').lower()}_{target.rsplit(b'/', 1)[-1].decode('ascii')}",
            method,
            target,
        )
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for method in (b"GET", b"HEAD")
    ),
    success_method_case(
        "successful_get_chat_completions_sse",
        b"GET",
        b"/v1/chat/completions",
        response_kind="sse",
    ),
    success_method_case(
        "successful_get_responses_sse",
        b"GET",
        b"/v1/responses",
        response_kind="sse",
        body=STREAM_REQUEST_BODY,
    ),
    *(head_bodyless_sse_case(status) for status in (204, 304)),
    {
        "name": "valid_escaped_query",
        "request": request_bytes(target=b"/v1/responses?x=a%2Fb"),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
)


def run_probe(binary: Path, case, upstream: Upstream):
    with tempfile.TemporaryDirectory(prefix="modex-raw-transport-01651-") as temporary:
        root = Path(temporary)
        for name in (
            "home", "prodex", "shared-codex", "xdg-config", "xdg-data", "xdg-cache", "work",
        ):
            (root / name).mkdir(mode=0o700)
        codex = root / "codex"
        make_codex(codex)
        result_path = root / "raw-response.json"
        environment = {
            "HOME": str(root / "home"),
            "PRODEX_HOME": str(root / "prodex"),
            "PRODEX_SHARED_CODEX_HOME": str(root / "shared-codex"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "TMPDIR": str(root),
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PRODEX_CODEX_BIN": str(codex),
            "PROBE_REQUEST_HEX": case["request"].hex(),
            "PROBE_REQUEST_METHOD": case["request"].split(b" ", 1)[0].decode("ascii"),
            "PROBE_HALF_CLOSE": "1" if case.get("half_close") else "0",
            "PROBE_FOLLOWUP_REQUEST_HEX": case.get("followup_request", b"").hex(),
            "PROBE_RESULT_PATH": str(result_path),
        }
        command = [
            str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
            "--base-url", f"http://127.0.0.1:{upstream.server_port}/v1",
            "--model", "deepseek-chat", "--no-presidio", "--no-sub-agent",
            "--skip-quota-check", "exec", "--", "synthetic raw transport probe",
        ]
        upstream.reset_records()
        process = subprocess.run(
            command,
            cwd=root / "work",
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=40,
            check=False,
        )
        if not result_path.is_file():
            raise AssertionError(
                f"{binary.name} did not reach the synthetic Codex raw client for {case['name']}: "
                f"exit={process.returncode}, stdout={process.stdout!r}, stderr={process.stderr!r}"
            )
        response = json.loads(result_path.read_text(encoding="utf-8"))
        response["body"] = base64.b64decode(response.pop("body_base64"))
        response["wire_body"] = base64.b64decode(response.pop("wire_body_base64"))
        if "followup_body_base64" in response:
            response["followup_body"] = base64.b64decode(response.pop("followup_body_base64"))
        response["process_exit"] = process.returncode
        response["stdout"] = process.stdout
        response["stderr"] = process.stderr
        return response, upstream.snapshot_records()


def normalize_response_body(case, body):
    if case["name"] == "successful_get_responses_sse":
        return re.sub(rb"msg_deepseek_[0-9]+", b"msg_deepseek_ID", body)
    return body


class LocalRewrite01651OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.165.1")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_raw_http_production_path_matches_pinned_oracle_controls(self):
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case in CASES:
                with self.subTest(case=case["name"]):
                    oracle_response, oracle_upstream = run_probe(ORACLE, case, upstream)
                    modex_response, modex_upstream = run_probe(MODEX, case, upstream)

                    self.assertEqual(oracle_response["process_exit"], 0, oracle_response["stderr"])
                    self.assertEqual(modex_response["process_exit"], 0, modex_response["stderr"])
                    oracle_request = None
                    for label, response, records in (
                        ("oracle", oracle_response, oracle_upstream),
                        ("modex", modex_response, modex_upstream),
                    ):
                        self.assertEqual(response["status"], case["expected_status"], label)
                        if "expected_reason" in case:
                            self.assertEqual(response["reason"], case["expected_reason"], label)
                        self.assertEqual(response["read_error"], case.get("expected_read_error", ""), label)
                        if "expected_followup_status" in case:
                            self.assertEqual(response["followup_status"], case["expected_followup_status"], label)
                            self.assertTrue(response["followup_body"], label)
                        if case["expected_body"] is not None:
                            self.assertEqual(response["body"], case["expected_body"], label)
                        else:
                            self.assertTrue(response["body"], label)
                        if case.get("expected_headers"):
                            response_headers = {name.lower(): value for name, value in response["headers"]}
                            for name, value in case["expected_headers"].items():
                                self.assertEqual(response_headers.get(name), value, label)
                        if case["request"].startswith(b"HEAD "):
                            self.assertTrue(response["wire_body_probe_complete"], label)
                            self.assertEqual(
                                response["wire_body"],
                                case.get("expected_wire_body", {}).get(label, b""),
                                label,
                            )
                        self.assertEqual(len(records), int(case["upstream"]), label)
                        if case["upstream"]:
                            record = records[0]
                            self.assertEqual(
                                (record["method"], record["path"]),
                                (case.get("expected_upstream_method", "POST"), case.get("expected_upstream_path", "/v1/chat/completions")),
                                label,
                            )
                            if case.get("compare_upstream_request"):
                                if label == "oracle":
                                    oracle_request = record
                                else:
                                    self.assertIsNotNone(oracle_request)
                                    self.assertEqual(record["body"], oracle_request["body"], label)
                            self.assertNotIn("upgrade", record["headers"], label)
                            self.assertNotIn("keep-alive", [value.lower() for value in record["headers"].values()], label)
                            self.assertNotEqual(record["headers"].get("connection", "").lower(), "upgrade", label)
                    if case.get("compare_response_body"):
                        self.assertEqual(
                            normalize_response_body(case, oracle_response["body"]),
                            normalize_response_body(case, modex_response["body"]),
                        )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
