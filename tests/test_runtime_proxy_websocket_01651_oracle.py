"""Characterize the pinned runtime-proxy WebSocket bootstrap on synthetic loopback data.

This is reference behavior evidence only; it does not exercise or qualify Modex.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def reserve_loopback_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def read_response_head(connection):
    data = bytearray()
    while b"\r\n\r\n" not in data:
        block = connection.recv(4096)
        if not block:
            break
        data.extend(block)
        if len(data) > 65536:
            raise AssertionError("reference WebSocket response head exceeded 64 KiB")
    marker = data.find(b"\r\n\r\n")
    if marker < 0:
        raise AssertionError(f"reference closed before response headers: {bytes(data)!r}")
    head = bytes(data[:marker])
    lines = head.decode("ascii").split("\r\n")
    headers = {}
    for line in lines[1:]:
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return lines[0], headers, bytes(data[marker + 4:])


@unittest.skipUnless(ORACLE.is_file(), f"pinned Prodex oracle unavailable: {ORACLE}")
class RuntimeProxyWebsocket01651OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        digest = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
        if digest != ORACLE_SHA256:
            raise AssertionError(f"pinned 0.165.1 oracle checksum mismatch: {digest}")

        cls.temporary = tempfile.TemporaryDirectory(prefix="modex-runtime-ws-oracle-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.prodex_home = cls.root / "prodex"
        cls.home = cls.root / "home"
        cls.logs = cls.root / "runtime-logs"
        for path in (cls.prodex_home, cls.home, cls.logs):
            path.mkdir(mode=0o700)

        profile = cls.prodex_home / "profiles" / "synthetic"
        profile.mkdir(parents=True, mode=0o700)
        (profile / "auth.json").write_text(json.dumps({
            "tokens": {
                "access_token": "synthetic-profile-access-token",
                "account_id": "synthetic-profile-account",
            },
        }), encoding="utf-8")
        (profile / "auth.json").chmod(0o600)
        state = {
            "active_profile": "synthetic",
            "profiles": {
                "synthetic": {
                    "codex_home": str(profile),
                    "managed": True,
                    "email": "synthetic@example.test",
                    "provider": {"provider_kind": "openai"},
                },
            },
            "last_run_selected_at": {},
            "response_profile_bindings": {},
            "session_profile_bindings": {},
        }
        (cls.prodex_home / "state.json").write_text(
            json.dumps(state), encoding="utf-8",
        )
        (cls.prodex_home / "state.json").chmod(0o600)

        cls.upstream = socket.socket()
        cls.upstream.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.upstream.bind(("127.0.0.1", 0))
        cls.upstream.listen()
        cls.upstream.settimeout(0.05)
        cls.addClassCleanup(cls.upstream.close)
        upstream_port = cls.upstream.getsockname()[1]
        listen_port = reserve_loopback_port()
        cls.bootstrap = {
            "version": 1,
            "current_profile": "synthetic",
            "upstream_base_url": f"http://127.0.0.1:{upstream_port}",
            "include_code_review": False,
            "upstream_no_proxy": True,
            "smart_context_enabled": False,
            "model_context_window_tokens": None,
            "broker_key": "synthetic-websocket",
            "instance_id": "synthetic-websocket-oracle",
            "admin_token": "synthetic-runtime-admin-token",
            "listen_addr": f"127.0.0.1:{listen_port}",
        }
        environment = {
            "HOME": str(cls.home),
            "PRODEX_HOME": str(cls.prodex_home),
            "PRODEX_RUNTIME_LOG_DIR": str(cls.logs),
            "PATH": "/usr/bin:/bin",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "no_proxy": "127.0.0.1,localhost,::1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        cls.stdout = (cls.root / "oracle.stdout").open("wb")
        cls.addClassCleanup(cls.stdout.close)
        cls.stderr = (cls.root / "oracle.stderr").open("wb")
        cls.addClassCleanup(cls.stderr.close)
        cls.process = subprocess.Popen(
            [str(ORACLE), "__runtime-broker"],
            stdin=subprocess.PIPE,
            stdout=cls.stdout,
            stderr=cls.stderr,
            env=environment,
        )
        cls.addClassCleanup(cls.stop_process)
        cls.process.stdin.write(json.dumps(cls.bootstrap).encode("utf-8"))
        cls.process.stdin.close()
        cls.listen_port = listen_port

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise AssertionError(
                    "pinned runtime broker exited during startup: "
                    + cls.stderr_path_text()
                )
            try:
                with socket.create_connection(("127.0.0.1", listen_port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise AssertionError("pinned runtime broker did not bind its synthetic loopback port")

    @classmethod
    def stderr_path_text(cls):
        cls.stderr.flush()
        return (cls.root / "oracle.stderr").read_text(encoding="utf-8", errors="replace")

    @classmethod
    def stop_process(cls):
        if cls.process.poll() is None:
            try:
                cls.process.terminate()
            except ProcessLookupError:
                pass
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

    def request(self, path, *, websocket_key=None):
        connection = socket.create_connection(("127.0.0.1", self.listen_port), timeout=3)
        connection.settimeout(3)
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: 127.0.0.1:{self.listen_port}",
            "Connection: Upgrade",
            "Upgrade: websocket",
            "Sec-WebSocket-Version: 13",
            "User-Agent: synthetic-runtime-websocket-probe",
        ]
        if websocket_key is not None:
            lines.append(f"Sec-WebSocket-Key: {websocket_key}")
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
        try:
            status, headers, extra = read_response_head(connection)
            if not status.startswith("HTTP/1.1 101 "):
                length = int(headers.get("content-length", "0"))
                body = bytearray(extra)
                while len(body) < length:
                    block = connection.recv(min(4096, length - len(body)))
                    if not block:
                        break
                    body.extend(block)
                return status, headers, bytes(body)
            return status, headers, extra
        finally:
            connection.close()

    def test_supported_path_performs_local_upgrade_without_upstream_io(self):
        key = base64.b64encode(b"0123456789abcdef").decode("ascii")
        status, headers, _ = self.request(
            "/backend-api/prodex/responses", websocket_key=key,
        )
        expected_accept = base64.b64encode(
            hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest(),
        ).decode("ascii")
        self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
        self.assertEqual(headers.get("upgrade", "").lower(), "websocket")
        self.assertIn("upgrade", headers.get("connection", "").lower())
        self.assertEqual(headers.get("sec-websocket-accept"), expected_accept)
        self.assertIsNone(self.process.poll())
        with self.assertRaises(TimeoutError):
            self.upstream.accept()

    def test_supported_path_requires_a_websocket_key(self):
        status, _, body = self.request("/backend-api/prodex/responses")
        self.assertEqual(status, "HTTP/1.1 400 Bad Request")
        self.assertIn(
            b"Missing Sec-WebSocket-Key header for runtime auto-rotate websocket proxy.",
            body,
        )

    def test_idle_connections_and_partial_frame_do_not_block_other_pings(self):
        clients = []
        try:
            for index in range(16):
                connection = socket.create_connection(("127.0.0.1", self.listen_port), timeout=3)
                clients.append(connection)
                connection.settimeout(3)
                key = base64.b64encode(index.to_bytes(16, "big")).decode("ascii")
                connection.sendall((
                    "GET /backend-api/prodex/responses HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{self.listen_port}\r\n"
                    "Connection: Upgrade\r\nUpgrade: websocket\r\n"
                    "Sec-WebSocket-Version: 13\r\n"
                    f"Sec-WebSocket-Key: {key}\r\n\r\n"
                ).encode("ascii"))
                status, headers, extra = read_response_head(connection)
                self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
                expected = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode()).digest()).decode()
                self.assertEqual(headers.get("sec-websocket-accept"), expected)
                self.assertEqual(extra, b"")

            clients[0].sendall(b"\x81")  # Hold an incomplete masked text frame.
            for connection in (clients[1], clients[-1]):
                connection.sendall(b"\x89\x81\x01\x02\x03\x04\x79")
                response = bytearray()
                while len(response) < 3:
                    block = connection.recv(3 - len(response))
                    if not block:
                        break
                    response.extend(block)
                self.assertEqual(bytes(response), b"\x8a\x01x")
            self.assertIsNone(self.process.poll())
            with self.assertRaises(TimeoutError):
                self.upstream.accept()
        finally:
            for connection in clients:
                connection.close()

    def test_unsupported_path_precedes_missing_key_validation(self):
        status, _, body = self.request("/backend-api/prodex/not-supported")
        self.assertEqual(status, "HTTP/1.1 404 Not Found")
        self.assertIn(
            b"Runtime websocket proxy only supports Codex responses and realtime endpoints.",
            body,
        )


if __name__ == "__main__":
    unittest.main()
