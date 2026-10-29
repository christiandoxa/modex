"""Synthetic TCP tests for Modex's native loopback HTTP listener."""

import json
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/loopback_server_driver"
DEFAULT_BODY_LIMIT = 64 * 1024 * 1024
SERVER_ENV = {}


def read_until(sock, marker):
    data = bytearray()
    while marker not in data:
        part = sock.recv(4096)
        if not part:
            break
        data.extend(part)
    return bytes(data)


def read_header_with_tail(sock):
    wire = read_until(sock, b"\r\n\r\n")
    head, separator, tail = wire.partition(b"\r\n\r\n")
    if not separator:
        raise AssertionError("HTTP response headers were truncated")
    return head + separator, tail


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise AssertionError(f"peer closed after {len(data)} of {size} bytes")
        data.extend(part)
    return bytes(data)


def start(mode):
    process = subprocess.Popen(
        [str(DRIVER), mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=SERVER_ENV["HOME"], env=SERVER_ENV,
    )
    ready = process.stdout.readline().strip()
    if not ready.startswith("READY "):
        error = process.stderr.read()
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()
        raise RuntimeError(f"server failed to start: {ready!r} {error!r}")
    address = ready[6:]
    if address.startswith("["):
        host, port = address[1:].split("]:", 1)
        family = socket.AF_INET6
    else:
        host, port = address.rsplit(":", 1)
        family = socket.AF_INET
    client = socket.socket(family, socket.SOCK_STREAM)
    client.settimeout(3)
    client.connect((host, int(port)))
    return process, client


def finish(process, client):
    response = bytearray()
    while True:
        try:
            part = client.recv(4096)
        except ConnectionResetError:
            break
        if not part:
            break
        response.extend(part)
    client.close()
    stdout = process.stdout.read()
    stderr = process.stderr.read()
    code = process.wait(timeout=4)
    process.stdout.close()
    process.stderr.close()
    if code:
        raise AssertionError(f"driver exited {code}: {stderr}\n{stdout}")
    return bytes(response), stdout


def status(response):
    head = response.split(b"\r\n", 1)[0]
    return int(head.split(b" ")[1])


def request(path="/synthetic", body=b"payload", method=b"POST"):
    return (
        method + b" " + path.encode() + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: "
        + str(len(body)).encode() + b"\r\n\r\n" + body
    )


class LoopbackHTTPServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.is_file():
            raise AssertionError(f"native driver is not built: {DRIVER}")
        cls.home = tempfile.TemporaryDirectory(prefix="modex-listener-home-")
        SERVER_ENV.update({
            "HOME": cls.home.name, "TMPDIR": cls.home.name, "PATH": "/usr/bin:/bin",
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        })

    @classmethod
    def tearDownClass(cls):
        SERVER_ENV.clear()
        cls.home.cleanup()

    def test_fixed_length_request_and_response_with_partial_body(self):
        process, client = start("echo")
        client.sendall(
            b"POST /synthetic HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 7\r\nX-Test:  a\t b \r\n\r\nabc"
        )
        time.sleep(0.02)
        client.sendall(b"defg")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        response_headers = response.split(b"\r\n\r\n", 1)[0].split(b"\r\n")
        self.assertFalse(any(line.lower().startswith((b"server:", b"date:")) for line in response_headers))
        self.assertIn(b"Connection: close\r\n", response.split(b"\r\n\r\n", 1)[0] + b"\r\n")
        self.assertTrue(response.endswith(b"abcdefg"))
        parsed = json.loads(next(line[8:] for line in stdout.splitlines() if line.startswith("REQUEST ")))
        self.assertEqual(parsed["method"], "POST")
        self.assertEqual(parsed["target"], "/synthetic")
        self.assertEqual(parsed["body_hex"], b"abcdefg".hex())
        self.assertIn(["X-Test", "a\t b"], parsed["headers"])

    def test_status_reason_phrases_match_pinned_transport_table(self):
        cases = (
            ("status-206", b"HTTP/1.1 206 Partial Content"),
            ("status-418", b"HTTP/1.1 418 Unknown"),
            ("status-422", b"HTTP/1.1 422 Unprocessable Entity"),
        )
        for mode, status_line in cases:
            with self.subTest(mode=mode):
                process, client = start(mode)
                client.sendall(request(body=b""))
                response, stdout = finish(process, client)
                self.assertTrue(response.startswith(status_line + b"\r\n"), response)
                self.assertIn("STATUS_SENT", stdout)

    def test_chunked_request_and_trailers_are_decoded(self):
        process, client = start("echo")
        client.sendall(
            b"POST /chunks HTTP/1.1\r\nHost: local\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"3\r\nfoo\r\n2;ext=yes\r\nba\r\n0\r\nX-Trace: synthetic\r\n\r\n"
        )
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        parsed = json.loads(next(line[8:] for line in stdout.splitlines() if line.startswith("REQUEST ")))
        self.assertEqual(parsed["body_hex"], b"fooba".hex())

    def test_expect_continue_is_answered_before_body_read(self):
        process, client = start("echo")
        client.sendall(
            b"POST /expect HTTP/1.1\r\nHost: local\r\nContent-Length: 4\r\nExpect: 100-continue\r\n\r\n"
        )
        self.assertEqual(read_until(client, b"\r\n\r\n"), b"HTTP/1.1 100 Continue\r\n\r\n")
        client.sendall(b"body")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        self.assertIn('"body_hex":"626f6479"', stdout)

    def test_default_parser_response_stays_http_1_1_for_http_1_0_request(self):
        process, client = start("echo")
        client.sendall(b"GET /version HTTP/1.0\r\n\r\n")
        response, stdout = finish(process, client)
        self.assertTrue(response.startswith(b"HTTP/1.1 200 OK\r\n"), response)
        self.assertIn('"target":"/version"', stdout)

    def test_default_parser_keeps_http_1_1_interim_for_http_1_0_request(self):
        process, client = start("echo")
        client.sendall(
            b"POST /expect HTTP/1.0\r\nContent-Length: 0\r\n"
            b"Expect: 100-continue\r\n\r\n"
        )
        response, _ = finish(process, client)
        self.assertTrue(response.startswith(b"HTTP/1.1 100 Continue\r\n\r\n"), response)

    def test_default_parser_still_sends_continue_before_body_limit_rejection(self):
        process, client = start("small-limit")
        client.sendall(
            b"POST /expect-large HTTP/1.1\r\nHost: local\r\nContent-Length: 4\r\n"
            b"Expect: 100-continue\r\n\r\n"
        )
        response, stdout = finish(process, client)
        self.assertTrue(response.startswith(b"HTTP/1.1 100 Continue\r\n\r\n"), response)
        self.assertIn(b"HTTP/1.1 413 Payload Too Large\r\n", response)
        self.assertIn("oversized HTTP request body", stdout)

    def test_ambiguous_duplicate_and_malformed_headers_are_rejected(self):
        samples = [
            b"POST / HTTP/1.1\r\nHost: local\r\nContent-Length: 0\r\nTransfer-Encoding: chunked\r\n\r\n",
            b"POST / HTTP/1.1\r\nHost: local\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",
            b"POST / HTTP/1.1\r\nHost: local\r\nExpect: 100-continue\r\nExpect: 100-continue\r\nContent-Length: 0\r\n\r\n",
            b"POST / HTTP/1.1\r\nHost: local\r\nExpect: 100-continue\x00bad\r\nContent-Length: 0\r\n\r\n",
            b"POST /fragment#x HTTP/1.1\r\nHost: local\r\nContent-Length: 0\r\n\r\n",
            b"POST / HTTP/1.1\r\nHost: local\r\nBad Header: x\r\nContent-Length: 0\r\n\r\n",
        ]
        for wire in samples:
            with self.subTest(wire=wire):
                process, client = start("echo")
                client.sendall(wire)
                response, stdout = finish(process, client)
                self.assertEqual(status(response), 400)
                self.assertIn("REJECT ", stdout)

    def test_tiny_http_header_whitespace_is_opt_in(self):
        raw = (
            b"POST / HTTP/1.1\r\nHost: local\r\n"
            b"\x0bX-Trim: \x0cvalue\x0b\x0c\r\nContent-Length: 0\r\n\r\n"
        )
        process, client = start("tiny-http-compat")
        client.sendall(raw)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        request_line = next(line for line in stdout.splitlines() if line.startswith("REQUEST "))
        self.assertIn(["X-Trim", "value"], json.loads(request_line.removeprefix("REQUEST "))["headers"])

        process, client = start("echo")
        client.sendall(raw)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("malformed HTTP header value", stdout)

    def test_tiny_http_compat_collapses_only_identical_content_lengths(self):
        raw = (
            b"POST / HTTP/1.1\r\nHost: local\r\n"
            b"Content-Length: 0\r\ncontent-length: 0\r\n\r\n"
        )
        process, client = start("tiny-http-compat")
        client.sendall(raw)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        request_line = next(line for line in stdout.splitlines() if line.startswith("REQUEST "))
        headers = json.loads(request_line.removeprefix("REQUEST "))["headers"]
        self.assertEqual([header for header in headers if header[0].lower() == "content-length"], [["Content-Length", "0"]])

        for mode, framing in (
            ("tiny-http-compat", b"Content-Length: 0\r\nContent-Length: 1\r\n"),
            ("echo", b"Content-Length: 0\r\nContent-Length: 0\r\n"),
        ):
            with self.subTest(mode=mode, framing=framing):
                process, client = start(mode)
                client.sendall(b"POST / HTTP/1.1\r\nHost: local\r\n" + framing + b"\r\n")
                response, stdout = finish(process, client)
                self.assertEqual(status(response), 400)
                self.assertIn("duplicate HTTP content length", stdout)

    def test_default_loopback_parser_keeps_upgrade_headers_rejected(self):
        process, client = start("echo")
        client.sendall(
            b"GET / HTTP/1.1\r\nHost: local\r\nUpgrade: websocket\r\n\r\n"
        )
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("HTTP protocol upgrades are unsupported", stdout)

        process, client = start("upgrade-allowed")
        client.sendall(
            b"GET / HTTP/1.1\r\nHost: local\r\nConnection: Upgrade\r\nUpgrade: h2c\r\n\r\n"
        )
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("HTTP protocol upgrades are unsupported", stdout)

    def test_upgraded_capture_retains_body_limit_and_timeout(self):
        head = b"POST / HTTP/1.1\r\nHost: local\r\nConnection: Upgrade\r\nContent-Length: 0\r\n\r\n"
        process, client = start("upgrade-small")
        client.sendall(head + b"abc")
        client.settimeout(0.1)
        with self.assertRaises(TimeoutError):
            client.recv(1)
        client.settimeout(3)
        client.shutdown(socket.SHUT_WR)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        self.assertIn('"body_hex":"616263"', stdout)

        process, client = start("upgrade-small")
        client.sendall(head + b"abcd")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 413)
        self.assertIn("oversized HTTP request body", stdout)

        process, client = start("upgrade-timeout")
        client.sendall(head + b"abc")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("loopback HTTP request timed out", stdout)

    def test_default_request_line_limit_stays_at_8192_bytes(self):
        for line_size, expected_status in ((8192, 200), (8193, 400)):
            with self.subTest(line_size=line_size):
                target = b"/" + b"a" * (line_size - len(b"GET / HTTP/1.1"))
                request_line = b"GET " + target + b" HTTP/1.1"
                self.assertEqual(len(request_line), line_size)
                process, client = start("echo")
                client.sendall(request_line + b"\r\nHost: local\r\n\r\n")
                response, stdout = finish(process, client)
                self.assertEqual(status(response), expected_status)
                if line_size == 8193:
                    self.assertIn("malformed HTTP request line", stdout)

    def test_shared_request_head_limit_stays_at_65536_bytes(self):
        template = b"GET / HTTP/1.1\r\nHost: local\r\nX-Pad: \r\nContent-Length: 0\r\n\r\n"
        prefix, suffix = template.split(b"X-Pad: ", 1)[0], template.split(b"X-Pad: ", 1)[1].split(b"\r\n", 1)[1]
        for head_size, expected_status in ((65536, 200), (65537, 400)):
            with self.subTest(head_size=head_size):
                value_size = head_size - template.index(b"\r\n\r\n")
                wire = prefix + b"X-Pad: " + b"x" * value_size + b"\r\n" + suffix
                self.assertEqual(wire.index(b"\r\n\r\n"), head_size)
                process, client = start("echo")
                stdout = []
                output_reader = threading.Thread(
                    target=lambda: stdout.append(process.stdout.read()), daemon=True
                )
                output_reader.start()
                client.sendall(wire)
                response = bytearray()
                while True:
                    try:
                        part = client.recv(4096)
                    except ConnectionResetError:
                        break
                    if not part:
                        break
                    response.extend(part)
                client.close()
                output_reader.join(timeout=4)
                self.assertFalse(output_reader.is_alive())
                stderr = process.stderr.read()
                code = process.wait(timeout=4)
                process.stdout.close()
                process.stderr.close()
                self.assertEqual(code, 0, f"{stderr}\n{stdout[0]}")
                stdout = stdout[0]
                self.assertEqual(status(response), expected_status)
                self.assertIn("REQUEST " if expected_status == 200 else "HTTP request headers exceed limit", stdout)

    def test_oversized_and_truncated_bodies_are_rejected(self):
        process, client = start("echo")
        client.sendall(
            b"POST /large HTTP/1.1\r\nHost: local\r\nContent-Length: "
            + str(DEFAULT_BODY_LIMIT + 1).encode()
            + b"\r\n\r\n"
        )
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 413)
        self.assertIn("oversized HTTP request body", stdout)

        process, client = start("echo")
        client.sendall(
            b"POST /exact-limit HTTP/1.1\r\nHost: local\r\nContent-Length: "
            + str(DEFAULT_BODY_LIMIT).encode()
            + b"\r\n\r\n"
        )
        client.shutdown(socket.SHUT_WR)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("truncated HTTP request", stdout)

        process, client = start("echo")
        client.sendall(b"POST /short HTTP/1.1\r\nHost: local\r\nContent-Length: 8\r\n\r\nabc")
        client.shutdown(socket.SHUT_WR)
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("truncated HTTP request", stdout)

    def test_http_0_9_requires_explicit_opt_in(self):
        process, client = start("echo")
        client.sendall(b"POST /synthetic HTTP/0.9\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\n\r\n")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn('"unsupported HTTP request version"', stdout)

    def test_small_caller_body_limit_accepts_exact_and_rejects_over(self):
        process, client = start("small-limit")
        client.sendall(request(body=b"abc"))
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 200)
        self.assertTrue(response.endswith(b"abc"))
        self.assertIn('"body_hex":"616263"', stdout)

        process, client = start("small-limit")
        client.sendall(request(body=b"abcd"))
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 413)
        self.assertIn("oversized HTTP request body", stdout)

    def test_read_timeout_and_idle_accept_timeout(self):
        process = subprocess.Popen(
            [str(DRIVER), "idle"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=SERVER_ENV["HOME"], env=SERVER_ENV,
        )
        self.assertTrue(process.stdout.readline().startswith("READY "))
        self.assertEqual(process.stdout.readline().strip(), "IDLE true")
        self.assertEqual(process.wait(timeout=2), 0)
        process.stdout.close()
        process.stderr.close()

        process, client = start("timeout")
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 400)
        self.assertIn("loopback HTTP request timed out", stdout)

    def test_response_rejects_header_injection_and_caller_framing(self):
        for mode in (
            "bad-response", "bad-default-response", "large-default-response-header",
            "framing-response",
        ):
            with self.subTest(mode=mode):
                process, client = start(mode)
                client.sendall(request(body=b""))
                response, stdout = finish(process, client)
                self.assertEqual(response, b"")
                self.assertIn("RESPONSE_REJECTED ", stdout)

    def test_bodyless_sse_header_and_empty_chunk_terminator(self):
        for response_status in (204, 304):
            with self.subTest(status=response_status):
                process, client = start(f"bodyless-sse-{response_status}")
                client.sendall(request(body=b""))
                response, stdout = finish(process, client)
                headers, separator, payload = response.partition(b"\r\n\r\n")
                self.assertEqual(separator, b"\r\n\r\n")
                self.assertEqual(status(response), response_status)
                self.assertIn(b"Transfer-Encoding: chunked\r\n", headers + b"\r\n")
                self.assertNotIn(b"Content-Length:", headers)
                self.assertEqual(payload, b"0\r\n\r\n")
                self.assertIn("BODYLESS_SENT", stdout)

    def test_head_buffered_reply_suppresses_body_but_keeps_representation_length(self):
        process, client = start("head-buffered")
        client.sendall(request(body=b"", method=b"HEAD"))
        response, stdout = finish(process, client)
        headers, separator, payload = response.partition(b"\r\n\r\n")
        self.assertEqual(separator, b"\r\n\r\n")
        self.assertEqual(status(response), 200)
        self.assertIn(b"Content-Length: 14\r\n", headers + b"\r\n")
        self.assertEqual(payload, b"")
        self.assertIn("HEAD_BUFFERED_SENT", stdout)

    def test_head_stream_suppresses_chunks_and_chunk_terminator(self):
        process, client = start("head-stream")
        client.sendall(request(body=b"", method=b"HEAD"))
        response, stdout = finish(process, client)
        headers, separator, payload = response.partition(b"\r\n\r\n")
        self.assertEqual(separator, b"\r\n\r\n")
        self.assertEqual(status(response), 200)
        self.assertIn(b"Transfer-Encoding: chunked\r\n", headers + b"\r\n")
        self.assertEqual(payload, b"")
        self.assertIn("HEAD_STREAM_DONE", stdout)

    def test_head_stream_can_write_only_the_terminal_chunk(self):
        process, client = start("head-stream-terminal")
        client.sendall(request(body=b"", method=b"HEAD"))
        response, stdout = finish(process, client)
        headers, separator, payload = response.partition(b"\r\n\r\n")
        self.assertEqual(separator, b"\r\n\r\n")
        self.assertEqual(status(response), 200)
        self.assertIn(b"Transfer-Encoding: chunked\r\n", headers + b"\r\n")
        self.assertEqual(payload, b"0\r\n\r\n")
        self.assertIn("HEAD_STREAM_DONE", stdout)

    def test_head_bodyless_chunked_reply_has_terminator(self):
        for response_status in (204, 304):
            with self.subTest(status=response_status):
                process, client = start(f"bodyless-sse-{response_status}")
                client.sendall(request(body=b"", method=b"HEAD"))
                response, stdout = finish(process, client)
                headers, separator, payload = response.partition(b"\r\n\r\n")
                self.assertEqual(separator, b"\r\n\r\n")
                self.assertEqual(status(response), response_status)
                self.assertIn(b"Transfer-Encoding: chunked\r\n", headers + b"\r\n")
                self.assertNotIn(b"Content-Length:", headers)
                self.assertEqual(payload, b"0\r\n\r\n")
                self.assertIn("BODYLESS_SENT", stdout)

    def test_head_stream_cancellation_is_still_detected(self):
        process, client = start("head-stream-cancel")
        client.sendall(request(body=b"", method=b"HEAD"))
        header, prefetched = read_header_with_tail(client)
        self.assertIn(b"Transfer-Encoding: chunked\r\n", header)
        self.assertEqual(prefetched, b"")
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        client.close()
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        self.assertEqual(process.wait(timeout=4), 0, stderr + stdout)
        self.assertIn("DISCONNECTED true", stdout)
        self.assertIn("WRITE_FAILED", stdout)
        process.stdout.close()
        process.stderr.close()

    def test_header_reader_keeps_coalesced_first_chunk(self):
        sender, client = socket.socketpair()
        try:
            first = b"6\r\nfirst\n\r\n"
            sender.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + first)
            head, prefetched = read_header_with_tail(client)
            self.assertIn(b"Transfer-Encoding: chunked", head)
            self.assertEqual(prefetched, first)
        finally:
            sender.close()
            client.close()

    def test_chunked_stream_delivers_first_chunk_before_finish(self):
        process, client = start("stream")
        client.sendall(request(body=b""))
        header, prefetched = read_header_with_tail(client)
        self.assertIn(b"Transfer-Encoding: chunked\r\n", header)
        expected_first = b"A\r\nfirst\nxxxx\r\n"
        self.assertLessEqual(len(prefetched), len(expected_first))
        first = prefetched + read_exact(client, len(expected_first) - len(prefetched))
        self.assertEqual(first, expected_first)
        client.settimeout(0.08)
        with self.assertRaises(socket.timeout):
            client.recv(1)
        client.settimeout(3)
        rest = bytearray()
        while not rest.endswith(b"0\r\n\r\n"):
            part = client.recv(4096)
            if not part:
                break
            rest.extend(part)
        client.close()
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        self.assertEqual(process.wait(timeout=4), 0, stderr + stdout)
        self.assertEqual(bytes(rest), b"7\r\nsecond\n\r\n0\r\n\r\n")
        self.assertIn("STREAM_DONE", stdout)
        process.stdout.close()
        process.stderr.close()

    def test_peer_reset_is_detected_and_connection_move_keeps_ownership(self):
        process, client = start("cancel")
        client.sendall(request(body=b""))
        header, prefetched = read_header_with_tail(client)
        self.assertIn(b"Transfer-Encoding: chunked", header)
        expected_first = b"6\r\nfirst\n\r\n"
        self.assertLessEqual(len(prefetched), len(expected_first))
        self.assertEqual(prefetched + read_exact(client, len(expected_first) - len(prefetched)), expected_first)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        client.close()
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        self.assertEqual(process.wait(timeout=4), 0, stderr + stdout)
        self.assertIn("DISCONNECTED true", stdout)
        self.assertIn("WRITE_FAILED", stdout)
        process.stdout.close()
        process.stderr.close()

        process, client = start("move")
        client.sendall(request(body=b"moved"))
        response, stdout = finish(process, client)
        self.assertEqual(status(response), 202)
        self.assertTrue(response.endswith(b"moved"))
        self.assertIn("RESPONDED", stdout)

        process, client = start("close")
        response, stdout = finish(process, client)
        self.assertEqual(response, b"")
        self.assertIn("CLOSED", stdout)

    def test_ipv6_loopback_listener_when_available(self):
        try:
            process, client = start("ipv6")
        except (OSError, RuntimeError) as error:
            self.skipTest(f"IPv6 loopback is unavailable: {error}")
        client.sendall(request(body=b"v6"))
        response, _ = finish(process, client)
        self.assertEqual(status(response), 200)
        self.assertTrue(response.endswith(b"v6"))


if __name__ == "__main__":
    unittest.main()
