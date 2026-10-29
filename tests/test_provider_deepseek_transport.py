"""Real loopback transport checks against frozen DeepSeek request/stream captures."""

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
REQUEST_FIXTURE = ROOT / "tests/fixtures/provider-requests/cases.json"
STREAM_FIXTURE = ROOT / "tests/fixtures/provider-stream/cases.json"
BUFFERED_FIXTURE = ROOT / "tests/fixtures/provider-buffered/cases.json"
DRIVER = Path(os.environ.get(
    "MODEX_PROVIDER_DEEPSEEK_TRANSPORT_DRIVER",
    ROOT / "build/tests/provider_deepseek_transport_driver",
))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"

sys.path.insert(0, str(ROOT / "tests"))
from session_oracle import sandbox_command
from test_local_rewrite import RunningLocalRewrite, json_bytes, post_relay


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, body=b"", *, status=200, content_type="text/event-stream",
                 chunked=False, hold_open=False, drop_connection=False,
                 response_headers=None, chunk_size=11, delay=0,
                 hold_before_response=False):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.chunked = chunked
        self.hold_open = hold_open
        self.drop_connection = drop_connection
        self.response_headers = response_headers
        self.chunk_size = chunk_size
        self.delay = delay
        self.hold_before_response = hold_before_response
        self.records = []
        self.request_received = threading.Event()
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
            "headers": {key.lower(): value for key, value in self.headers.items()},
            "body": self.rfile.read(length),
        })
        self.server.request_received.set()
        if self.server.hold_before_response:
            self.connection.settimeout(3)
            try:
                if self.connection.recv(1) == b"":
                    self.server.client_closed.set()
            except OSError:
                self.server.client_closed.set()
            self.close_connection = True
            return
        if self.server.drop_connection:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.close_connection = True
            return
        self.send_response(self.server.status)
        if self.server.response_headers is None:
            self.send_header("Content-Type", self.server.content_type)
        else:
            for name, value in self.server.response_headers:
                self.send_header(name, value)
        if self.server.chunked:
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "keep-alive")
        else:
            self.send_header("Content-Length", str(len(self.server.body)))
            self.send_header("Connection", "close")
        self.end_headers()
        body = self.server.body
        try:
            for offset in range(0, len(body), self.server.chunk_size):
                part = body[offset:offset + self.server.chunk_size]
                if self.server.chunked:
                    self.wfile.write(f"{len(part):X}\r\n".encode() + part + b"\r\n")
                else:
                    self.wfile.write(part)
                self.wfile.flush()
                if self.server.delay:
                    time.sleep(self.server.delay)
        except OSError:
            self.server.client_closed.set()
            self.close_connection = True
            return
        if self.server.hold_open:
            self.connection.settimeout(2)
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


class ProviderDeepSeekTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
        cls.streams = json.loads(STREAM_FIXTURE.read_text(encoding="utf-8"))
        cls.buffered = json.loads(BUFFERED_FIXTURE.read_text(encoding="utf-8"))
        for catalog in (cls.requests, cls.streams, cls.buffered):
            if catalog["oracle_sha256"] != ORACLE_SHA256:
                raise AssertionError("fixture does not identify the pinned Prodex oracle")
            if catalog["baseline_commit"] != "433aad44bb249d5c25a231a6b06c2fa522a39a1f":
                raise AssertionError("fixture does not identify the frozen baseline commit")
        if not DRIVER.is_file():
            raise AssertionError(f"native transport driver has not been built: {DRIVER}")
        cls.request_cases = {case["name"]: case for case in cls.requests["cases"]}
        cls.stream_cases = {case["name"]: case for case in cls.streams["cases"]}
        cls.buffered_cases = {case["name"]: case for case in cls.buffered["cases"]}

    def run_native(self, server, request_case, stream_case=None, *, options=None,
                   timeout=5, sandbox=False, pass_fds=()):
        with tempfile.TemporaryDirectory(prefix="modex-deepseek-transport-") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir(mode=0o700)
            (root / "workspace").mkdir(mode=0o700)
            config = {
                "address": f"127.0.0.1:{server.server_port}",
                "path": "/v1/chat/completions",
                "api_key": "synthetic-provider-key",
                "request": request_case["request"],
                "history": request_case.get("history", []),
                "strict_tools": request_case.get("strict_tools", False),
                "web_search_mode": request_case.get("web_search_mode", "auto"),
                "request_id": 1,
                "response_id": "resp_deepseek_1",
                "created_at": 1,
                "connect_timeout_ms": 1000,
                "request_timeout_ms": 1000,
                "idle_timeout_ms": 1000,
                "max_body_bytes": 4194304,
            }
            if stream_case is not None:
                for key in ("request_id", "response_id", "created_at"):
                    config[key] = stream_case["header"][key]
            if options:
                config.update(options)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config, separators=(",", ":")), encoding="utf-8")
            environment = {
                "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
                "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                "TMPDIR": str(root),
            }
            command = [str(DRIVER), str(config_path)]
            if sandbox:
                command = sandbox_command(
                    DRIVER, root, [str(config_path)],
                    environment={"TMPDIR": str(root), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                )
                command.insert(command.index("--"), "--share-net")
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=timeout, check=False,
                cwd=root, env=environment, pass_fds=pass_fds,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        lines = result.stdout.decode("utf-8", "replace").splitlines()
        self.assertTrue(lines, result.stderr.decode("utf-8", "replace"))
        try:
            output = [json.loads(line) for line in lines]
        except json.JSONDecodeError as error:
            self.fail(f"native driver emitted invalid JSONL: {error}: {lines!r}")
        return output, result.stdout, result.stderr

    def call(self, body=b"", *, status=200, content_type="text/event-stream",
             chunked=False, hold_open=False, drop_connection=False,
             response_headers=None, chunk_size=11, delay=0,
             request_name="defaults", request_case=None, stream_name="text_done", options=None,
             timeout=5, sandbox=False):
        server = Upstream(
            body, status=status, content_type=content_type, chunked=chunked,
            hold_open=hold_open, drop_connection=drop_connection,
            response_headers=response_headers,
            chunk_size=chunk_size, delay=delay,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_native(
                server, request_case or self.request_cases[request_name],
                self.stream_cases.get(stream_name) if stream_name else None,
                options=options, timeout=timeout, sandbox=sandbox,
            )
            return (*result, server)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    @staticmethod
    def records(output, kind):
        return [item for item in output if item.get("type") == kind]

    def buffered_response_bytes(self, output, stdout, expected_case):
        self.assertEqual([item.get("type") for item in output], ["headers", "buffered", "done"], output)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])
        response = self.records(output, "buffered")
        self.assertEqual(len(response), 1, output)
        expected = expected_case["oracle_response"]
        self.assertEqual(response[0]["status"], expected["status"])
        lines = stdout.splitlines()
        raw = next(
            line for line in lines
            if json.loads(line).get("type") == "buffered"
        ).decode("utf-8")
        marker = '"body":'
        start = raw.index(marker) + len(marker)
        _, end = json.JSONDecoder().raw_decode(raw, start)
        actual = raw[start:end].encode("utf-8")
        expected_bytes = expected["body"].encode("utf-8")
        self.assertEqual(hashlib.sha256(expected_bytes).hexdigest(), expected["sha256"])
        if expected_case["name"].startswith("missing_tool_call_id_"):
            actual_body = json.loads(actual)
            expected_body = json.loads(expected_bytes)
            actual_id = actual_body["output"][0]["call_id"]
            expected_id = expected_body["output"][0]["call_id"]
            for call_id in (actual_id, expected_id):
                self.assertTrue(call_id.startswith("call_deepseek_"), call_id)
                suffix = call_id.removeprefix("call_deepseek_")
                parsed = uuid.UUID(suffix)
                self.assertEqual(suffix, str(parsed), call_id)
                self.assertEqual(parsed.version, 7, call_id)
                self.assertEqual(parsed.variant, uuid.RFC_4122, call_id)
            actual_marker = actual_id.encode("utf-8")
            expected_marker = expected_id.encode("utf-8")
            self.assertEqual(actual.count(actual_marker), 1)
            self.assertEqual(expected_bytes.count(expected_marker), 1)
            actual = actual.replace(actual_marker, b"call_deepseek_UUIDv7")
            expected_bytes = expected_bytes.replace(expected_marker, b"call_deepseek_UUIDv7")
        else:
            self.assertEqual(hashlib.sha256(actual).hexdigest(), expected["sha256"])
        self.assertEqual(actual, expected_bytes)
        return actual

    def test_real_post_and_buffered_responses_match_frozen_fixtures(self):
        request_case = self.buffered_cases["text_tool_usage_metadata"]
        upstream = request_case["upstream_response"]
        expected_request = request_case["upstream_request"]
        body = upstream["body"].encode("utf-8")
        self.assertEqual(hashlib.sha256(body).hexdigest(), upstream["sha256"])
        output, stdout, _, server = self.call(
            body, status=upstream["status"], content_type=upstream["content_type"],
            request_case={"request": request_case["request"]}, stream_name=None,
            chunk_size=13, delay=0.001,
        )
        self.assertEqual(len(server.records), 1, "buffered transport must issue one POST")
        sent = server.records[0]
        self.assertEqual((sent["method"], sent["path"]), (expected_request["method"], expected_request["path"]))
        self.assertEqual(sent["body"].decode("utf-8"), expected_request["body"])
        self.assertEqual(hashlib.sha256(sent["body"]).hexdigest(), expected_request["body_sha256"])
        self.assertEqual(sent["headers"].get("authorization"), expected_request["authorization"])
        self.assertEqual(sent["headers"].get("content-type"), expected_request["content_type"])
        self.assertNotIn(b'"metadata"', sent["body"])
        expected_response = self.buffered_response_bytes(output, stdout, request_case)
        self.assertIn('"trace":"synthetic"'.encode(), expected_response)
        pending = self.records(output, "headers")[0]["messages"]
        history = self.records(output, "buffered")[0]["conversation_messages"]
        self.assertEqual(history[:-1], pending)
        original = json.loads(upstream["body"])["choices"][0]["message"]
        self.assertEqual(history[-1], {
            "role": "assistant", "content": original["content"],
            "reasoning_content": original["reasoning_content"],
            "tool_calls": original["tool_calls"],
        })
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_buffered_mapper_cases_match_frozen_bytes(self):
        for name, case in self.buffered_cases.items():
            with self.subTest(case=name):
                upstream = case["upstream_response"]
                output, stdout, _, server = self.call(
                    upstream["body"].encode("utf-8"),
                    status=upstream["status"], content_type=upstream["content_type"],
                    request_case={"request": case["request"]}, stream_name=None,
                    chunk_size=17,
                )
                self.assertEqual(len(server.records), 1)
                self.assertEqual(
                    server.records[0]["body"].decode("utf-8"),
                    case["upstream_request"]["body"],
                )
                self.buffered_response_bytes(output, stdout, case)
                if json.loads(case["oracle_response"]["body"]).get("status") == "failed":
                    self.assertEqual(self.records(output, "buffered")[0]["conversation_messages"], [])
                self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_real_post_and_fragmented_sse_match_frozen_fixtures(self):
        request_case = self.request_cases["defaults"]
        for case_name in ("text_done", "fragmented_json_data_lines"):
            with self.subTest(stream_case=case_name):
                stream_case = self.stream_cases[case_name]
                upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
                expected = base64.b64decode(stream_case["expected_base64"], validate=True)
                self.assertEqual(hashlib.sha256(expected).hexdigest(), stream_case["oracle_response_sha256"])
                output, _, _, server = self.call(
                    upstream, stream_name=case_name, chunk_size=7, delay=0.001,
                )
                self.assertEqual(len(server.records), 1, "transport must issue one POST")
                sent = server.records[0]
                self.assertEqual((sent["method"], sent["path"]), ("POST", "/v1/chat/completions"))
                self.assertEqual(sent["body"].decode(), request_case["upstream_request"]["body"])
                self.assertEqual(hashlib.sha256(sent["body"]).hexdigest(), request_case["upstream_body_sha256"])
                self.assertEqual(sent["headers"].get("authorization"), "Bearer synthetic-provider-key")
                self.assertEqual(sent["headers"].get("content-type"), "application/json")
                observed = self.records(output, "headers")
                self.assertEqual(len(observed), 1, output)
                self.assertEqual(observed[0]["body"], json.loads(request_case["upstream_request"]["body"]))
                actual = "".join(item["sse"] for item in self.records(output, "event")).encode()
                self.assertEqual(actual, expected)
                self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_headers_are_filtered_and_request_metadata_is_preserved(self):
        request_case = self.request_cases["metadata"]
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        injected_secret = "Bearer caller-must-not-win"
        headers = [
            ["Authorization", injected_secret], ["Host", "attacker.invalid"],
            ["Content-Length", "0"], ["Connection", "X-Nominated, keep-alive"],
            ["X-Nominated", "strip-me"], ["chatgpt-account-id", "account-secret"],
            ["x-prodex-internal-marker", "internal-secret"], ["X-Trace", "trace-17"],
        ]
        output, stdout, stderr, server = self.call(
            upstream, request_name="metadata", options={"headers": headers},
        )
        self.assertEqual(len(server.records), 1, "filtered headers must not cause retries")
        sent = server.records[0]["headers"]
        self.assertEqual(sent.get("authorization"), "Bearer synthetic-provider-key")
        self.assertEqual(sent.get("host"), f"127.0.0.1:{server.server_port}")
        self.assertNotIn("x-nominated", sent)
        self.assertNotIn("chatgpt-account-id", sent)
        self.assertNotIn("x-prodex-internal-marker", sent)
        self.assertEqual(sent.get("x-trace"), "trace-17")
        self.assertEqual(server.records[0]["body"].decode(), request_case["upstream_request"]["body"])
        header = self.records(output, "headers")[0]
        self.assertEqual(header["response_metadata"], request_case["expected_response_metadata"])
        self.assertNotIn(injected_secret.encode(), stdout + stderr)
        self.assertNotIn(b"account-secret", stdout + stderr)

    def test_prepared_body_does_not_replace_pending_messages(self):
        request_case = self.request_cases["json_schema"]
        upstream = base64.b64decode(
            self.stream_cases["text_done"]["upstream_base64"], validate=True,
        )
        output, _, _, server = self.call(
            upstream, request_name="json_schema", stream_name="text_done",
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(server.records[0]["body"].decode(), request_case["upstream_request"]["body"])
        exchange = self.records(output, "headers")[0]
        prepared_body = json.loads(request_case["upstream_request"]["body"])
        self.assertEqual(exchange["body"], prepared_body)
        self.assertEqual(exchange["response_metadata"], request_case["expected_response_metadata"])
        self.assertEqual(prepared_body["messages"][0]["role"], "user")
        self.assertEqual(exchange["messages"][0]["role"], "system")
        self.assertNotEqual(exchange["messages"], prepared_body["messages"])

    def test_non_2xx_is_reported_without_retry(self):
        output, _, _, server = self.call(
            b"synthetic upstream unavailable", status=503,
            content_type="text/plain", stream_name=None,
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(self.records(output, "headers")[0]["status"], 503)
        self.assertEqual(self.records(output, "http_error"), [{
            "type": "http_error", "status": 503,
            "body_hex": b"synthetic upstream unavailable".hex(),
        }])
        self.assertEqual(self.records(output, "event"), [])
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_content_type_matching_is_case_insensitive(self):
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        expected = base64.b64decode(stream_case["expected_base64"], validate=True)
        output, _, _, server = self.call(
            upstream, content_type="Text/Event-Stream; charset=UTF-8",
        )
        self.assertEqual(len(server.records), 1)
        actual = b"".join(item["sse"].encode() for item in self.records(output, "event"))
        self.assertEqual(actual, expected)

    def test_first_content_type_header_controls_reader_selection(self):
        upstream = base64.b64decode(
            self.stream_cases["text_done"]["upstream_base64"], validate=True,
        )
        output, _, _, server = self.call(
            upstream, hold_open=True,
            response_headers=[
                ("Content-Type", "application/json"),
                ("Content-Type", "text/event-stream"),
            ],
        )
        self.assertEqual(len(server.records), 1)
        errors = self.records(output, "error")
        self.assertEqual(len(errors), 1, output)
        self.assertEqual(errors[0]["message"], "failed to parse DeepSeek chat response JSON")
        self.assertEqual(self.records(output, "buffered"), [])
        self.assertEqual(self.records(output, "http_error"), [])
        self.assertTrue(server.client_closed.wait(0.5), "JSON parse failure must close the socket")

    def test_sse_first_content_type_header_selects_stream_reader(self):
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        expected = base64.b64decode(stream_case["expected_base64"], validate=True)
        output, _, _, server = self.call(
            upstream,
            response_headers=[
                ("Content-Type", "text/event-stream"),
                ("Content-Type", "application/json"),
            ],
        )
        self.assertEqual(len(server.records), 1)
        actual = b"".join(item["sse"].encode() for item in self.records(output, "event"))
        self.assertEqual(actual, expected)
        self.assertEqual(self.records(output, "error"), [])

    def test_malformed_json_response_closes_the_socket(self):
        output, _, _, server = self.call(
            b'{"synthetic":', content_type="application/json", hold_open=True,
        )
        self.assertEqual(len(server.records), 1)
        errors = self.records(output, "error")
        self.assertEqual(len(errors), 1, output)
        self.assertEqual(errors[0]["message"], "failed to parse DeepSeek chat response JSON")
        self.assertEqual(self.records(output, "buffered"), [])
        self.assertEqual(self.records(output, "http_error"), [])
        self.assertTrue(server.client_closed.wait(0.5), "malformed buffered JSON must close the socket")

    def test_empty_and_whitespace_api_keys_are_rejected_before_post(self):
        upstream = base64.b64decode(
            self.stream_cases["text_done"]["upstream_base64"], validate=True,
        )
        for api_key in ("", "   ", "\u2003"):
            with self.subTest(api_key=repr(api_key)):
                output, _, _, server = self.call(
                    upstream, options={"api_key": api_key},
                )
                self.assertEqual(server.records, [], "invalid API key must fail before networking")
                self.assertEqual(len(self.records(output, "error")), 1, output)
                self.assertEqual(self.records(output, "headers"), [])

    def test_bounded_http_error_body(self):
        output, stdout, _, server = self.call(
            b"x" * 2048, status=502, content_type="text/plain",
            stream_name=None, options={"max_body_bytes": 64},
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(self.records(output, "http_error"), [])
        bounded = self.records(output, "error")
        self.assertEqual(len(bounded), 1, output)
        message = bounded[0]["message"].lower()
        self.assertTrue(any(word in message for word in ("oversized", "limit", "too large")), output)
        self.assertNotIn(b"x" * 128, stdout)

    def test_buffered_body_limit_fails_closed_without_emitting_payload(self):
        oversized = b'{"padding":"' + b"x" * 2048 + b'"}'
        output, stdout, _, server = self.call(
            oversized, content_type="application/json", hold_open=True,
            stream_name=None, options={"max_body_bytes": 64},
        )
        self.assertEqual(len(server.records), 1)
        errors = self.records(output, "error")
        self.assertEqual(len(errors), 1, output)
        self.assertEqual(self.records(output, "buffered"), [])
        self.assertEqual(self.records(output, "http_error"), [])
        message = errors[0]["message"].lower()
        self.assertTrue(any(word in message for word in ("oversized", "limit", "too large")), output)
        self.assertNotIn(b"x" * 128, stdout)
        self.assertTrue(server.client_closed.wait(0.5), "oversized buffered JSON must close the socket")

    def test_sse_line_limit_fails_without_emitting_oversized_input(self):
        oversized = b"data: " + b"x" * 128 + b"\n\n"
        output, stdout, _, server = self.call(
            oversized, options={"line_max_bytes": 64},
        )
        self.assertEqual(len(server.records), 1)
        events = self.records(output, "event")
        self.assertEqual(len(events), 1, output)
        self.assertIn("response.failed", events[0]["sse"])
        self.assertNotIn(b"x" * 128, stdout)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_idle_timeout_emits_failure(self):
        output, _, _, server = self.call(
            b"", chunked=True, hold_open=True, stream_name=None,
            options={"idle_timeout_ms": 100}, timeout=3,
        )
        self.assertEqual(len(server.records), 1)
        self.assertTrue(self.records(output, "headers"))
        failed = [item["sse"] for item in self.records(output, "event")]
        self.assertTrue(any("response.failed" in event for event in failed), output)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_connected_local_rewrite_streams_over_4_mib_total(self):
        content = b"x" * 2_100_000
        event = b'data: {"choices":[{"delta":{"content":"' + content + b'"}}]}\n\n'
        upstream = event + event + b"data: [DONE]\n\n"
        self.assertGreater(len(upstream), 4 * 1024 * 1024)
        server = Upstream(upstream, chunked=True, chunk_size=65536)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, body = post_relay(
                    relay.address,
                    json_bytes({"model": "deepseek-chat", "input": "synthetic large stream", "stream": True}),
                    timeout=20,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-type"), "text/event-stream; charset=utf-8")
        self.assertEqual(body.count(b"event: response.output_text.delta"), 2)
        self.assertIn(content + content, body)
        self.assertIn(b"response.completed", body)
        self.assertEqual(len(server.records), 1)

    def test_connected_local_rewrite_projects_provider_rate_limits(self):
        buffered = json.dumps({
            "id": "chatcmpl_rate_limit",
            "model": "deepseek-chat",
            "created": 1700000000,
            "choices": [{"message": {"content": "limited"}, "finish_reason": "stop"}],
        }, separators=(",", ":")).encode()
        streamed = base64.b64decode(self.stream_cases["text_done"]["upstream_base64"], validate=True)
        rate_headers = [
            ("x-ratelimit-limit-requests", "100"),
            ("x-ratelimit-remaining-requests", "40"),
            ("x-ratelimit-reset-requests", "60s"),
            ("x-ratelimit-limit-tokens", "80"),
            ("x-ratelimit-remaining-tokens", "60"),
            ("x-ratelimit-reset-tokens", "1700000000000"),
        ]
        for streaming, body, content_type in (
            (False, buffered, "application/json"),
            (True, streamed, "text/event-stream"),
        ):
            response_headers = [("Content-Type", content_type), *rate_headers]
            server = Upstream(body, content_type=content_type, response_headers=response_headers)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with RunningLocalRewrite(server.server_port) as relay:
                    request = dict(self.request_cases["defaults"]["request"])
                    request["stream"] = streaming
                    before = int(time.time())
                    status, headers, response = post_relay(relay.address, json_bytes(request))
                    after = int(time.time())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("x-deepseek-requests-limit-name"), "DeepSeek requests")
            self.assertEqual(headers.get("x-deepseek-requests-primary-used-percent"), "60")
            request_reset = int(headers["x-deepseek-requests-primary-reset-at"])
            self.assertGreaterEqual(request_reset, before + 60)
            self.assertLessEqual(request_reset, after + 60)
            self.assertEqual(headers.get("x-deepseek-tokens-limit-name"), "DeepSeek tokens")
            self.assertEqual(headers.get("x-deepseek-tokens-primary-used-percent"), "25")
            self.assertEqual(headers.get("x-deepseek-tokens-primary-reset-at"), "1700000000")
            self.assertEqual(len(server.records), 1)
            if streaming:
                self.assertIn(b"event: response.completed", response)
            else:
                self.assertEqual(json.loads(response)["output"][0]["content"][0]["text"], "limited")

    def test_connected_local_rewrite_rejects_oversized_sse_event(self):
        data = b"x" * 2_100_000
        body = b"data: " + data + b"\ndata: " + data + b"\n\n"
        self.assertGreater(len(body), 4 * 1024 * 1024)
        server = Upstream(body, chunked=True, chunk_size=65536)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, response = post_relay(
                    relay.address,
                    json_bytes({"model": "deepseek-chat", "input": "synthetic oversized event", "stream": True}),
                    timeout=20,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-type"), "text/event-stream; charset=utf-8")
        self.assertIn(b"response.failed", response)
        self.assertNotIn(b"x" * 1024, response)
        self.assertEqual(len(server.records), 1)

    def test_connect_error_is_explicit(self):
        with tempfile.TemporaryDirectory(prefix="modex-deepseek-refused-") as directory:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                address = f"127.0.0.1:{listener.getsockname()[1]}"
            root = Path(directory)
            home = root / "home"
            home.mkdir(mode=0o700)
            config = {
                "address": address, "path": "/v1/chat/completions",
                "api_key": "synthetic-provider-key",
                "request": self.request_cases["defaults"]["request"],
                "connect_timeout_ms": 100, "request_timeout_ms": 100,
                "idle_timeout_ms": 100, "max_body_bytes": 1024,
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config, separators=(",", ":")))
            result = subprocess.run(
                [str(DRIVER), str(config_path)], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=3, check=False, cwd=root,
                env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
                     "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TMPDIR": str(root)},
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        output = [json.loads(line) for line in result.stdout.decode().splitlines()]
        self.assertEqual(len(self.records(output, "error")), 1, output)
        self.assertEqual(self.records(output, "headers"), [])

    def test_upstream_disconnect_does_not_retry(self):
        output, _, _, server = self.call(drop_connection=True, stream_name=None)
        self.assertEqual(len(server.records), 1, "a failed exchange must not retry its POST")
        self.assertEqual(len(self.records(output, "error")), 1, output)
        self.assertEqual(self.records(output, "headers"), [])

    def test_cancel_fd_reaches_chat_and_native_anthropic_exchanges(self):
        native_case = {
            "request": {
                "model": "deepseek-chat",
                "input": "synthetic cancellation request",
                "stream": True,
                "tools": [{"type": "web_search_preview"}],
            },
            "web_search_mode": "anthropic",
        }
        cases = ((False, self.request_cases["defaults"]), (True, native_case))
        for native_messages, request_case in cases:
            with self.subTest(native_messages=native_messages):
                server = Upstream(hold_before_response=True)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                child_cancel, parent_cancel = socket.socketpair()
                outcome = {}
                cancelled = False

                def run_exchange():
                    try:
                        outcome["value"] = self.run_native(
                            server,
                            request_case,
                            options={
                                "native_messages": native_messages,
                                "cancel_fd": child_cancel.fileno(),
                            },
                            timeout=4,
                            pass_fds=(child_cancel.fileno(),),
                        )
                    except BaseException as error:
                        outcome["error"] = error

                probe = threading.Thread(target=run_exchange, daemon=True)
                probe.start()
                try:
                    self.assertTrue(server.request_received.wait(2), "exchange did not reach the synthetic peer")
                    parent_cancel.shutdown(socket.SHUT_WR)
                    cancelled = True
                    probe.join(3)
                    self.assertFalse(probe.is_alive(), "exchange did not observe cancellation")
                    if "error" in outcome:
                        raise outcome["error"]
                    output, _, _ = outcome["value"]
                    self.assertEqual(
                        self.records(output, "error"),
                        [{"type": "error", "message": "loopback HTTP request cancelled"}],
                    )
                    self.assertTrue(server.client_closed.wait(1), "cancellation must close the upstream socket")
                finally:
                    if not cancelled:
                        parent_cancel.shutdown(socket.SHUT_WR)
                    child_cancel.close()
                    parent_cancel.close()
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=2)
                    probe.join(timeout=2)

    def test_done_closes_stream_before_eof_and_ignores_trailing_payload(self):
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        expected = base64.b64decode(stream_case["expected_base64"], validate=True)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), stream_case["oracle_response_sha256"])
        malicious_tail = b'\xffdata: {"id":"late-malicious","choices":[]}\n\n'
        started = time.monotonic()
        output, _, _, server = self.call(
            upstream + malicious_tail, chunked=True, hold_open=True,
            chunk_size=len(upstream) + len(malicious_tail),
            options={"idle_timeout_ms": 1500}, timeout=3,
        )
        self.assertLess(time.monotonic() - started, 1.2, "DONE must not wait for response EOF")
        self.assertTrue(server.client_closed.wait(0.5), "native transport must close the socket after DONE")
        actual = b"".join(item["sse"].encode() for item in self.records(output, "event"))
        self.assertEqual(actual, expected)
        self.assertNotIn(b"late-malicious", actual)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

    def test_cancel_after_first_event_closes_once(self):
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        output, _, _, server = self.call(
            upstream, chunked=True, hold_open=True, chunk_size=9,
            options={"cancel_after_events": 1}, timeout=3,
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(len(self.records(output, "event")), 1)
        self.assertTrue(server.client_closed.wait(0.5), "cancel must close the active socket")
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": True}])

    def test_native_reader_modes_and_exchange_ownership(self):
        unit = ROOT / "build/tests/test_provider_deepseek_transport"
        self.assertTrue(unit.is_file(), f"build native lifecycle test first: {unit}")
        upstream = base64.b64decode(self.stream_cases["text_done"]["upstream_base64"], validate=True)
        successful = {
            "id": "chat-buffered-lifecycle", "created": 7,
            "choices": [{"message": {
                "content": "synthetic buffered", "tool_calls": [{
                    "id": "call-lifecycle", "function": {
                        "name": "shell", "arguments": '{"cmd":"cargo test"}',
                    },
                }],
            }}],
        }
        buffered = {
            "buffered": successful, "buffered_events": successful,
            "buffered_failed": {"id": "chat-buffered-failed", "choices": [{"message": {
                "content": "before error", "tool_calls": [{}],
            }}]},
            "buffered_blank_id": {"id": "   ", "choices": [{"message": {"content": "synthetic buffered"}}]},
        }
        for mode in ("body", "events", "cancel", "drop", "events_buffered", *buffered):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="modex-exchange-lifecycle-") as directory:
                body = json.dumps(buffered[mode], separators=(",", ":")).encode() if mode in buffered else upstream
                server = Upstream(
                    body, chunked=mode not in buffered and mode != "body", hold_open=True,
                    chunk_size=len(body), content_type="application/json" if mode in buffered else "text/event-stream",
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    result = subprocess.run(
                        [str(unit), f"127.0.0.1:{server.server_port}", mode],
                        capture_output=True, timeout=3, check=False, cwd=directory,
                        env={"HOME": directory, "TMPDIR": directory, "PATH": "/usr/bin:/bin",
                             "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                    )
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                    self.assertIn(b"PASS", result.stdout)
                    self.assertTrue(server.client_closed.wait(0.5), "native lifecycle path must close the socket")
                    self.assertEqual(len(server.records), 1)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)

    def test_clean_runtime_with_native_transport_only(self):
        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap is unavailable; clean-runtime transport not verified")
        stream_case = self.stream_cases["text_done"]
        upstream = base64.b64decode(stream_case["upstream_base64"], validate=True)
        expected = base64.b64decode(stream_case["expected_base64"], validate=True)
        output, _, _, server = self.call(
            upstream, stream_name="text_done", chunk_size=13, sandbox=True,
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(
            server.records[0]["body"].decode(),
            self.request_cases["defaults"]["upstream_request"]["body"],
        )
        actual = b"".join(item["sse"].encode() for item in self.records(output, "event"))
        self.assertEqual(actual, expected)

    def test_clean_runtime_buffered_transport_only(self):
        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap is unavailable; clean-runtime buffered transport not verified")
        case = self.buffered_cases["text_tool_usage_metadata"]
        upstream = case["upstream_response"]
        expected_request = case["upstream_request"]
        output, stdout, _, server = self.call(
            upstream["body"].encode("utf-8"),
            status=upstream["status"], content_type=upstream["content_type"],
            request_case={"request": case["request"]}, stream_name=None,
            chunk_size=13, sandbox=True,
        )
        self.assertEqual(len(server.records), 1)
        self.assertEqual(server.records[0]["body"].decode("utf-8"), expected_request["body"])
        self.buffered_response_bytes(output, stdout, case)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])


if __name__ == "__main__":
    unittest.main()
