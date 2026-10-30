"""Native loopback HTTP client tests against a local raw TCP server."""

import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get("LOOPBACK_HTTP_DRIVER", ROOT / "build/tests/loopback_http_driver"))


class LoopbackHTTPTests(unittest.TestCase):
    def setUp(self):
        if not DRIVER.exists():
            self.fail(f"loopback HTTP driver missing: {DRIVER}")

    def serve(self, response, family=socket.AF_INET, delay=0, keep_open=0):
        listener = socket.socket(family, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        host = "::1" if family == socket.AF_INET6 else "127.0.0.1"
        listener.bind((host, 0))
        listener.listen()
        listener.settimeout(3)
        port = listener.getsockname()[1]
        observed = []
        accepted = []
        self._last_accepted = accepted

        def run():
            try:
                conn, _ = listener.accept()
                accepted.append(True)
                conn.settimeout(2.5)
                with conn:
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        data = conn.recv(4096)
                        if not data:
                            return
                        request.extend(data)
                    observed.append(bytes(request))
                    if delay:
                        time.sleep(delay)
                    if response:
                        try:
                            conn.sendall(response)
                        except OSError:
                            pass
                    if keep_open:
                        time.sleep(keep_open)
            except socket.timeout:
                pass
            finally:
                listener.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return f"[{host}]:{port}" if family == socket.AF_INET6 else f"{host}:{port}", observed, thread

    def call(self, address, path="/logs?after=5", name="X-Admin", value="secret"):
        with tempfile.TemporaryDirectory(prefix="modex-http-client-") as directory:
            return subprocess.run(
                [str(DRIVER), address, path, name, value],
                cwd=directory,
                env={"HOME": directory, "TMPDIR": directory, "PATH": "/usr/bin:/bin",
                     "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                capture_output=True,
                timeout=3,
            )

    def test_content_length_and_sensitive_header_request(self):
        address, observed, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"
        )
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nhello")
        self.assertIn(b"GET /logs?after=5 HTTP/1.1\r\n", observed[0])
        self.assertIn(b"X-Admin: secret\r\n", observed[0])
        self.assertIn(b"Connection: close\r\n", observed[0])
        self.assertIn(b"Host: " + address.encode() + b"\r\n", observed[0])

    def test_equal_comma_and_repeated_content_lengths(self):
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2, \t2\r\nContent-Length: 2\r\n\r\nok"
        )
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")

    def test_chunked_with_extension_and_trailer(self):
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2;kind=x\r\nhi\r\n3\r\n!!!\r\n0\r\nX-Trace: yes\r\n\r\n"
        )
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nhi!!!")

    def test_close_delimited_body_and_non_success_status(self):
        address, _, thread = self.serve(b"HTTP/1.0 503 Busy\r\nX-Test: yes\r\n\r\nretry")
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"503\nretry")

    def test_ipv6_loopback(self):
        try:
            address, _, thread = self.serve(
                b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok",
                socket.AF_INET6,
            )
        except OSError as exc:
            self.skipTest(f"IPv6 loopback unavailable: {exc}")
        result = self.call(address, "/")
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")

    def test_ipv4_shorthand_normalizes_to_numeric_loopback(self):
        address, observed, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        )
        _, port = address.rsplit(":", 1)
        shorthand = f"127.1:{int(port):08d}"
        result = self.call(shorthand)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")
        self.assertIn(b"Host: " + address.encode() + b"\r\n", observed[0])

    def test_rejects_malformed_numeric_and_hostname_authorities(self):
        for address in (
            "127.0.0.08:1", "127..1:1", "127.1.2.3.4:1", "127.1.example:1",
            "localhost:1", "0x:1", "0x100000000:1", "126.0.0.1:1",
            "128.0.0.1:1", "8.8.8.8:1", "0x08080808:1", "167772161:1",
        ):
            with self.subTest(address=address):
                result = self.call(address)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(
                    b"invalid loopback HTTP address" in result.stderr
                    or b"not loopback" in result.stderr,
                    result.stderr,
                )
                self.assertNotIn(b"connect failed", result.stderr)

    def test_rejects_nonloopback_and_header_injection(self):
        nonloopback = self.call("127.0.0.1:1", value="x\r\nInjected: yes")
        self.assertNotEqual(nonloopback.returncode, 0)
        self.assertIn(b"invalid HTTP header value", nonloopback.stderr)
        refused = self.call("8.8.8.8:80")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(b"not loopback", refused.stderr)

    def test_body_limit_and_connect_refusal(self):
        payload = b"x" * (4 * 1024 * 1024 + 1)
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: "
            + str(len(payload)).encode()
            + b"\r\n\r\n"
            + payload
        )
        oversized = self.call(address)
        thread.join(1)
        self.assertNotEqual(oversized.returncode, 0)
        self.assertIn(b"oversized", oversized.stderr)

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        unused_port = listener.getsockname()[1]
        listener.close()
        refused = self.call(f"127.0.0.1:{unused_port}")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(b"connect failed", refused.stderr)


    def test_truncated_conflicting_and_ambiguous_content_length(self):
        responses = [
            b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhi",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\nab",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2, 3\r\n\r\nab",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2,\r\n\r\nab",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2x, 2\r\n\r\nab",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
        ]
        for response in responses:
            with self.subTest(response=response[:60]):
                address, _, thread = self.serve(response)
                result = self.call(address)
                thread.join(1)
                self.assertNotEqual(result.returncode, 0)

    def test_malformed_chunks_and_trailers(self):
        responses = [
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhiX\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\nBad Trailer\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: xchunked\r\n\r\n0\r\n\r\n",
        ]
        for response in responses:
            with self.subTest(response=response[:60]):
                address, _, thread = self.serve(response)
                result = self.call(address)
                thread.join(1)
                self.assertNotEqual(result.returncode, 0)


    def test_header_controls_rejected_before_ows_trim(self):
        for raw_value in (b"\x0b2", b"\x0c2", b"2\x0b", b"2\x0c", b"\r2", b"2\r"):
            with self.subTest(raw_value=raw_value):
                address, _, thread = self.serve(
                    b"HTTP/1.1 200 OK\r\nContent-Length: " + raw_value + b"\r\n\r\nxx"
                )
                result = self.call(address)
                thread.join(1)
                self.assertNotEqual(result.returncode, 0)

        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: \t2 \t\r\n\r\nhi"
        )
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nhi")

    def test_chunk_extension_and_total_trailer_limits(self):
        extension = b";" + b"x" * (65537 - 1)
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            + b"1" + extension + b"\r\nx\r\n0\r\n\r\n"
        )
        result = self.call(address)
        thread.join(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"chunk-size line", result.stderr)

        trailers = b"X-Trace: 1234567890\r\n" * 4000
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n"
            + trailers
            + b"\r\n"
        )
        result = self.call(address)
        thread.join(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"trailers exceed limit", result.stderr)

    def test_keepalive_content_length_and_informational_response(self):
        address, _, thread = self.serve(
            b"HTTP/1.1 100 Continue\r\nX-Info: yes\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok",
            delay=0.2,
            keep_open=1.5,
        )
        result = self.call(address)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")

    def test_absolute_deadline_with_slow_drip(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        address = f"127.0.0.1:{listener.getsockname()[1]}"

        def run():
            try:
                conn, _ = listener.accept()
                with conn:
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        data = conn.recv(4096)
                        if not data:
                            return
                        request.extend(data)
                    for part in (
                        b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n",
                        b"a",
                        b"b",
                        b"c",
                        b"d",
                    ):
                        conn.sendall(part)
                        time.sleep(0.32)
            finally:
                listener.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        started = time.monotonic()
        result = self.call(address)
        elapsed = time.monotonic() - started
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"timed out", result.stderr)
        self.assertLess(elapsed, 1.4)
        thread.join(2)

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        address = f"127.0.0.1:{listener.getsockname()[1]}"

        def slow_headers():
            try:
                conn, _ = listener.accept()
                with conn:
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        data = conn.recv(4096)
                        if not data:
                            return
                        request.extend(data)
                    for part in (b"HTTP/1.1 200 OK\r\n", b"Content-Length: 0\r\n", b"\r\n"):
                        conn.sendall(part)
                        time.sleep(0.6)
            finally:
                listener.close()

        thread = threading.Thread(target=slow_headers, daemon=True)
        thread.start()
        started = time.monotonic()
        slow = self.call(address)
        elapsed = time.monotonic() - started
        self.assertNotEqual(slow.returncode, 0)
        self.assertIn(b"timed out", slow.stderr)
        self.assertLess(elapsed, 1.4)
        thread.join(2)


    def test_multiple_informational_responses_fragmented_and_coalesced(self):
        address, _, thread = self.serve(
            b"HTTP/1.1 100 Continue\r\n\r\n"
            b"HTTP/1.1 103 Early Hints\r\nLink: </x>; rel=preload\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok",
            delay=0.1,
            keep_open=1.2,
        )
        result = self.call(address)
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")

    def test_informational_response_bounds_and_upgrade_rejection(self):
        many = b"HTTP/1.1 103 Hints\r\n\r\n" * 9 + b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        address, _, thread = self.serve(many)
        result = self.call(address)
        thread.join(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"informational", result.stderr)

        oversized = b"HTTP/1.1 103 Hints\r\nX: " + b"x" * 70000 + b"\r\n\r\n"
        address, _, thread = self.serve(oversized)
        result = self.call(address)
        thread.join(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"headers exceed limit", result.stderr)

        address, _, thread = self.serve(b"HTTP/1.1 101 Switching Protocols\r\n\r\n")
        result = self.call(address)
        thread.join(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"upgrade is unsupported", result.stderr)

    def test_exact_body_cap_and_many_small_chunks(self):
        exact = b"x" * (4 * 1024 * 1024)
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nContent-Length: "
            + str(len(exact)).encode()
            + b"\r\n\r\n"
            + exact
        )
        result = self.call(address)
        thread.join(3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout), len(exact) + 4)

        full_chunk = 65535
        chunked_exact = b"".join(
            f"{full_chunk:x}\r\n".encode() + b"x" * full_chunk + b"\r\n"
            for _ in range((len(exact) + full_chunk - 1) // full_chunk)
        )
        final_size = len(exact) % full_chunk
        if final_size:
            chunked_exact = chunked_exact[: -(full_chunk + len(f"{full_chunk:x}".encode()) + 4)]
            chunked_exact += f"{final_size:x}\r\n".encode() + b"x" * final_size + b"\r\n"
        chunked_exact += b"0\r\n\r\n"
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunked_exact
        )
        result = self.call(address)
        thread.join(3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout), len(exact) + 4)

        chunks = b"1\r\nx\r\n" * 5000 + b"0\r\n\r\n"
        address, _, thread = self.serve(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks
        )
        result = self.call(address)
        thread.join(3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\n" + b"x" * 5000)


    def test_malformed_header_fails_before_peer_close(self):
        address, _, thread = self.serve(b"HTTP/1.1 200 OK\r\nBad Header: yes\r\n\r\n", keep_open=1.5)
        started = time.monotonic()
        result = self.call(address)
        elapsed = time.monotonic() - started
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(elapsed, 1.0)
        thread.join(3)


    def test_zero_body_and_no_body_status(self):
        address, _, thread = self.serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n", keep_open=1.5)
        result = subprocess.run(
            [str(DRIVER), address, "/", "X-Admin", "secret", "zero"],
            capture_output=True,
            timeout=3,
        )
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\n")

        address, _, thread = self.serve(b"HTTP/1.1 204 No Content\r\n\r\n", keep_open=1.5)
        result = self.call(address, "/")
        thread.join(2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"204\n")

    def test_unsafe_body_cap_rejected_before_socket(self):
        address, _, thread = self.serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        result = subprocess.run(
            [str(DRIVER), address, "/", "X-Admin", "secret", "overflow"],
            capture_output=True,
            timeout=3,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"unsupported HTTP body limit", result.stderr)
        self.assertEqual(self._last_accepted, [])
        thread.join(3)

    def test_descriptors_close_on_repeated_success_and_error(self):
        import resource

        def repeated_server(response):
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(3)
            address = f"127.0.0.1:{listener.getsockname()[1]}"

            def run():
                try:
                    for _ in range(100):
                        conn, _ = listener.accept()
                        with conn:
                            conn.settimeout(1)
                            request = bytearray()
                            while b"\r\n\r\n" not in request:
                                data = conn.recv(4096)
                                if not data:
                                    break
                                request.extend(data)
                            if response:
                                conn.sendall(response)
                except (OSError, socket.timeout):
                    pass
                finally:
                    listener.close()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            return address, thread

        def limit_fds():
            resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))

        address, thread = repeated_server(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        ok = subprocess.run(
            [str(DRIVER), address, "/", "X-Admin", "secret", "zero", "repeat"],
            capture_output=True,
            timeout=10,
            preexec_fn=limit_fds,
        )
        thread.join(4)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.count(b"200\n"), 100)

        address, thread = repeated_server(b"bad response\r\n\r\n")
        failed = subprocess.run(
            [str(DRIVER), address, "/", "X-Admin", "secret", "zero", "repeat"],
            capture_output=True,
            timeout=10,
            preexec_fn=limit_fds,
        )
        thread.join(4)
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(failed.stdout.count(b"ERROR\n"), 100)

    def test_clean_filesystem_runtime_with_shared_network(self):
        import shutil
        import sys
        import tempfile

        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap is required")
        sys.path.insert(0, str(ROOT / "tests"))
        from session_oracle import sandbox_command

        address, _, thread = self.serve(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        with tempfile.TemporaryDirectory(prefix="modex-loopback-http-") as directory:
            root = Path(directory)
            (root / "home").mkdir()
            (root / "workspace").mkdir()
            command = sandbox_command(
                DRIVER,
                root,
                [address, "/", "X-Admin", "secret"],
                environment={"NO_PROXY": "", "no_proxy": ""},
            )
            command.insert(2, "--share-net")
            result = subprocess.run(command, capture_output=True, timeout=5)
        thread.join(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"200\nok")

    def test_request_injection_rejected_before_connect(self):
        address, observed, thread = self.serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        result = self.call(address, path="/ok\r\nInjected: yes")
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(observed, [])
        self.assertEqual(self._last_accepted, [])
        thread.join(3)

        address, observed, thread = self.serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        result = self.call(address, value="secret\r\nInjected: yes")
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(observed, [])
        self.assertEqual(self._last_accepted, [])
        thread.join(3)

    def test_peer_close_during_send_does_not_signal_process(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        address = f"127.0.0.1:{listener.getsockname()[1]}"

        def run():
            conn, _ = listener.accept()
            conn.close()
            listener.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        result = self.call(address, path="/" + "x" * 60000)
        thread.join(1)
        self.assertNotEqual(result.returncode, -13)  # SIGPIPE

    def test_header_limit(self):
        response = b"HTTP/1.1 200 OK\r\nX-Large: " + b"x" * 70000 + b"\r\nContent-Length: 0\r\n\r\n"
        address, _, thread = self.serve(response)
        result = self.call(address)
        thread.join(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"headers exceed limit", result.stderr)

    def test_malformed_response_and_timeout(self):
        address, _, thread = self.serve(b"not an HTTP response")
        malformed = self.call(address)
        thread.join(1)
        self.assertNotEqual(malformed.returncode, 0)

        address, _, thread = self.serve(b"", delay=1.5)
        started = time.monotonic()
        timed_out = self.call(address)
        elapsed = time.monotonic() - started
        self.assertNotEqual(timed_out.returncode, 0)
        self.assertIn(b"timed out", timed_out.stderr)
        self.assertLess(elapsed, 1.4)
        thread.join(2)


if __name__ == "__main__":
    unittest.main()
