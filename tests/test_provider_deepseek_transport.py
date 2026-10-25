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

ROOT = Path(__file__).resolve().parents[1]
REQUEST_FIXTURE = ROOT / "tests/fixtures/provider-requests/cases.json"
STREAM_FIXTURE = ROOT / "tests/fixtures/provider-stream/cases.json"
DRIVER = Path(os.environ.get(
    "MODEX_PROVIDER_DEEPSEEK_TRANSPORT_DRIVER",
    ROOT / "build/tests/provider_deepseek_transport_driver",
))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"

sys.path.insert(0, str(ROOT / "tests"))
from session_oracle import sandbox_command


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, body=b"", *, status=200, content_type="text/event-stream",
                 chunked=False, hold_open=False, drop_connection=False,
                 response_headers=None, chunk_size=11, delay=0):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.chunked = chunked
        self.hold_open = hold_open
        self.drop_connection = drop_connection
        self.response_headers = response_headers
        self.chunk_size = chunk_size
        self.delay = delay
        self.records = []
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
        for catalog in (cls.requests, cls.streams):
            if catalog["oracle_sha256"] != ORACLE_SHA256:
                raise AssertionError("fixture does not identify the pinned Prodex oracle")
            if catalog["baseline_commit"] != "433aad44bb249d5c25a231a6b06c2fa522a39a1f":
                raise AssertionError("fixture does not identify the frozen baseline commit")
        if not DRIVER.is_file():
            raise AssertionError(f"native transport driver has not been built: {DRIVER}")
        cls.request_cases = {case["name"]: case for case in cls.requests["cases"]}
        cls.stream_cases = {case["name"]: case for case in cls.streams["cases"]}

    def run_native(self, server, request_case, stream_case=None, *, options=None,
                   timeout=5, sandbox=False):
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
                cwd=root, env=environment,
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
             request_name="defaults", stream_name="text_done", options=None,
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
                server, self.request_cases[request_name],
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
        self.assertTrue(self.records(output, "headers"), output)
        errors = self.records(output, "error")
        self.assertEqual(len(errors), 1, output)
        self.assertIn("text/event-stream", errors[0]["message"])
        self.assertTrue(server.client_closed.wait(0.5), "unsupported MIME must close the socket")

    def test_unsupported_json_mime_closes_the_socket(self):
        output, _, _, server = self.call(
            b'{"synthetic":true}', content_type="application/json", hold_open=True,
        )
        self.assertEqual(len(server.records), 1)
        errors = self.records(output, "error")
        self.assertEqual(len(errors), 1, output)
        self.assertIn("text/event-stream", errors[0]["message"])
        self.assertTrue(server.client_closed.wait(0.5), "unsupported MIME must close the socket")

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

    def test_idle_timeout_emits_failure_without_retry(self):
        output, _, _, server = self.call(
            b"", chunked=True, hold_open=True, stream_name=None,
            options={"idle_timeout_ms": 100}, timeout=3,
        )
        self.assertEqual(len(server.records), 1)
        self.assertTrue(self.records(output, "headers"))
        failed = [item["sse"] for item in self.records(output, "event")]
        self.assertTrue(any("response.failed" in event for event in failed), output)
        self.assertEqual(self.records(output, "done"), [{"type": "done", "cancelled": False}])

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
        for mode in ("body", "events", "cancel", "drop"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="modex-exchange-lifecycle-") as directory:
                server = Upstream(upstream, chunked=mode != "body", hold_open=True, chunk_size=len(upstream))
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


if __name__ == "__main__":
    unittest.main()
