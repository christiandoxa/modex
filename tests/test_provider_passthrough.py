"""Synthetic loopback checks for the native passthrough driver."""
import os
from pathlib import Path
import select
import socket
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/provider_passthrough_driver"


def check(payload, status=200, chunked=False, fragmented=False, truncated=False):
    errors = []
    with socket.socket() as listener, tempfile.TemporaryDirectory(prefix="modex-passthrough-") as home:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)
        address = "%s:%d" % listener.getsockname()

        def serve():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(10)
                    wire = b""
                    while b"\r\n\r\n" not in wire:
                        wire += peer.recv(8192)
                    head, body = wire.split(b"\r\n\r\n", 1)
                    lines = head.split(b"\r\n")
                    assert lines[0] == b"POST /chat/completions?raw=%2B&raw=2 HTTP/1.1"
                    headers = {}
                    for line in lines[1:]:
                        name, value = line.split(b":", 1)
                        headers.setdefault(name.lower(), []).append(value.strip())
                    assert headers[b"authorization"] == [b"Bearer fake-upstream"]
                    assert headers[b"content-type"] == [b"application/json", b"application/custom+json"]
                    assert headers[b"accept-encoding"] == [b"identity"]
                    assert headers[b"accept"] == [b"text/event-stream, application/json"]
                    assert b"connection" not in headers
                    assert b"x-private" not in headers
                    while len(body) < int(headers[b"content-length"][0]):
                        body += peer.recv(8192)
                    assert body == bytes([0, 255, 10, 123, 125])
                    framing = b"Transfer-Encoding: chunked" if chunked else b"Content-Length: " + str(len(payload) + int(truncated)).encode()
                    response_head = b"HTTP/1.1 " + str(status).encode() + b" Synthetic\r\nContent-Type: text/event-stream\r\n" + framing + b"\r\n\r\n"
                    if fragmented:
                        for byte in response_head:
                            peer.sendall(bytes([byte]))
                    else:
                        peer.sendall(response_head)
                    if chunked:
                        for start in range(0, len(payload), 65537):
                            part = payload[start:start + 65537]
                            peer.sendall(("%x\r\n" % len(part)).encode() + part + b"\r\n")
                        peer.sendall(b"0\r\nX-Trailer: ignored\r\n\r\n")
                    elif fragmented:
                        for byte in payload:
                            peer.sendall(bytes([byte]))
                    else:
                        peer.sendall(payload)
            except (BrokenPipeError, ConnectionResetError):
                if status < 400:
                    errors.append("unexpected disconnect")
            except BaseException as exc:
                errors.append(repr(exc))

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        env = {"PATH": os.environ["PATH"], "HOME": home, "XDG_CONFIG_HOME": home, "XDG_DATA_HOME": home, "XDG_CACHE_HOME": home}
        result = subprocess.run([str(DRIVER), address, "fake-upstream"], env=env, capture_output=True, text=True, timeout=20)
        worker.join(12)
        assert not worker.is_alive(), "fixture did not finish"
        assert not errors, errors
        listener.settimeout(0.05)
        try:
            extra, _ = listener.accept()
        except TimeoutError:
            pass
        else:
            extra.close()
            raise AssertionError("POST was replayed")
        if truncated or (status >= 400 and len(payload) > 4 * 1024 * 1024):
            assert result.returncode != 0, result.stdout
        else:
            assert result.returncode == 0, result.stderr
            assert f"status {status}" in result.stdout
            assert f"body {len(payload)} {sum(payload)}" in result.stdout, result.stdout


def main():
    check(b"data: synthetic\n\n", fragmented=True)
    large = b"data: synthetic\n\n" * 280000
    assert len(large) > 4 * 1024 * 1024
    check(large)
    check(large, chunked=True, fragmented=True)
    check(b'{"error":"synthetic"}', status=429)
    check(large, status=500)
    check(b"short", truncated=True)
    print("Provider passthrough loopback checks: PASS")


class ProviderPassthroughTests(unittest.TestCase):
    def test_loopback_framing_auth_and_bounded_streaming(self):
        main()

    def test_cancellation_after_response_headers_closes_stalled_upstream(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(3)
        address = "%s:%d" % listener.getsockname()
        response_head_sent = threading.Event()
        upstream_closed = threading.Event()
        errors = []

        def serve():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(3)
                    request = bytearray()
                    while b"\r\n\r\n" not in request:
                        data = peer.recv(4096)
                        if not data:
                            return
                        request.extend(data)
                    head, body = bytes(request).split(b"\r\n\r\n", 1)
                    content_length = next(
                        int(line.split(b":", 1)[1])
                        for line in head.split(b"\r\n")
                        if line.lower().startswith(b"content-length:")
                    )
                    while len(body) < content_length:
                        body += peer.recv(4096)
                    peer.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                        b"Transfer-Encoding: chunked\r\n\r\n"
                    )
                    response_head_sent.set()
                    if peer.recv(1) == b"":
                        upstream_closed.set()
            except (OSError, TimeoutError) as error:
                errors.append(repr(error))
            finally:
                listener.close()

        server = threading.Thread(target=serve, daemon=True)
        server.start()
        child_cancel, parent_cancel = socket.socketpair()
        with tempfile.TemporaryDirectory(prefix="modex-passthrough-cancel-") as home:
            env = {
                "PATH": os.environ["PATH"], "HOME": home,
                "XDG_CONFIG_HOME": home, "XDG_DATA_HOME": home, "XDG_CACHE_HOME": home,
            }
            process = subprocess.Popen(
                [str(DRIVER), address, "fake-upstream", str(child_cancel.fileno())],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                pass_fds=(child_cancel.fileno(),),
            )
            child_cancel.close()
            try:
                self.assertTrue(response_head_sent.wait(2), "upstream response headers were not sent")
                ready, _, _ = select.select([process.stdout], [], [], 2)
                self.assertTrue(ready, "passthrough did not finish reading response headers")
                status_line = process.stdout.readline()
                self.assertEqual(status_line, b"status 200\n")
                parent_cancel.shutdown(socket.SHUT_WR)
                stdout, stderr = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertIn(b"CANCELLED loopback HTTP request cancelled", stdout)
                self.assertTrue(upstream_closed.wait(1), "cancellation must close the upstream socket")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                parent_cancel.close()
                server.join(3)
        self.assertEqual(errors, [])
        self.assertFalse(server.is_alive(), "synthetic peer did not finish")

    def test_chat_completions_304_ignores_large_representation_length(self):
        from test_local_rewrite import RunningLocalRewrite, post_relay, serving
        with serving([{"status": 304, "content_type": "application/json", "body": b"",
                       "declared_length": 5242881}]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, _, body = post_relay(relay.address,
                    b'{"model":"deepseek-chat","messages":[]}',
                    path="/v1/chat/completions?trace=synthetic")
        self.assertEqual((status, body), (304, b""))
        self.assertEqual(len(server.records), 1)
        self.assertEqual(server.records[0]["path"], "/v1/chat/completions?trace=synthetic")


if __name__ == "__main__":
    unittest.main()
