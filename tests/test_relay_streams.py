"""Redirect SSE and text-header filtering through the actual production relay."""

from contextlib import contextmanager
from http.client import HTTPConnection
import hashlib
import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import tempfile
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes, serving
from test_super_launch import CODEX
from test_deepseek_continuation import observe_turns


@contextmanager
def production_relay(upstream_port):
    with tempfile.TemporaryDirectory(prefix="modex-error-sse-") as home:
        environment = {"HOME": home, "TMPDIR": home, "PATH": "/usr/bin:/bin",
                       "PRODEX_HOME": home, "PRODEX_SHARED_CODEX_HOME": home,
                       "XDG_CONFIG_HOME": home, "XDG_CACHE_HOME": home,
                       "PRODEX_RUNTIME_LOCAL_UPSTREAM": f"http://127.0.0.1:{upstream_port}/v1",
                       "PRODEX_RUNTIME_LOCAL_KEY": SYNTHETIC_API_KEY}
        process = subprocess.Popen([str(MODEX), "__modex-local-rewrite"], env=environment,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            if not select.select([process.stdout], [], [], 5)[0]:
                raise AssertionError("production relay did not become ready")
            ready = process.stdout.readline().decode().strip()
            host, port = ready.rsplit(":", 1)
            if host != "127.0.0.1":
                raise AssertionError(f"unexpected relay readiness: {ready!r}")
            yield host, int(port)
        finally:
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=2)
                raise AssertionError("production relay did not exit after parent-channel EOF")
            if process.returncode != 0 or stdout or stderr:
                raise AssertionError((process.returncode, stdout, stderr))


class RelayStreamTests(unittest.TestCase):
    def test_pinned_release_and_native_deliver_redirect_prefix_before_eof(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        payload = b"data: " + b"x" * (65536 - 8) + b"\n\n"
        script = CODEX[:CODEX.index("response=connection.getresponse()")]
        script += '\nresponse=connection.getresponse()\n'
        script += 'save({"kind":"prefix","status":response.status,"headers":dict(response.getheaders()),"body":response.read(' + str(len(payload)) + ').hex()})\n'
        script += 'response.close()\nconnection.close()\nprint("synthetic-prefix-complete")\n'
        script = script.replace("target.port,timeout=10)", "target.port,timeout=1)")
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                with tempfile.TemporaryDirectory(prefix="modex-error-prefix-oracle-") as temporary:
                    root = Path(temporary)
                    for name in ("home", "state", "shared", "work"):
                        (root / name).mkdir(mode=0o700)
                    (root / "state/update-check.json").write_text('{"source":"GitHub","latest_version":"0.439.2","checked_at":4102444800}')
                    codex = root / "codex"
                    codex.write_text("#!" + sys.executable + "\n" + script)
                    codex.chmod(0o700)
                    capture = root / "capture.jsonl"
                    environment = {"HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
                                   "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
                                   "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
                                   "MODEX_LAUNCH_SCENARIO": "stream", "TERM": "dumb", "NO_COLOR": "1",
                                   **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")}}
                    with serving([{"status": 307, "body": payload, "chunked": True, "hold_open": True,
                                   "response_headers": [("Content-Type", "text/event-stream"),
                                                        ("x-ratelimit-limit-requests", "100"),
                                                        ("x-ratelimit-remaining-requests", "0"),
                                                        ("X-Synthetic-Non-ASCII", "\x80")]}]) as server:
                        result = subprocess.run([str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
                                                 "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", "deepseek-chat",
                                                 "--no-presidio", "--no-sub-agent", "--skip-quota-check", "exec", "--", "synthetic"],
                                                cwd=root / "work", env=environment, capture_output=True, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn(b"synthetic-prefix-complete", result.stdout)
                    records = [json.loads(line) for line in capture.read_text().splitlines()]
                    prefix = next(record for record in records if record["kind"] == "prefix")
                    self.assertEqual((prefix["status"], bytes.fromhex(prefix["body"])), (307, payload))
                    headers = {name.lower(): value for name, value in prefix["headers"].items()}
                    self.assertFalse(any(name.startswith("x-deepseek-") for name in headers))
                    self.assertNotIn("x-synthetic-non-ascii", headers)
                    self.assertEqual(len(server.records), 1)

    def test_redirects_stream_before_upstream_eof_and_cancel_without_replay(self):
        payload = b'data: {"error":"synthetic provider failure"}\n\n'
        for path in ("/v1/responses", "/v1/chat/completions"):
            for status in (200, 302, 307, 308):
                if path == "/v1/responses" and status == 200:
                    continue
                with self.subTest(path=path, status=status):
                    with serving([{
                        "status": status, "body": payload, "chunked": True, "hold_open": True,
                        "response_headers": [("Content-Type", "text/event-stream"),
                                             ("x-ratelimit-limit-requests", "100"),
                                             ("x-ratelimit-remaining-requests", "0"),
                                             ("X-Synthetic-Visible", "kept"),
                                             ("X-Synthetic-Non-ASCII", "\x80"),
                                             ("Connection", "X-Synthetic-Hop"),
                                             ("X-Synthetic-Hop", "synthetic-private-hop")],
                    }]) as server:
                        with production_relay(server.server_port) as address:
                            connection = HTTPConnection(*address, timeout=0.75)
                            try:
                                connection.request("POST", path, json_bytes({"model": "deepseek-chat", "input": "synthetic", "stream": True}),
                                                   {"Content-Type": "application/json"})
                                response = connection.getresponse()
                                self.assertEqual(response.status, status)
                                headers = {name.lower(): value for name, value in response.getheaders()}
                                self.assertEqual(headers["transfer-encoding"], "chunked")
                                self.assertEqual(headers["x-synthetic-visible"], "kept")
                                self.assertNotIn("x-synthetic-non-ascii", headers)
                                self.assertNotIn("x-synthetic-hop", headers)
                                self.assertFalse(any(name.startswith("x-deepseek-") for name in headers))
                                self.assertEqual(response.read(len(payload)), payload)
                                client = connection.sock or response.fp.raw._sock
                                client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                                client.close()
                                response.close()
                                self.assertTrue(server.client_closed.wait(0.75))
                                self.assertFalse(server.hold_timed_out.is_set())
                            finally:
                                connection.close()
                    self.assertEqual(len(server.records), 1)

    def test_unknown_length_redirect_sse_above_four_mib_matches_release(self):
        # The released 0.439.2 streams redirect SSE past the buffered cap
        # even when Transfer-Encoding: chunked hides representation length.
        # The historical native-only cap assertion was incompatible with
        # the current binary on both Responses and Chat Completions routes.
        payload = b"x" * (4 * 1024 * 1024 + 1)
        for route in ("responses", "chat/completions"):
            for status in (302, 307):
                for binary in (ORACLE, MODEX):
                    with self.subTest(route=route, status=status, binary=str(binary)):
                        upstream, responses = observe_turns(
                            binary,
                            [{"model": "deepseek-chat", "input": "synthetic redirect",
                              "_path": "/v1/" + route}],
                            [{"status": status, "content_type": "text/event-stream",
                              "body": payload, "chunked": True, "chunk_size": 65536}],
                        )
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(responses[0]["status"], status)
                        self.assertEqual(bytes.fromhex(responses[0]["body"]), payload)
                        headers = {name.lower(): value
                                   for name, value in responses[0]["headers"].items()}
                        self.assertEqual(headers.get("transfer-encoding"), "chunked")
                        self.assertNotIn("content-length", headers)
                        self.assertEqual(upstream[0]["headers"]["authorization"],
                                         "Bearer " + SYNTHETIC_API_KEY)


if __name__ == "__main__":
    unittest.main()
