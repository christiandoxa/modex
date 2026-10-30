"""Characterize the pinned runtime-proxy WebSocket bootstrap on synthetic loopback data.

This is reference behavior evidence only; it does not exercise or qualify Modex.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import select
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


def read_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        block = connection.recv(size - len(data))
        if not block:
            raise AssertionError("WebSocket peer closed inside a frame")
        data.extend(block)
    return bytes(data)


def read_websocket_frame(connection):
    first, second = read_exact(connection, 2)
    size = second & 0x7F
    if size == 126:
        size = int.from_bytes(read_exact(connection, 2), "big")
    elif size == 127:
        size = int.from_bytes(read_exact(connection, 8), "big")
    mask = read_exact(connection, 4) if second & 0x80 else None
    payload = read_exact(connection, size)
    if mask is not None:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return first & 0x0F, payload


def send_websocket_frame(connection, opcode, payload, *, masked):
    size = len(payload)
    prefix = bytes([0x80 | opcode])
    mask_bit = 0x80 if masked else 0
    if size < 126:
        header = prefix + bytes([mask_bit | size])
    elif size <= 0xFFFF:
        header = prefix + bytes([mask_bit | 126]) + size.to_bytes(2, "big")
    else:
        header = prefix + bytes([mask_bit | 127]) + size.to_bytes(8, "big")
    if masked:
        mask = b"\x13\x57\x9b\xdf"
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        header += mask
    connection.sendall(header + payload)


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


class RuntimeProxyWebsocketOracleFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        digest = hashlib.sha256(cls.ORACLE.read_bytes()).hexdigest()
        if digest != cls.ORACLE_SHA256:
            raise AssertionError(f"pinned runtime WebSocket oracle checksum mismatch: {digest}")

        cls.temporary = tempfile.TemporaryDirectory(prefix="modex-runtime-ws-oracle-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.prodex_home = cls.root / "prodex"
        cls.home = cls.root / "home"
        cls.logs = cls.root / "runtime-logs"
        for path in (cls.prodex_home, cls.home, cls.logs):
            path.mkdir(mode=0o700)

        profile = cls.prodex_home / "profiles" / "synthetic"
        profile.parent.mkdir(mode=0o700)
        profile.mkdir(mode=0o700)
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
        checked_at = int(time.time())
        usage_snapshots = cls.prodex_home / "runtime-usage-snapshots.json"
        usage_snapshots.write_text(json.dumps({
            "synthetic": {
                "checked_at": checked_at,
                "plan_type": "plus",
                "five_hour_status": "Ready",
                "five_hour_remaining_percent": 100,
                "five_hour_reset_at": checked_at + 3600,
                "weekly_status": "Ready",
                "weekly_remaining_percent": 100,
                "weekly_reset_at": checked_at + 604800,
            },
        }), encoding="utf-8")
        usage_snapshots.chmod(0o600)

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
            "PRODEX_RUNTIME_LOG_RECORD": "1",
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
            [str(cls.ORACLE), "__runtime-broker"],
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

    def open_websocket(self):
        connection = socket.create_connection(("127.0.0.1", self.listen_port), timeout=3)
        connection.settimeout(3)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        connection.sendall((
            f"GET /backend-api/prodex/responses HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.listen_port}\r\n"
            "Connection: Upgrade\r\nUpgrade: websocket\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Key: {key}\r\n\r\n"
        ).encode("ascii"))
        status, _, extra = read_response_head(connection)
        if status != "HTTP/1.1 101 Switching Protocols" or extra:
            connection.close()
            raise AssertionError(f"runtime WebSocket upgrade failed: {status!r}, {extra!r}")
        return connection

    def accept_upstream_websocket(self, local=None):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                connection, _ = self.upstream.accept()
                break
            except TimeoutError:
                if self.process.poll() is not None:
                    self.fail("pinned runtime broker exited before upstream WebSocket connect")
        else:
            local_message = None
            if local is not None and select.select([local], [], [], 0)[0]:
                try:
                    local_message = read_websocket_frame(local)
                except (AssertionError, OSError, TimeoutError) as error:
                    local_message = str(error)
            logs = {
                str(path.relative_to(self.logs)): path.read_text(encoding="utf-8", errors="replace")
                for path in self.logs.rglob("*") if path.is_file()
            }
            self.fail(
                "response.create did not open a synthetic upstream WebSocket: "
                + repr(local_message) + " " + repr(logs) + " " + self.stderr_path_text()
            )
        connection.settimeout(3)
        request = bytearray()
        while b"\r\n\r\n" not in request:
            block = connection.recv(4096)
            if not block:
                self.fail("upstream WebSocket handshake ended early")
            request.extend(block)
            if len(request) > 65536:
                self.fail("upstream WebSocket request headers exceeded 64 KiB")
        lines = bytes(request).split(b"\r\n")
        headers = {}
        for line in lines[1:]:
            if not line:
                break
            name, value = line.decode("ascii").split(":", 1)
            headers[name.strip().lower()] = value.strip()
        websocket_key = headers.get("sec-websocket-key")
        if not websocket_key:
            connection.close()
            self.fail("upstream handshake omitted Sec-WebSocket-Key")
        accept = base64.b64encode(
            hashlib.sha1((websocket_key + WEBSOCKET_GUID).encode("ascii")).digest(),
        ).decode("ascii")
        connection.sendall((
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode("ascii"))
        return connection, headers

    def create_response_on(self, local, upstream_id):
        request = json.dumps({"type": "response.create", "input": "synthetic"}, separators=(",", ":"))
        send_websocket_frame(local, 1, request.encode("utf-8"), masked=True)
        upstream, headers = self.accept_upstream_websocket(local)
        opcode, payload = read_websocket_frame(upstream)
        self.assertEqual(opcode, 1)
        self.assertEqual(json.loads(payload)["type"], "response.create")
        self.assertEqual(headers.get("authorization"), "Bearer synthetic-profile-access-token")
        self.assertEqual(headers.get("chatgpt-account-id"), "synthetic-profile-account")
        send_websocket_frame(
            upstream, 1,
            json.dumps({"type": "response.created", "response": {"id": upstream_id, "status": "in_progress"}}, separators=(",", ":")).encode(),
            masked=False,
        )
        send_websocket_frame(
            upstream, 1,
            json.dumps({"type": "response.output_text.delta", "response_id": upstream_id, "delta": "synthetic pending"}, separators=(",", ":")).encode(),
            masked=False,
        )
        received = []
        while not any("response.output_text.delta" in text for text in received):
            opcode, payload = read_websocket_frame(local)
            self.assertEqual(opcode, 1)
            received.append(payload.decode("utf-8"))
        self.assertTrue(any("response.created" in text for text in received), received)
        return upstream


@unittest.skipUnless(ORACLE.is_file(), f"pinned Prodex oracle unavailable: {ORACLE}")
class RuntimeProxyWebsocket01651OracleTests(RuntimeProxyWebsocketOracleFixture):
    ORACLE = ORACLE
    ORACLE_SHA256 = ORACLE_SHA256

    def test_interrupt_is_forwarded_only_on_the_connection_that_created_its_response(self):
        local_owner, local_other = self.open_websocket(), self.open_websocket()
        upstream_owner = upstream_other = None
        try:
            upstream_owner = self.create_response_on(local_owner, "resp_owner")
            upstream_other = self.create_response_on(local_other, "resp_other")

            cross_interrupt = json.dumps({
                "type": "response.interrupt", "response_id": "resp_other",
                "mode": "discard_partial_items",
            }, separators=(",", ":"))
            send_websocket_frame(local_owner, 1, cross_interrupt.encode(), masked=True)

            readable, _, _ = select.select([local_owner], [], [], 0.2)
            self.assertTrue(readable, "foreign interrupt did not terminate the submitting local session")
            with self.assertRaisesRegex(AssertionError, "WebSocket peer closed inside a frame"):
                read_websocket_frame(local_owner)
            self.assertEqual(local_owner.recv(1), b"")

            readable, _, _ = select.select([upstream_owner], [], [], 0.2)
            self.assertTrue(readable, "foreign interrupt did not terminate the submitting session")
            self.assertEqual(
                upstream_owner.recv(4096), b"",
                "foreign interrupt sent a frame instead of closing the submitting upstream",
            )
            readable, _, _ = select.select([upstream_other], [], [], 0.2)
            self.assertFalse(readable, "cross-session interrupt reached its response owner")

            with self.assertRaises(TimeoutError):
                self.upstream.accept()
            self.assertIsNone(self.process.poll(), "the pinned runtime broker exited after rejecting the interrupt")

            own_interrupt = json.dumps({
                "type": "response.interrupt", "response_id": "resp_other",
                "mode": "discard_partial_items",
            }, separators=(",", ":"))
            send_websocket_frame(local_other, 1, own_interrupt.encode(), masked=True)
            opcode, payload = read_websocket_frame(upstream_other)
            self.assertEqual((opcode, payload), (1, own_interrupt.encode()))
            send_websocket_frame(
                upstream_other, 1,
                b'{"type":"response.interrupt.accepted","response_id":"resp_other"}',
                masked=False,
            )
            send_websocket_frame(
                upstream_other, 1,
                b'{"type":"response.completed","response":{"id":"resp_other","status":"completed"}}',
                masked=False,
            )
            events = []
            while not any("response.completed" in event for event in events):
                opcode, payload = read_websocket_frame(local_other)
                self.assertEqual(opcode, 1)
                events.append(payload.decode("utf-8"))
            self.assertEqual(sum("response.interrupt.accepted" in event for event in events), 1)
            self.assertEqual(sum("response.completed" in event for event in events), 1)
        finally:
            local_owner.close()
            local_other.close()
            for connection in (upstream_owner, upstream_other):
                if connection is not None:
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

    def test_binary_message_returns_error_and_keeps_connection_usable(self):
        connection = socket.create_connection(("127.0.0.1", self.listen_port), timeout=3)
        connection.settimeout(3)
        try:
            key = base64.b64encode(b"0123456789abcdef").decode("ascii")
            connection.sendall((
                "GET /backend-api/prodex/responses HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.listen_port}\r\n"
                "Connection: Upgrade\r\nUpgrade: websocket\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                f"Sec-WebSocket-Key: {key}\r\n\r\n"
            ).encode("ascii"))
            status, _, extra = read_response_head(connection)
            self.assertEqual(status, "HTTP/1.1 101 Switching Protocols")
            self.assertEqual(extra, b"")
            connection.sendall(b"\x82\x81\x01\x02\x03\x04\x79")

            def receive_exact(size):
                data = bytearray()
                while len(data) < size:
                    chunk = connection.recv(size - len(data))
                    if not chunk:
                        self.fail("reference closed inside a WebSocket frame")
                    data.extend(chunk)
                return bytes(data)

            head = receive_exact(2)
            self.assertEqual(head, b"\x81\x7e")
            size = int.from_bytes(receive_exact(2), "big")
            self.assertEqual(json.loads(receive_exact(size)), {
                "error": {
                    "code": "invalid_request_error",
                    "message": "Binary websocket messages are not supported by the runtime auto-rotate proxy.",
                },
                "status": 400,
                "type": "error",
            })
            connection.sendall(b"\x89\x81\x01\x02\x03\x04\x79")
            self.assertEqual(receive_exact(3), b"\x8a\x01x")
            with self.assertRaises(TimeoutError):
                self.upstream.accept()
        finally:
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
