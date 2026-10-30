"""Production-path DeepSeek SSE framing and precommit boundary checks."""

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

import test_cli
import test_deepseek_continuation as continuation
from test_local_rewrite import json_bytes


class FragmentedUpstream:
    def __init__(self, parts):
        self.parts = parts
        self.records = []
        self.closed = threading.Event()
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(4)
        self.listener.settimeout(0.1)
        self.server_port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _request(self, connection):
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = connection.recv(8192)
            if not chunk:
                return
            data.extend(chunk)
        head, body = data.split(b"\r\n\r\n", 1)
        headers = {}
        for line in head.split(b"\r\n")[1:]:
            name, value = line.split(b":", 1)
            headers[name.decode().lower()] = value.strip().decode()
        length = int(headers.get("content-length", "0"))
        while len(body) < length:
            chunk = connection.recv(8192)
            if not chunk:
                return
            body.extend(chunk)
        self.records.append({"headers": headers, "body": bytes(body[:length])})

    def _serve(self):
        while not self.closed.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(5)
                try:
                    self._request(connection)
                    for fragment, delay in self.parts:
                        if delay:
                            time.sleep(delay)
                        if fragment:
                            connection.sendall(fragment)
                    connection.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

    def close(self):
        self.closed.set()
        self.listener.close()
        self.thread.join(timeout=2)


class GatedUpstream(FragmentedUpstream):
    def __init__(self, parts, gate_before):
        self.gate_before = gate_before
        self.gate_reached = threading.Event()
        self.release_gate = threading.Event()
        self.gated_chunk_sent = threading.Event()
        self.gated_chunk_send_started_at = None
        super().__init__(parts)

    def _serve(self):
        while not self.closed.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(5)
                try:
                    self._request(connection)
                    for index, (fragment, delay) in enumerate(self.parts):
                        if index == self.gate_before:
                            self.gate_reached.set()
                            if not self.release_gate.wait(10):
                                return
                        if delay:
                            time.sleep(delay)
                        if fragment:
                            if index == self.gate_before:
                                self.gated_chunk_send_started_at = time.monotonic()
                            connection.sendall(fragment)
                            if index == self.gate_before:
                                self.gated_chunk_sent.set()
                    connection.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

    def close(self):
        self.release_gate.set()
        super().close()


@contextmanager
def fragmented_serving(responses):
    server = FragmentedUpstream(responses[0]["raw_parts"])
    server.responses = responses
    try:
        yield server
    finally:
        server.close()


def observe_raw(binary, parts, *, idle_timeout_ms=1000, lookahead_timeout_ms=1000):
    turns = [{"model": "deepseek-chat", "input": "synthetic fragmented response", "stream": True}]
    with patch.object(continuation, "serving", fragmented_serving):
        return continuation.observe_turns(
            binary,
            turns,
            [{"raw_parts": parts}],
            idle_timeout_ms=idle_timeout_ms,
            lookahead_timeout_ms=lookahead_timeout_ms,
        )


def response_summary(row):
    payload = bytes.fromhex(row["body"])
    events = [json.loads(line[6:]) for line in payload.splitlines() if line.startswith(b"data: ")]
    return row["status"], [
        (event.get("type"), event.get("delta"),
         (event.get("response", {}).get("error", {}).get("code"),
          event.get("response", {}).get("error", {}).get("message")))
        for event in events
    ], payload if not events else None


def gated_client(source):
    imports = "import http.client, json, os, pathlib, signal, sys, time"
    if imports not in source:
        raise AssertionError("synthetic Codex client imports changed")
    source = source.replace(imports, imports + ", socket", 1)
    original = "    response = connection.getresponse()\n    payload = response.read()\n"
    replacement = (
        "    response = connection.getresponse()\n"
        "    def notify_gate(marker):\n"
        "        with socket.create_connection((\"127.0.0.1\", int(os.environ[\"MODEX_TEST_SIGNAL_PORT\"])), timeout=5) as gate:\n"
        "            gate.sendall(marker)\n"
        "    notify_gate(b\"H\")\n"
        "    first = response.read1(1)\n"
        "    if first: notify_gate(b\"B\")\n"
        "    chunks = [first]\n"
        "    while True:\n"
        "        chunk = response.read1(4096)\n"
        "        if not chunk: break\n"
        "        chunks.append(chunk)\n"
        "    payload = b\"\".join(chunks)\n"
    )
    if original not in source:
        raise AssertionError("synthetic Codex response reader changed")
    return source.replace(original, replacement, 1)


class ClientSignals:
    def __init__(self):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(4)
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.closed = threading.Event()
        self.events = {b"H": threading.Event(), b"B": threading.Event()}
        self.times = {}
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.closed.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                marker = connection.recv(1)
            with self.lock:
                self.times[marker] = time.monotonic()
                if marker in self.events:
                    self.events[marker].set()

    def wait(self, marker, timeout):
        return self.events[marker].wait(timeout)

    def timestamp(self, marker):
        with self.lock:
            return self.times[marker]

    def close(self):
        self.closed.set()
        self.listener.close()
        self.thread.join(timeout=2)


def observe_gated(binary, parts, gate_before, *, idle_timeout_ms, lookahead_timeout_ms,
                  response_signal, expect_signal_before_release):
    servers = []
    server_ready = threading.Event()
    signals = ClientSignals()
    result = {}

    @contextmanager
    def gated_serving(responses):
        server = GatedUpstream(responses[0]["raw_parts"], gate_before)
        servers.append(server)
        server_ready.set()
        try:
            yield server
        finally:
            server.close()

    original_run = continuation.subprocess.run

    def run_with_signal(*args, **kwargs):
        environment = kwargs["env"].copy()
        environment["MODEX_TEST_SIGNAL_PORT"] = str(signals.port)
        kwargs["env"] = environment
        return original_run(*args, **kwargs)

    def run():
        try:
            with patch.object(continuation, "serving", gated_serving), \
                 patch.object(continuation, "CLIENT", gated_client(continuation.CLIENT)), \
                 patch.object(continuation.subprocess, "run", run_with_signal):
                result["value"] = continuation.observe_turns(
                    binary,
                    [{"model": "deepseek-chat", "input": "synthetic gated response", "stream": True}],
                    [{"raw_parts": parts}],
                    idle_timeout_ms=idle_timeout_ms,
                    lookahead_timeout_ms=lookahead_timeout_ms,
                )
        except BaseException as error:
            result["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        if not server_ready.wait(5):
            raise AssertionError("synthetic upstream did not start")
        server = servers[0]
        if not server.gate_reached.wait(5):
            raise AssertionError("synthetic upstream did not reach its gate")
        marker = b"H" if response_signal == "headers" else b"B"
        if expect_signal_before_release:
            if not signals.wait(marker, 3):
                raise AssertionError(f"downstream {response_signal} did not arrive before the next upstream chunk")
            if server.gated_chunk_sent.is_set():
                raise AssertionError(f"downstream {response_signal} arrived after the next upstream chunk")
            server.release_gate.set()
        else:
            if signals.wait(marker, 1):
                raise AssertionError(f"downstream {response_signal} arrived before provider progress")
            server.release_gate.set()
            if not signals.wait(marker, 5):
                raise AssertionError(f"downstream {response_signal} did not arrive after provider progress")
            if not server.gated_chunk_sent.wait(5):
                raise AssertionError("synthetic upstream did not send its gated chunk")
            if signals.timestamp(marker) < server.gated_chunk_send_started_at:
                raise AssertionError(f"downstream {response_signal} arrived before provider progress")
        worker.join(timeout=15)
        if worker.is_alive():
            raise AssertionError("synthetic gated request did not finish")
        if "error" in result:
            raise result["error"]
        return result["value"]
    finally:
        if servers:
            servers[0].release_gate.set()
        signals.close()
        if worker.is_alive():
            worker.join(timeout=2)


def observed_events(row):
    return [json.loads(line[6:]) for line in bytes.fromhex(row["body"]).splitlines()
            if line.startswith(b"data: ")]


class DeepSeekPrecommitBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if hashlib.sha256(test_cli.ORACLE.read_bytes()).hexdigest() != test_cli.ORACLE_SHA256:
            raise AssertionError("oracle does not match frozen Prodex 0.439.2")
        if hashlib.sha256(continuation.ORACLE_01651.read_bytes()).hexdigest() != continuation.ORACLE_01651_SHA256:
            raise AssertionError("oracle does not match pinned Prodex 0.165.1")

    def test_partial_status_header_chunk_size_and_body_framing_match_release(self):
        event = {"id": "synthetic-fragmented", "created": 42, "model": "deepseek-chat",
                 "choices": [{"index": 0, "delta": {"content": "fragmented-http"},
                              "finish_reason": "stop"}]}
        body = b"data: " + json_bytes(event) + b"\n\n" + b"data: [DONE]\n\n"
        framed = f"{len(body):X}\r\n".encode() + body + b"\r\n"
        head = (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
        parts = [
            (head[:5], 0.01), (head[5:14], 0.01), (head[14:41], 0.01),
            (head[41:63], 0.01), (head[63:], 0.01),
            (framed[:1], 0.01), (framed[1:2], 0.01), (framed[2:5], 0.01),
            (framed[5:19], 0.01), (framed[19:-3], 0.01),
            (framed[-3:-1], 0.01), (framed[-1:], 0.01),
            (b"0", 0.01), (b"\r", 0.01), (b"\n", 0.01),
            (b"\r", 0.01), (b"\n", 0),
        ]
        observations = []
        for binary in (test_cli.ORACLE, test_cli.MODEX):
            upstream, responses = observe_raw(binary, parts)
            self.assertEqual(len(upstream), 1)
            self.assertEqual(len(responses), 1)
            events = observed_events(responses[0])
            self.assertIn("fragmented-http", [event.get("delta") for event in events])
            self.assertIn("response.completed", [event.get("type") for event in events])
            observations.append(response_summary(responses[0]))
        self.assertEqual(observations[0], observations[1])

    def test_empty_and_truncated_eof_shapes_match_release(self):
        cases = (
            ("eof-before-head", []),
            ("empty-content-length", [
                (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                 b"Content-Length: 0\r\nConnection: close\r\n\r\n", 0),
            ]),
            ("empty-chunked", [
                (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                 b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n", 0),
                (b"0", 0.01), (b"\r\n", 0.01), (b"\r", 0.01), (b"\n", 0),
            ]),
            ("empty-close-delimited", [
                (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                 b"Connection: close\r\n\r\n", 0),
            ]),
            ("truncated-content-length", [
                (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                 b"Content-Length: 20\r\nConnection: close\r\n\r\n", 0),
                (b"data: {", 0),
            ]),
            ("truncated-chunked-body", [
                (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                 b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n", 0),
                (b"20\r\ndata: {\r\n", 0),
            ]),
        )
        for name, parts in cases:
            with self.subTest(case=name):
                observations = []
                for binary in (continuation.ORACLE_01651, test_cli.ORACLE, test_cli.MODEX):
                    upstream, responses = observe_raw(binary, parts)
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(len(responses), 1)
                    observations.append(response_summary(responses[0]))
                self.assertEqual(observations[0], observations[1])
                if name == "eof-before-head":
                    self.assertEqual(observations[0], (502, [], b"upstream request failed"))
                elif name.startswith("empty-"):
                    self.assertEqual(observations[0][0], 200)
                    self.assertEqual(observations[0][1][-1][0], "response.failed")
                    self.assertEqual(observations[0][1][-1][2],
                                     ("provider_stream_error", "unexpected end of stream"))
                elif name.startswith("truncated-"):
                    self.assertEqual(observations[0][0], 200)
                    self.assertEqual(observations[0][1][-1][0], "response.failed")
                    self.assertEqual(observations[0][1][-1][2],
                                     ("provider_stream_error", "error decoding response body"))

    def test_equal_idle_and_lookahead_deadlines_allow_release_race_outcomes(self):
        cases = (("empty", b""), ("partial", b"data: {"))
        for name, body in cases:
            with self.subTest(case=name):
                for binary in (test_cli.ORACLE, test_cli.MODEX):
                    upstream, responses = continuation.observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic equal deadline", "stream": True}],
                        [{"status": 200, "content_type": "text/event-stream", "body": body,
                          "chunked": True, "hold_open": True}],
                        idle_timeout_ms=100,
                        lookahead_timeout_ms=100,
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(len(responses), 1)
                    row = responses[0]
                    events = observed_events(row)
                    payload = bytes.fromhex(row["body"])
                    if row["status"] == 502:
                        self.assertEqual(events, [])
                        self.assertEqual(payload, b"upstream request failed")
                    else:
                        self.assertEqual(row["status"], 200)
                        self.assertTrue(events)
                        self.assertEqual(events[-1].get("type"), "response.failed")
                        error = events[-1].get("response", {}).get("error", {})
                        self.assertEqual(error.get("code"), "provider_stream_error")
                        self.assertIn(error.get("message"), (
                            "error decoding response body",
                            "runtime upstream stream idle timed out",
                        ))

    def test_lookahead_before_after_and_postcommit_delays_match_release(self):
        hold = b'data: {"type":"response.created"}\n\n'
        first = b'data: ' + json_bytes({"id": "synthetic-delayed", "created": 42,
            "model": "deepseek-chat", "choices": [{"index": 0,
            "delta": {"content": "early"}}]}) + b"\n\n"
        second = b'data: ' + json_bytes({"id": "synthetic-delayed", "created": 42,
            "model": "deepseek-chat", "choices": [{"index": 0,
            "delta": {"content": "late"}, "finish_reason": "stop"}]}) + b"\n\n"
        done = b"data: [DONE]\n\n"
        head = (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")

        def chunk(body):
            return f"{len(body):X}\r\n".encode() + body + b"\r\n"

        final_chunk = b"0\r\n\r\n"
        cases = (
            ("progress-before-lookahead", [head, chunk(hold), chunk(first + done), final_chunk],
             10000, 10000, "headers", False, ["early"]),
            ("progress-after-lookahead", [head, chunk(hold), chunk(first + done), final_chunk],
             10000, 300, "headers", True, ["early"]),
            ("delayed-followup-after-commit", [head, chunk(first), chunk(second + done), final_chunk],
             10000, 1000, "body", True, ["early", "late"]),
        )
        for name, fragments, idle_timeout_ms, lookahead_timeout_ms, response_signal, before_release, expected_deltas in cases:
            with self.subTest(case=name):
                observations = []
                for binary in (test_cli.ORACLE, test_cli.MODEX):
                    upstream, responses = observe_gated(
                        binary, [(fragment, 0) for fragment in fragments], 2,
                        idle_timeout_ms=idle_timeout_ms,
                        lookahead_timeout_ms=lookahead_timeout_ms,
                        response_signal=response_signal,
                        expect_signal_before_release=before_release,
                    )
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(len(responses), 1)
                    summary = response_summary(responses[0])
                    events = observed_events(responses[0])
                    self.assertEqual(responses[0]["status"], 200)
                    deltas = [event["delta"] for event in events
                              if event.get("type") == "response.output_text.delta"]
                    self.assertEqual(deltas, expected_deltas)
                    self.assertIn("response.completed", [event.get("type") for event in events])
                    observations.append(summary)
                self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
