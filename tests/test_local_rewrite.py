"""Exercise the internal local-rewrite relay through its native test driver."""

import base64
import hashlib
from http.client import HTTPConnection, HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get(
    "MODEX_LOCAL_REWRITE_DRIVER", ROOT / "build/tests/local_rewrite_driver",
))
REQUEST_FIXTURE = ROOT / "tests/fixtures/provider-requests/cases.json"
STREAM_FIXTURE = ROOT / "tests/fixtures/provider-stream/cases.json"
BUFFERED_FIXTURE = ROOT / "tests/fixtures/provider-buffered/cases.json"
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
BASELINE_COMMIT = "433aad44bb249d5c25a231a6b06c2fa522a39a1f"
SYNTHETIC_API_KEY = "synthetic-provider-key"

sys.path.insert(0, str(ROOT / "tests"))
from session_oracle import sandbox_command


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.records = []
        self.response_lock = threading.Lock()
        self.client_closed = threading.Event()
        self.hold_timed_out = threading.Event()
        super().__init__(("127.0.0.1", 0), UpstreamHandler)


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.records.append({
            "method": self.command,
            "path": self.path,
            "headers": {name.lower(): value for name, value in self.headers.items()},
            "body": self.rfile.read(length),
        })
        with self.server.response_lock:
            response = self.server.responses.pop(0) if self.server.responses else {
                "status": 500, "content_type": "text/plain", "body": b"no fixture response",
            }
        self.send_response(response["status"])
        if response.get("response_headers") is None:
            self.send_header("Content-Type", response["content_type"])
        else:
            for name, value in response["response_headers"]:
                self.send_header(name, value)
        if response.get("chunked"):
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "keep-alive")
        else:
            self.send_header("Content-Length", str(response.get("declared_length", len(response["body"]))))
            self.send_header("Connection", "close")
        self.end_headers()
        body = response["body"]
        size = response.get("chunk_size", 4096)
        try:
            for offset in range(0, len(body), size):
                chunk = body[offset:offset + size]
                if response.get("chunked"):
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
                if response.get("delay"):
                    time.sleep(response["delay"])
            if response.get("chunked") and not response.get("hold_open"):
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except OSError:
            self.server.client_closed.set()
            self.close_connection = True
            return
        if response.get("hold_open"):
            self.connection.settimeout(3)
            try:
                if self.connection.recv(1) == b"":
                    self.server.client_closed.set()
            except TimeoutError:
                self.server.hold_timed_out.set()
            except OSError:
                self.server.client_closed.set()
        self.close_connection = True

    def log_message(self, *_args):
        pass


@contextmanager
def serving(responses):
    server = Upstream(responses)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class RunningLocalRewrite:
    def __init__(
        self, upstream_port, *, sandbox=False, environment_overrides=None,
        config_toml=None,
    ):
        self.upstream_url = f"http://127.0.0.1:{upstream_port}/v1"
        self.sandbox = sandbox
        self.environment_overrides = environment_overrides or {}
        self.config_toml = config_toml
        self.temporary = tempfile.TemporaryDirectory(prefix="modex-local-rewrite-")
        self.root = Path(self.temporary.name)
        self.process = None
        self.address = None
        self.startup_line = ""
        self.startup_tail = ""
        self.shutdown_returncode = None
        self._closed = False

    def __enter__(self):
        for name in (
            "home", "prodex", "shared-codex", "xdg-config", "xdg-cache", "workspace",
        ):
            (self.root / name).mkdir(mode=0o700)
        if self.config_toml is not None:
            (self.root / "shared-codex" / "config.toml").write_text(
                self.config_toml, encoding="utf-8",
            )
        environment = {
            "HOME": str(self.root / "home"),
            "PRODEX_HOME": str(self.root / "prodex"),
            "PRODEX_SHARED_CODEX_HOME": str(self.root / "shared-codex"),
            "XDG_CONFIG_HOME": str(self.root / "xdg-config"),
            "XDG_CACHE_HOME": str(self.root / "xdg-cache"),
            "TMPDIR": str(self.root),
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        environment.update(self.environment_overrides)
        arguments = [
            "127.0.0.1:0", self.upstream_url, SYNTHETIC_API_KEY,
        ]
        command = [str(DRIVER), *arguments]
        if self.sandbox:
            sandbox_environment = {
                name: environment[name]
                for name in (
                    "HOME", "PRODEX_HOME", "PRODEX_SHARED_CODEX_HOME",
                    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR", "LANG", "LC_ALL",
                )
            }
            command = sandbox_command(
                DRIVER, self.root, arguments, environment=sandbox_environment,
            )
            command.insert(command.index("--"), "--share-net")
        self.process = subprocess.Popen(
            command, cwd=self.root / "workspace", env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        )
        try:
            self.startup_line = self._read_startup_line(5).decode("utf-8").rstrip("\r\n")
            match = re.fullmatch(r"READY http://127\.0\.0\.1:(\d+)/v1", self.startup_line)
            if not match:
                raise RuntimeError(f"local relay failed during startup: {self.startup_line}")
            self.address = ("127.0.0.1", int(match.group(1)))
            return self
        except BaseException:
            self.close()
            raise

    def _read_startup_line(self, timeout):
        output = bytearray()
        deadline = time.monotonic() + timeout
        while b"\n" not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"relay did not start; captured output: {bytes(output)!r}")
            readable, _, _ = select.select([self.process.stdout], [], [], remaining)
            if not readable:
                raise TimeoutError(f"relay did not start; captured output: {bytes(output)!r}")
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError(f"relay exited {self.process.poll()}; captured output: {bytes(output)!r}")
            output.extend(chunk)
        return bytes(output).split(b"\n", 1)[0] + b"\n"

    def close(self):
        if self._closed:
            return self.shutdown_returncode
        self._closed = True
        if self.process is not None:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGTERM)
            try:
                self.shutdown_returncode = self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.shutdown_returncode = self.process.wait(timeout=3)
            output, _ = self.process.communicate(timeout=1)
            self.startup_tail = output.decode("utf-8", errors="replace")
        self.temporary.cleanup()
        return self.shutdown_returncode

    def __exit__(self, *_args):
        self.close()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def post_relay(address, body, *, path="/v1/responses", headers=None, timeout=5):
    connection = HTTPConnection(address[0], address[1], timeout=timeout)
    connection.request(
        "POST", path, body=body,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    response = connection.getresponse()
    status = response.status
    response_headers = {name.lower(): value for name, value in response.getheaders()}
    response_body = response.read()
    connection.close()
    return status, response_headers, response_body


def post_declared_oversized_body(address, body_bytes):
    request = (
        b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\nConnection: close\r\n"
        b"Content-Length: " + str(body_bytes).encode() + b"\r\n\r\n"
    )
    response = bytearray()
    with socket.create_connection(address, timeout=5) as connection:
        connection.sendall(request)
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    head, body = bytes(response).split(b"\r\n\r\n", 1)
    return int(head.split(b" ", 2)[1]), body


def raw_http_exchange(address, request, *, half_close=False):
    response = bytearray()
    with socket.create_connection(address, timeout=5) as connection:
        connection.sendall(request)
        if half_close:
            connection.shutdown(socket.SHUT_WR)
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    return bytes(response)


def post_then_half_close(address, body):
    connection = socket.create_connection(address, timeout=5)
    connection.sendall(
        b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\nConnection: close\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    )
    connection.shutdown(socket.SHUT_WR)
    response = HTTPResponse(connection)
    response.begin()
    status = response.status
    headers = {name.lower(): value for name, value in response.getheaders()}
    response_body = response.read()
    response.close()
    connection.close()
    return status, headers, response_body


class LocalRewriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.is_file():
            raise AssertionError(f"build the native local-rewrite test driver first: {DRIVER}")
        cls.requests = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
        cls.streams = json.loads(STREAM_FIXTURE.read_text(encoding="utf-8"))
        cls.buffered = json.loads(BUFFERED_FIXTURE.read_text(encoding="utf-8"))
        for fixture in (cls.requests, cls.streams, cls.buffered):
            if fixture["oracle_sha256"] != ORACLE_SHA256:
                raise AssertionError("fixture does not identify the pinned Prodex oracle")
            if fixture["baseline_commit"] != BASELINE_COMMIT:
                raise AssertionError("fixture does not identify the frozen baseline commit")
        cls.request_cases = {case["name"]: case for case in cls.requests["cases"]}
        cls.stream_cases = {case["name"]: case for case in cls.streams["cases"]}
        cls.buffered_cases = {case["name"]: case for case in cls.buffered["cases"]}

    @staticmethod
    def strict_tool_request():
        return {
            "model": "deepseek-chat",
            "input": "synthetic strict tool request",
            "stream": False,
            "tools": [{
                "type": "function",
                "name": "lookup",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }],
        }

    def run_tool_request(self, server, *, environment_overrides=None, config_toml=None):
        with RunningLocalRewrite(
            server.server_port, environment_overrides=environment_overrides,
            config_toml=config_toml,
        ) as relay:
            result = post_relay(relay.address, json_bytes(self.strict_tool_request()))
        self.assertEqual(result[0], 200)
        self.assertEqual(len(server.records), 1)
        return server.records[0]

    def assert_runtime_rejected(self, port, *, environment_overrides=None, config_toml=None):
        relay = RunningLocalRewrite(
            port, environment_overrides=environment_overrides,
            config_toml=config_toml,
        )
        with self.assertRaises(RuntimeError):
            with relay:
                self.fail("invalid DeepSeek configuration unexpectedly started")
        return relay.startup_line + relay.startup_tail

    def assert_stream_matches_fixture(self, actual, expected, fixture_request_id):
        actual_ids = set(re.findall(rb"msg_deepseek_[0-9]+", actual))
        expected_id = f"msg_deepseek_{fixture_request_id}".encode()
        self.assertEqual(actual_ids, {b"msg_deepseek_1"})
        self.assertIn(expected_id, expected)
        actual = actual.replace(b"msg_deepseek_1", b"msg_deepseek_REQUEST_ID")
        expected = expected.replace(expected_id, b"msg_deepseek_REQUEST_ID")
        self.assertEqual(actual, expected)

    def test_strict_tools_environment_routes_to_beta_and_normalizes_schema(self):
        response = self.buffered_cases["text_tool_usage_metadata"]["upstream_response"]
        with serving([{
            "status": response["status"], "content_type": response["content_type"],
            "body": response["body"].encode("utf-8"),
        }]) as server:
            record = self.run_tool_request(
                server,
                environment_overrides={
                    "PRODEX_DEEPSEEK_STRICT_TOOLS": "TrUe",
                    "PRODEX_DEEPSEEK_BETA_BASE_URL": (
                        f"http://127.0.0.1:{server.server_port}/beta///"
                    ),
                },
            )
        self.assertEqual(record["path"], "/beta/chat/completions")
        tool = json.loads(record["body"])["tools"][0]["function"]
        self.assertIs(tool["strict"], True)
        self.assertEqual(tool["parameters"], {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        })

    def test_environment_overrides_do_not_read_deepseek_config(self):
        response = self.buffered_cases["text_tool_usage_metadata"]["upstream_response"]
        with serving([{
            "status": response["status"], "content_type": response["content_type"],
            "body": response["body"].encode("utf-8"),
        }]) as server:
            config = (
                "[deepseek]\n"
                "strict_tools = true\n"
                f'beta_base_url = "http://127.0.0.1:{server.server_port}/configured-beta/"\n'
            )
            record = self.run_tool_request(
                server,
                environment_overrides={
                    "PRODEX_DEEPSEEK_STRICT_TOOLS": "false",
                    "PRODEX_DEEPSEEK_BETA_BASE_URL": (
                        f"http://127.0.0.1:{server.server_port}/environment-beta"
                    ),
                },
                config_toml=config,
            )
        self.assertEqual(record["path"], "/v1/chat/completions")
        tool = json.loads(record["body"])["tools"][0]["function"]
        self.assertNotIn("strict", tool)
        self.assertNotIn("required", tool["parameters"])

    def test_strict_tools_mixed_web_function_tools_fail_closed(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic strict web request",
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "name": "lookup",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
                {
                    "type": "web_search_preview",
                    "allowed_domains": ["example.test"],
                },
            ],
        }
        with serving([]) as server:
            with RunningLocalRewrite(
                server.server_port,
                environment_overrides={
                    "PRODEX_DEEPSEEK_STRICT_TOOLS": "true",
                    "PRODEX_DEEPSEEK_BETA_BASE_URL": (
                        f"http://127.0.0.1:{server.server_port}/beta"
                    ),
                },
            ) as relay:
                status, _, body = post_relay(relay.address, json_bytes(request))
        self.assertEqual(status, 502)
        self.assertEqual(body, b"upstream request failed")
        self.assertEqual(server.records, [])

    def test_disabled_strict_tools_keeps_default_route_and_schema(self):
        response = self.buffered_cases["text_tool_usage_metadata"]["upstream_response"]
        with serving([{
            "status": response["status"], "content_type": response["content_type"],
            "body": response["body"].encode("utf-8"),
        }]) as server:
            record = self.run_tool_request(
                server, environment_overrides={"PRODEX_DEEPSEEK_STRICT_TOOLS": "false"},
            )
        self.assertEqual(record["path"], "/v1/chat/completions")
        tool = json.loads(record["body"])["tools"][0]["function"]
        self.assertNotIn("strict", tool)
        self.assertEqual(tool["parameters"], self.strict_tool_request()["tools"][0]["parameters"])

    def test_invalid_strict_tools_values_are_rejected_before_listening(self):
        with serving([]) as server:
            for value in ("", " true ", "maybe"):
                with self.subTest(value=value):
                    self.assert_runtime_rejected(
                        server.server_port,
                        environment_overrides={"PRODEX_DEEPSEEK_STRICT_TOOLS": value},
                    )
        self.assertEqual(server.records, [])

    def test_strict_beta_base_url_rejects_unsafe_values_without_echoing_them(self):
        unsafe = (
            "",
            "http://user:synthetic-secret@127.0.0.1:1234/beta",
            "http://127.0.0.1:1234/beta?token=synthetic-secret",
            "http://127.0.0.1:1234/beta#synthetic-secret",
            " http://127.0.0.1:1234/beta ",
            "http:///beta",
            "http://127.0.0.1:/beta",
            "ftp://api.deepseek.com/beta",
        )
        with serving([]) as server:
            for value in unsafe:
                with self.subTest(value=value):
                    output = self.assert_runtime_rejected(
                        server.server_port,
                        environment_overrides={
                            "PRODEX_DEEPSEEK_STRICT_TOOLS": "true",
                            "PRODEX_DEEPSEEK_BETA_BASE_URL": value,
                        },
                    )
                    self.assertNotIn("synthetic-secret", output)
            self.assert_runtime_rejected(
                server.server_port,
                environment_overrides={"PRODEX_DEEPSEEK_STRICT_TOOLS": "true"},
            )
        self.assertEqual(server.records, [])

    def test_sigterm_exit_status_remains_visible(self):
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                self.assertEqual(relay.close(), -signal.SIGTERM)
            self.assertEqual(server.records, [])

    def test_buffered_request_and_response_match_frozen_fixtures(self):
        case = self.buffered_cases["text_tool_usage_metadata"]
        provider = case["upstream_response"]
        expected_request = case["upstream_request"]
        response_bytes = provider["body"].encode("utf-8")
        self.assertEqual(hashlib.sha256(response_bytes).hexdigest(), provider["sha256"])
        with serving([{
            "status": provider["status"], "content_type": provider["content_type"],
            "body": response_bytes,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, actual = post_relay(
                    relay.address, json_bytes(case["request"]),
                    path="/v1/responses?synthetic=buffered",
                )
        expected = case["oracle_response"]["body"].encode("utf-8")
        self.assertEqual(status, case["oracle_response"]["status"])
        self.assertEqual(headers.get("content-type"), "application/json; charset=utf-8")
        self.assertEqual(actual, expected)
        self.assertEqual(hashlib.sha256(actual).hexdigest(), case["oracle_response"]["sha256"])
        self.assertEqual(len(server.records), 1)
        sent = server.records[0]
        self.assertEqual((sent["method"], sent["path"]), (expected_request["method"], expected_request["path"]))
        self.assertEqual(sent["body"].decode("utf-8"), expected_request["body"])
        self.assertEqual(hashlib.sha256(sent["body"]).hexdigest(), expected_request["body_sha256"])
        self.assertEqual(sent["headers"].get("authorization"), expected_request["authorization"])
        self.assertEqual(sent["headers"].get("content-type"), expected_request["content_type"])

    def test_sse_completes_before_upstream_eof(self):
        case = self.stream_cases["text_done"]
        request_case = self.request_cases["defaults"]
        provider = base64.b64decode(case["upstream_base64"], validate=True)
        expected = base64.b64decode(case["expected_base64"], validate=True)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), case["oracle_response_sha256"])
        late = b'data: {"id":"late-malicious","choices":[]}\n\n'
        with serving([{
            "status": 200, "content_type": "text/event-stream",
            "body": provider + late, "chunked": True, "hold_open": True,
            "chunk_size": 23,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                request = dict(request_case["request"])
                request["stream"] = True
                started = time.monotonic()
                status, headers, actual = post_relay(relay.address, json_bytes(request), timeout=5)
                elapsed = time.monotonic() - started
                self.assertEqual(status, 200)
                self.assertEqual(headers.get("content-type"), "text/event-stream; charset=utf-8")
                self.assertLess(elapsed, 2.0, "relay waited for upstream EOF after response.completed")
                self.assertTrue(server.client_closed.wait(0.5), "relay must close upstream after [DONE]")
                self.assertNotIn(b"late-malicious", actual)
                self.assert_stream_matches_fixture(actual, expected, case["header"]["request_id"])
        self.assertEqual(len(server.records), 1)
        sent = server.records[0]
        expected_upstream = request_case["upstream_request"]["body"].encode("utf-8")
        expected_upstream = expected_upstream.replace(b'"stream":false', b'"stream":true', 1)
        self.assertEqual((sent["method"], sent["path"]), ("POST", "/v1/chat/completions"))
        self.assertEqual(sent["body"], expected_upstream)

    def test_downstream_rst_closes_active_upstream_stream(self):
        stream = base64.b64decode(self.stream_cases["text_done"]["upstream_base64"], validate=True)
        first_event = stream.split(b"\n\n", 1)[0] + b"\n\n"
        with serving([{
            "status": 200, "content_type": "text/event-stream",
            "body": first_event, "chunked": True, "hold_open": True,
            "chunk_size": 11,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                request = dict(self.request_cases["defaults"]["request"])
                request["stream"] = True
                connection = HTTPConnection(relay.address[0], relay.address[1], timeout=5)
                connection.request(
                    "POST", "/v1/responses", body=json_bytes(request),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "text/event-stream; charset=utf-8")
                self.assertTrue(response.read(1), "relay must forward an event before client reset")
                client_socket = connection.sock or response.fp.raw._sock
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                client_socket.close()
                response.close()
                connection.close()
                self.assertTrue(server.client_closed.wait(0.75), "downstream RST must close upstream")
                self.assertFalse(server.hold_timed_out.is_set())
        self.assertEqual(len(server.records), 1)

    def test_sse_completes_after_downstream_half_close(self):
        case = self.stream_cases["text_done"]
        provider = base64.b64decode(case["upstream_base64"], validate=True)
        request = dict(self.request_cases["defaults"]["request"])
        request["stream"] = True
        with serving([{
            "status": 200, "content_type": "text/event-stream", "body": provider,
            "chunked": True, "chunk_size": 19,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, body = post_then_half_close(relay.address, json_bytes(request))
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-type"), "text/event-stream; charset=utf-8")
        self.assertIn(b"event: response.completed", body)
        self.assertEqual(len(server.records), 1)

    def test_bound_empty_history_is_rejected_before_an_unknown_followup(self):
        empty = {"id": "chat-empty", "created": 1, "model": "deepseek-chat", "choices": []}
        answer = {"id": "chat-next", "created": 1, "model": "deepseek-chat", "choices": [{"message": {"content": "next"}}]}
        responses = [{"status": 200, "content_type": "application/json", "body": json_bytes(value)}
                     for value in (empty, answer)]
        with serving(responses) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                first = {"model": "deepseek-chat", "input": []}
                follow = {"model": "deepseek-chat", "input": "next", "previous_response_id": "chat-empty", "stream": True, "text": {"format": {"type": "json_object"}}}
                self.assertEqual(post_relay(relay.address, json_bytes(first), headers={"session_id": "a"})[0], 200)
                self.assertEqual(post_relay(relay.address, json_bytes(follow), headers={"session_id": "a"})[0], 503)
                self.assertEqual(post_relay(relay.address, json_bytes(follow), headers={"session_id": "b"})[0], 503)
                unknown = {**follow, "previous_response_id": "unknown"}
                self.assertEqual(post_relay(relay.address, json_bytes(unknown), headers={"session_id": "b"})[0], 200)
        self.assertEqual(len(server.records), 2)
        fresh = json.loads(server.records[1]["body"])
        self.assertNotIn("response_format", fresh)
        self.assertNotIn("stream_options", fresh)

    def test_buffered_and_streamed_response_ownership_precedes_history(self):
        buffered = self.buffered_cases["text_tool_usage_metadata"]
        streamed = self.stream_cases["function_namespace_dot"]
        follow = self.buffered_cases["blank_provider_metadata"]
        follow_upstream = follow["upstream_response"]
        modes = [
            {
                "name": "buffered", "request": dict(buffered["request"]),
                "response": {
                    "status": buffered["upstream_response"]["status"],
                    "content_type": buffered["upstream_response"]["content_type"],
                    "body": buffered["upstream_response"]["body"].encode("utf-8"),
                },
                "call_id": "call_東京",
                "expected_request": buffered["upstream_request"]["body"].encode("utf-8"),
            },
            {
                "name": "streamed", "request": dict(self.request_cases["defaults"]["request"]),
                "response": {
                    "status": 200, "content_type": "text/event-stream",
                    "body": base64.b64decode(streamed["upstream_base64"], validate=True),
                },
                "call_id": "call-namespace-dot", "stream_case": streamed,
                "expected_request": self.request_cases["defaults"]["upstream_request"]["body"].encode(
                    "utf-8",
                ).replace(b'"stream":false', b'"stream":true', 1),
            },
        ]
        for mode in modes:
            with self.subTest(mode=mode["name"]):
                first_request = dict(mode["request"])
                first_request["session_id"] = "scope-a"
                if mode["name"] == "streamed":
                    first_request["stream"] = True
                responses = [
                    mode["response"],
                    {"status": follow_upstream["status"],
                     "content_type": follow_upstream["content_type"],
                     "body": follow_upstream["body"].encode("utf-8")},
                ]
                with serving(responses) as server:
                    with RunningLocalRewrite(server.server_port) as relay:
                        status, headers, first_body = post_relay(
                            relay.address, json_bytes(first_request),
                        )
                        self.assertEqual(status, 200)
                        if mode["name"] == "buffered":
                            first_body_expected = buffered["oracle_response"]["body"].encode("utf-8")
                            self.assertEqual(first_body, first_body_expected)
                            first_response_id = json.loads(first_body)["id"]
                        else:
                            self.assertEqual(headers.get("content-type"), "text/event-stream; charset=utf-8")
                            expected_stream = base64.b64decode(
                                mode["stream_case"]["expected_base64"], validate=True,
                            )
                            self.assert_stream_matches_fixture(
                                first_body, expected_stream,
                                mode["stream_case"]["header"]["request_id"],
                            )
                            completed = re.search(
                                rb"event: response.completed\r\ndata: ([^\r\n]+)", first_body,
                            )
                            self.assertIsNotNone(completed, first_body)
                            first_response_id = json.loads(completed.group(1))["response"]["id"]

                        follow_request = {
                            "model": "deepseek-chat",
                            "previous_response_id": first_response_id,
                            "session_id": "scope-a",
                            "input": [
                                {
                                    "type": "function_call_output", "call_id": mode["call_id"],
                                    "output": "synthetic tool result",
                                },
                                {"type": "message", "role": "user", "content": "continue"},
                            ],
                        }
                        status, _, _ = post_relay(relay.address, json_bytes(follow_request))
                        self.assertEqual(status, 503)
                        isolated_request = {
                            "model": "deepseek-chat",
                            "previous_response_id": first_response_id,
                            "session_id": "scope-b", "input": "fresh namespace",
                        }
                        status, _, _ = post_relay(relay.address, json_bytes(isolated_request))
                        self.assertEqual(status, 503)
                        fresh_request = {"model": "deepseek-chat", "session_id": "scope-b", "input": "fresh namespace"}
                        self.assertEqual(post_relay(relay.address, json_bytes(fresh_request))[0], 200)
                self.assertEqual(len(server.records), 2)
                self.assertEqual(server.records[0]["body"], mode["expected_request"])
                isolated = json.loads(server.records[1]["body"])
                self.assertEqual(isolated["messages"], [{"role": "user", "content": "fresh namespace"}])

    def test_invalid_and_oversized_requests_never_reach_upstream(self):
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, _, body = post_relay(relay.address, b'{"model":')
                self.assertEqual((status, body), (502, b"upstream request failed"))
                status, body = post_declared_oversized_body(relay.address, 64 * 1024 * 1024 + 1)
                self.assertEqual((status, body), (413, b"proxied request body is too large"))
        self.assertEqual(server.records, [])

    def test_malformed_http_line_and_header_return_empty_400(self):
        malformed = (
            b"POST /v1/responses\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
            b"POST /v1/responses bad HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nMalformed\r\n\r\n",
        )
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                for request in malformed:
                    with self.subTest(request=request):
                        response = raw_http_exchange(relay.address, request)
                        head, body = response.split(b"\r\n\r\n", 1)
                        self.assertEqual(head.split(b"\r\n", 1)[0], b"HTTP/1.1 400 Bad Request")
                        self.assertEqual(body, b"")
                        self.assertIn(b"Content-Length: 0", head)
        self.assertEqual(server.records, [])

    def test_extra_request_line_token_keeps_the_capture_error_response(self):
        request = (
            b"POST /v1/responses HTTP/1.1 extra\r\nHost: 127.0.0.1\r\n"
            b"Connection: close\r\n\r\n"
        )
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                response = raw_http_exchange(relay.address, request)
        head, body = response.split(b"\r\n\r\n", 1)
        self.assertEqual(head.split(b" ", 2)[:2], [b"HTTP/1.1", b"502"])
        self.assertEqual(body, b"upstream request failed")
        self.assertEqual(server.records, [])

    def test_websocket_upgrade_returns_the_https_fallback_response(self):
        expected = b"provider adapter requires HTTPS Responses transport fallback"
        body = b'{"model":"deepseek-chat","input":"synthetic websocket probe"}'
        requests = (
            (b"Upgrade: WebSocket\r\n",),
            (b"Connection: keep-alive\r\n", b"Upgrade: websocket\r\n"),
            (
                b"Connection: keep-alive\r\n", b"Connection: Upgrade\r\n",
                b"Upgrade: websocket\r\n",
            ),
        )
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                for headers in requests:
                    request = (
                        b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        + b"".join(headers)
                        + b"Content-Type: application/json\r\nContent-Length: "
                        + str(len(body)).encode() + b"\r\n\r\n" + body
                    )
                    with self.subTest(headers=headers):
                        response = raw_http_exchange(relay.address, request)
                        head, response_body = response.split(b"\r\n\r\n", 1)
                        self.assertEqual(head.split(b"\r\n", 1)[0], b"HTTP/1.1 426 Upgrade Required")
                        self.assertEqual(response_body, expected)
        self.assertEqual(server.records, [])

    def test_unsupported_route_returns_json_without_upstream_request(self):
        with serving([]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                connection = HTTPConnection(relay.address[0], relay.address[1], timeout=5)
                connection.request("GET", "/v1/responses")
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 404)
                self.assertEqual(response.getheader("Content-Type"), "application/json")
                self.assertEqual(
                    body,
                    b'{"error":{"code":"unsupported_provider_route","message":"provider route is not supported"}}',
                )
                connection.close()
        self.assertEqual(server.records, [])

    def test_non_2xx_upstream_status_and_body_are_forwarded(self):
        upstream_body = b"synthetic upstream unavailable"
        with serving([{
            "status": 503, "content_type": "text/plain", "body": upstream_body,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                request = self.request_cases["defaults"]["request"]
                status, headers, body = post_relay(relay.address, json_bytes(request))
        self.assertEqual((status, body), (503, upstream_body))
        self.assertEqual(headers.get("content-type"), "text/plain")
        self.assertEqual(len(server.records), 1)

    def test_chat_completions_passthrough_preserves_body_query_headers_and_error(self):
        request_body = (
            b'{ "model": "deepseek-chat", "messages": '
            b'[{"role":"user","content":"passthrough"}], "stream": false }\n'
        )
        upstream_body = b'{"error":{"type":"rate_limit_error","message":"synthetic limit"}}'
        response_headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("X-Request-Id", "synthetic-deepseek-request"),
            ("x-codex-turn-state", "synthetic-turn-state"),
            ("Connection", "keep-alive, X-Upstream-Hop"),
            ("X-Upstream-Hop", "strip-me"),
        ]
        with serving([{
            "status": 429, "content_type": "application/json", "body": upstream_body,
            "response_headers": response_headers,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, body = post_relay(
                    relay.address,
                    request_body,
                    path="/v1/chat/completions?trace=synthetic",
                    headers={
                        "Authorization": "Bearer caller-secret",
                        "Connection": "X-Request-Hop, keep-alive",
                        "X-Request-Hop": "strip-me",
                        "chatgpt-account-id": "account-secret",
                        "x-prodex-internal-marker": "internal-secret",
                        "X-Trace": "trace-17",
                        "session_id": "session-17",
                        "x-codex-turn-state": "turn-state-17",
                    },
                )

        self.assertEqual((status, body), (429, upstream_body))
        self.assertEqual(headers.get("content-type"), "application/json; charset=utf-8")
        self.assertEqual(headers.get("x-request-id"), "synthetic-deepseek-request")
        self.assertEqual(headers.get("x-codex-turn-state"), "synthetic-turn-state")
        self.assertNotIn("x-upstream-hop", headers)
        self.assertEqual(headers.get("content-length"), str(len(upstream_body)))
        self.assertEqual(len(server.records), 1, "passthrough must never replay the request")
        sent = server.records[0]
        self.assertEqual((sent["method"], sent["path"]), (
            "POST", "/v1/chat/completions?trace=synthetic",
        ))
        self.assertEqual(sent["body"], request_body)
        self.assertEqual(sent["headers"].get("authorization"), "Bearer synthetic-provider-key")
        self.assertEqual(sent["headers"].get("x-trace"), "trace-17")
        self.assertEqual(sent["headers"].get("session_id"), "session-17")
        self.assertEqual(sent["headers"].get("x-codex-turn-state"), "turn-state-17")
        for name in (
            "x-request-hop", "chatgpt-account-id", "x-prodex-internal-marker",
        ):
            self.assertNotIn(name, sent["headers"])

    def test_chat_completions_sse_is_incremental_and_cancellation_closes_upstream(self):
        event = b'data: {"id":"raw-chat-chunk","choices":[{"delta":{"content":"ok"}}]}\n\n'
        with serving([{
            "status": 200,
            "content_type": "text/event-stream; charset=utf-8",
            "body": event,
            "chunked": True,
            "hold_open": True,
            "chunk_size": 7,
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                connection = HTTPConnection(relay.address[0], relay.address[1], timeout=5)
                connection.request(
                    "POST",
                    "/v1/chat/completions?trace=stream",
                    body=b'{"model":"deepseek-chat","stream":true}',
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.getheader("Content-Type"),
                    "text/event-stream; charset=utf-8",
                )
                self.assertEqual(response.getheader("Transfer-Encoding"), "chunked")
                self.assertEqual(response.read(len(event)), event)
                client_socket = connection.sock or response.fp.raw._sock
                client_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0),
                )
                client_socket.close()
                response.close()
                connection.close()
                self.assertTrue(
                    server.client_closed.wait(0.75),
                    "downstream cancellation must close the provider connection",
                )
                self.assertFalse(server.hold_timed_out.is_set())

        self.assertEqual(len(server.records), 1, "stream cancellation must not replay")
        sent = server.records[0]
        self.assertEqual((sent["method"], sent["path"]), (
            "POST", "/v1/chat/completions?trace=stream",
        ))
        self.assertEqual(sent["body"], b'{"model":"deepseek-chat","stream":true}')

    def test_clean_runtime_buffered_relay_with_loopback_upstream(self):
        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap is unavailable; clean-runtime relay not verified")
        case = self.buffered_cases["blank_provider_metadata"]
        upstream = case["upstream_response"]
        with serving([{
            "status": upstream["status"], "content_type": upstream["content_type"],
            "body": upstream["body"].encode("utf-8"),
        }]) as server:
            with RunningLocalRewrite(server.server_port, sandbox=True) as relay:
                status, _, actual = post_relay(relay.address, json_bytes(case["request"]))
        self.assertEqual(status, case["oracle_response"]["status"])
        self.assertEqual(actual, case["oracle_response"]["body"].encode("utf-8"))
        self.assertEqual(len(server.records), 1)


if __name__ == "__main__":
    unittest.main()
