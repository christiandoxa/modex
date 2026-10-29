"""Exercise retained overflow and parent EOF on the real local relay."""

import http.client
import os
from pathlib import Path
import re
import select
import socket
import subprocess
import tempfile
import threading
import time
import unittest

import test_local_rewrite_01651_oracle as transport


ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get(
    "MODEX_LOCAL_REWRITE_DRIVER", ROOT / "build/tests/local_rewrite_driver",
))
SYNTHETIC_API_KEY = "synthetic-admission-key"


class LocalRewriteAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.is_file():
            raise AssertionError(f"Build the local relay test driver first: {DRIVER}")

    def setUp(self):
        self.upstream = transport.Upstream()
        self.upstream_thread = threading.Thread(
            target=self.upstream.serve_forever, daemon=True,
        )
        self.upstream_thread.start()

    def tearDown(self):
        self.upstream.shutdown()
        self.upstream.server_close()
        self.upstream_thread.join(timeout=2)

    def _start_relay(self, temporary):
        root = Path(temporary)
        for name in ("home", "prodex", "config", "data", "cache", "tmp"):
            (root / name).mkdir(mode=0o700)
        parent_read, parent_write = os.pipe()
        environment = {
            "HOME": str(root / "home"),
            "PRODEX_HOME": str(root / "prodex"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "TMPDIR": str(root / "tmp"),
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
        }
        try:
            process = subprocess.Popen(
                [
                    str(DRIVER), "127.0.0.1:0",
                    f"http://127.0.0.1:{self.upstream.server_port}/v1",
                    SYNTHETIC_API_KEY, str(parent_read),
                ],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                pass_fds=(parent_read,),
                bufsize=0,
            )
        finally:
            os.close(parent_read)
        try:
            readable, _, _ = select.select([process.stdout], [], [], 5)
            if not readable:
                raise TimeoutError("local relay did not report startup")
            startup = process.stdout.readline().decode("utf-8", errors="replace").rstrip()
            match = re.fullmatch(
                r"READY http://127\.0\.0\.1:(\d+)/v1 WORKERS=(\d+)", startup,
            )
            if not match:
                raise RuntimeError(f"local relay failed during startup: {startup!r}")
            return process, parent_write, ("127.0.0.1", int(match.group(1))), int(match.group(2))
        except BaseException:
            os.close(parent_write)
            process.kill()
            process.wait(timeout=2)
            raise

    @staticmethod
    def _connect(address, request):
        client = socket.create_connection(address, timeout=3)
        client.settimeout(3)
        if request:
            client.sendall(request)
        return client

    def _saturate(self, address, worker_count):
        blockers = []
        parked = []
        overflow = []
        blocked_body = (
            b"POST /v1/responses HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\nContent-Type: application/json\r\n"
            b"Content-Length: 1\r\nConnection: close\r\n\r\n"
        )
        partial_head = b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Pending: unfinished"
        try:
            for _ in range(worker_count):
                blockers.append(self._connect(address, blocked_body))
            time.sleep(0.1)
            for _ in range(128):
                parked.append(self._connect(address, partial_head))
            # Let the listener admit all 128 partial headers before creating the overflow clients.
            time.sleep(0.4)
            first = transport.request_bytes(
                headers=(("Connection", "close"),),
                body=b'{"model":"deepseek-chat","input":"synthetic admission first"}',
                target=b"/v1/responses?admission=first",
            )
            overflow.append(self._connect(address, first))
            time.sleep(0.15)
            second = transport.request_bytes(
                headers=(("Connection", "close"),),
                body=b'{"model":"deepseek-chat","input":"synthetic admission second"}',
                target=b"/v1/responses?admission=second",
            )
            overflow.append(self._connect(address, second))
            time.sleep(0.15)
            for index, client in enumerate(overflow, 1):
                readable, _, _ = select.select([client], [], [], 0)
                self.assertFalse(
                    readable,
                    f"overflow client {index} responded or closed before worker release",
                )
            return blockers, parked, overflow
        except BaseException:
            for client in blockers + parked + overflow:
                client.close()
            raise

    @staticmethod
    def _close_clients(clients):
        for client in clients:
            try:
                client.close()
            except OSError:
                pass

    def _close_relay(self, process, parent_write, clients):
        self._close_clients(clients)
        try:
            os.close(parent_write)
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        if process.stdout:
            process.stdout.close()

    @staticmethod
    def _read_response(client):
        client.settimeout(5)
        response = http.client.HTTPResponse(client)
        response.begin()
        body = response.read()
        return response.status, body

    def test_healthy_request_dispatches_while_128_headers_are_partial(self):
        with tempfile.TemporaryDirectory(prefix="modex-admission-healthy-") as temporary:
            process, parent_write, address, _worker_count = self._start_relay(temporary)
            partial_clients = []
            healthy = None
            try:
                partial_head = b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Pending: unfinished"
                for _ in range(128):
                    partial_clients.append(self._connect(address, partial_head))
                time.sleep(0.4)
                request = transport.request_bytes(
                    headers=(("Connection", "close"),),
                    body=b'{"model":"deepseek-chat","input":"synthetic healthy request"}',
                    target=b"/v1/responses?admission=healthy",
                )
                healthy = socket.create_connection(address, timeout=3)
                healthy.settimeout(3)
                started = time.monotonic()
                healthy.sendall(request)
                status, body = self._read_response(healthy)
                elapsed_ms = (time.monotonic() - started) * 1000
                if os.environ.get("MODEX_TEST_REPORT_TIMING") == "1":
                    print(f"healthy_response_before_partial_release_ms={elapsed_ms:.1f}")
                self.assertEqual((status, body), (200, transport.RESPONSES_RESPONSE))
                self.assertLess(elapsed_ms, 750)
                self.assertEqual(
                    [row["path"] for row in self.upstream.snapshot_records()],
                    ["/v1/chat/completions"],
                )
            finally:
                self._close_relay(
                    process, parent_write, partial_clients + ([healthy] if healthy else []),
                )

    def test_two_overflow_clients_are_retained_and_served(self):
        with tempfile.TemporaryDirectory(prefix="modex-admission-") as temporary:
            process, parent_write, address, worker_count = self._start_relay(temporary)
            clients = []
            try:
                blockers, parked, overflow = self._saturate(address, worker_count)
                clients = blockers + parked + overflow
                blockers[0].close()
                self.assertEqual(
                    [self._read_response(client)[0] for client in overflow],
                    [200, 200],
                )
                records = self.upstream.snapshot_records()
                self.assertEqual(
                    [row["path"] for row in records],
                    ["/v1/chat/completions", "/v1/chat/completions"],
                )
                body_markers = [
                    marker for row in records
                    for marker in (b"synthetic admission first", b"synthetic admission second")
                    if marker in row["body"]
                ]
                self.assertCountEqual(
                    body_markers,
                    [b"synthetic admission first", b"synthetic admission second"],
                )
            finally:
                self._close_relay(process, parent_write, clients)

    def test_parent_eof_closes_a_retained_overflow_client(self):
        with tempfile.TemporaryDirectory(prefix="modex-admission-parent-eof-") as temporary:
            process, parent_write, address, worker_count = self._start_relay(temporary)
            clients = []
            try:
                blockers, parked, overflow = self._saturate(address, worker_count)
                clients = blockers + parked + overflow
                os.close(parent_write)
                parent_write = -1
                self._close_clients(blockers)
                process.wait(timeout=3)
                for index, client in enumerate(overflow, 1):
                    client.settimeout(2)
                    try:
                        data = client.recv(1)
                    except OSError:
                        continue
                    self.assertEqual(data, b"", f"overflow client {index} received data during shutdown")
                self.assertEqual(self.upstream.snapshot_records(), [])
            finally:
                if parent_write >= 0:
                    self._close_relay(process, parent_write, clients)
                else:
                    self._close_clients(clients)
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=3)
                    if process.stdout:
                        process.stdout.close()


if __name__ == "__main__":
    unittest.main()
