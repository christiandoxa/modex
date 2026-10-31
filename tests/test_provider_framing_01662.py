"""Pin selected provider response-framing controls to Prodex 0.166.2."""

import contextlib
import hashlib
import json
import socket
import socketserver
import threading
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
import test_provider_passthrough_01660 as historical

class RawPeer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, fixture):
        self.fixture = fixture
        self.records = []
        super().__init__(("127.0.0.1", 0), RawPeerHandler)


class RawPeerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(5)
            received = bytearray()
            while b"\r\n\r\n" not in received:
                part = self.request.recv(8192)
                if not part:
                    return
                received.extend(part)
            head, body = bytes(received).split(b"\r\n\r\n", 1)
            content_length = next(
                (int(line.split(b":", 1)[1].strip()) for line in head.split(b"\r\n")[1:]
                 if line.lower().startswith(b"content-length:")),
                0,
            )
            while len(body) < content_length:
                part = self.request.recv(8192)
                if not part:
                    break
                body += part
            self.server.records.append((head, body))
            self.request.sendall(self.server.fixture["wire"])
        except BaseException as error:
            self.server.records.append((b"fixture_error", repr(error).encode()))


@contextlib.contextmanager
def raw_serving(responses, *_args, **_kwargs):
    with RawPeer(responses[0]) as server:
        server.server_port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=2)


def decoded_response(wire):
    head, separator, body = wire.partition(b"\r\n\r\n")
    if not separator:
        raise AssertionError("captured local response has no HTTP header terminator")
    headers = {}
    for line in head.split(b"\r\n")[1:]:
        name, value = line.split(b":", 1)
        headers[name.lower()] = value.strip()
    if b"content-length" in headers:
        body = body[:int(headers[b"content-length"])]
    status = int(head.split(b" ", 2)[1])
    if headers.get(b"content-type", b"").startswith(b"application/json"):
        value = json.loads(body)
        value.pop("created_at", None)
        body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return status, body


class ProviderFraming01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_response_framing_controls_match_active_release(self):
        body = (
            b'{"id":"synthetic-raw","model":"deepseek-chat","choices":'
            b'[{"message":{"content":"synthetic"},"finish_reason":"stop"}]}'
        )
        length = str(len(body)).encode()
        chunked = f"{len(body):X}\r\n".encode() + body + b"\r\n0\r\nX-Synthetic-Trailer: ignored\r\n\r\n"
        cases = (
            (
                "close_delimited",
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Connection: close\r\n\r\n" + body,
                200,
            ),
            (
                "early_hints_before_final_response",
                b"HTTP/1.1 103 Early Hints\r\nLink: </synthetic>; rel=preload\r\n\r\n"
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + length + b"\r\n\r\n" + body,
                200,
            ),
            (
                "chunked_with_trailer",
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n" + chunked,
                200,
            ),
            (
                "truncated_fixed_length",
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(body) + 8).encode() + b"\r\n\r\n" + body,
                502,
            ),
        )
        original_serving = historical.serving
        try:
            historical.serving = raw_serving
            for name, upstream_response, expected_status in cases:
                observed = []
                for binary in (ORACLE, MODEX):
                    upstream, wire, _eof, _timed_out = historical.observe_response_wire(
                        binary, {"wire": upstream_response},
                    )
                    self.assertEqual(len(upstream), 1, name)
                    self.assertEqual(len(upstream[0][1]), int(next(
                        line.split(b":", 1)[1].strip()
                        for line in upstream[0][0].split(b"\r\n")[1:]
                        if line.lower().startswith(b"content-length:")
                    )), name)
                    observed.append(decoded_response(wire))
                with self.subTest(case=name):
                    self.assertEqual(observed[0][0], expected_status)
                    self.assertEqual(observed[1][0], expected_status)
                    self.assertEqual(observed[0], observed[1])
        finally:
            historical.serving = original_serving


if __name__ == "__main__":
    unittest.main()
