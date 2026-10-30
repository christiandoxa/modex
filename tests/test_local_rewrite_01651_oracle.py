"""Compare raw DeepSeek local-proxy HTTP behavior with Prodex 0.165.1."""

import base64
from email.utils import parsedate_to_datetime
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.client import HTTPResponse


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651 = ORACLE
ORACLE_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
SYNTHETIC_API_KEY = "synthetic-provider-key"
WEBSOCKET_FALLBACK = b"provider adapter requires HTTPS Responses transport fallback"
INVALID_REQUEST_TARGET_BODY = b'{"error":{"code":"invalid_request_target","message":"request target is invalid"}}'
UNSUPPORTED_ROUTE_BODY = b'{"error":{"code":"unsupported_provider_route","message":"provider route is not supported"}}'
PROVIDER_RESPONSE = json.dumps({
    "id": "chatcmpl_transport_oracle",
    "model": "deepseek-chat",
    "created": 1,
    "choices": [{"message": {"content": "synthetic response"}, "finish_reason": "stop"}],
}, separators=(",", ":")).encode()
PROVIDER_SSE_RESPONSE = base64.b64decode(next(
    case["upstream_base64"]
    for case in json.loads((ROOT / "tests/fixtures/provider-stream/cases.json").read_text(encoding="utf-8"))["cases"]
    if case["name"] == "text_done"
))
REQUEST_BODY = b'{"model":"deepseek-chat","input":"synthetic raw transport probe"}'
STREAM_REQUEST_BODY = b'{"model":"deepseek-chat","input":"synthetic raw transport probe","stream":true}'
RESPONSES_RESPONSE = b'{"created_at":1,"id":"chatcmpl_transport_oracle","metadata":{"deepseek":{"finish_reason":"stop"}},"model":"deepseek-chat","object":"response","output":[{"content":[{"text":"synthetic response","type":"output_text"}],"role":"assistant","type":"message"}]}'
TARGET_PREFIX = b"/v1/responses?x="
MAX_LENGTH_VALID_TARGET = TARGET_PREFIX + b"a" * (8192 - len(TARGET_PREFIX))
OVER_LENGTH_INVALID_TARGET = MAX_LENGTH_VALID_TARGET + b"a"
LOCAL_RELAY_REQUEST_HEADER_LIMIT = 2 * 1024 * 1024


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.records = []
        self.records_lock = threading.Lock()
        self.parallel_probe_barrier = threading.Barrier(2)
        self.parallel_probe_active = 0
        self.parallel_probe_peak_active = 0
        self.parallel_probe_overlapped = threading.Event()
        self.parent_exit_slow_started = threading.Event()
        self.parent_exit_upstream_closed = threading.Event()
        super().__init__(("127.0.0.1", 0), UpstreamHandler)

    def reset_records(self):
        with self.records_lock:
            self.records.clear()

    def snapshot_records(self):
        with self.records_lock:
            return list(self.records)

    def reset_parallel_probe(self, participants=2):
        with self.records_lock:
            self.parallel_probe_barrier = threading.Barrier(participants)
            self.parallel_probe_active = 0
            self.parallel_probe_peak_active = 0
            self.parallel_probe_overlapped.clear()

    def snapshot_parallel_probe(self):
        with self.records_lock:
            return self.parallel_probe_peak_active, self.parallel_probe_overlapped.is_set()


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _serve_request(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        with self.server.records_lock:
            self.server.records.append({
                "method": self.command,
                "path": self.path,
                "headers": {name.lower(): value for name, value in self.headers.items()},
                "body": body,
            })
        if self.path.startswith("/v1/chat/completions?parent-exit=slow") or self.headers.get("X-Parent-Exit-Slow") == "1":
            self.server.parent_exit_slow_started.set()
            self.connection.settimeout(0.05)
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                try:
                    if self.connection.recv(1, socket.MSG_PEEK) == b"":
                        self.server.parent_exit_upstream_closed.set()
                        self.close_connection = True
                        return
                except TimeoutError:
                    pass
                except OSError:
                    self.server.parent_exit_upstream_closed.set()
                    self.close_connection = True
                    return
                time.sleep(0.01)
        if self.path.startswith("/v1/chat/completions?parallel="):
            with self.server.records_lock:
                self.server.parallel_probe_active += 1
                self.server.parallel_probe_peak_active = max(
                    self.server.parallel_probe_peak_active,
                    self.server.parallel_probe_active,
                )
            try:
                timeout = 2 if self.server.parallel_probe_barrier.parties == 2 else 5
                self.server.parallel_probe_barrier.wait(timeout=timeout)
                if self.server.parallel_probe_barrier.parties > 1:
                    self.server.parallel_probe_overlapped.set()
            except threading.BrokenBarrierError:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(b"concurrent upstream peer did not arrive")))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(b"concurrent upstream peer did not arrive")
                self.close_connection = True
                with self.server.records_lock:
                    self.server.parallel_probe_active -= 1
                return
            with self.server.records_lock:
                self.server.parallel_probe_active -= 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(PROVIDER_RESPONSE)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(PROVIDER_RESPONSE)
            self.close_connection = True
            return
        if self.path.endswith("?header-controls=custom"):
            self.send_response_only(200)
            self.send_header("sErVeR", "synthetic-server-one")
            self.send_header("Server", "synthetic-server-two")
            self.send_header("dAtE", "Sat, 01 Jan 2000 00:00:00 GMT")
            self.send_header("Date", "Sun, 02 Jan 2000 00:00:00 GMT")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(PROVIDER_RESPONSE)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(PROVIDER_RESPONSE)
            self.close_connection = True
            return
        if self.path.endswith("?header-controls=filtered"):
            self.send_response_only(200)
            self.send_header("Server", "nominated-server")
            self.send_header("Date", "Sat, 01 Jan 2000 00:00:00 GMT")
            self.send_header("Connection", "Date, Server, close")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(PROVIDER_RESPONSE)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(PROVIDER_RESPONSE)
            self.close_connection = True
            return
        if self.path.endswith(("?header-controls=invalid", "?header-controls=invalid-date")):
            invalid_header = (
                b"Date: invalid\x01value\r\n"
                if self.path.endswith("invalid-date")
                else b"Server: invalid\x01value\r\n"
            )
            other_header = (
                b"Server: safe-server\r\n"
                if self.path.endswith("invalid-date")
                else b"Date: Sat, 01 Jan 2000 00:00:00 GMT\r\n"
            )
            self.wfile.write(
                b"HTTP/1.1 200 OK\r\n" + invalid_header + other_header
                + b"Content-Type: application/json\r\n"
                + b"Content-Length: " + str(len(PROVIDER_RESPONSE)).encode("ascii")
                + b"\r\nConnection: close\r\n\r\n" + PROVIDER_RESPONSE
            )
            self.wfile.flush()
            self.close_connection = True
            return
        if self.path.endswith(("?header-controls=folded", "?header-controls=folded-server")):
            folded_header = (
                b"Server: folded-server\r\n folded\r\n"
                if self.path.endswith("folded-server")
                else b"Server: safe-server\r\n"
            )
            other_header = (
                b"Date: Sat, 01 Jan 2000 00:00:00 GMT\r\n"
                if self.path.endswith("folded-server")
                else b"Date: Sat, 01 Jan 2000 00:00:00 GMT\r\n folded\r\n"
            )
            self.wfile.write(
                b"HTTP/1.1 200 OK\r\n"
                + folded_header + other_header
                + b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(PROVIDER_RESPONSE)).encode("ascii")
                + b"\r\nConnection: close\r\n\r\n" + PROVIDER_RESPONSE
            )
            self.wfile.flush()
            self.close_connection = True
            return
        response_kind = self.headers.get("X-Oracle-Response", "json")
        if response_kind == "sse-slow":
            first, separator, rest = PROVIDER_SSE_RESPONSE.partition(b"\n\n")
            first_event = first + separator
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(first_event)
            self.wfile.flush()
            time.sleep(1.2)
            self.wfile.write(rest)
            self.wfile.flush()
            self.close_connection = True
            return
        if response_kind in ("sse-204", "sse-304"):
            self.send_response(int(response_kind[-3:]))
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        response_body = PROVIDER_SSE_RESPONSE if response_kind == "sse" else PROVIDER_RESPONSE
        status = int(response_kind[7:]) if response_kind.startswith("status-") else 200
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream" if response_kind == "sse" else "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response_body)

    def do_GET(self):
        self._serve_request() if self.headers.get("X-Oracle-Response") else self.send_error(501)

    def do_HEAD(self):
        self._serve_request() if self.headers.get("X-Oracle-Response") else self.send_error(501)

    def do_POST(self):
        self._serve_request()

    def send_error(self, code, message=None, explain=None):
        if code == 501:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            with self.server.records_lock:
                self.server.records.append({
                    "method": self.command,
                    "path": self.path,
                    "headers": {name.lower(): value for name, value in self.headers.items()},
                    "body": body,
                })
        super().send_error(code, message, explain)

    def log_message(self, *_args):
        pass


class LargeHeaderUpstreamHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        wire = bytearray()
        while b"\r\n\r\n" not in wire:
            chunk = self.request.recv(65536)
            if not chunk:
                return
            wire.extend(chunk)
            if len(wire) > 5 * 1024 * 1024:
                raise AssertionError("synthetic upstream request head exceeded its bound")
        head, _, body = bytes(wire).partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        method, path, _ = lines[0].decode("ascii").split(" ", 2)
        headers = {}
        pad_headers = {}
        user_agent_values = []
        selected_header_values = {}
        for line in lines[1:]:
            name, value = line.split(b":", 1)
            lowered_name = name.decode("ascii").lower()
            headers[lowered_name] = value.strip().decode("ascii")
            if lowered_name.startswith("x-pad"):
                pad_headers[lowered_name] = value.lstrip(b" \t")
            if lowered_name == "user-agent":
                user_agent_values.append(value.lstrip(b" \t"))
            if lowered_name in ("accept", "content-type", "connection"):
                selected_header_values.setdefault(lowered_name, []).append(
                    value.lstrip(b" \t").decode("ascii")
                )
        body_length = int(headers.get("content-length", "0"))
        while len(body) < body_length:
            chunk = self.request.recv(min(65536, body_length - len(body)))
            if not chunk:
                return
            body += chunk
        record = {
            "method": method,
            "path": path,
            "headers": headers,
            "pad_headers": pad_headers,
            "user_agent_values": user_agent_values,
            "selected_header_values": selected_header_values,
            "body": body[:body_length],
            "head_bytes": len(head),
        }
        with self.server.records_lock:
            self.server.records.append(record)
        response = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + b"Content-Length: " + str(len(PROVIDER_RESPONSE)).encode("ascii")
            + b"\r\nConnection: close\r\n\r\n" + PROVIDER_RESPONSE
        )
        self.request.sendall(response)


class LargeHeaderUpstream(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.records = []
        self.records_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), LargeHeaderUpstreamHandler)
        self.server_port = self.server_address[1]

    def reset_records(self):
        with self.records_lock:
            self.records.clear()

    def snapshot_records(self):
        with self.records_lock:
            return list(self.records)


class RelayFramingUpstreamHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        wire = bytearray()
        while b"\r\n\r\n" not in wire:
            chunk = self.request.recv(65536)
            if not chunk:
                return
            wire.extend(chunk)
            if len(wire) > 3 * 1024 * 1024:
                raise AssertionError("synthetic framing upstream request exceeded its bound")
        head, _, body = bytes(wire).partition(b"\r\n\r\n")
        body = bytearray(body)
        headers = {}
        for line in head.split(b"\r\n")[1:]:
            name, value = line.split(b":", 1)
            headers[name.decode("ascii").lower()] = value.strip().decode("ascii")
        body_length = int(headers.get("content-length", "0"))
        while len(body) < body_length:
            chunk = self.request.recv(min(65536, body_length - len(body)))
            if not chunk:
                return
            body.extend(chunk)
        with self.server.records_lock:
            self.server.records.append({"headers": headers, "body": bytes(body[:body_length])})

        payload = PROVIDER_RESPONSE
        mode = self.server.response_mode
        response_head = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        if mode == "fixed-keep-alive":
            self.request.sendall(
                response_head + b"Content-Length: " + str(len(payload)).encode("ascii")
                + b"\r\nConnection: keep-alive\r\n\r\n" + payload
            )
            _hold_framed_connection_open(self.request)
        elif mode == "chunked-keep-alive":
            self.request.sendall(
                response_head + b"Transfer-Encoding: chunked\r\n"
                + b"Connection: keep-alive\r\n\r\n"
                + f"{len(payload):X}\r\n".encode("ascii") + payload + b"\r\n0\r\n\r\n"
            )
            _hold_framed_connection_open(self.request)
        elif mode == "eof":
            self.request.sendall(response_head + b"Connection: close\r\n\r\n" + payload)
        else:
            raise AssertionError(f"unknown synthetic response framing: {mode}")


def _hold_framed_connection_open(connection):
    connection.settimeout(2)
    try:
        while connection.recv(1):
            pass
    except (OSError, TimeoutError):
        pass


class RelayFramingUpstream(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, response_mode):
        self.response_mode = response_mode
        self.records = []
        self.records_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), RelayFramingUpstreamHandler)
        self.server_port = self.server_address[1]

    def reset_records(self):
        with self.records_lock:
            self.records.clear()

    def snapshot_records(self):
        with self.records_lock:
            return list(self.records)


def make_codex(path: Path):
    source = r'''import base64, http.client, json, os, re, socket, subprocess, sys, threading, time
from urllib.parse import urlsplit

def product_process_resources():
    root = os.getppid()
    pending = [root]
    seen = set()
    sampled = 0
    rss_kib = 0
    cpu_ticks = 0
    fd_count = 0
    while pending:
        pid = pending.pop()
        if pid == os.getpid() or pid in seen:
            continue
        seen.add(pid)
        try:
            proc = f"/proc/{pid}"
            status_text = open(proc + "/status", encoding="ascii").read()
            rss_kib += int(next(
                line.split()[1] for line in status_text.splitlines()
                if line.startswith("VmRSS:")
            ))
            stat_fields = open(proc + "/stat", encoding="ascii").read().rsplit(")", 1)[1].split()
            cpu_ticks += int(stat_fields[11]) + int(stat_fields[12])
            fd_count += len(os.listdir(proc + "/fd"))
            children = open(proc + f"/task/{pid}/children", encoding="ascii").read().split()
            pending.extend(int(child) for child in children)
            sampled += 1
        except (OSError, ValueError, StopIteration):
            continue
    if not sampled:
        raise RuntimeError("could not find the real product process tree")
    return sampled, rss_kib, cpu_ticks / os.sysconf("SC_CLK_TCK"), fd_count

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.153.2")
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        result = {} if request.get("method") == "initialize" else {"data": []}
        print(json.dumps({"id": request["id"], "result": result}), flush=True)
    raise SystemExit(0)

base = None
for arg in args:
    match = re.search(r"model_providers\.prodex-deepseek\.base_url=(.*)", arg)
    if match:
        base = match.group(1).strip('"')
if not base:
    raise SystemExit("synthetic Codex did not receive the local provider URL")
target = urlsplit(base)
admission_stress = os.environ.get("PROBE_ADMISSION_STRESS") == "1"
admission_baseline_resources = product_process_resources() if admission_stress else None
connection = socket.create_connection((target.hostname, target.port), timeout=5)
connection.settimeout(5)
request_parts = [base64.b64decode(part) for part in json.loads(os.environ.get("PROBE_REQUEST_PARTS_BASE64", "[]"))]
sequential_requests = [base64.b64decode(part) for part in json.loads(os.environ.get("PROBE_SEQUENTIAL_REQUESTS_BASE64", "[]"))]
pipelined_requests = [base64.b64decode(part) for part in json.loads(os.environ.get("PROBE_PIPELINED_REQUESTS_BASE64", "[]"))]
concurrent_requests = [base64.b64decode(part) for part in json.loads(os.environ.get("PROBE_CONCURRENT_REQUESTS_BASE64", "[]"))]
parent_exit_active = os.environ.get("PROBE_PARENT_EXIT_ACTIVE") == "1"
preconnected_idle = os.environ.get("PROBE_PRECONNECTED_IDLE") == "1"
pipelined_request_parts = [base64.b64decode(part) for part in json.loads(os.environ.get("PROBE_PIPELINED_REQUEST_PARTS_BASE64", "[]"))]
pipelined_request_delay = int(os.environ.get("PROBE_PIPELINED_REQUEST_DELAY_MS", "0")) / 1000
request_parts_sent = [0]
first_request_part_finished = threading.Event()
half_close = os.environ.get("PROBE_HALF_CLOSE") == "1"
request_part_delay = int(os.environ.get("PROBE_REQUEST_PART_DELAY_MS", "0")) / 1000
writer_thread = None
if sequential_requests or pipelined_requests or concurrent_requests or parent_exit_active or preconnected_idle or admission_stress:
    pass
elif request_parts:
    def send_request_parts():
        for index, part in enumerate(request_parts):
            if index:
                time.sleep(request_part_delay)
            try:
                connection.sendall(part)
            except OSError:
                if index == 0:
                    first_request_part_finished.set()
                return
            request_parts_sent[0] += 1
            if index == 0:
                first_request_part_finished.set()
        if half_close:
            try:
                connection.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    writer_thread = threading.Thread(target=send_request_parts, daemon=True)
    writer_thread.start()
    first_request_part_finished.wait(5)
else:
    request_file = os.environ.get("PROBE_REQUEST_FILE")
    if request_file:
        with open(request_file, "rb") as source:
            request = source.read()
    else:
        request = base64.b64decode(os.environ["PROBE_REQUEST_BASE64"])
    connection.sendall(request)
    request_parts_sent[0] = 1
    if half_close:
        connection.shutdown(socket.SHUT_WR)
request_started = time.monotonic()

class RecordingReader:
    def __init__(self, reader):
        self.reader = reader
        self.lines = []
    def readline(self, *args):
        line = self.reader.readline(*args)
        self.lines.append(line)
        return line
    def read(self, *args):
        return self.reader.read(*args)
    def close(self):
        return self.reader.close()
    def __getattr__(self, name):
        return getattr(self.reader, name)

class PersistentReader(RecordingReader):
    def close(self):
        pass

class RecordingHTTPResponse(http.client.HTTPResponse):
    def __init__(self, sock, method=None):
        super().__init__(sock, method=method)
        self.raw_reader = RecordingReader(self.fp)
        self.fp = self.raw_reader
        self.raw_response_head = b""
    def begin(self):
        super().begin()
        pending = []
        for line in self.raw_reader.lines:
            pending.append(line)
            if line == b"\r\n":
                block = b"".join(pending)
                pending = []
                status_line = block.split(b"\r\n", 1)[0].split(b" ", 2)
                if len(status_line) > 1 and status_line[1] != b"100":
                    self.raw_response_head = block

result = {"status": None, "reason": "", "response_line": "", "raw_response_head_base64": "", "headers": [], "body_base64": "", "wire_body_base64": "", "wire_body_probe_complete": False, "read_error": "", "connection_closed": False, "request_parts_sent_at_response": 0, "response_elapsed_ms": 0, "response_headers_elapsed_ms": 0, "first_body_byte_elapsed_ms": 0, "interim_statuses": []}

def read_expect_response():
    response_file = RecordingReader(connection.makefile("rb"))
    interim_statuses = []
    interim_status_lines = []
    def read_head():
        start = len(response_file.lines)
        line = response_file.readline()
        if not line:
            raise ConnectionError("remote closed before response")
        version, status, reason = line.decode("iso-8859-1").rstrip("\r\n").split(" ", 2)
        headers = http.client.parse_headers(response_file)
        return version, int(status), reason, headers, b"".join(response_file.lines[start:])
    version, status, reason, headers, raw_response_head = read_head()
    while status == 100:
        interim_statuses.append(status)
        interim_status_lines.append(f"{version} {status} {reason}")
        result["interim_statuses"] = interim_statuses
        result["interim_status_lines"] = interim_status_lines
        body = base64.b64decode(os.environ.get("PROBE_BODY_AFTER_CONTINUE_BASE64", ""))
        if body:
            connection.sendall(body)
        if os.environ.get("PROBE_HALF_CLOSE_AFTER_CONTINUE") == "1":
            connection.shutdown(socket.SHUT_WR)
        version, status, reason, headers, raw_response_head = read_head()
    length = headers.get("Content-Length")
    body = response_file.read(int(length)) if length is not None else response_file.read()
    return status, reason, list(headers.items()), body, interim_statuses, interim_status_lines, f"{version} {status} {reason}", raw_response_head

try:
    request_method = os.environ.get("PROBE_REQUEST_METHOD")
    if os.environ.get("PROBE_RAW_RESPONSE") == "1":
        raw_requests = pipelined_requests or [base64.b64decode(os.environ["PROBE_REQUEST_BASE64"])]
        connection.sendall(b"".join(raw_requests))
        request_parts_sent[0] = len(raw_requests)
        if half_close:
            connection.shutdown(socket.SHUT_WR)
        raw_response = bytearray()
        deadline = time.monotonic() + int(os.environ.get("PROBE_RAW_RESPONSE_TIMEOUT_MS", "1000")) / 1000
        while time.monotonic() < deadline:
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                chunk = connection.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                result["connection_closed"] = True
                break
            raw_response.extend(chunk)
        result["wire_body_base64"] = base64.b64encode(raw_response).decode("ascii")
        result["wire_body_probe_complete"] = True
    elif admission_stress:
        baseline_resources = admission_baseline_resources
        partial_count = int(os.environ.get("PROBE_ADMISSION_PARTIAL_COUNT", "136"))
        blocker_count = int(os.environ.get("PROBE_ADMISSION_BLOCKER_COUNT", "7"))
        partial_request = base64.b64decode(os.environ["PROBE_ADMISSION_PARTIAL_REQUEST_BASE64"])
        blocker_request = base64.b64decode(os.environ["PROBE_ADMISSION_BLOCKER_REQUEST_BASE64"])
        healthy_request = base64.b64decode(os.environ["PROBE_ADMISSION_HEALTHY_REQUEST_BASE64"])
        blockers = []
        partials = []
        healthy_result = {}
        healthy_done = threading.Event()
        for _ in range(blocker_count):
            blocked = socket.create_connection((target.hostname, target.port), timeout=5)
            blocked.settimeout(5)
            blocked.sendall(blocker_request)
            blockers.append(blocked)
        time.sleep(0.1)
        connection.sendall(partial_request)
        partials.append(connection)
        for _ in range(max(0, partial_count - 1)):
            partial = socket.create_connection((target.hostname, target.port), timeout=5)
            partial.settimeout(5)
            partial.sendall(partial_request)
            partials.append(partial)
        expected_client_fds = baseline_resources[3] + partial_count + blocker_count
        admission_ready_deadline = time.monotonic() + 5
        while time.monotonic() < admission_ready_deadline:
            if product_process_resources()[3] >= expected_client_fds:
                break
            time.sleep(0.01)
        result["admission_client_fds_ready"] = product_process_resources()[3] >= expected_client_fds
        healthy = socket.create_connection((target.hostname, target.port), timeout=5)
        healthy.settimeout(5)
        def send_healthy_reuse_requests():
            try:
                started = time.monotonic()
                healthy.sendall(healthy_request)
                first = http.client.HTTPResponse(healthy)
                first.begin()
                first_body = first.read()
                healthy_result["first_status"] = first.status
                healthy_result["first_body_base64"] = base64.b64encode(first_body).decode("ascii")
                healthy_result["first_elapsed_ms"] = int((time.monotonic() - started) * 1000)
                started = time.monotonic()
                healthy.sendall(healthy_request)
                second = http.client.HTTPResponse(healthy)
                second.begin()
                second_body = second.read()
                healthy_result["second_status"] = second.status
                healthy_result["second_body_base64"] = base64.b64encode(second_body).decode("ascii")
                healthy_result["second_elapsed_ms"] = int((time.monotonic() - started) * 1000)
            except Exception as error:
                healthy_result["error"] = type(error).__name__
            finally:
                healthy_done.set()
        healthy_worker = threading.Thread(target=send_healthy_reuse_requests, daemon=True)
        healthy_worker.start()
        responded_before_release = healthy_done.wait(2.0)
        loaded_resources = product_process_resources()
        sample_ms = int(os.environ.get("PROBE_ADMISSION_RESOURCE_SAMPLE_MS", "1000"))
        time.sleep(sample_ms / 1000)
        rested_resources = product_process_resources()
        result["admission_partial_connections"] = len(partials)
        result["admission_blockers"] = len(blockers)
        result["admission_process_count"] = loaded_resources[0]
        result["admission_rss_delta_kib"] = loaded_resources[1] - baseline_resources[1]
        result["admission_fd_delta"] = loaded_resources[3] - baseline_resources[3]
        result["admission_cpu_seconds"] = rested_resources[2] - loaded_resources[2]
        result["admission_sample_seconds"] = sample_ms / 1000
        result["admission_healthy_before_release"] = responded_before_release or healthy_done.is_set()
        for held in blockers + [partial for partial in partials if partial is not connection]:
            held.close()
        healthy_done.wait(5)
        healthy_worker.join(1)
        healthy.close()
        result["admission_healthy_results"] = healthy_result
        result["status"] = healthy_result.get("first_status")
        result["reason"] = "OK" if result["status"] == 200 else ""
        result["body_base64"] = healthy_result.get("first_body_base64", "")
        result["headers"] = []
        result["request_parts_sent_at_response"] = 1
        result["response_elapsed_ms"] = healthy_result.get("first_elapsed_ms", 0)
        result["response_line"] = ""
        result["wire_body_base64"] = result["body_base64"]
        result["raw_response_head_base64"] = ""
    elif preconnected_idle:
        time.sleep(int(os.environ.get("PROBE_PRECONNECTED_SETTLE_MS", "100")) / 1000)
        baseline_resources = product_process_resources()
        partial_request = base64.b64decode(os.environ["PROBE_PRECONNECTED_PARTIAL_REQUEST_BASE64"])
        partial_count = int(os.environ.get("PROBE_PRECONNECTED_PARTIAL_COUNT", "136"))
        idle_count = int(os.environ.get("PROBE_PRECONNECTED_IDLE_COUNT", "0"))
        idle_clients = []
        for _ in range(idle_count):
            idle = socket.create_connection((target.hostname, target.port), timeout=5)
            idle.settimeout(5)
            idle_clients.append(idle)
        partial_clients = []
        for _ in range(partial_count):
            partial = socket.create_connection((target.hostname, target.port), timeout=5)
            partial.settimeout(5)
            partial.sendall(partial_request)
            partial_clients.append(partial)
        time.sleep(int(os.environ.get("PROBE_PRECONNECTED_FLOOD_SETTLE_MS", "400")) / 1000)
        loaded_resources = product_process_resources()
        time.sleep(int(os.environ.get("PROBE_PRECONNECTED_RESOURCE_SAMPLE_MS", "1000")) / 1000)
        rested_resources = product_process_resources()
        healthy_request = base64.b64decode(os.environ["PROBE_PRECONNECTED_HEALTHY_REQUEST_BASE64"])
        result.update({
            "preconnected_partial_count": len(partial_clients),
            "preconnected_idle_count": len(idle_clients),
            "admission_process_count": loaded_resources[0],
            "admission_rss_delta_kib": loaded_resources[1] - baseline_resources[1],
            "admission_fd_delta": loaded_resources[3] - baseline_resources[3],
            "admission_cpu_seconds": rested_resources[2] - loaded_resources[2],
            "admission_sample_seconds": int(os.environ.get("PROBE_PRECONNECTED_RESOURCE_SAMPLE_MS", "1000")) / 1000,
        })
        connection.sendall(healthy_request)
        response = RecordingHTTPResponse(connection, method="POST")
        response.begin()
        body = response.read()
        result.update({
            "status": response.status,
            "reason": response.reason,
            "response_line": f"HTTP/1.{response.version - 10} {response.status} {response.reason}",
            "raw_response_head_base64": base64.b64encode(response.raw_response_head).decode("ascii"),
            "headers": response.getheaders(),
            "body_base64": base64.b64encode(body).decode("ascii"),
        })
        for partial in partial_clients + idle_clients:
            partial.close()
    elif parent_exit_active:
        connection.close()
        active_client = socket.create_connection((target.hostname, target.port), timeout=5)
        active_client.settimeout(5)
        request_file = os.environ.get("PROBE_REQUEST_FILE")
        if request_file:
            with open(request_file, "rb") as source:
                active_request = source.read()
        else:
            active_request = base64.b64decode(os.environ["PROBE_REQUEST_BASE64"])
        active_client.sendall(active_request)
        trigger = os.environ["PROBE_PARENT_EXIT_TRIGGER"]
        deadline = time.monotonic() + 5
        while not os.path.exists(trigger) and time.monotonic() < deadline:
            time.sleep(0.005)
        if not os.path.exists(trigger):
            raise TimeoutError("parent-exit trigger was not released")
        holder = subprocess.Popen(
            ["/bin/sleep", "10"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(active_client.fileno(),),
        )
        result["holder_pid"] = holder.pid
        request_parts_sent[0] = 1
        active_client.close()
    elif concurrent_requests:
        connection.close()
        concurrent_results = [None] * len(concurrent_requests)
        def send_concurrent_request(index, request_bytes):
            client = socket.create_connection((target.hostname, target.port), timeout=5)
            client.settimeout(5)
            try:
                client.sendall(request_bytes)
                response = http.client.HTTPResponse(client)
                response.begin()
                body = response.read()
                concurrent_results[index] = {
                    "status": response.status,
                    "body_base64": base64.b64encode(body).decode("ascii"),
                }
            except Exception as error:
                concurrent_results[index] = {"error": type(error).__name__}
            finally:
                client.close()
        concurrent_workers = [
            threading.Thread(target=send_concurrent_request, args=(index, request_bytes), daemon=True)
            for index, request_bytes in enumerate(concurrent_requests)
        ]
        for worker in concurrent_workers:
            worker.start()
        for worker in concurrent_workers:
            worker.join(10)
        for index, worker in enumerate(concurrent_workers):
            if worker.is_alive():
                concurrent_results[index] = {"error": "TimeoutError"}
        result["concurrent_responses"] = concurrent_results
        request_parts_sent[0] = len(concurrent_requests)
        if concurrent_results and concurrent_results[0] is not None:
            first = concurrent_results[0]
            result["status"] = first.get("status")
            result["body_base64"] = first.get("body_base64", "")
    elif pipelined_requests:
        if pipelined_request_parts:
            for index, part in enumerate(pipelined_request_parts):
                connection.sendall(part)
                request_parts_sent[0] += 1
                if index + 1 < len(pipelined_request_parts) and pipelined_request_delay:
                    time.sleep(pipelined_request_delay)
        else:
            connection.sendall(b"".join(pipelined_requests))
            request_parts_sent[0] = 1
        if half_close:
            connection.shutdown(socket.SHUT_WR)
        response_file = PersistentReader(connection.makefile("rb"))
        pipelined_results = []
        response_count = int(os.environ.get("PROBE_PIPELINED_RESPONSE_COUNT", str(len(pipelined_requests))))
        for request_bytes in pipelined_requests[:response_count]:
            method = request_bytes.split(b" ", 1)[0].decode("ascii")
            response = http.client.HTTPResponse(connection, method=method)
            response.fp.close()
            response.fp = response_file
            response.begin()
            body = response.read()
            head_wire_body = b""
            if method == "HEAD" and response.getheader("Transfer-Encoding", "").lower() == "chunked":
                if response_file.peek(1).startswith(b"0"):
                    head_wire_body = response_file.read(5)
            pipelined_results.append({
                "status": response.status,
                "reason": response.reason,
                "headers": response.getheaders(),
                "body_base64": base64.b64encode(body).decode("ascii"),
                "head_wire_body_base64": base64.b64encode(head_wire_body).decode("ascii"),
            })
            result["pipelined_responses"] = pipelined_results
        response_file.reader.close()
        if pipelined_results:
            first = pipelined_results[0]
            result.update({
                "status": first["status"],
                "reason": first["reason"],
                "headers": first["headers"],
                "body_base64": first["body_base64"],
            })
    elif sequential_requests:
        sequential_results = []
        for request_bytes in sequential_requests:
            connection.sendall(request_bytes)
            request_parts_sent[0] += 1
            response = http.client.HTTPResponse(connection)
            response.begin()
            body = response.read()
            sequential_results.append({
                "status": response.status,
                "reason": response.reason,
                "headers": response.getheaders(),
                "body_base64": base64.b64encode(body).decode("ascii"),
            })
            result["sequential_responses"] = sequential_results
            if response.will_close and os.environ.get("PROBE_CONTINUE_AFTER_WILL_CLOSE") != "1":
                break
        if sequential_results:
            first = sequential_results[0]
            result.update({
                "status": first["status"],
                "reason": first["reason"],
                "headers": first["headers"],
                "body_base64": first["body_base64"],
            })
        second_client_request = os.environ.get("PROBE_SECOND_CLIENT_REQUEST_BASE64", "")
        if second_client_request:
            reused_partial_request = base64.b64decode(
                os.environ.get("PROBE_REUSED_PARTIAL_REQUEST_BASE64", "")
            )
            if reused_partial_request:
                connection.sendall(reused_partial_request)
            second_client = socket.create_connection((target.hostname, target.port), timeout=5)
            second_client.settimeout(5)
            second_client_done = threading.Event()
            def read_second_client_response():
                try:
                    second_client.sendall(base64.b64decode(second_client_request))
                    second_response = http.client.HTTPResponse(second_client)
                    second_response.begin()
                    second_body = second_response.read()
                    result["second_client"] = {
                        "status": second_response.status,
                        "reason": second_response.reason,
                        "headers": second_response.getheaders(),
                        "body_base64": base64.b64encode(second_body).decode("ascii"),
                    }
                except Exception as error:
                    result["second_client_error"] = type(error).__name__
                finally:
                    second_client.close()
                    second_client_done.set()
            if reused_partial_request:
                second_client_worker = threading.Thread(target=read_second_client_response, daemon=True)
                second_client_worker.start()
                time.sleep(int(os.environ.get("PROBE_PARTIAL_HOLD_MS", "300")) / 1000)
                result["second_client_responded_before_partial_close"] = second_client_done.is_set()
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
                second_client_worker.join(5)
                result["second_client_finished_after_partial_close"] = second_client_done.is_set()
            else:
                read_second_client_response()
        hold_first_client_ms = int(os.environ.get("PROBE_HOLD_FIRST_CLIENT_MS", "0"))
        if hold_first_client_ms > 0:
            holder = subprocess.Popen(
                ["/bin/sleep", str(hold_first_client_ms / 1000)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(connection.fileno(),),
            )
            result["holder_pid"] = holder.pid
        fairness_extra_connections = int(os.environ.get("PROBE_FAIRNESS_EXTRA_CONNECTIONS", "0"))
        fairness_churn_count = int(os.environ.get("PROBE_FAIRNESS_CHURN_COUNT", "0"))
        if fairness_extra_connections or fairness_churn_count:
            fairness_request = base64.b64decode(os.environ["PROBE_FAIRNESS_REQUEST_BASE64"])
            fairness_churn_request = base64.b64decode(os.environ["PROBE_FAIRNESS_CHURN_REQUEST_BASE64"])
            fairness_connections = [connection]
            for _ in range(fairness_extra_connections):
                parked = socket.create_connection((target.hostname, target.port), timeout=5)
                parked.settimeout(5)
                parked.sendall(fairness_request)
                parked_response = http.client.HTTPResponse(parked)
                parked_response.begin()
                parked_response.read()
                fairness_connections.append(parked)
            fairness_lock = threading.Lock()
            fairness_reused_statuses = []
            fairness_churn_statuses = []
            fairness_errors = []
            fairness_reused_stream_finished = threading.Event()
            fairness_churn_interleaved = []
            def reuse_parked_connection(parked):
                try:
                    repeat_count = int(os.environ.get("PROBE_FAIRNESS_REPEATS", "1")) if parked is connection else 1
                    for _ in range(repeat_count):
                        parked.sendall(fairness_request)
                        parked_response = http.client.HTTPResponse(parked)
                        parked_response.begin()
                        parked_response.read()
                        with fairness_lock:
                            fairness_reused_statuses.append(parked_response.status)
                except Exception as error:
                    with fairness_lock:
                        fairness_errors.append(type(error).__name__)
                finally:
                    if parked is connection:
                        fairness_reused_stream_finished.set()
            def churn_new_connections():
                for _ in range(fairness_churn_count):
                    fresh = socket.create_connection((target.hostname, target.port), timeout=5)
                    fresh.settimeout(5)
                    try:
                        fresh.sendall(fairness_churn_request)
                        fresh_response = http.client.HTTPResponse(fresh)
                        fresh_response.begin()
                        fresh_response.read()
                        with fairness_lock:
                            if not fairness_churn_statuses:
                                fairness_churn_interleaved.append(not fairness_reused_stream_finished.is_set())
                            fairness_churn_statuses.append(fresh_response.status)
                    except Exception as error:
                        with fairness_lock:
                            fairness_errors.append(type(error).__name__)
                    finally:
                        fresh.close()
            fairness_workers = [
                threading.Thread(target=reuse_parked_connection, args=(parked,), daemon=True)
                for parked in fairness_connections
            ]
            for fairness_worker in fairness_workers:
                fairness_worker.start()
            churn_worker = threading.Thread(target=churn_new_connections, daemon=True)
            churn_worker.start()
            for fairness_worker in fairness_workers:
                fairness_worker.join(15)
            churn_worker.join(15)
            result["fairness_reused_statuses"] = fairness_reused_statuses
            result["fairness_churn_statuses"] = fairness_churn_statuses
            result["fairness_errors"] = fairness_errors
            result["fairness_churn_interleaved"] = fairness_churn_interleaved
            result["fairness_workers_finished"] = not churn_worker.is_alive() and all(
                not fairness_worker.is_alive() for fairness_worker in fairness_workers
            )
            for parked in fairness_connections:
                parked.close()
    elif os.environ.get("PROBE_EXPECT_HANDSHAKE") == "1":
        status, reason, headers, body, interim_statuses, interim_status_lines, response_line, raw_response_head = read_expect_response()
        result.update({
            "status": status,
            "reason": reason,
            "response_line": response_line,
            "raw_response_head_base64": base64.b64encode(raw_response_head).decode("ascii"),
            "headers": headers,
            "body_base64": base64.b64encode(body).decode("ascii"),
            "interim_statuses": interim_statuses,
            "interim_status_lines": interim_status_lines,
        })
    else:
        response = RecordingHTTPResponse(connection, method=request_method)
        response.begin()
        result["response_headers_elapsed_ms"] = int((time.monotonic() - request_started) * 1000)
        interim_statuses = []
        wire_body = b""
        wire_body_probe_complete = False
        if request_method == "HEAD" and response.fp:
            connection.settimeout(0.25)
            try:
                wire_body = response.fp.peek(4096)
                wire_body_probe_complete = True
            except socket.timeout:
                pass
            finally:
                connection.settimeout(5)
        if request_method == "HEAD":
            body = response.read()
        else:
            first_body_byte = response.read(1)
            result["first_body_byte_elapsed_ms"] = int((time.monotonic() - request_started) * 1000)
            body = first_body_byte + response.read()
        response_version = f"HTTP/1.{response.version - 10}"
        result.update({
            "status": response.status,
            "response_line": f"{response_version} {response.status} {response.reason}",
            "raw_response_head_base64": base64.b64encode(response.raw_response_head).decode("ascii"),
            "interim_statuses": interim_statuses,
            "reason": response.reason,
            "headers": response.getheaders(),
            "body_base64": base64.b64encode(body).decode("ascii"),
            "wire_body_base64": base64.b64encode(wire_body).decode("ascii"),
            "wire_body_probe_complete": wire_body_probe_complete,
        })
    result["request_parts_sent_at_response"] = request_parts_sent[0]
    result["response_elapsed_ms"] = int((time.monotonic() - request_started) * 1000)
    if os.environ.get("PROBE_CHECK_CLOSE") == "1":
        connection.settimeout(0.5)
        try:
            result["connection_closed"] = connection.recv(1) == b""
        except socket.timeout:
            pass
        except OSError:
            result["connection_closed"] = True
        finally:
            connection.settimeout(5)
    saturation_count = int(os.environ.get("PROBE_SATURATION_EXTRA_CONNECTIONS", "0"))
    if saturation_count:
        saturation_request = base64.b64decode(os.environ["PROBE_SATURATION_REQUEST_BASE64"])
        saturation_connections = []
        for _ in range(saturation_count):
            saturated = socket.create_connection((target.hostname, target.port), timeout=5)
            saturated.settimeout(5)
            saturated.sendall(saturation_request)
            saturated_response = http.client.HTTPResponse(saturated)
            saturated_response.begin()
            saturated_response.read()
            saturation_connections.append(saturated)
        oldest_partial = base64.b64decode(
            os.environ.get("PROBE_SATURATION_OLDEST_PARTIAL_BASE64", "")
        )
        if oldest_partial:
            connection.sendall(oldest_partial)
        overflow = socket.create_connection((target.hostname, target.port), timeout=5)
        overflow.settimeout(5)
        overflow.sendall(saturation_request)
        if oldest_partial:
            time.sleep(0.05)
            connection.sendall(saturation_request[len(oldest_partial):])
            oldest_response = http.client.HTTPResponse(connection)
            oldest_response.begin()
            oldest_body = oldest_response.read()
            result["saturation_oldest_status"] = oldest_response.status
            result["saturation_oldest_body_base64"] = base64.b64encode(oldest_body).decode("ascii")
        overflow_response = http.client.HTTPResponse(overflow)
        overflow_response.begin()
        overflow_body = overflow_response.read()
        result["saturation_overflow_status"] = overflow_response.status
        result["saturation_overflow_body_base64"] = base64.b64encode(overflow_body).decode("ascii")
        result["saturation_held_connections"] = len(saturation_connections)
        connection.settimeout(1)
        try:
            result["saturation_oldest_closed"] = connection.recv(1) == b""
        except socket.timeout:
            result["saturation_oldest_closed"] = False
        connection.settimeout(5)
        overflow.close()
        for saturated in saturation_connections:
            saturated.close()
except Exception as error:
    result["read_error"] = type(error).__name__
finally:
    connection.close()
followup_hex = os.environ.get("PROBE_FOLLOWUP_REQUEST_HEX", "")
if followup_hex:
    followup_connection = socket.create_connection((target.hostname, target.port), timeout=5)
    followup_connection.settimeout(5)
    followup_connection.sendall(bytes.fromhex(followup_hex))
    followup_response = http.client.HTTPResponse(followup_connection)
    followup_response.begin()
    followup_body = followup_response.read()
    result.update({
        "followup_status": followup_response.status,
        "followup_body_base64": base64.b64encode(followup_body).decode("ascii"),
    })
    followup_connection.close()
with open(os.environ["PROBE_RESULT_PATH"], "w", encoding="utf-8") as output:
    json.dump(result, output, separators=(",", ":"))
'''
    path.write_text("#!" + sys.executable + "\n" + source, encoding="utf-8")
    path.chmod(0o700)


def configured_modex_worker_capacity(worker_count):
    driver = Path(os.environ.get(
        "MODEX_LOCAL_REWRITE_DRIVER", ROOT / "build/tests/local_rewrite_driver",
    ))
    if not driver.is_file():
        raise AssertionError(f"Build the local relay test driver first: {driver}")
    with tempfile.TemporaryDirectory(prefix="modex-worker-count-probe-") as temporary:
        root = Path(temporary)
        for name in ("home", "prodex", "config", "data", "cache", "tmp"):
            (root / name).mkdir(mode=0o700)
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
            "PRODEX_RUNTIME_PROXY_WORKER_COUNT": str(worker_count),
        }
        result = subprocess.run(
            [str(driver), "--worker-info"],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"worker count probe failed: {result.stderr.decode('utf-8', errors='replace')}"
            )
        match = re.fullmatch(
            r"WORKERS=(\d+) PARALLELISM=(\d+)",
            result.stdout.decode("ascii").strip(),
        )
        if not match:
            raise AssertionError(f"worker info probe returned invalid output: {result.stdout!r}")
        return int(match.group(1)), int(match.group(2))


def request_bytes(headers=(), body=REQUEST_BODY, target=b"/v1/responses", method=b"POST", version=b"HTTP/1.1"):
    all_headers = [
        ("Host", "127.0.0.1"),
        *headers,
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ]
    return (
        method + b" " + target + b" " + version + b"\r\n"
        + b"".join(name.encode() + b": " + value.encode() + b"\r\n" for name, value in all_headers)
        + b"\r\n" + body
    )


def large_request_head_case(head_bytes, target=b"/v1/responses"):
    empty = request_bytes(headers=(("X-Pad", ""),), target=target)
    value_bytes = head_bytes - empty.index(b"\r\n\r\n")
    request = request_bytes(headers=(("X-Pad", "x" * value_bytes),), target=target)
    if request.index(b"\r\n\r\n") != head_bytes:
        raise AssertionError(f"request head did not reach {head_bytes} bytes")
    return {
        "name": f"large_request_head_{head_bytes}",
        "request": request,
        "expected_status": 200,
        "expected_body": PROVIDER_RESPONSE if target == b"/v1/chat/completions" else RESPONSES_RESPONSE,
        "compare_upstream_request": True,
        "upstream": True,
    }


def large_user_agent_case(head_bytes=1024 * 1024):
    empty = request_bytes(headers=(("User-Agent", ""),))
    value_bytes = head_bytes - empty.index(b"\r\n\r\n")
    request = request_bytes(headers=(("User-Agent", "u" * value_bytes),))
    if request.index(b"\r\n\r\n") != head_bytes:
        raise AssertionError(f"request head did not reach {head_bytes} bytes")
    return {
        "name": f"large_user_agent_{head_bytes}",
        "request": request,
        "expected_status": 200,
        "expected_body": RESPONSES_RESPONSE,
        "upstream": True,
        "expected_user_agent_count": 2,
    }


def large_user_agent_value_case(value_bytes, target=b"/v1/responses"):
    request = request_bytes(headers=(("User-Agent", "u" * value_bytes),), target=target)
    return {
        "name": f"large_user_agent_value_{value_bytes}",
        "request": request,
        "expected_status": 200,
        "expected_body": PROVIDER_RESPONSE if target == b"/v1/chat/completions" else RESPONSES_RESPONSE,
        "upstream": True,
        "expected_user_agent_count": 2,
        "expected_error_body": b"upstream request failed",
    }


def many_small_header_case(head_bytes, count=4096, target=b"/v1/responses"):
    base = request_bytes(target=target)
    names = [f"X-Pad-{index:04d}" for index in range(count)]
    remaining = head_bytes - base.index(b"\r\n\r\n") - sum(len(name) + 4 for name in names)
    if remaining < 0:
        raise AssertionError(f"{count} headers do not fit in a {head_bytes}-byte request head")
    value_bytes, extra = divmod(remaining, count)
    headers = [
        (name, "x" * (value_bytes + (index < extra)))
        for index, name in enumerate(names)
    ]
    request = request_bytes(headers=headers, target=target)
    if request.index(b"\r\n\r\n") != head_bytes:
        raise AssertionError(f"request head did not reach {head_bytes} bytes")
    return {
        "name": f"many_small_request_headers_{head_bytes}",
        "request": request,
        "expected_status": 200,
        "expected_body": PROVIDER_RESPONSE if target == b"/v1/chat/completions" else RESPONSES_RESPONSE,
        "compare_upstream_request": True,
        "upstream": True,
        "expected_header_count": count,
    }


def many_connection_token_headers_case(head_bytes=1024 * 1024, count=8192):
    connection_value = ", ".join(f"x-hide-{index:04d}" for index in range(count))
    hidden_names = [f"X-HiDe-{index:04d}" for index in range(count)]
    pad_names = [f"X-Pad-{index:04d}" for index in range(count)]
    names = hidden_names + pad_names
    base = request_bytes(headers=(("Connection", connection_value),), target=b"/v1/chat/completions")
    remaining = head_bytes - base.index(b"\r\n\r\n") - sum(len(name) + 4 for name in names)
    if remaining < 0:
        raise AssertionError(f"{count} connection tokens and fields do not fit in a {head_bytes}-byte request head")
    value_bytes, extra = divmod(remaining, len(names))
    fields = [
        (name, ("y" if index < count else "x") * (value_bytes + (index < extra)))
        for index, name in enumerate(names)
    ]
    request = request_bytes(
        headers=(("Connection", connection_value), *fields),
        target=b"/v1/chat/completions",
    )
    if request.index(b"\r\n\r\n") != head_bytes:
        raise AssertionError(f"request head did not reach {head_bytes} bytes")
    return {
        "name": f"many_connection_tokens_and_headers_{head_bytes}",
        "request": request,
        "expected_status": 200,
        "expected_body": PROVIDER_RESPONSE,
        "upstream": True,
        "expected_header_count": count,
        "expected_hidden_count": count,
    }


def expected_pad_headers(request):
    head = request.split(b"\r\n\r\n", 1)[0]
    result = {}
    for line in head.split(b"\r\n")[1:]:
        name, separator, value = line.partition(b":")
        if separator and name.lower().startswith(b"x-pad"):
            result[name.decode("ascii").lower()] = value.lstrip(b" \t")
    return result


def upgrade_eof_cases():
    variants = [
        ("h2c", (("Connection", "Upgrade"), ("Upgrade", "h2c")), len(REQUEST_BODY), 200),
        ("connection_only", (("Connection", "Upgrade"),), 0, 200),
        ("connection_substring", (("Connection", "preupgradepost"),), 0, 200),
        ("first_upgrade", (("Connection", "Upgrade"), ("Connection", "keep-alive"), ("Upgrade", "h2c")), 0, 200),
        ("second_upgrade", (("Connection", "keep-alive"), ("Connection", "Upgrade"), ("Upgrade", "h2c")), 0, 502),
        ("length_exceeds_actual", (("Connection", "Upgrade"), ("Upgrade", "h2c")), len(REQUEST_BODY) + 9, 200),
        ("oversized_declared", (("Connection", "Upgrade"), ("Upgrade", "h2c")), 67108865, 413),
    ]
    cases = []
    for name, headers, declared, status in variants:
        request = request_bytes(headers).replace(
            b"Content-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n",
            b"Content-Length: " + str(declared).encode() + b"\r\n",
        )
        cases.append({"name": name, "request": request, "half_close": True, "status": status})
    raw_chunked = request_bytes((("Connection", "Upgrade"), ("Upgrade", "h2c"))).replace(
        b"Content-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n",
        b"Transfer-Encoding: chunked\r\n",
    )
    cases.append({"name": "upgrade_takes_precedence_over_chunked", "request": raw_chunked, "half_close": True, "status": 200})
    request = request_bytes((("Connection", "Upgrade"), ("Upgrade", "h2c")))
    split = len(request) - len(REQUEST_BODY) // 2
    cases.append({
        "name": "fragmented_upgrade_body", "request": request, "half_close": True,
        "request_parts": [request[:split], request[split:]], "request_part_delay_ms": 100,
        "expected_request_parts_sent": 2, "status": 200,
    })
    return cases


def expectation_request_case(
    name,
    expectations,
    *,
    target=b"/v1/responses",
    body=REQUEST_BODY,
    body_after_continue=None,
    half_close=False,
    half_close_after_continue=False,
    extra_headers=(),
    version=b"HTTP/1.1",
):
    request = request_bytes(
        (*extra_headers, *(("Expect", value) for value in expectations)),
        body=body,
        target=target,
        version=version,
    )
    header_end = request.index(b"\r\n\r\n") + 4
    return {
        "name": name,
        "request": request,
        "request_parts": [request[:header_end]],
        "body_after_continue": body if body_after_continue is None else body_after_continue,
        "expect_handshake": True,
        "half_close": half_close,
        "half_close_after_continue": half_close_after_continue,
        "check_close": True,
    }


def raw_expectation_case(name, request, *, half_close=False):
    return {
        "name": name,
        "request": request,
        "expect_handshake": True,
        "half_close": half_close,
        "check_close": True,
    }


def chunked_request_case(
    name,
    *,
    extension=b"",
    trailer=b"",
    trailer_terminated=True,
    target=b"/v1/responses",
    half_close=False,
    check_close=False,
    expected_connection_closed=None,
):
    invalid_target = target != b"/v1/responses"
    rejected = bool(trailer) or not trailer_terminated
    chunk_line = format(len(REQUEST_BODY), "X").encode("ascii") + extension
    chunked_body = chunk_line + b"\r\n" + REQUEST_BODY + b"\r\n0\r\n" + trailer
    if trailer_terminated:
        chunked_body += b"\r\n"
    if invalid_target:
        expected_status = 400
        expected_reason = "Bad Request"
        expected_body = INVALID_REQUEST_TARGET_BODY
        upstream = False
    else:
        expected_status = 502 if rejected else 200
        expected_reason = "Bad Gateway" if rejected else "OK"
        expected_body = b"gateway request capture failed" if rejected else RESPONSES_RESPONSE
        upstream = not rejected
    case = {
        "name": name,
        "request": (
            b"POST " + target + b" HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
            + chunked_body
        ),
        "expected_status": expected_status,
        "expected_reason": expected_reason,
        "expected_body": expected_body,
        "expected_headers": {} if not upstream else {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(RESPONSES_RESPONSE)),
        },
        "compare_response_body": upstream,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": upstream,
        "upstream": upstream,
        "half_close": half_close,
        "check_close": check_close,
    }
    if expected_connection_closed is not None:
        case["expected_connection_closed"] = expected_connection_closed
    return case


def fragmented_chunked_request_case(name, *, trailer):
    case = chunked_request_case(name, trailer=trailer, check_close=True)
    trailer_start = case["request"].rfind(b"0\r\n") + 3
    case["request_parts"] = [
        case["request"][:trailer_start],
        case["request"][trailer_start:trailer_start + 1],
        case["request"][trailer_start + 1:],
    ]
    case["request_part_delay_ms"] = 500
    case["expected_request_parts_sent"] = 2
    case["expected_connection_closed"] = {"oracle": False, "modex": True}
    return case


def fragmented_empty_chunked_request_case(name):
    case = chunked_request_case(name, check_close=True)
    empty_trailer_start = case["request"].rfind(b"0\r\n") + 3
    case["request_parts"] = [
        case["request"][:empty_trailer_start],
        b"\r",
        b"\n",
    ]
    case["request_part_delay_ms"] = 500
    case["expected_request_parts_sent"] = 3
    case["expected_connection_closed"] = {"oracle": False, "modex": False}
    return case


def delayed_invalid_target_chunked_request_case(name, *, body, half_close=False, fragmented=True):
    target = b"http://example.test/v1/responses"
    header = (
        b"POST " + target + b" HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
    )
    return {
        "name": name,
        "request": header + body,
        "request_parts": [header, body] if fragmented else [],
        "request_part_delay_ms": 500 if fragmented else 0,
        "expected_request_parts_sent": 1,
        "expected_connection_closed": {"oracle": False, "modex": True},
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": False,
        "upstream": False,
        "half_close": half_close,
        "check_close": True,
    }


def invalid_target_case(name, target):
    return {
        "name": name,
        "request": request_bytes(target=target),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    }


def method_case(name, method, target):
    return {
        "name": name,
        "request": request_bytes(
            headers=(("Connection", "close"),) if method == b"HEAD" else (),
            target=target,
            method=method,
        ),
        "expected_status": 501,
        "expected_reason": "Not Implemented",
        "expected_body": b"" if method == b"HEAD" else None,
        "expected_upstream_method": method.decode("ascii"),
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def success_method_case(name, method, target, response_kind="json", body=REQUEST_BODY):
    request_headers = [("X-Oracle-Response", response_kind)]
    if method == b"HEAD":
        request_headers.insert(0, ("Connection", "close"))
    if method == b"HEAD":
        expected_body = b""
        expected_headers = (
            {"content-type": "text/plain; charset=utf-8", "content-length": "40"}
            if target == b"/v1/responses"
            else {"content-type": "application/json", "content-length": "0"}
        )
    elif response_kind == "sse":
        expected_body = PROVIDER_SSE_RESPONSE if target == b"/v1/chat/completions" else None
        expected_headers = {
            "content-type": "text/event-stream" if target == b"/v1/chat/completions" else "text/event-stream; charset=utf-8",
            "transfer-encoding": "chunked",
        }
    else:
        expected_body = PROVIDER_RESPONSE if target == b"/v1/chat/completions" else RESPONSES_RESPONSE
        expected_headers = {
            "content-type": "application/json" if target == b"/v1/chat/completions" else "application/json; charset=utf-8",
            "content-length": str(len(expected_body)),
        }
    return {
        "name": name,
        "request": request_bytes(
            request_headers,
            body=body,
            target=target,
            method=method,
        ),
        "expected_status": 502 if method == b"HEAD" and target == b"/v1/responses" else 200,
        "expected_reason": "Bad Gateway" if method == b"HEAD" and target == b"/v1/responses" else "OK",
        "expected_body": expected_body,
        "expected_headers": expected_headers,
        "compare_response_body": method != b"HEAD",
        "expected_upstream_method": method.decode("ascii"),
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def head_bodyless_sse_case(status, version=b"HTTP/1.1"):
    suffix = "_http_1_0" if version == b"HTTP/1.0" else ""
    return {
        "name": f"head_chat_completions_{status}_sse_framing{suffix}",
        "request": request_bytes(
            (("Connection", "close"), ("X-Oracle-Response", f"sse-{status}")),
            target=b"/v1/chat/completions",
            method=b"HEAD",
            version=version,
        ),
        "expected_response_line": f"HTTP/1.1 {status} {'No Content' if status == 204 else 'Not Modified'}",
        "expected_status": status,
        "expected_reason": "No Content" if status == 204 else "Not Modified",
        "expected_body": b"",
        "expected_headers": {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked",
        },
        "expected_wire_body": {"oracle": b"0\r\n\r\n", "modex": b"0\r\n\r\n"},
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "HEAD",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def head_sse_case(version=b"HTTP/1.1"):
    suffix = "_http_1_0" if version == b"HTTP/1.0" else ""
    return {
        "name": f"head_chat_completions_200_sse_framing{suffix}",
        "request": request_bytes(
            (("Connection", "close"), ("X-Oracle-Response", "sse")),
            target=b"/v1/chat/completions",
            method=b"HEAD",
            version=version,
        ),
        "expected_response_line": "HTTP/1.1 200 OK",
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_body": b"",
        "expected_headers": {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked",
        },
        "expected_wire_body": {"oracle": b"0\r\n\r\n", "modex": b"0\r\n\r\n"},
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "HEAD",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def response_status_case(status, reason, version=b"HTTP/1.1"):
    return {
        "name": f"chat_completions_status_{status}_reason",
        "request": request_bytes(
            (("X-Oracle-Response", f"status-{status}"),),
            target=b"/v1/chat/completions",
            version=version,
        ),
        **({"expected_response_line": f"{version.decode()} {status} {reason}"} if version == b"HTTP/1.0" else {}),
        "expected_status": status,
        "expected_reason": reason,
        "expected_body": PROVIDER_RESPONSE,
        "expected_headers": {
            "content-type": "application/json",
            "content-length": str(len(PROVIDER_RESPONSE)),
        },
        "compare_response_body": True,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def http_1_0_status_case(status, reason, response_kind):
    case = response_status_case(status, reason, version=b"HTTP/1.0")
    case["name"] = f"http_1_0_chat_completions_status_{status}"
    case["request"] = request_bytes(
        (("X-Oracle-Response", response_kind),),
        target=b"/v1/chat/completions",
        version=b"HTTP/1.0",
    )
    case["check_close"] = True
    case["expected_connection_closed"] = {"oracle": True, "modex": True}
    return case


def ordinary_http_upgrade_case(name, value):
    return {
        "name": name,
        "request": request_bytes((("Upgrade", value),)),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_body": RESPONSES_RESPONSE,
        "expected_headers": {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(RESPONSES_RESPONSE)),
        },
        "compare_response_body": True,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    }


def websocket_upgrade_declared_body_case(target=b"/v1/responses"):
    request = request_bytes(
        (("Connection", "Upgrade"), ("Upgrade", "websocket")),
        body=b"x" * 100, target=target,
    ).split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
    return {
        "name": "websocket_upgrade_does_not_wait_for_declared_body",
        "request": request,
        "request_parts": [request],
        "expected_status": 426,
        "expected_reason": "Upgrade Required",
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    }


CASES = (
    {
        "name": "leading_request_line_whitespace_is_trimmed",
        "request": b" \t" + request_bytes((('Connection', 'close'),), version=b'HTTP/1.0'),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.0 200 OK",
        "expected_body": RESPONSES_RESPONSE,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "http_1_2_request_line_is_malformed",
        "request": b"POST /v1/responses HTTP/1.2\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Length: 0\r\n\r\n",
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_response_line": "HTTP/1.1 400 Bad Request",
        "expected_body": b"",
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "http_0_9_request_uses_request_version",
        "request": request_bytes((('Connection', 'close'),), version=b'HTTP/0.9'),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.0 200 OK",
        "expected_wire_response_line": "HTTP/0.9 200 OK",
        "expected_body": RESPONSES_RESPONSE,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "http_0_9_malformed_header_uses_request_version",
        "request": b"POST /v1/responses HTTP/0.9\r\nHost: 127.0.0.1\r\nMalformed\r\nContent-Length: 0\r\n\r\n",
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_response_line": "HTTP/1.0 400 Bad Request",
        "expected_wire_response_line": "HTTP/0.9 400 Bad Request",
        "expected_body": b"",
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "http_0_9_expect_continue_uses_request_version",
        "request": b"POST /v1/responses HTTP/0.9\r\nHost: 127.0.0.1\r\nConnection: close\r\nExpect: 100-continue\r\nContent-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n\r\n",
        "body_after_continue": REQUEST_BODY,
        "expect_handshake": True,
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/0.9 200 OK",
        "expected_wire_response_line": "HTTP/0.9 200 OK",
        "expected_body": RESPONSES_RESPONSE,
        "expected_interim_statuses": [100],
        "expected_interim_status_lines": ["HTTP/0.9 100 Continue"],
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "http_0_9_truncated_declared_body_closes",
        "request": b"POST /v1/responses HTTP/0.9\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "malformed_request_line_missing_version",
        "request": b"POST /v1/responses\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_response_line": "HTTP/1.1 400 Bad Request",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "malformed_request_line_extra_token",
        "request": b"POST /v1/responses HTTP/1.1 extra\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 502,
        "expected_body": b"upstream request failed",
        "upstream": False,
    },
    {
        "name": "http_1_0_request_line_extra_token_keeps_request_version",
        "request": b"POST /v1/responses HTTP/1.0 extra\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 502,
        "expected_reason": "Bad Gateway",
        "expected_response_line": "HTTP/1.0 502 Bad Gateway",
        "expected_body": b"upstream request failed",
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "duplicate_request_versions_keep_first_version",
        "request": b"POST /v1/responses HTTP/1.1 HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n\r\n" + REQUEST_BODY,
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.1 200 OK",
        "expected_body": RESPONSES_RESPONSE,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "malformed_request_target_spacing",
        "request": b"POST /v1/responses bad HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "malformed_header",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nMalformed\r\nConnection: close\r\n\r\n",
        "expected_status": 400,
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "websocket_without_connection_header",
        "request": request_bytes((("Upgrade", "websocket"),)),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    {
        "name": "websocket_duplicate_upgrade",
        "request": request_bytes((("Upgrade", "websocket"), ("Upgrade", "websocket"))),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    {
        "name": "websocket_duplicate_connection",
        "request": request_bytes((
            ("Connection", "keep-alive"), ("Connection", "Upgrade"),
            ("Upgrade", "websocket"),
        )),
        "expected_status": 426,
        "expected_body": WEBSOCKET_FALLBACK,
        "upstream": False,
    },
    ordinary_http_upgrade_case("h2c_without_connection_upgrade", "h2c"),
    ordinary_http_upgrade_case("mixed_case_h2c_without_connection_upgrade", "H2C"),
    ordinary_http_upgrade_case("other_protocol_without_connection_upgrade", "example/1"),
    chunked_request_case("chunked_request_with_empty_trailers"),
    chunked_request_case("chunk_extension_without_trailers", extension=b";synthetic=yes"),
    chunked_request_case(
        "nonempty_chunked_trailer_rejected",
        trailer=b"X-Trace: synthetic\r\n",
    ),
    chunked_request_case(
        "malformed_chunked_trailer_rejected",
        trailer=b"X-Trace synthetic\r\n",
    ),
    chunked_request_case(
        "truncated_nonempty_chunked_trailer_rejected",
        trailer=b"X-Trace: partial",
        trailer_terminated=False,
        half_close=True,
        check_close=True,
    ),
    chunked_request_case(
        "truncated_empty_chunked_terminator_rejected",
        trailer_terminated=False,
        half_close=True,
        check_close=True,
    ),
    chunked_request_case(
        "oversized_chunked_trailer_rejected",
        trailer=b"X-Pad: " + b"x" * 65537 + b"\r\n",
        check_close=True,
        expected_connection_closed={"oracle": False, "modex": True},
    ),
    chunked_request_case(
        "invalid_target_precedes_valid_chunked_trailer",
        target=b"http://example.test/v1/responses",
        trailer=b"X-Trace: synthetic\r\n",
        check_close=True,
        expected_connection_closed={"oracle": False, "modex": True},
    ),
    chunked_request_case(
        "invalid_target_precedes_malformed_chunked_trailer",
        target=b"http://example.test/v1/responses",
        trailer=b"X-Trace synthetic\r\n",
        check_close=True,
        expected_connection_closed={"oracle": False, "modex": True},
    ),
    delayed_invalid_target_chunked_request_case(
        "invalid_target_precedes_delayed_chunked_trailer",
        body=(format(len(REQUEST_BODY), "X").encode("ascii") + b"\r\n" + REQUEST_BODY
              + b"\r\n0\r\nX-Trace: synthetic\r\n\r\n"),
    ),
    delayed_invalid_target_chunked_request_case(
        "invalid_target_precedes_truncated_chunk_data",
        body=b"5\r\nab",
        half_close=True,
        fragmented=False,
    ),
    delayed_invalid_target_chunked_request_case(
        "invalid_target_precedes_missing_chunk_terminator",
        body=b"0\r\n",
        half_close=True,
        fragmented=False,
    ) | {"expected_connection_closed": {"oracle": None, "modex": True}},
    fragmented_chunked_request_case(
        "fragmented_nonempty_chunked_trailer_rejected",
        trailer=b"X-Trace: synthetic\r\n",
    ),
    fragmented_empty_chunked_request_case("fragmented_empty_chunked_terminator_accepted"),
    {
        "name": "truncated_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "websocket_truncated_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "oversized_declared_body",
        "request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: 67108865\r\n\r\n",
        "expected_status": 413,
        "expected_reason": "Payload Too Large",
        "expected_body": b"proxied request body is too large",
        "upstream": False,
    },
    {
        "name": "valid_request_control",
        "request": request_bytes((("Connection", "close"),)),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
    {
        "name": "http_1_0_buffered_responses_keep_request_version",
        "request": request_bytes((("Connection", "close"),), version=b"HTTP/1.0"),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.0 200 OK",
        "expected_body": RESPONSES_RESPONSE,
        "expected_headers": {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(RESPONSES_RESPONSE)),
        },
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "http_1_0_head_response_keeps_request_version",
        "request": request_bytes(
            (("Connection", "close"), ("X-Oracle-Response", "json")),
            target=b"/v1/chat/completions",
            method=b"HEAD",
            version=b"HTTP/1.0",
        ),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.0 200 OK",
        "expected_body": b"",
        "expected_headers": {"content-length": "0"},
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "expected_upstream_method": "HEAD",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    {
        "name": "http_1_0_unsupported_route_error_keeps_request_version",
        "request": request_bytes(target=b"/v1/not-real", version=b"HTTP/1.0"),
        "expected_status": 404,
        "expected_reason": "Not Found",
        "expected_response_line": "HTTP/1.0 404 Not Found",
        "expected_body": UNSUPPORTED_ROUTE_BODY,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "http_1_0_invalid_target_keeps_request_version",
        "request": request_bytes(target=b"http://example.test/v1/responses", version=b"HTTP/1.0"),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_response_line": "HTTP/1.0 400 Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "http_1_0_fragment_target_keeps_request_version",
        "request": request_bytes(target=b"/v1/responses#fragment", version=b"HTTP/1.0"),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_response_line": "HTTP/1.0 400 Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        "name": "http_1_0_malformed_header_keeps_request_version",
        "request": b"POST /v1/responses HTTP/1.0\r\nHost: 127.0.0.1\r\nMalformed\r\nContent-Length: 0\r\n\r\n",
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_response_line": "HTTP/1.0 400 Bad Request",
        "expected_body": b"",
        "check_close": True,
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        **expectation_request_case("single_valid_expect_continue", ["100-continue"]),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_body": RESPONSES_RESPONSE,
        "expected_headers": {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(RESPONSES_RESPONSE)),
        },
        "expected_interim_statuses": [100],
        "expected_connection_closed": {"oracle": False, "modex": False},
        "compare_response_body": True,
        "compare_upstream_request": True,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "upstream": True,
    },
    {
        **expectation_request_case(
            "http_1_0_expect_continue_uses_http_1_0_interim",
            ["100-continue"],
            version=b"HTTP/1.0",
        ),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_body": RESPONSES_RESPONSE,
        "expected_headers": {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(RESPONSES_RESPONSE)),
        },
        "expected_interim_statuses": [100],
        "expected_interim_status_lines": ["HTTP/1.0 100 Continue"],
        "expected_response_line": "HTTP/1.0 200 OK",
        "expected_connection_closed": {"oracle": True, "modex": True},
        "compare_response_body": True,
        "compare_upstream_request": True,
        "expected_upstream_method": "POST",
        "expected_upstream_path": "/v1/chat/completions",
        "upstream": True,
    },
    {
        **expectation_request_case(
            "websocket_upgrade_valid_expect_short_circuits_continue",
            ["100-continue"],
            extra_headers=(("Connection", "Upgrade"), ("Upgrade", "websocket")),
        ),
        "check_close": False,
        "expected_status": 426,
        "expected_reason": "Upgrade Required",
        "expected_body": WEBSOCKET_FALLBACK,
        "expected_interim_statuses": [],
        "upstream": False,
    },
    {
        **expectation_request_case(
            "http_1_0_unsupported_expect_returns_417",
            ["100-wait"],
            version=b"HTTP/1.0",
            half_close=True,
        ),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_response_line": "HTTP/1.0 417 Expectation Failed",
        "expected_body": b"",
        "expected_interim_statuses": [],
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        **expectation_request_case(
            "valid_expect_truncated_body",
            ["100-continue"],
            body_after_continue=b"{",
            half_close_after_continue=True,
        ),
        "expected_status": 502,
        "expected_reason": "Bad Gateway",
        "expected_body": b"upstream request failed",
        "expected_interim_statuses": [100],
        "upstream": False,
    },
    {
        **expectation_request_case("unsupported_expect_returns_417", ["100-wait"], half_close=True),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **expectation_request_case(
            "unsupported_expect_precedes_invalid_target",
            ["100-wait"],
            target=b"http://example.test/v1/responses",
            half_close=True,
        ),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **expectation_request_case(
            "unsupported_expect_precedes_fragment_target",
            ["100-wait"],
            target=b"/v1/responses#fragment",
        ),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **raw_expectation_case(
            "unsupported_expect_precedes_request_line_suffix",
            b"POST /v1/responses HTTP/1.1 extra\r\nHost: 127.0.0.1\r\n"
            b"Expect: 100-wait\r\nContent-Length: 0\r\n\r\n",
        ),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **raw_expectation_case(
            "malformed_request_line_precedes_unsupported_expect",
            b"POST /v1/responses bad HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Expect: 100-wait\r\nContent-Length: 0\r\n\r\n",
        ),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **raw_expectation_case(
            "malformed_header_precedes_unsupported_expect",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Expect: 100-wait\r\nBroken\r\nContent-Length: 0\r\n\r\n",
        ),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": b"",
        "upstream": False,
    },
    {
        **expectation_request_case(
            "invalid_target_valid_expect_precedes_continue",
            ["100-continue"],
            target=b"http://example.test/v1/responses",
            half_close=True,
        ),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "expected_interim_statuses": [],
        "expected_connection_closed": {"oracle": True, "modex": True},
        "upstream": False,
    },
    {
        **raw_expectation_case(
            "valid_target_oversized_expect_precedes_continue",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-continue\r\n"
            b"Content-Length: 67108865\r\n\r\n",
        ),
        "expected_status": 413,
        "expected_reason": "Payload Too Large",
        "expected_body": b"proxied request body is too large",
        "expected_interim_statuses": [],
        "expected_connection_closed": {"oracle": False, "modex": True},
        "upstream": False,
    },
    {
        **expectation_request_case(
            "invalid_target_valid_expect_without_half_close",
            ["100-continue"],
            target=b"http://example.test/v1/responses",
        ),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "expected_interim_statuses": [],
        "expected_connection_closed": {"oracle": False, "modex": True},
        "upstream": False,
    },
    {
        **expectation_request_case(
            "unknown_expect_before_supported_duplicate",
            ["100-wait", "100-continue"],
            half_close=True,
        ),
        "expected_status": 417,
        "expected_reason": "Expectation Failed",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "invalid_target_websocket_precedes_upgrade_fallback",
        "request": request_bytes((("Upgrade", "websocket"),), target=b"http://example.test/v1/responses"),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_declared_body_precedes_body_limit",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: 67108865\r\n\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_expected_body_precedes_continue",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-continue\r\nContent-Length: 67108865\r\n\r\n",
        "half_close": True,
        "expect_handshake": True,
        "check_close": True,
        "expected_interim_statuses": [],
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_expected_body_precedes_continue",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-continue\r\nContent-Length: 10\r\n\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_oversized_chunked_body_precedes_body_limit",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nTransfer-Encoding: chunked\r\n\r\n4000001\r\n",
        "half_close": True,
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "upstream": False,
    },
    {
        "name": "invalid_target_truncated_body_closes_without_response",
        "request": b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 10\r\n\r\nx",
        "half_close": True,
        "expected_status": None,
        "expected_read_error": "RemoteDisconnected",
        "expected_body": b"",
        "upstream": False,
    },
    {
        "name": "invalid_target_reply_keeps_relay_accepting_requests",
        "request": request_bytes(target=b"http://example.test/v1/responses"),
        "followup_request": request_bytes((("Connection", "close"),)),
        "expected_status": 400,
        "expected_reason": "Bad Request",
        "expected_body": INVALID_REQUEST_TARGET_BODY,
        "expected_followup_status": 200,
        "upstream": True,
    },
    {
        "name": "valid_escaped_path_is_not_normalized",
        "request": request_bytes(target=b"/v1/resp%6Fnses"),
        "expected_status": 404,
        "expected_reason": "Not Found",
        "expected_body": UNSUPPORTED_ROUTE_BODY,
        "upstream": False,
    },
    {
        "name": "valid_target_length_8192",
        "request": request_bytes(target=MAX_LENGTH_VALID_TARGET),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
    *(
        invalid_target_case(name, target)
        for name, target in (
            ("absolute_form_request_target", b"http://example.test/v1/responses"),
            ("asterisk_request_target", b"*"),
            ("leading_double_slash_request_target", b"//v1/responses"),
            ("interior_double_slash_request_target", b"/v1//responses"),
            ("dot_segment_request_target", b"/v1/../responses"),
            ("encoded_dot_segment_request_target", b"/v1/%2e%2e/responses"),
            ("encoded_slash_request_target", b"/v1/%2f/responses"),
            ("fragment_request_target", b"/v1/responses#x"),
            ("malformed_query_percent_escape", b"/v1/responses?x=%GG"),
            ("request_target_length_8193", OVER_LENGTH_INVALID_TARGET),
        )
    ),
    *(
        method_case(f"method_{method.decode('ascii').lower()}_{target.rsplit(b'/', 1)[-1].decode('ascii')}", method, target)
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for method in (b"GET", b"HEAD", b"PUT", b"DELETE", b"OPTIONS", b"X-EXT")
    ),
    *(
        method_case(f"extension_method_length_{size}_{target.rsplit(b'/', 1)[-1].decode('ascii')}", b"A" * size, target)
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for size in (8192, 8193)
    ),
    *(
        success_method_case(
            f"successful_{method.decode('ascii').lower()}_{target.rsplit(b'/', 1)[-1].decode('ascii')}",
            method,
            target,
        )
        for target in (b"/v1/responses", b"/v1/chat/completions")
        for method in (b"GET", b"HEAD")
    ),
    success_method_case(
        "successful_get_chat_completions_sse",
        b"GET",
        b"/v1/chat/completions",
        response_kind="sse",
    ),
    head_sse_case(),
    head_sse_case(version=b"HTTP/1.0"),
    {
        "name": "http_1_0_sse_stream_starts_before_upstream_eof",
        "request": request_bytes(
            (("X-Oracle-Response", "sse-slow"),),
            target=b"/v1/chat/completions",
            method=b"GET",
            version=b"HTTP/1.0",
        ),
        "expected_status": 200,
        "expected_reason": "OK",
        "expected_response_line": "HTTP/1.1 200 OK",
        "expected_body": PROVIDER_SSE_RESPONSE,
        "expected_headers": {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked",
        },
        "response_before_upstream_eof_ms": 900,
        "compare_response_body": True,
        "expected_upstream_method": "GET",
        "expected_upstream_path": "/v1/chat/completions",
        "compare_upstream_request": True,
        "upstream": True,
    },
    success_method_case(
        "successful_get_responses_sse",
        b"GET",
        b"/v1/responses",
        response_kind="sse",
        body=STREAM_REQUEST_BODY,
    ),
    *(head_bodyless_sse_case(status) for status in (204, 304)),
    *(head_bodyless_sse_case(status, version=b"HTTP/1.0") for status in (204, 304)),
    http_1_0_status_case(302, "Found", "status-302"),
    http_1_0_status_case(404, "Not Found", "status-404"),
    http_1_0_status_case(503, "Service Unavailable", "status-503"),
    response_status_case(200, "OK"),
    response_status_case(206, "Partial Content"),
    response_status_case(302, "Found"),
    response_status_case(404, "Not Found"),
    response_status_case(500, "Internal Server Error"),
    response_status_case(418, "Unknown"),
    response_status_case(422, "Unprocessable Entity"),
    response_status_case(503, "Service Unavailable", version=b"HTTP/1.0"),
    {
        "name": "valid_escaped_query",
        "request": request_bytes(target=b"/v1/responses?x=a%2Fb"),
        "expected_status": 200,
        "expected_body": None,
        "upstream": True,
    },
)


def response_header_values(response):
    values = {}
    for line in response["raw_response_head"].split(b"\r\n")[1:-2]:
        name, separator, value = line.partition(b":")
        if separator:
            values.setdefault(name.lower(), []).append(value.strip())
    return values


def assert_response_headers(test_case, response, before, after, label):
    if response["status"] is None:
        return
    if response["raw_response_head"]:
        header_sets = [response_header_values(response)]
    else:
        result_sets = response.get("pipelined_responses") or response.get("sequential_responses") or [response]
        header_sets = []
        for result in result_sets:
            values = {}
            for name, value in result.get("headers", []):
                name = name.encode("ascii") if isinstance(name, str) else name
                value = value.encode("ascii") if isinstance(value, str) else value
                values.setdefault(name.lower(), []).append(value.strip())
            header_sets.append(values)
    for index, values in enumerate(header_sets):
        with test_case.subTest(label=label, response=index):
            servers = values.get(b"server", [])
            test_case.assertLessEqual(len(servers), 1)
            if servers:
                test_case.assertIn(servers[0], (
                    b"tiny-http (Rust)",
                    f"{UpstreamHandler.server_version} {UpstreamHandler.sys_version}".encode("ascii"),
                ))
            dates = values.get(b"date", [])
            test_case.assertLessEqual(len(dates), 1)
            if dates:
                date_text = dates[0].decode("ascii")
                test_case.assertRegex(
                    date_text,
                    r"^[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT$",
                )
                date_epoch = parsedate_to_datetime(date_text).timestamp()
                test_case.assertGreaterEqual(date_epoch, before - 2)
                test_case.assertLessEqual(date_epoch, after + 2)


def response_header_control_case(control):
    target = f"/v1/chat/completions?header-controls={control}".encode("ascii")
    return {
        "name": "response_header_" + control,
        "request": request_bytes((("Connection", "close"),), target=target),
        "upstream": True,
    }


def run_probe(binary: Path, case, upstream: Upstream):
    with tempfile.TemporaryDirectory(prefix="modex-raw-transport-01651-") as temporary:
        root = Path(temporary)
        for name in (
            "home", "prodex", "shared-codex", "xdg-config", "xdg-data", "xdg-cache", "work",
        ):
            (root / name).mkdir(mode=0o700)
        codex = root / "codex"
        make_codex(codex)
        result_path = root / "raw-response.json"
        request_file = None
        if len(case["request"]) > 64 * 1024:
            request_file = root / "raw-request.bin"
            request_file.write_bytes(case["request"])
        environment = {
            "HOME": str(root / "home"),
            "PRODEX_HOME": str(root / "prodex"),
            "PRODEX_SHARED_CODEX_HOME": str(root / "shared-codex"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "TMPDIR": str(root),
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PRODEX_CODEX_BIN": str(codex),
            "PROBE_REQUEST_BASE64": "" if request_file else base64.b64encode(case["request"]).decode("ascii"),
            "PROBE_REQUEST_FILE": str(request_file) if request_file else "",
            "PROBE_REQUEST_PARTS_BASE64": json.dumps(
                [base64.b64encode(part).decode("ascii") for part in case.get("request_parts", [])],
                separators=(",", ":"),
            ),
            "PROBE_REQUEST_PART_DELAY_MS": str(case.get("request_part_delay_ms", 0)),
            "PROBE_SEQUENTIAL_REQUESTS_BASE64": json.dumps(
                [base64.b64encode(part).decode("ascii") for part in case.get("sequential_requests", [])],
                separators=(",", ":"),
            ),
            "PROBE_PIPELINED_REQUESTS_BASE64": json.dumps(
                [base64.b64encode(part).decode("ascii") for part in case.get("pipelined_requests", [])],
                separators=(",", ":"),
            ),
            "PROBE_CONCURRENT_REQUESTS_BASE64": json.dumps(
                [base64.b64encode(part).decode("ascii") for part in case.get("concurrent_requests", [])],
                separators=(",", ":"),
            ),
            "PROBE_PARENT_EXIT_ACTIVE": "1" if case.get("parent_exit_active") else "0",
            "PROBE_PRECONNECTED_IDLE": "1" if case.get("preconnected_idle") else "0",
            "PROBE_PRECONNECTED_SETTLE_MS": str(case.get("preconnected_settle_ms", 100)),
            "PROBE_PRECONNECTED_PARTIAL_COUNT": str(case.get("preconnected_partial_count", 136)),
            "PROBE_PRECONNECTED_IDLE_COUNT": str(case.get("preconnected_idle_count", 0)),
            "PROBE_PRECONNECTED_FLOOD_SETTLE_MS": str(case.get("preconnected_flood_settle_ms", 400)),
            "PROBE_PRECONNECTED_RESOURCE_SAMPLE_MS": str(case.get("preconnected_resource_sample_ms", 1000)),
            "PROBE_ADMISSION_STRESS": "1" if case.get("admission_stress") else "0",
            "PROBE_ADMISSION_PARTIAL_COUNT": str(case.get("admission_partial_count", 136)),
            "PROBE_ADMISSION_BLOCKER_COUNT": str(case.get("admission_blocker_count", 7)),
            "PROBE_ADMISSION_PARTIAL_REQUEST_BASE64": base64.b64encode(
                case.get("admission_partial_request", b"")
            ).decode("ascii"),
            "PROBE_ADMISSION_BLOCKER_REQUEST_BASE64": base64.b64encode(
                case.get("admission_blocker_request", b"")
            ).decode("ascii"),
            "PROBE_ADMISSION_HEALTHY_REQUEST_BASE64": base64.b64encode(
                case.get("admission_healthy_request", b"")
            ).decode("ascii"),
            "PROBE_ADMISSION_RESOURCE_SAMPLE_MS": str(case.get("admission_resource_sample_ms", 1000)),
            "PROBE_PRECONNECTED_PARTIAL_REQUEST_BASE64": base64.b64encode(
                case.get("preconnected_partial_request", b"")
            ).decode("ascii"),
            "PROBE_PRECONNECTED_HEALTHY_REQUEST_BASE64": base64.b64encode(
                case.get("preconnected_healthy_request", b"")
            ).decode("ascii"),
            "PROBE_PARENT_EXIT_TRIGGER": str(case.get("parent_exit_trigger", "")),
            "PROBE_PIPELINED_REQUEST_PARTS_BASE64": json.dumps(
                [base64.b64encode(part).decode("ascii") for part in case.get("pipelined_request_parts", [])],
                separators=(",", ":"),
            ),
            "PROBE_PIPELINED_REQUEST_DELAY_MS": str(case.get("pipelined_request_delay_ms", 0)),
            "PROBE_PIPELINED_RESPONSE_COUNT": str(case.get("pipelined_response_count", len(case.get("pipelined_requests", [])))),
            "PROBE_SECOND_CLIENT_REQUEST_BASE64": base64.b64encode(
                case.get("second_client_request", b"")
            ).decode("ascii"),
            "PROBE_REUSED_PARTIAL_REQUEST_BASE64": base64.b64encode(
                case.get("reused_partial_request", b"")
            ).decode("ascii"),
            "PROBE_PARTIAL_HOLD_MS": str(case.get("partial_hold_ms", 300)),
            "PROBE_HOLD_FIRST_CLIENT_MS": str(case.get("hold_first_client_ms", 0)),
            "PROBE_SATURATION_EXTRA_CONNECTIONS": str(case.get("saturation_extra_connections", 0)),
            "PROBE_SATURATION_REQUEST_BASE64": base64.b64encode(
                case.get("saturation_request", b"")
            ).decode("ascii"),
            "PROBE_SATURATION_OLDEST_PARTIAL_BASE64": base64.b64encode(
                case.get("saturation_oldest_partial", b"")
            ).decode("ascii"),
            "PROBE_FAIRNESS_EXTRA_CONNECTIONS": str(case.get("fairness_extra_connections", 0)),
            "PROBE_FAIRNESS_CHURN_COUNT": str(case.get("fairness_churn_count", 0)),
            "PROBE_FAIRNESS_REPEATS": str(case.get("fairness_repeat_count", 1)),
            "PROBE_FAIRNESS_REQUEST_BASE64": base64.b64encode(
                case.get("fairness_request", b"")
            ).decode("ascii"),
            "PROBE_FAIRNESS_CHURN_REQUEST_BASE64": base64.b64encode(
                case.get("fairness_churn_request", b"")
            ).decode("ascii"),
            "PROBE_CONTINUE_AFTER_WILL_CLOSE": "1" if case.get("continue_after_will_close") else "0",
            "PROBE_BODY_AFTER_CONTINUE_BASE64": base64.b64encode(
                case.get("body_after_continue", b"")
            ).decode("ascii"),
            "PROBE_HALF_CLOSE_AFTER_CONTINUE": "1" if case.get("half_close_after_continue") else "0",
            "PROBE_EXPECT_HANDSHAKE": "1" if case.get("expect_handshake") else "0",
            "PROBE_REQUEST_METHOD": case["request"].split(b" ", 1)[0].decode("ascii"),
            "PROBE_HALF_CLOSE": "1" if case.get("half_close") else "0",
            "PROBE_CHECK_CLOSE": "1" if case.get("check_close") else "0",
            "PROBE_RAW_RESPONSE": "1" if case.get("raw_response") else "0",
            "PROBE_RAW_RESPONSE_TIMEOUT_MS": str(case.get("raw_response_timeout_ms", 1000)),
            "PROBE_FOLLOWUP_REQUEST_HEX": case.get("followup_request", b"").hex(),
            "PROBE_RESULT_PATH": str(result_path),
        }
        environment.update(case.get("environment_overrides", {}))
        command = [
            str(binary), "super", "--provider", "deepseek", "--api-key", SYNTHETIC_API_KEY,
            "--base-url", f"http://127.0.0.1:{upstream.server_port}/v1",
            "--model", "deepseek-chat", "--no-presidio", "--no-sub-agent",
            "--skip-quota-check", "exec", "--", "synthetic raw transport probe",
        ]
        upstream.reset_records()
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                cwd=root / "work",
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=case.get("process_timeout", 40),
                check=False,
            )
        finally:
            if result_path.is_file():
                try:
                    holder_pid = json.loads(result_path.read_text(encoding="utf-8")).get("holder_pid")
                    if holder_pid:
                        os.kill(holder_pid, 9)
                except (OSError, ValueError):
                    pass
        if not result_path.is_file():
            raise AssertionError(
                f"{binary.name} did not reach the synthetic Codex raw client for {case['name']}: "
                f"exit={process.returncode}, stdout={process.stdout!r}, stderr={process.stderr!r}"
            )
        response = json.loads(result_path.read_text(encoding="utf-8"))
        response["process_elapsed_ms"] = int((time.monotonic() - started) * 1000)
        response["body"] = base64.b64decode(response.pop("body_base64"))
        response["raw_response_head"] = base64.b64decode(response.pop("raw_response_head_base64"))
        response["wire_body"] = base64.b64decode(response.pop("wire_body_base64"))
        if "followup_body_base64" in response:
            response["followup_body"] = base64.b64decode(response.pop("followup_body_base64"))
        for item in response.get("sequential_responses", []):
            item["body"] = base64.b64decode(item.pop("body_base64"))
        for item in response.get("pipelined_responses", []):
            item["body"] = base64.b64decode(item.pop("body_base64"))
            item["head_wire_body"] = base64.b64decode(item.pop("head_wire_body_base64"))
        for item in response.get("concurrent_responses", []):
            if "body_base64" in item:
                item["body"] = base64.b64decode(item.pop("body_base64"))
        if "second_client" in response:
            response["second_client"]["body"] = base64.b64decode(response["second_client"].pop("body_base64"))
        if "saturation_overflow_body_base64" in response:
            response["saturation_overflow_body"] = base64.b64decode(response.pop("saturation_overflow_body_base64"))
        if "saturation_oldest_body_base64" in response:
            response["saturation_oldest_body"] = base64.b64decode(response.pop("saturation_oldest_body_base64"))
        response["process_exit"] = process.returncode
        response["stdout"] = process.stdout
        response["stderr"] = process.stderr
        return response, upstream.snapshot_records()


def normalize_response_body(case, body):
    if case["name"] == "successful_get_responses_sse":
        return re.sub(rb"msg_deepseek_[0-9]+", b"msg_deepseek_ID", body)
    return body


def assert_large_request_head_cases(test, oracle, modex):
    upstream = LargeHeaderUpstream()
    worker = threading.Thread(target=upstream.serve_forever, daemon=True)
    worker.start()
    try:
        cases = (
            (large_request_head_case(131072), 200, 200),
            (large_request_head_case(131072, target=b"/v1/chat/completions"), 200, 200),
            (large_user_agent_case(), 200, 200),
            (large_user_agent_value_case(1024 * 1024), 200, 200),
            (large_user_agent_value_case(1024 * 1024 + 1), 200, 200),
            (large_user_agent_case(LOCAL_RELAY_REQUEST_HEADER_LIMIT), 200, 200),
            (large_user_agent_case(LOCAL_RELAY_REQUEST_HEADER_LIMIT + 1), 200, 502),
            (
                {
                    **large_user_agent_value_case(
                        1024 * 1024 + 1, target=b"/v1/chat/completions",
                    ),
                    "expected_user_agent_count": 2,
                },
                200,
                200,
            ),
            (many_small_header_case(1024 * 1024), 200, 200),
            (many_connection_token_headers_case(), 200, 200),
            (many_small_header_case(1024 * 1024 + 1), 200, 200),
            (many_small_header_case(LOCAL_RELAY_REQUEST_HEADER_LIMIT), 200, 200),
            (many_small_header_case(LOCAL_RELAY_REQUEST_HEADER_LIMIT, target=b"/v1/chat/completions"), 200, 200),
            (many_small_header_case(LOCAL_RELAY_REQUEST_HEADER_LIMIT + 1), 200, 502),
        )
        for case, oracle_status, modex_status in cases:
            with test.subTest(case=case["name"]):
                oracle_response, oracle_records = run_probe(oracle, case, upstream)
                modex_response, modex_records = run_probe(modex, case, upstream)
                for label, response, records, status in (
                    ("oracle", oracle_response, oracle_records, oracle_status),
                    ("modex", modex_response, modex_records, modex_status),
                ):
                    test.assertEqual(response["process_exit"], 0, response["stderr"])
                    test.assertEqual(response["status"], status, label)
                    if status == 200:
                        test.assertEqual(response["body"], case["expected_body"], label)
                        test.assertEqual(len(records), 1, label)
                        test.assertEqual(records[0]["pad_headers"], expected_pad_headers(case["request"]), label)
                        if "expected_user_agent_count" in case or "expected_user_agent_count_by_label" in case:
                            expected_user_agent = next(
                                line.partition(b":")[2].strip()
                                for line in case["request"].split(b"\r\n")
                                if line.lower().startswith(b"user-agent:")
                            )
                            expected_count = case.get("expected_user_agent_count_by_label", {}).get(
                                label, case.get("expected_user_agent_count"),
                            )
                            test.assertEqual(
                                records[0]["user_agent_values"],
                                [expected_user_agent] * expected_count,
                                label,
                            )
                            if case["name"] == f"large_user_agent_{LOCAL_RELAY_REQUEST_HEADER_LIMIT}":
                                test.assertGreater(records[0]["head_bytes"], 2 * 1024 * 1024 + 2048, label)
                                test.assertLessEqual(records[0]["head_bytes"], 4 * 1024 * 1024 + 2048, label)
                        if case["name"].startswith("large_request_head_"):
                            expected_pad = case["request"].split(b"X-Pad: ", 1)[1].split(b"\r\n", 1)[0]
                            test.assertEqual(len(records[0]["headers"]["x-pad"]), len(expected_pad), label)
                        if "expected_header_count" in case:
                            test.assertEqual(
                                sum(name.startswith("x-pad-") for name in records[0]["headers"]),
                                case["expected_header_count"],
                                label,
                            )
                        if "expected_hidden_count" in case:
                            test.assertEqual(
                                sum(name.startswith("x-hide-") for name in records[0]["headers"]),
                                0,
                                label,
                            )
                            input_connection = next(
                                line.partition(b":")[2].strip().decode("ascii")
                                for line in case["request"].split(b"\r\n")
                                if line.lower().startswith(b"connection:")
                            )
                            test.assertNotEqual(records[0]["headers"].get("connection"), input_connection, label)
                    else:
                        test.assertEqual(response["body"], case.get("expected_error_body", b"gateway request capture failed"), label)
                        test.assertEqual(records, [], label)
                if oracle_status == modex_status:
                    test.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
    finally:
        upstream.shutdown()
        upstream.server_close()
        worker.join(timeout=2)


def assert_chat_request_header_parity(test, oracle, modex):
    upstream = LargeHeaderUpstream()
    worker = threading.Thread(target=upstream.serve_forever, daemon=True)
    worker.start()
    cases = (
        (
            "ordinary",
            (("User-Agent", "synthetic-agent"),),
            [b"synthetic-agent", b"synthetic-agent"],
            ["text/event-stream, application/json"],
            ["application/json", "application/json"],
        ),
        (
            "duplicate",
            (("User-Agent", "first-agent"), ("User-Agent", "second-agent"),
             ("Accept", "first-accept"), ("Accept", "second-accept"),
             ("Content-Type", "application/custom+json")),
            [b"first-agent", b"first-agent", b"second-agent"],
            ["text/event-stream, application/json", "first-accept", "second-accept"],
            ["application/json", "application/custom+json", "application/json"],
        ),
        (
            "missing-user-agent-and-accept",
            (),
            [],
            ["text/event-stream, application/json"],
            ["application/json", "application/json"],
        ),
    )
    try:
        for name, headers, expected_user_agents, expected_accept, expected_content_type in cases:
            case = {
                "name": f"chat_header_{name}",
                "request": request_bytes(headers, target=b"/v1/chat/completions"),
            }
            for label, binary in (("oracle", oracle), ("modex", modex)):
                with test.subTest(case=name, binary=label):
                    response, records = run_probe(binary, case, upstream)
                    test.assertEqual(response["process_exit"], 0, response["stderr"])
                    test.assertEqual((response["status"], response["body"]), (200, PROVIDER_RESPONSE), label)
                    test.assertEqual(len(records), 1, label)
                    test.assertEqual(records[0]["user_agent_values"], expected_user_agents, label)
                    selected = records[0]["selected_header_values"]
                    test.assertEqual(selected.get("accept", []), expected_accept, label)
                    test.assertEqual(selected.get("content-type", []), expected_content_type, label)
                    test.assertEqual(selected.get("connection", []), [], label)
    finally:
        upstream.shutdown()
        upstream.server_close()
        worker.join(timeout=2)


def assert_chat_response_framing(test, oracle, modex):
    request_case = {
        "name": "chat_response_framing",
        "request": request_bytes(
            (("User-Agent", "synthetic-agent"),), target=b"/v1/chat/completions",
        ),
    }
    for mode in ("fixed-keep-alive", "chunked-keep-alive", "eof"):
        upstream = RelayFramingUpstream(mode)
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for label, binary in (("oracle", oracle), ("modex", modex)):
                with test.subTest(framing=mode, binary=label):
                    response, records = run_probe(binary, request_case, upstream)
                    test.assertEqual(response["process_exit"], 0, response["stderr"])
                    test.assertEqual((response["status"], response["body"]), (200, PROVIDER_RESPONSE), label)
                    test.assertEqual(len(records), 1, label)
                    if mode.endswith("keep-alive"):
                        # Framed responses complete while the upstream keeps its socket open.
                        test.assertLess(response["response_elapsed_ms"], 1500, label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


class LocalRewrite01651OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.165.1")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_websocket_upgrade_rejects_before_reading_declared_body(self):
        invalid_target_case = websocket_upgrade_declared_body_case(
            target=b"http://example.test/v1/responses",
        )
        invalid_target_case["name"] = "websocket_invalid_target_precedes_upgrade_fallback"
        unsupported_expect_case = expectation_request_case(
            "websocket_unsupported_expect_precedes_upgrade_fallback",
            ["100-wait"],
            extra_headers=(("Connection", "Upgrade"), ("Upgrade", "websocket")),
        )
        unsupported_expect_case.update({
            "expected_status": 417,
            "expected_reason": "Expectation Failed",
            "expected_body": b"",
            "expected_interim_statuses": [],
            "upstream": False,
        })
        ambiguous_framing_case = raw_expectation_case(
            "websocket_ambiguous_framing_precedes_upgrade_fallback",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: Upgrade\r\nUpgrade: websocket\r\n"
            b"Authorization: Bearer synthetic-websocket-key\r\n"
            b"Content-Length: 0\r\nContent-Length: 100\r\n\r\n"
            + request_bytes(headers=(("Connection", "close"),)),
        )
        invalid_target_framing_case = raw_expectation_case(
            "websocket_ambiguous_framing_keeps_invalid_target_precedence",
            b"POST http://example.test/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: Upgrade\r\nUpgrade: websocket\r\n"
            b"Content-Length: 0\r\nContent-Length: 100\r\n\r\n",
        )
        unsupported_expect_framing_case = raw_expectation_case(
            "websocket_ambiguous_framing_keeps_unsupported_expect_precedence",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: Upgrade\r\nUpgrade: websocket\r\nExpect: 100-wait\r\n"
            b"Content-Length: 0\r\nContent-Length: 100\r\n\r\n",
        )
        missing_connection_upgrade_case = raw_expectation_case(
            "websocket_header_without_connection_upgrade_uses_fallback",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Upgrade: websocket\r\nContent-Length: 0\r\n"
            b"Content-Length: 100\r\n\r\n",
        )
        missing_connection_upgrade_case["expected_connection_closed"] = {
            "0.165.1": False, "0.439.2": False, "Modex": True,
        }
        non_websocket_upgrade_case = raw_expectation_case(
            "ambiguous_framing_h2c_upgrade_does_not_use_websocket_fallback",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: Upgrade\r\nUpgrade: h2c\r\n"
            b"Content-Length: 0\r\nContent-Length: 100\r\n\r\n",
            half_close=True,
        )
        non_websocket_upgrade_case["expected_connection_closed"] = {
            "0.165.1": True, "0.439.2": True, "Modex": True,
        }
        for case in (
            ambiguous_framing_case,
            invalid_target_framing_case,
            unsupported_expect_framing_case,
            non_websocket_upgrade_case,
        ):
            case["expected_connection_closed"] = {
                "0.165.1": True, "0.439.2": True, "Modex": True,
            }
        scenarios = (
            (websocket_upgrade_declared_body_case(), {
                "0.165.1": (426, WEBSOCKET_FALLBACK),
                "0.439.2": (426, WEBSOCKET_FALLBACK),
                "Modex": (426, WEBSOCKET_FALLBACK),
            }),
            (invalid_target_case, {
                "0.165.1": (400, INVALID_REQUEST_TARGET_BODY),
                "0.439.2": (400, INVALID_REQUEST_TARGET_BODY),
                "Modex": (400, INVALID_REQUEST_TARGET_BODY),
            }),
            (unsupported_expect_case, {
                "0.165.1": (417, b""),
                "0.439.2": (417, b""),
                "Modex": (417, b""),
            }),
            (ambiguous_framing_case, {
                "0.165.1": (426, WEBSOCKET_FALLBACK),
                "0.439.2": (426, WEBSOCKET_FALLBACK),
                "Modex": (426, WEBSOCKET_FALLBACK),
            }),
            (invalid_target_framing_case, {
                "0.165.1": (400, INVALID_REQUEST_TARGET_BODY),
                "0.439.2": (400, INVALID_REQUEST_TARGET_BODY),
                "Modex": (400, INVALID_REQUEST_TARGET_BODY),
            }),
            (unsupported_expect_framing_case, {
                "0.165.1": (417, b""),
                "0.439.2": (417, b""),
                "Modex": (417, b""),
            }),
            (missing_connection_upgrade_case, {
                "0.165.1": (426, WEBSOCKET_FALLBACK),
                "0.439.2": (426, WEBSOCKET_FALLBACK),
                "Modex": (426, WEBSOCKET_FALLBACK),
            }),
            (non_websocket_upgrade_case, {
                "0.165.1": (502, b"upstream request failed"),
                "0.439.2": (502, b"upstream request failed"),
                "Modex": (502, b"gateway request capture failed"),
            }),
        )
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        binaries = (
            ("0.165.1", ORACLE, ORACLE_SHA256),
            ("0.439.2", ORACLE_04392, ORACLE_04392_SHA256),
            ("Modex", MODEX, None),
        )
        reasons = {
            400: "Bad Request",
            417: "Expectation Failed",
            426: "Upgrade Required",
            502: "Bad Gateway",
        }

        def stable_wire_head(response):
            lines = response["raw_response_head"].split(b"\r\n")
            fields = []
            for line in lines[1:-2]:
                name, separator, value = line.partition(b":")
                if separator and name.lower() != b"date":
                    fields.append((name.lower(), value.strip()))
            return lines[0], fields

        try:
            for case, expected in scenarios:
                observed = {}
                for label, binary, expected_hash in binaries:
                    with self.subTest(case=case["name"], binary=label):
                        if expected_hash:
                            self.assertTrue(binary.is_file(), f"pinned {label} oracle is missing: {binary}")
                            self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), expected_hash)
                        response, records = run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        status, body = expected[label]
                        self.assertEqual(
                            (response["status"], response["reason"], response["body"]),
                            (status, reasons[status], body),
                        )
                        self.assertEqual(response["read_error"], "")
                        self.assertEqual(response["request_parts_sent_at_response"], 1)
                        if case is ambiguous_framing_case:
                            self.assertNotIn(b"synthetic-websocket-key", response["stdout"])
                            self.assertNotIn(b"synthetic-websocket-key", response["stderr"])
                        if "expected_connection_closed" in case:
                            self.assertEqual(
                                response["connection_closed"],
                                case["expected_connection_closed"][label],
                            )
                        self.assertEqual(response["interim_statuses"], [])
                        self.assertTrue(response["raw_response_head"].endswith(b"\r\n\r\n"))
                        dates = [
                            line.partition(b":")[2].strip()
                            for line in response["raw_response_head"].split(b"\r\n")
                            if line.lower().startswith(b"date:")
                        ]
                        self.assertEqual(len(dates), 1)
                        self.assertIsNotNone(parsedate_to_datetime(dates[0].decode("ascii")))
                        self.assertEqual(
                            dict(stable_wire_head(response)[1])[b"content-length"],
                            str(len(body)).encode("ascii"),
                        )
                        self.assertEqual(records, [])
                        observed[label] = (stable_wire_head(response), body)
                self.assertEqual(observed["0.165.1"], observed["0.439.2"])
                if expected["Modex"] == expected["0.165.1"]:
                    self.assertEqual(observed["Modex"], observed["0.165.1"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade(self):
        valid_websocket = request_bytes((("Upgrade", "websocket"),))
        ambiguous_websocket = (
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Upgrade: websocket\r\nAuthorization: Bearer synthetic-websocket-key\r\n"
            b"Content-Length: 0\r\nContent-Length: 100\r\n\r\n"
        )
        followup = request_bytes((("Connection", "close"),), body=REQUEST_BODY)
        valid_split = valid_websocket.index(b"Upgrade: websocket") + len(b"Upgrade: websocket") - 3
        ambiguous_split = ambiguous_websocket.index(b"Content-Length: 0") + len(b"Content-Length: 0")
        cases = (
            (
                "valid_websocket_pipeline_without_connection_upgrade",
                valid_websocket,
                [valid_websocket[:valid_split], valid_websocket[valid_split:] + followup],
            ),
            (
                "ambiguous_websocket_pipeline_without_connection_upgrade",
                ambiguous_websocket,
                [ambiguous_websocket[:ambiguous_split], ambiguous_websocket[ambiguous_split:] + followup],
            ),
        )
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, first_request, parts in cases:
                case = {
                    "name": name,
                    "request": first_request + followup,
                    "pipelined_requests": [first_request, followup],
                    "pipelined_request_parts": parts,
                    "pipelined_request_delay_ms": 10,
                    "pipelined_response_count": 2,
                    "check_close": True,
                    "process_timeout": 15,
                }
                for label, binary in (
                    ("0.165.1", ORACLE),
                    ("0.439.2", ORACLE_04392),
                    ("Modex", MODEX),
                ):
                    with self.subTest(case=name, product=label):
                        response, records = run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertNotIn(b"synthetic-websocket-key", response["stdout"])
                        self.assertNotIn(b"synthetic-websocket-key", response["stderr"])
                        if label == "Modex":
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                                [(426, WEBSOCKET_FALLBACK)],
                            )
                            self.assertEqual(response["read_error"], "RemoteDisconnected")
                            self.assertEqual(records, [])
                        else:
                            self.assertEqual(
                                (response["status"], response["body"]),
                                (426, WEBSOCKET_FALLBACK),
                                label,
                            )
                            self.assertEqual(response["read_error"], "")
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                                [(426, WEBSOCKET_FALLBACK), (200, RESPONSES_RESPONSE)],
                            )
                            self.assertEqual(len(records), 1)
                            self.assertEqual(records[0]["path"], "/v1/chat/completions")
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_raw_http_production_path_matches_pinned_oracle_controls(self):
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case in CASES:
                with self.subTest(case=case["name"]):
                    before = time.time()
                    oracle_response, oracle_upstream = run_probe(ORACLE, case, upstream)
                    modex_response, modex_upstream = run_probe(MODEX, case, upstream)
                    after = time.time()

                    assert_response_headers(self, oracle_response, before, after, "oracle")
                    assert_response_headers(self, modex_response, before, after, "modex")
                    self.assertEqual(
                        {name for name in (b"server", b"date") if name in response_header_values(oracle_response)},
                        {name for name in (b"server", b"date") if name in response_header_values(modex_response)},
                        case["name"],
                    )

                    self.assertEqual(oracle_response["process_exit"], 0, oracle_response["stderr"])
                    self.assertEqual(modex_response["process_exit"], 0, modex_response["stderr"])
                    oracle_request = None
                    for label, response, records in (
                        ("oracle", oracle_response, oracle_upstream),
                        ("modex", modex_response, modex_upstream),
                    ):
                        self.assertEqual(response["status"], case["expected_status"], label)
                        if "expected_reason" in case:
                            self.assertEqual(response["reason"], case["expected_reason"], label)
                        if "expected_response_line" in case:
                            self.assertEqual(response["response_line"], case["expected_response_line"], label)
                        if "expected_wire_response_line" in case:
                            self.assertEqual(response["raw_response_head"].split(b"\r\n", 1)[0].decode(), case["expected_wire_response_line"], label)
                        if "response_before_upstream_eof_ms" in case:
                            limit = case["response_before_upstream_eof_ms"]
                            self.assertLess(response["response_headers_elapsed_ms"], limit, label)
                            self.assertLess(response["first_body_byte_elapsed_ms"], limit, label)
                        self.assertEqual(response["read_error"], case.get("expected_read_error", ""), label)
                        self.assertEqual(response["interim_statuses"], case.get("expected_interim_statuses", []), label)
                        expected_interim_lines = case.get(
                            "expected_interim_status_lines",
                            ["HTTP/1.1 100 Continue" for _ in case.get("expected_interim_statuses", [])],
                        )
                        self.assertEqual(response.get("interim_status_lines", []), expected_interim_lines, label)
                        if "expected_request_parts_sent" in case:
                            self.assertEqual(
                                response["request_parts_sent_at_response"],
                                case["expected_request_parts_sent"],
                                label,
                            )
                        if case.get("check_close"):
                            expected_close = case.get("expected_connection_closed", {}).get(label, True)
                            if expected_close is not None:
                                self.assertEqual(response["connection_closed"], expected_close, label)
                        if "expected_followup_status" in case:
                            self.assertEqual(response["followup_status"], case["expected_followup_status"], label)
                            self.assertTrue(response["followup_body"], label)
                        if case["expected_body"] is not None:
                            self.assertEqual(response["body"], case["expected_body"], label)
                        else:
                            self.assertTrue(response["body"], label)
                        if case.get("expected_headers"):
                            response_headers = {name.lower(): value for name, value in response["headers"]}
                            for name, value in case["expected_headers"].items():
                                self.assertEqual(response_headers.get(name), value, label)
                        if case["request"].startswith(b"HEAD "):
                            self.assertTrue(response["wire_body_probe_complete"], label)
                            self.assertEqual(
                                response["wire_body"],
                                case.get("expected_wire_body", {}).get(label, b""),
                                label,
                            )
                        self.assertEqual(len(records), int(case["upstream"]), label)
                        if case["upstream"]:
                            record = records[0]
                            self.assertEqual(
                                (record["method"], record["path"]),
                                (case.get("expected_upstream_method", "POST"), case.get("expected_upstream_path", "/v1/chat/completions")),
                                label,
                            )
                            if case.get("compare_upstream_request"):
                                if label == "oracle":
                                    oracle_request = record
                                else:
                                    self.assertIsNotNone(oracle_request)
                                    self.assertEqual(record["body"], oracle_request["body"], label)
                            self.assertNotIn("upgrade", record["headers"], label)
                            self.assertNotIn("keep-alive", [value.lower() for value in record["headers"].values()], label)
                            self.assertNotEqual(record["headers"].get("connection", "").lower(), "upgrade", label)
                    if case.get("compare_response_body"):
                        self.assertEqual(
                            normalize_response_body(case, oracle_response["body"]),
                            normalize_response_body(case, modex_response["body"]),
                        )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_admission_eviction_compares_preconnected_idle_and_keepalive_sockets(self):
        if not ORACLE_04392.is_file():
            raise AssertionError(f"Pinned Prodex 0.439.2 oracle is missing: {ORACLE_04392}")
        if hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.439.2")
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        scenarios = [
            (
                "preconnected_idle_partial_flood",
                {
                    "name": "preconnected_idle_before_partial_header_flood",
                    "request": b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n",
                    "preconnected_idle": True,
                    "preconnected_partial_count": 136,
                    "preconnected_partial_request": (
                        b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        b"X-Pending: unfinished"
                    ),
                    "preconnected_healthy_request": request_bytes(
                        headers=(("Connection", "close"),),
                        target=b"/v1/responses?admission=preconnected",
                    ),
                    "environment_overrides": {"PRODEX_RUNTIME_PROXY_WORKER_COUNT": "8"},
                    "process_timeout": 40,
                },
            ),
            (
                "preconnected_idle_flood",
                {
                    "name": "preconnected_idle_before_idle_client_flood",
                    "request": b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n",
                    "preconnected_idle": True,
                    "preconnected_partial_count": 0,
                    "preconnected_idle_count": 136,
                    "preconnected_healthy_request": request_bytes(
                        headers=(("Connection", "close"),),
                        target=b"/v1/responses?admission=preconnected-idle",
                    ),
                    "environment_overrides": {"PRODEX_RUNTIME_PROXY_WORKER_COUNT": "8"},
                    "process_timeout": 40,
                },
            ),
            (
                "full_partial_backlog_without_idle_slots",
                {
                    "name": "aggregate_admission_136_partial_heads",
                    "request": b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n",
                    "admission_stress": True,
                    "admission_partial_count": 136,
                    "admission_blocker_count": 7,
                    "admission_partial_request": (
                        b"GET /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        b"X-Pending: unfinished"
                    ),
                    "admission_blocker_request": (
                        b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        b"Content-Type: application/json\r\nContent-Length: 1\r\n"
                        b"Connection: close\r\n\r\n"
                    ),
                    "admission_healthy_request": request_bytes(
                        headers=(("Connection", "keep-alive"),),
                        target=b"/v1/responses?admission=healthy",
                    ),
                    "environment_overrides": {"PRODEX_RUNTIME_PROXY_WORKER_COUNT": "8"},
                    "process_timeout": 40,
                },
            ),
        ]
        try:
            for name, case in scenarios:
                results = {
                    label: run_probe(binary, case, upstream)
                    for label, binary in (
                        ("0.165.1", ORACLE),
                        ("0.439.2", ORACLE_04392),
                        ("Modex", MODEX),
                    )
                }
                for label, (response, records) in results.items():
                    with self.subTest(scenario=name, label=label):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        if name == "full_partial_backlog_without_idle_slots":
                            healthy = response["admission_healthy_results"]
                            self.assertEqual(response["admission_partial_connections"], 136)
                            self.assertEqual(response["admission_blockers"], 7)
                            self.assertTrue(response["admission_client_fds_ready"], response)
                            self.assertEqual(
                                response["admission_healthy_before_release"],
                                label != "Modex",
                                response,
                            )
                            self.assertEqual(healthy.get("first_status"), 200, response)
                            self.assertEqual(healthy.get("second_status"), 200, response)
                            self.assertEqual(
                                base64.b64decode(healthy["first_body_base64"]),
                                RESPONSES_RESPONSE,
                                label,
                            )
                            self.assertEqual(
                                base64.b64decode(healthy["second_body_base64"]),
                                RESPONSES_RESPONSE,
                                label,
                            )
                            self.assertEqual(len(records), 2, label)
                            if label == "Modex":
                                self.assertLessEqual(
                                    response["admission_fd_delta"],
                                    response["admission_partial_connections"]
                                    + response["admission_blockers"]
                                    + 40,
                                    response,
                                )
                        elif label != "Modex":
                            self.assertEqual(response.get("status"), 200, response)
                            self.assertEqual(response.get("body"), RESPONSES_RESPONSE, label)
                            self.assertEqual(len(records), 1, label)
                        else:
                            self.assertIsNone(response.get("status"), response)
                            self.assertIn("read_error", response)
                            self.assertEqual(records, [], label)
                        if label == "Modex" and name != "full_partial_backlog_without_idle_slots":
                            self.assertLessEqual(
                                response["admission_fd_delta"],
                                case["preconnected_partial_count"] + case.get("preconnected_idle_count", 0) + 40,
                                response,
                            )
                        if name == "full_partial_backlog_without_idle_slots":
                            healthy = response["admission_healthy_results"]
                            print(
                                f"admission-case[{name}/{label}] "
                                f"before_release={response['admission_healthy_before_release']} "
                                f"client_fds_ready={response['admission_client_fds_ready']} "
                                f"first_elapsed_ms={healthy.get('first_elapsed_ms')} "
                                f"statuses={healthy.get('first_status')},{healthy.get('second_status')} "
                                f"upstream_requests={len(records)}"
                            )
                        else:
                            print(
                                f"admission-case[{name}/{label}] status={response.get('status')} "
                                f"read_error={response.get('read_error')} "
                                f"upstream_requests={len(records)}"
                            )
                        if "admission_process_count" in response:
                            self.assertGreaterEqual(response["admission_process_count"], 1)
                            print(
                                f"admission[{name}/{label}] "
                                f"pids={response['admission_process_count']} "
                                f"rss_delta_kib={response['admission_rss_delta_kib']} "
                                f"fd_delta={response['admission_fd_delta']} "
                                f"cpu_seconds_over_{response['admission_sample_seconds']:.1f}s="
                                f"{response['admission_cpu_seconds']:.3f}"
                            )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_http_0_9_keepalive_and_pipelined_requests_match_oracle(self):
        first = request_bytes(target=b"/v1/responses", version=b"HTTP/0.9")
        second = request_bytes((('Connection', 'close'),), target=b"/v1/chat/completions", version=b"HTTP/0.9")
        case = {
            "name": "http_0_9_pipelined_keepalive",
            "request": first,
            "pipelined_requests": [first, second],
            "check_close": True,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = [
                run_probe(binary, case, upstream)
                for binary in (ORACLE, MODEX)
            ]
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)
        expected = [(200, RESPONSES_RESPONSE), (200, PROVIDER_RESPONSE)]
        for response, records in results:
            self.assertEqual(response["process_exit"], 0, response["stderr"])
            self.assertEqual(
                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                expected,
            )
            self.assertTrue(response["connection_closed"])
            self.assertEqual(len(records), 2)
        self.assertEqual(
            [(record["method"], record["path"]) for record in results[0][1]],
            [(record["method"], record["path"]) for record in results[1][1]],
        )

    def test_response_header_overrides_filtering_and_invalid_values_match_oracle(self):
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for control in (
                "custom", "filtered", "invalid", "invalid-date", "folded", "folded-server",
            ):
                case = response_header_control_case(control)
                with self.subTest(control=control):
                    before = time.time()
                    oracle, oracle_records = run_probe(ORACLE, case, upstream)
                    modex, modex_records = run_probe(MODEX, case, upstream)
                    after = time.time()
                    for label, response in (("oracle", oracle), ("modex", modex)):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["read_error"], "", label)
                    self.assertEqual(oracle["status"], modex["status"])
                    self.assertEqual(oracle["body"], modex["body"])
                    self.assertEqual(
                        {name for name in (b"server", b"date") if name in response_header_values(oracle)},
                        {name for name in (b"server", b"date") if name in response_header_values(modex)},
                        control,
                    )
                    self.assertEqual(len(oracle_records), 1)
                    self.assertEqual(len(modex_records), 1)

                    if control == "custom":
                        for response in (oracle, modex):
                            values = response_header_values(response)
                            self.assertEqual(values.get(b"server"), [
                                b"synthetic-server-one", b"synthetic-server-two",
                            ])
                            self.assertEqual(values.get(b"date"), [
                                b"Sat, 01 Jan 2000 00:00:00 GMT",
                                b"Sun, 02 Jan 2000 00:00:00 GMT",
                            ])
                    else:
                        assert_response_headers(self, oracle, before, after, "oracle")
                        assert_response_headers(self, modex, before, after, "modex")
                        for response in (oracle, modex):
                            names = [line.partition(b":")[0].lower() for line in response["raw_response_head"].split(b"\r\n")]
                            self.assertNotIn(b"x-injected", names)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_large_request_head_boundaries_match_pinned_oracle(self):
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for head_bytes in (65535, 65536, 65537):
                case = large_request_head_case(head_bytes)
                with self.subTest(head_bytes=head_bytes):
                    oracle, oracle_records = run_probe(ORACLE, case, upstream)
                    modex, modex_records = run_probe(MODEX, case, upstream)
                    for label, response, records in (
                        ("oracle", oracle, oracle_records),
                        ("modex", modex, modex_records),
                    ):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual((response["status"], response["body"]), (200, RESPONSES_RESPONSE), label)
                        self.assertEqual(len(records), 1, label)
                        expected_pad = case["request"].split(b"X-Pad: ", 1)[1].split(b"\r\n", 1)[0]
                        self.assertEqual(len(records[0]["headers"]["x-pad"]), len(expected_pad), label)
                    self.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_large_request_heads_use_bounded_linear_capture(self):
        assert_large_request_head_cases(self, ORACLE, MODEX)

    def test_chat_passthrough_request_header_parity(self):
        assert_chat_request_header_parity(self, ORACLE, MODEX)

    def test_chat_passthrough_response_framing(self):
        assert_chat_response_framing(self, ORACLE, MODEX)

    def test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed(self):
        single_valid_expect = expectation_request_case(
            "single_valid_expect_control",
            ["100-continue"],
        )
        request_with_expect = expectation_request_case(
            "duplicate_valid_expect",
            ["100-continue", "100-continue"],
        )
        mixed_expect = expectation_request_case(
            "valid_expect_before_unknown_duplicate",
            ["100-continue", "100-wait"],
        )
        mixed_expect_reverse = expectation_request_case(
            "unknown_expect_before_valid_duplicate",
            ["100-wait", "100-continue"],
        )
        invalid_target_duplicate = expectation_request_case(
            "invalid_target_duplicate_valid_expect",
            ["100-continue", "100-continue"],
            target=b"http://example.test/v1/responses",
        )
        conflicting_framing = raw_expectation_case(
            "unsupported_expect_with_conflicting_framing",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-wait\r\n"
            b"Content-Length: 0\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
        )
        duplicate_content_length = raw_expectation_case(
            "unsupported_expect_with_duplicate_content_length",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\nExpect: 100-wait\r\n"
            b"Content-Length: 0\r\nContent-Length: 0\r\n\r\n",
        )
        duplicate_transfer_encoding = raw_expectation_case(
            "unsupported_expect_with_duplicate_transfer_encoding",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n"
            b"Expect: 100-wait\r\n\r\n0\r\n\r\n",
        )
        malformed_content_length = raw_expectation_case(
            "unsupported_expect_with_malformed_content_length",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: x\r\nExpect: 100-wait\r\n\r\n",
        )
        unsupported_transfer_encoding = raw_expectation_case(
            "unsupported_expect_with_unsupported_transfer_encoding",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Transfer-Encoding: gzip\r\nExpect: 100-wait\r\n\r\n",
        )
        valid_expect_ambiguous_framing = raw_expectation_case(
            "valid_expect_with_ambiguous_framing",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n"
            b"Content-Length: " + str(len(REQUEST_BODY)).encode() + b"\r\n"
            b"Transfer-Encoding: chunked\r\nExpect: 100-continue\r\nConnection: close\r\n\r\n",
        )
        valid_expect_ambiguous_framing["body_after_continue"] = (
            format(len(REQUEST_BODY), "X").encode("ascii")
            + b"\r\n" + REQUEST_BODY + b"\r\n0\r\n\r\n"
        )
        fragmented_unsupported_expect = raw_expectation_case(
            "fragmented_unsupported_expect_half_closed",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: x\r\nTransfer-Encoding: chunked\r\nExpect: 100-wait\r\n"
            b"Connection: close\r\n\r\n",
            half_close=True,
        )
        split = fragmented_unsupported_expect["request"].index(b"Transfer-Encoding") + 8
        fragmented_unsupported_expect["request_parts"] = [
            fragmented_unsupported_expect["request"][:split],
            fragmented_unsupported_expect["request"][split:],
        ]
        fragmented_unsupported_expect["request_part_delay_ms"] = 5
        pipelined_unsupported_expect = raw_expectation_case(
            "unsupported_expect_framing_closes_before_pipeline_tail",
            fragmented_unsupported_expect["request"],
        )
        pipelined_unsupported_expect["pipelined_requests"] = [
            fragmented_unsupported_expect["request"],
            request_bytes((("Connection", "close"),)),
        ]
        pipelined_unsupported_expect["pipelined_response_count"] = 1
        malformed_expect_value = raw_expectation_case(
            "malformed_expect_value_token",
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Expect: 100-continue\x00bad\r\nContent-Length: 0\r\n\r\n",
        )
        cases = (
            (single_valid_expect, {
                "oracle": (200, "OK", RESPONSES_RESPONSE, [100], 1, False),
                "modex": (200, "OK", RESPONSES_RESPONSE, [100], 1, False),
            }),
            (request_with_expect, {
                "oracle": (200, "OK", RESPONSES_RESPONSE, [100], 1, False),
                "modex": (200, "OK", RESPONSES_RESPONSE, [100], 1, False),
            }),
            (mixed_expect, {
                "oracle": (200, "OK", RESPONSES_RESPONSE, [100], 1, False),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (mixed_expect_reverse, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (invalid_target_duplicate, {
                "oracle": (400, "Bad Request", INVALID_REQUEST_TARGET_BODY, [], 0, False),
                "modex": (400, "Bad Request", INVALID_REQUEST_TARGET_BODY, [], 0, True),
            }),
            (conflicting_framing, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (duplicate_content_length, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (duplicate_transfer_encoding, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (malformed_content_length, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (unsupported_transfer_encoding, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (fragmented_unsupported_expect, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (pipelined_unsupported_expect, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
            (valid_expect_ambiguous_framing, {
                "oracle": (200, "OK", RESPONSES_RESPONSE, [100], 1, True),
                "modex": (502, "Bad Gateway", b"gateway request capture failed", [], 0, True),
            }),
            (malformed_expect_value, {
                "oracle": (417, "Expectation Failed", b"", [], 0, True),
                "modex": (417, "Expectation Failed", b"", [], 0, True),
            }),
        )
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case, expected in cases:
                with self.subTest(case=case["name"]):
                    oracle_response, oracle_records = run_probe(ORACLE, case, upstream)
                    modex_response, modex_records = run_probe(MODEX, case, upstream)
                    upstream_bodies = {}
                    for label, response, records in (
                        ("oracle", oracle_response, oracle_records),
                        ("modex", modex_response, modex_records),
                    ):
                        status, reason, body, interim, upstream_count, closed = expected[label]
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], status, label)
                        self.assertEqual(response["reason"], reason, label)
                        self.assertEqual(response["body"], body, label)
                        self.assertEqual(response["interim_statuses"], interim, label)
                        self.assertEqual(response["read_error"], "", label)
                        self.assertEqual(response["connection_closed"], closed, label)
                        self.assertEqual(len(records), upstream_count, label)
                        if records:
                            upstream_bodies[label] = records[0]["body"]
                    if case["name"] in ("single_valid_expect_control", "duplicate_valid_expect"):
                        self.assertEqual(upstream_bodies["oracle"], upstream_bodies["modex"])
                    if case["name"] == "unsupported_expect_framing_closes_before_pipeline_tail":
                        for response in (oracle_response, modex_response):
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                                [(417, b"")],
                            )
                    if case["name"] in (
                        "malformed_expect_value_token",
                        "unsupported_expect_with_duplicate_content_length",
                    ):
                        stable_head = lambda response: b"\r\n".join(
                            line for line in response["raw_response_head"].split(b"\r\n")
                            if not line.lower().startswith(b"date:")
                        )
                        expected_head = (
                            b"HTTP/1.1 417 Expectation Failed\r\n"
                            b"Server: tiny-http (Rust)\r\nContent-Length: 0\r\n\r\n"
                        )
                        self.assertEqual(stable_head(oracle_response), expected_head)
                        self.assertEqual(stable_head(modex_response), expected_head)
                        self.assertEqual(stable_head(oracle_response), stable_head(modex_response))
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_non_websocket_connection_upgrade_reads_through_eof(self):
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case in upgrade_eof_cases():
                with self.subTest(case=case["name"]):
                    status = case["status"]
                    oracle_response, oracle_records = run_probe(ORACLE, case, upstream)
                    modex_response, modex_records = run_probe(MODEX, case, upstream)
                    for response in (oracle_response, modex_response):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], status)
                        self.assertEqual(response["read_error"], "")
                        if "expected_request_parts_sent" in case:
                            self.assertEqual(response["request_parts_sent_at_response"], case["expected_request_parts_sent"])
                    self.assertEqual(modex_response["body"], oracle_response["body"])
                    self.assertEqual(len(oracle_records), int(status == 200))
                    self.assertEqual(len(modex_records), int(status == 200))
                    if oracle_records:
                        self.assertNotIn("upgrade", oracle_records[0]["headers"])
                        self.assertNotIn("upgrade", modex_records[0]["headers"])
                        self.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_http_1_1_sequential_requests_reuse_the_client_connection(self):
        first = request_bytes(target=b"/v1/responses")
        second = request_bytes(target=b"/v1/chat/completions")
        case = {
            "name": "sequential_keep_alive_requests",
            "request": first,
            "sequential_requests": [first, second],
            "check_close": True,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        expected_bodies = [RESPONSES_RESPONSE, PROVIDER_RESPONSE]
        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(
                    [(item["status"], item["body"]) for item in response["sequential_responses"]],
                    [(200, body) for body in expected_bodies],
                )
                self.assertFalse(any(
                    name.lower() == "connection" and value.lower() == "close"
                    for item in response["sequential_responses"]
                    for name, value in item["headers"]
                ))
                self.assertFalse(response["connection_closed"])
                self.assertEqual(len(records), 2)
                self.assertEqual(
                    [(item["method"], item["path"]) for item in records],
                    [("POST", "/v1/chat/completions")] * 2,
                )

    def test_two_codex_requests_overlap_at_the_provider(self):
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "synthetic concurrent request"}],
        }, separators=(",", ":")).encode()
        requests = [
            request_bytes(
                headers=(("Connection", "close"),),
                body=body,
                target=f"/v1/chat/completions?parallel={index}".encode(),
            )
            for index in (1, 2)
        ]
        case = {
            "name": "two_concurrent_chat_completions",
            "request": requests[0],
            "concurrent_requests": requests,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {}
            for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
                upstream.reset_parallel_probe()
                response, records = run_probe(binary, case, upstream)
                results[label] = (response, records, upstream.snapshot_parallel_probe())
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        expected_paths = ["/v1/chat/completions?parallel=1", "/v1/chat/completions?parallel=2"]
        for label, (response, records, (peak_active, overlapped)) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(
                    response["concurrent_responses"],
                    [{"status": 200, "body": PROVIDER_RESPONSE}] * 2,
                )
                self.assertTrue(overlapped, "the upstream barrier observed both requests together")
                self.assertGreaterEqual(peak_active, 2)
                self.assertEqual(sorted(record["path"] for record in records), sorted(expected_paths))

    def test_worker_count_controls_parallel_provider_stalls(self):
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "synthetic configured concurrency"}],
        }, separators=(",", ":")).encode()
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            pinned_binaries = []
            for label, binary, expected_hash in (
                ("0.165.1", ORACLE_01651, ORACLE_SHA256),
                ("0.439.2", ORACLE_04392, ORACLE_04392_SHA256),
            ):
                if not binary.is_file() or any(path == binary for _, path in pinned_binaries):
                    continue
                actual_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
                self.assertEqual(actual_hash, expected_hash, label)
                pinned_binaries.append((label, binary))
            binaries = (*pinned_binaries, ("Modex", MODEX))
            oracle_parallelism = max(
                1,
                len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity")
                else (os.cpu_count() or 1),
            )
            for worker_count in (1, 2, 12):
                for label, binary in binaries:
                    if label == "Modex":
                        configured_count, scheduler_parallelism = configured_modex_worker_capacity(worker_count)
                        self.assertEqual(
                            configured_count,
                            min(worker_count, min(12, max(4, scheduler_parallelism))),
                        )
                        request_count = (
                            2 if worker_count == 1
                            else min(configured_count, scheduler_parallelism)
                        )
                    else:
                        request_count = (
                            2 if worker_count == 1
                            else min(worker_count, oracle_parallelism)
                        )
                    requests = [
                        request_bytes(
                            headers=(("Connection", "close"),),
                            body=body,
                            target=f"/v1/chat/completions?parallel={index}".encode(),
                        )
                        for index in range(request_count)
                    ]
                    case = {
                        "name": f"configured_worker_count_{worker_count}",
                        "request": requests[0],
                        "concurrent_requests": requests,
                        "process_timeout": 30,
                        "environment_overrides": {
                            "PRODEX_RUNTIME_PROXY_WORKER_COUNT": str(worker_count),
                        },
                    }
                    with self.subTest(worker_count=worker_count, label=label):
                        upstream.reset_parallel_probe(request_count)
                        response, records = run_probe(binary, case, upstream)
                        peak_active, overlapped = upstream.snapshot_parallel_probe()
                        expected_overlap = worker_count > 1 and request_count > 1
                        expected_peak = 1 if worker_count == 1 else request_count
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(len(records), request_count)
                        self.assertEqual(
                            len(response["concurrent_responses"]), request_count,
                        )
                        self.assertEqual(overlapped, expected_overlap)
                        self.assertEqual(peak_active, expected_peak)
                        if expected_overlap:
                            self.assertEqual(
                                [item["status"] for item in response["concurrent_responses"]],
                                [200] * request_count,
                            )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_parent_eof_interrupts_a_stalled_provider_request(self):
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "synthetic stalled request"}],
        }, separators=(",", ":")).encode()
        chat_request = request_bytes(
            headers=(("Connection", "close"),),
            body=body,
            target=b"/v1/chat/completions?parent-exit=slow",
        )
        messages_request = request_bytes(
            headers=(("Connection", "close"), ("X-Parent-Exit-Slow", "1")),
            body=json.dumps({"model": "deepseek-chat", "input": "synthetic stalled request",
                             "tools": [{"type": "web_search_preview"}]}).encode(),
            target=b"/v1/responses",
        )
        results = {}
        for label, binary, request, expected_path in (
            ("oracle-chat", ORACLE, chat_request, "/v1/chat/completions?parent-exit=slow"),
            ("modex-chat", MODEX, chat_request, "/v1/chat/completions?parent-exit=slow"),
            ("oracle-messages", ORACLE, messages_request, "/anthropic/v1/messages"),
            ("modex-messages", MODEX, messages_request, "/anthropic/v1/messages"),
        ):
            upstream = Upstream()
            upstream_worker = threading.Thread(target=upstream.serve_forever, daemon=True)
            upstream_worker.start()
            try:
                with tempfile.TemporaryDirectory(prefix="modex-parent-exit-trigger-") as temporary:
                    trigger = Path(temporary) / "release-codex"
                    case = {
                        "name": "parent_exit_during_stalled_upstream",
                        "request": request,
                        "parent_exit_active": True,
                        "parent_exit_trigger": str(trigger),
                        "process_timeout": 12,
                    }
                    outcome = {}

                    def run():
                        try:
                            outcome["value"] = run_probe(binary, case, upstream)
                        except BaseException as error:
                            outcome["error"] = error

                    probe_worker = threading.Thread(target=run, daemon=True)
                    probe_worker.start()
                    self.assertTrue(
                        upstream.parent_exit_slow_started.wait(8),
                        f"{label} did not reach the stalled upstream",
                    )
                    trigger.touch()
                    probe_worker.join(12)
                    self.assertFalse(probe_worker.is_alive(), f"{label} did not exit after parent EOF")
                    if "error" in outcome:
                        raise outcome["error"]
                    response, records = outcome["value"]
                    results[label] = (
                        response,
                        records,
                        upstream.parent_exit_upstream_closed.is_set(),
                        expected_path,
                    )
            finally:
                upstream.shutdown()
                upstream.server_close()
                upstream_worker.join(timeout=2)

        for label, (response, records, upstream_closed, expected_path) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["path"], expected_path)
                if label.startswith("modex"):
                    self.assertLess(response["process_elapsed_ms"], 3000, label)
                    self.assertTrue(upstream_closed, "parent EOF closed the stalled provider socket")

    def test_partial_request_headers_still_complete_before_relay_dispatch(self):
        request = request_bytes(target=b"/v1/responses")
        header_end = request.index(b"\r\n\r\n") + 4
        case = {
            "name": "partial_keep_alive_request_headers",
            "request": request,
            "request_parts": [request[:10], request[10:header_end - 1], request[header_end - 1:header_end], request[header_end:]],
            "request_part_delay_ms": 30,
            "check_close": True,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual((response["status"], response["body"]), (200, RESPONSES_RESPONSE))
                self.assertFalse(response["connection_closed"])
                self.assertEqual(len(records), 1)

    def test_pipelined_requests_match_oracle_across_framing_and_responses(self):
        first_body = b'{"model":"deepseek-chat","messages":[{"role":"user","content":"pipeline-first"}],"stream":false}'
        second_body = b'{"model":"deepseek-chat","input":"pipeline-second"}'
        first = request_bytes(target=b"/v1/responses", body=first_body)
        bodyless_error = (
            b"GET /v1/not-supported HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        )
        chunked = (
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
            + format(len(first_body), "X").encode("ascii") + b"\r\n"
            + first_body + b"\r\n0\r\n\r\n"
        )
        second = request_bytes(target=b"/v1/responses", body=second_body)
        head_sse = request_bytes(
            (("X-Oracle-Response", "sse"),), body=first_body,
            target=b"/v1/chat/completions", method=b"HEAD",
        )
        chunked_zero = chunked.rfind(b"0\r\n")
        chunked_terminator = chunked_zero + 3
        oversized_second = (
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: close\r\nContent-Length: 67108865\r\n\r\n"
        )
        cases = [
            {
                "name": "pipelined_fixed_then_bodyless_error",
                "request": first,
                "pipelined_requests": [first, bodyless_error],
                "expected": [(200, RESPONSES_RESPONSE), (404, UNSUPPORTED_ROUTE_BODY)],
                "upstream_count": 1,
            },
            {
                "name": "pipelined_fragmented_chunked_then_fixed",
                "request": chunked,
                "pipelined_requests": [chunked, second],
                "pipelined_request_parts": [
                    chunked[:chunked.index(b"\r\n\r\n") + 4],
                    chunked[chunked.index(b"\r\n\r\n") + 4:chunked_zero],
                    chunked[chunked_zero:chunked_terminator],
                    chunked[chunked_terminator:chunked_terminator + 1],
                    chunked[chunked_terminator + 1:] + second,
                ],
                "pipelined_request_delay_ms": 10,
                "expected_pipelined_request_parts_sent": 5,
                "expected": [(200, PROVIDER_RESPONSE), (200, RESPONSES_RESPONSE)],
                "upstream_count": 2,
            },
            {
                "name": "pipelined_oversized_body_keeps_limit",
                "request": first,
                "pipelined_requests": [first, oversized_second],
                "check_close": True,
                "expected": [(200, RESPONSES_RESPONSE), (413, b"proxied request body is too large")],
                "upstream_count": 1,
            },
            {
                "name": "pipelined_head_then_get",
                "request": request_bytes(
                    (("X-Oracle-Response", "json"),),
                    body=first_body, method=b"HEAD",
                ),
                "pipelined_requests": [
                    request_bytes(
                        (("X-Oracle-Response", "json"),),
                        body=first_body, method=b"HEAD",
                    ),
                    second,
                ],
                "expected": [(502, b""), (200, RESPONSES_RESPONSE)],
                "upstream_count": 2,
            },
            {
                "name": "pipelined_head_sse_half_close_then_get",
                "request": head_sse,
                "pipelined_requests": [head_sse, second],
                "half_close": True,
                "check_close": True,
                "expected": [(200, b""), (200, RESPONSES_RESPONSE)],
                "expected_head_wire_body": {"oracle": b"0\r\n\r\n", "modex": b"0\r\n\r\n"},
                "upstream_count": 2,
            },
            {
                "name": "pipelined_head_sse_then_get",
                "request": head_sse,
                "pipelined_requests": [head_sse, second],
                "expected": [(200, b""), (200, RESPONSES_RESPONSE)],
                "expected_head_wire_body": {"oracle": b"0\r\n\r\n", "modex": b"0\r\n\r\n"},
                "upstream_count": 2,
            },
            {
                "name": "pipelined_sse_then_buffered_response",
                "request": request_bytes(
                    (("X-Oracle-Response", "sse"),),
                    body=first_body, target=b"/v1/chat/completions",
                ),
                "pipelined_requests": [
                    request_bytes(
                        (("X-Oracle-Response", "sse"),),
                        body=first_body, target=b"/v1/chat/completions",
                    ),
                    second,
                ],
                "expected": [(200, PROVIDER_SSE_RESPONSE), (200, RESPONSES_RESPONSE)],
                "upstream_count": 2,
            },
            {
                "name": "pipelined_connection_close_stops_after_first",
                "request": request_bytes((("Connection", "close"),), body=first_body),
                "pipelined_requests": [
                    request_bytes((("Connection", "close"),), body=first_body), second,
                ],
                "pipelined_response_count": 1,
                "check_close": True,
                "expected": [(200, RESPONSES_RESPONSE)],
                "upstream_count": 1,
            },
        ]
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case in cases:
                with self.subTest(case=case["name"]):
                    results = {
                        label: run_probe(binary, case, upstream)
                        for label, binary in (("oracle", ORACLE), ("modex", MODEX))
                    }
                    for label, (response, records) in results.items():
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(
                            [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                            case["expected"], label,
                        )
                        if "expected_pipelined_request_parts_sent" in case:
                            self.assertEqual(
                                response["request_parts_sent_at_response"],
                                case["expected_pipelined_request_parts_sent"], label,
                            )
                        self.assertEqual(len(records), case["upstream_count"], label)
                        if case.get("check_close"):
                            self.assertTrue(response["connection_closed"], label)
                        if "expected_head_wire_body" in case:
                            self.assertEqual(
                                response["pipelined_responses"][0]["head_wire_body"],
                                case["expected_head_wire_body"][label], label,
                            )
                    if case["name"] == "pipelined_fragmented_chunked_then_fixed":
                        oracle_bodies = sorted(record["body"] for record in results["oracle"][1])
                        modex_bodies = sorted(record["body"] for record in results["modex"][1])
                        self.assertEqual(modex_bodies, oracle_bodies)
                        self.assertIn(first_body, modex_bodies)
                        self.assertTrue(any(b"pipeline-second" in body for body in modex_bodies))
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_http_1_1_connection_close_still_closes_after_one_request(self):
        request = request_bytes((("Connection", "close"),))
        case = {
            "name": "explicit_connection_close",
            "request": request,
            "sequential_requests": [request],
            "check_close": True,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual([item["status"] for item in response["sequential_responses"]], [200])
                self.assertFalse(any(
                    name.lower() == "connection" and value.lower() == "close"
                    for item in response["sequential_responses"]
                    for name, value in item["headers"]
                ))
                self.assertTrue(response["connection_closed"])
                self.assertEqual(len(records), 1)

    def test_connection_keep_alive_selection_matches_pinned_tinyhttp_rules(self):
        cases = (
            (
                "http_1_0_keep_alive",
                (("Connection", "keep-alive"),),
                b"HTTP/1.0",
                True,
            ),
            (
                "http_1_0_keep_alive_substring",
                (("Connection", "not-keep-alive"),),
                b"HTTP/1.0",
                True,
            ),
            (
                "duplicate_connection_first_header_wins",
                (("Connection", "keep-alive"), ("Connection", "close")),
                b"HTTP/1.1",
                False,
            ),
        )
        for name, headers, version, continue_after_will_close in cases:
            first = request_bytes(headers=headers, target=b"/v1/responses", version=version)
            second_headers = (("Connection", "keep-alive"),) if version == b"HTTP/1.0" else ()
            second = request_bytes(headers=second_headers, target=b"/v1/chat/completions", version=version)
            case = {
                "name": name,
                "request": first,
                "sequential_requests": [first, second],
                "continue_after_will_close": continue_after_will_close,
                "check_close": True,
            }
            upstream = Upstream()
            worker = threading.Thread(target=upstream.serve_forever, daemon=True)
            worker.start()
            try:
                results = {
                    label: run_probe(binary, case, upstream)
                    for label, binary in (("oracle", ORACLE), ("modex", MODEX))
                }
            finally:
                upstream.shutdown()
                upstream.server_close()
                worker.join(timeout=2)

            for label, (response, records) in results.items():
                with self.subTest(case=name, label=label):
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(
                        [(item["status"], item["body"]) for item in response["sequential_responses"]],
                        [(200, RESPONSES_RESPONSE), (200, PROVIDER_RESPONSE)],
                    )
                    self.assertFalse(any(
                        header_name.lower() == "connection"
                        for item in response["sequential_responses"]
                        for header_name, _ in item["headers"]
                    ))
                    self.assertFalse(response["connection_closed"])
                    self.assertEqual(len(records), 2)

    def test_idle_keep_alive_client_does_not_block_a_second_client(self):
        first = request_bytes(target=b"/v1/responses")
        second = request_bytes(target=b"/v1/chat/completions")
        case = {
            "name": "idle_keep_alive_does_not_block_second_client",
            "request": first,
            "sequential_requests": [first],
            "second_client_request": second,
            "check_close": True,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(
                    [(item["status"], item["body"]) for item in response["sequential_responses"]],
                    [(200, RESPONSES_RESPONSE)],
                )
                self.assertEqual(
                    (response["second_client"]["status"], response["second_client"]["body"]),
                    (200, PROVIDER_RESPONSE),
                )
                self.assertFalse(response["connection_closed"])
                self.assertEqual(len(records), 2)

    def test_partial_reused_request_does_not_block_second_client(self):
        first = request_bytes(target=b"/v1/responses")
        second = request_bytes(( ("Connection", "close"),), target=b"/v1/chat/completions")
        case = {
            "name": "partial_reused_request_blocks_second_client",
            "request": first,
            "sequential_requests": [first],
            "reused_partial_request": b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n",
            "second_client_request": second,
            "partial_hold_ms": 1000,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(response["second_client"]["status"], 200)
                self.assertEqual(
                    response["second_client"]["body"],
                    PROVIDER_RESPONSE,
                )
                self.assertTrue(response["second_client_finished_after_partial_close"])
                self.assertEqual(len(records), 2)
                self.assertTrue(response["second_client_responded_before_partial_close"])

    def test_parent_shutdown_exits_while_idle_keep_alive_socket_is_held(self):
        first = request_bytes(target=b"/v1/responses")
        case = {
            "name": "parent_shutdown_during_idle_keep_alive",
            "request": first,
            "sequential_requests": [first],
            "hold_first_client_ms": 5000,
            "process_timeout": 3,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", MODEX))
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertLess(response["process_elapsed_ms"], 3000, label)
                self.assertEqual(
                    [(item["status"], item["body"]) for item in response["sequential_responses"]],
                    [(200, RESPONSES_RESPONSE)],
                )
                self.assertEqual(len(records), 1)

    def test_saturated_idle_pool_evicts_oldest_connection_to_admit_new_client(self):
        if (
            not ORACLE_04392.is_file()
            or hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256
        ):
            raise AssertionError("Pinned Prodex 0.439.2 oracle is missing or has the wrong checksum")
        request = request_bytes(target=b"/v1/responses")
        case = {
            "name": "saturated_idle_pool_admits_new_client",
            "request": request,
            "saturation_extra_connections": 127,
            "saturation_request": request,
            "process_timeout": 30,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (
                    ("0.165.1", ORACLE), ("0.439.2", ORACLE_04392), ("Modex", MODEX),
                )
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual((response["status"], response["body"]), (200, RESPONSES_RESPONSE))
                self.assertEqual(response["saturation_held_connections"], 127)
                self.assertEqual(response["saturation_overflow_status"], 200)
                self.assertEqual(response["saturation_overflow_body"], RESPONSES_RESPONSE)
                self.assertEqual(response["saturation_oldest_closed"], label == "Modex")
                self.assertEqual(len(records), 129)

    def test_saturated_pool_preserves_oldest_partial_request_during_admission(self):
        if (
            not ORACLE_04392.is_file()
            or hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256
        ):
            raise AssertionError("Pinned Prodex 0.439.2 oracle is missing or has the wrong checksum")
        request = request_bytes(target=b"/v1/responses")
        header_end = request.index(b"\r\n\r\n") + 4
        case = {
            "name": "saturated_pool_preserves_oldest_partial_request",
            "request": request,
            "saturation_extra_connections": 127,
            "saturation_request": request,
            "saturation_oldest_partial": request[:header_end - 1],
            "process_timeout": 30,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (
                    ("0.165.1", ORACLE), ("0.439.2", ORACLE_04392), ("Modex", MODEX),
                )
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertEqual(response["saturation_oldest_status"], 200)
                self.assertEqual(response["saturation_oldest_body"], RESPONSES_RESPONSE)
                self.assertEqual(response["saturation_overflow_status"], 200)
                self.assertEqual(response["saturation_overflow_body"], RESPONSES_RESPONSE)
                self.assertEqual(response["saturation_held_connections"], 127)
                self.assertFalse(response["saturation_oldest_closed"])
                self.assertEqual(len(records), 130)

    def test_ready_parked_clients_are_served_during_new_client_churn(self):
        if (
            not ORACLE_04392.is_file()
            or hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256
        ):
            raise AssertionError("Pinned Prodex 0.439.2 oracle is missing or has the wrong checksum")
        request = request_bytes(target=b"/v1/responses")
        churn_request = request_bytes(
            (("Connection", "close"),), target=b"/v1/chat/completions"
        )
        case = {
            "name": "ready_parked_clients_under_new_client_churn",
            "request": request,
            "sequential_requests": [request],
            "fairness_extra_connections": 7,
            "fairness_churn_count": 24,
            "fairness_request": request,
            "fairness_churn_request": churn_request,
            "fairness_repeat_count": 32,
            "process_timeout": 30,
        }
        upstream = Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            results = {
                label: run_probe(binary, case, upstream)
                for label, binary in (
                    ("0.165.1", ORACLE), ("0.439.2", ORACLE_04392), ("Modex", MODEX),
                )
            }
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

        for label, (response, records) in results.items():
            with self.subTest(label=label):
                self.assertEqual(response["process_exit"], 0, response["stderr"])
                self.assertTrue(response["fairness_workers_finished"])
                self.assertEqual(response["fairness_errors"], [])
                self.assertEqual(response["fairness_reused_statuses"], [200] * 39)
                self.assertEqual(response["fairness_churn_statuses"], [200] * 24)
                self.assertEqual(response["fairness_churn_interleaved"], [True])
                self.assertEqual(len(records), 71)
                print(
                    f"fairness[{label}] elapsed_ms={response['response_elapsed_ms']} "
                    f"reused={len(response['fairness_reused_statuses'])} "
                    f"churn={len(response['fairness_churn_statuses'])}"
                )


if __name__ == "__main__":
    unittest.main()
