"""Incremental POST stream tests against synthetic local TCP peers."""

import os
import select
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get("LOOPBACK_HTTP_STREAM_DRIVER", ROOT / "build/tests/loopback_http_stream_driver"))


class LoopbackHTTPStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.exists():
            raise AssertionError(f"build test driver first: {DRIVER}")
        cls.home = tempfile.TemporaryDirectory(prefix="modex-loopback-stream-home-")
        cls.env = {
            "HOME": cls.home.name, "TMPDIR": cls.home.name,
            "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        }

    @classmethod
    def tearDownClass(cls):
        cls.home.cleanup()

    def serve(self, handler, family=socket.AF_INET):
        listener = socket.socket(family)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        host = "::1" if family == socket.AF_INET6 else "127.0.0.1"
        listener.bind((host, 0))
        listener.listen()
        listener.settimeout(0.5)
        port = listener.getsockname()[1]
        address = f"[{host}]:{port}" if family == socket.AF_INET6 else f"{host}:{port}"
        accepted, errors = [], []

        def run():
            try:
                conn, _ = listener.accept()
                accepted.append(True)
                conn.settimeout(2)
                with conn:
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        data = conn.recv(4096)
                        if not data:
                            return
                        request.extend(data)
                    head, body = bytes(request).split(b"\r\n\r\n", 1)
                    length = 0
                    for line in head.split(b"\r\n")[1:]:
                        if line.lower().startswith(b"content-length:"):
                            length = int(line.split(b":", 1)[1])
                    while len(body) < length:
                        data = conn.recv(4096)
                        if not data:
                            break
                        body += data
                    handler(conn, head + b"\r\n\r\n" + body)
            except (OSError, TimeoutError) as exc:
                errors.append(exc)
            finally:
                listener.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return address, accepted, errors, thread

    def downstream_peer(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        client = socket.create_connection(listener.getsockname(), timeout=2)
        watched, _ = listener.accept()
        listener.close()
        client.settimeout(2)
        return client, watched

    def start_watching(self, address, watched):
        return subprocess.Popen(
            [str(DRIVER), address, "/v1/chat", "payload", "watch", str(watched.fileno())],
            cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(watched.fileno(),),
        )

    def call(self, address, path="/v1/chat", body="payload", mode=None):
        args = [str(DRIVER), address, path, body]
        if mode:
            args.append(mode)
        return subprocess.run(args, cwd=ROOT, env=self.env, capture_output=True, timeout=3)

    def test_post_and_duplicate_response_headers(self):
        captured = []

        def respond(conn, request):
            captured.append(request)
            conn.sendall(b"HTTP/1.1 201 Created\r\nX-Trace: one\r\nX-Trace: two\r\nX.Foo: a\tb\r\nContent-Length: 2\r\n\r\nok")

        address, _, errors, thread = self.serve(respond)
        result = self.call(address, mode="header-compat")
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        request = captured[0]
        self.assertTrue(request.startswith(b"POST /v1/chat HTTP/1.1\r\n"))
        self.assertIn(b"Host: " + address.encode() + b"\r\n", request)
        self.assertIn(b"Connection: close\r\n", request)
        self.assertIn(b"Content-Length: 7\r\n", request)
        self.assertIn(b"X-Test: one\r\n", request)
        self.assertIn(b"X-Test: two\r\n", request)
        self.assertIn(b"X.Foo: a\tb\r\n", request)
        self.assertTrue(request.endswith(b"\r\n\r\npayload"))
        self.assertIn(b"S 201\nH X-Trace: one\nH X-Trace: two\nH X.Foo: a\tb\nH Content-Length: 2\n\nok", result.stdout)
        self.assertEqual(errors, [])

    def test_connect_errno_survives_downstream_probe(self):
        left, right = socket.socketpair()
        try:
            result = subprocess.run(
                [str(DRIVER), "127.0.0.1:1", "/", "", "connect-errno", str(left.fileno())],
                cwd=ROOT, env=self.env, capture_output=True, timeout=3,
                pass_fds=(left.fileno(),),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"CONNECT_ERRNO_PASS", result.stdout)
            left.sendall(b"owned-by-test")
            self.assertEqual(right.recv(13), b"owned-by-test")
        finally:
            left.close()
            right.close()

    def test_chunk_payload_streams_before_chunk_and_response_finish(self):
        def respond(conn, request):
            conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhe")
            time.sleep(0.12)
            conn.sendall(b"llo\r\n")
            time.sleep(0.12)
            conn.sendall(b"0\r\nX-End: yes\r\n\r\n")

        address, _, _, thread = self.serve(respond)
        process = subprocess.Popen(
            [str(DRIVER), address, "/", "payload"],
            cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            data = bytearray()
            deadline = time.monotonic() + 1
            while b"\n\n" not in data and time.monotonic() < deadline:
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if ready:
                    data.extend(os.read(process.stdout.fileno(), 4096))
            self.assertIn(b"\n\n", data)
            body = data.split(b"\n\n", 1)[1]
            if len(body) < 2:
                ready, _, _ = select.select([process.stdout], [], [], 0.08)
                self.assertTrue(ready, "partial chunk bytes waited for chunk completion")
                body += os.read(process.stdout.fileno(), 2 - len(body))
            self.assertEqual(body[:2], b"he")
            tail, _ = process.communicate(timeout=2)
            self.assertEqual(process.returncode, 0, tail)
            self.assertEqual(body + tail, b"hello")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        thread.join(2)

    def test_interim_and_fragmented_chunk_response(self):
        def respond(conn, request):
            conn.sendall(b"HTTP/1.1 100 Continue\r\n\r")
            conn.sendall(b"\nHTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhi\r\n0\r\nX-T: v\r\n\r\n")

        address, _, _, thread = self.serve(respond)
        result = self.call(address)
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"S 200\n", result.stdout)
        self.assertTrue(result.stdout.endswith(b"\n\nhi"))

    def test_ipv6_loopback(self):
        try:
            address, _, _, thread = self.serve(
                lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"),
                socket.AF_INET6,
            )
        except OSError as exc:
            self.skipTest(f"IPv6 loopback unavailable: {exc}")
        result = self.call(address, path="/")
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith(b"\n\nok"))

    def test_rejects_bad_framing(self):
        responses = (
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\nab",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhi",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhiX\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\ninvalid trailer\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx\r",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\nX-T:",
            b"HTTP/1.1 200 OK\r\nBad Header: value\r\nContent-Length: 0\r\n\r\n",
            b"HTTP/1.1 20 OK\r\nContent-Length: 0\r\n\r\n",
            b"HTTP/1.1 101 Switching Protocols\r\n\r\n",
        )
        for response in responses:
            with self.subTest(response=response[:50]):
                address, _, _, thread = self.serve(lambda conn, request, r=response: conn.sendall(r))
                result = self.call(address)
                thread.join(2)
                self.assertNotEqual(result.returncode, 0)

    def test_informational_and_line_limits(self):
        responses = (
            b"HTTP/1.1 103 Early Hints\r\n\r\n" * 9
            + b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nX-Large: " + b"x" * 65537 + b"\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1;" + b"x" * 65537 + b"\r\nx\r\n0\r\n\r\n",
        )
        for response in responses:
            with self.subTest(response=response[:50]):
                address, _, _, thread = self.serve(lambda conn, request, r=response: conn.sendall(r))
                result = self.call(address)
                thread.join(2)
                self.assertNotEqual(result.returncode, 0)

    def test_status_799_and_full_token_names_are_accepted(self):
        address, _, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 799 Private\r\nX.Foo: yes\r\nContent-Length: 0\r\n\r\n")
        )
        result = self.call(address)
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"S 799\nH X.Foo: yes", result.stdout)

    def test_close_delimited_body(self):
        address, _, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nX-Trace: eof\r\n\r\nclose-body")
        )
        result = self.call(address)
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith(b"\n\nclose-body"))

    def test_body_can_outlast_setup_deadline_while_not_idle(self):
        def respond(conn, request):
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\na")
            for part in (b"b", b"c", b"d"):
                time.sleep(0.07)
                conn.sendall(part)

        address, _, _, thread = self.serve(respond)
        result = self.call(address, mode="request-short")
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith(b"\n\nabcd"))

    def test_stream_move_preserves_socket_ownership(self):
        address, _, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        )
        result = self.call(address, path="/", mode="move")
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith(b"\n\nok"))

    def test_constructor_error_closes_socket(self):
        closed = []

        def malformed(conn, request):
            conn.sendall(b"invalid response\r\n\r\n")
            closed.append(conn.recv(1) == b"")

        address, _, _, thread = self.serve(malformed)
        result = self.call(address)
        thread.join(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(closed, [True])

    def test_chunk_decode_error_closes_socket(self):
        closed = []

        def malformed_chunk(conn, request):
            conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nnot-hex\r\n")
            closed.append(conn.recv(1) == b"")

        address, _, _, thread = self.serve(malformed_chunk)
        result = self.call(address)
        thread.join(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(closed, [True])

    def test_limit_loopback_validation_and_path_injection(self):
        address, accepted, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1048577\r\n\r\n")
        )
        result = self.call(address)
        thread.join(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(accepted)
        self.assertNotEqual(self.call("8.8.8.8:80").returncode, 0)

        address, accepted, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        )
        result = self.call(address, path="/ok\r\nX-Evil: yes")
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(accepted, [])

    def test_request_and_idle_deadlines(self):
        address, _, _, thread = self.serve(lambda conn, request: time.sleep(0.25))
        started = time.monotonic()
        result = self.call(address, mode="request-short")
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(time.monotonic() - started, 0.8)

        def slow_body(conn, request):
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\na")
            time.sleep(0.25)
            conn.sendall(b"bcd")

        address, _, _, thread = self.serve(slow_body)
        result = self.call(address, body="", mode="idle-short")
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"timed out", result.stderr)

    def test_close_and_destructor_close_peer_after_first_chunk(self):
        for mode in ("close", "drop"):
            peer_closed = []

            def respond(conn, request):
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nfirst")
                conn.settimeout(1)
                peer_closed.append(conn.recv(1) == b"")
                time.sleep(0.1)

            address, _, _, thread = self.serve(respond)
            result = self.call(address, mode=mode)
            thread.join(2)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.endswith(b"first"))
            self.assertEqual(peer_closed, [True])

    def test_downstream_reset_cancels_held_open_sse(self):
        upstream_closed = threading.Event()

        def hold_sse(conn, request):
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                b"6\r\nfirst\n\r\n"
            )
            try:
                if conn.recv(1) == b"":
                    upstream_closed.set()
            except ConnectionResetError:
                upstream_closed.set()

        address, _, errors, thread = self.serve(hold_sse)
        client, watched = self.downstream_peer()
        process = self.start_watching(address, watched)
        watched.close()
        try:
            self.assertEqual(client.recv(1), b"f")
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            client.close()
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn(b"CANCELLED downstream client disconnected", stdout)
            self.assertTrue(upstream_closed.wait(1), "reset must close the held-open upstream stream")
            thread.join(2)
            self.assertEqual(errors, [])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if client.fileno() >= 0:
                client.close()
            thread.join(2)

    def test_downstream_request_half_close_keeps_response_readable(self):
        address, _, errors, thread = self.serve(
            lambda conn, request: conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
            )
        )
        client, watched = self.downstream_peer()
        client.shutdown(socket.SHUT_WR)
        process = self.start_watching(address, watched)
        watched.close()
        try:
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertNotIn(b"CANCELLED", stdout)
            self.assertEqual(client.recv(2), b"ok")
            thread.join(2)
            self.assertEqual(errors, [])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            client.close()
            thread.join(2)

    def test_rejects_injected_and_caller_framing_headers_before_connect(self):
        address, accepted, _, thread = self.serve(
            lambda conn, request: conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        )
        for mode in (
            "header-inject", "header-value", "header-host", "header-length",
            "header-transfer", "header-connection", "header-large",
        ):
            with self.subTest(mode=mode):
                self.assertNotEqual(self.call(address, mode=mode).returncode, 0)
        thread.join(1)
        self.assertEqual(accepted, [])


if __name__ == "__main__":
    unittest.main()
