"""Production Super CLI against isolated synthetic Codex and loopback providers."""
import errno
import hashlib
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256

CODEX = r'''
import http.client, json, os, pathlib, signal, sys, time
from urllib.parse import urlsplit
args = sys.argv[1:]
capture = pathlib.Path(os.environ["MODEX_LAUNCH_CAPTURE"])
def save(value):
    value["script_argv0"] = sys.argv[0]
    with capture.open("a") as handle: handle.write(json.dumps(value) + "\n")
probe_environment = ("CODEX_HOME", "TEST_CODEX_LOG", "TEST_CODEX_LOG_APPEND",
                     "TEST_CODEX_ARGS_LOG", "TEST_CODEX_ARGS_LOG_APPEND", "TEST_CODEX_STDIN_LOG")
if args == ["--version"]:
    save({"kind":"probe", "args":args,
          "environment":{key:os.environ.get(key) for key in probe_environment}})
    if os.environ.get("MODEX_TEST_CODEX_VERSION_OVERSIZE"):
        sys.stdout.buffer.write(b"codex-cli " + b"0" * (1024 * 1024))
        raise SystemExit(0)
    version = os.environ.get("MODEX_TEST_CODEX_VERSION", "codex-cli 0.216.0")
    print(version, file=sys.stderr if os.environ.get("MODEX_TEST_CODEX_VERSION_STDERR") else sys.stdout)
    if os.environ.get("MODEX_TEST_CODEX_VERSION_EXIT"):
        raise SystemExit(int(os.environ["MODEX_TEST_CODEX_VERSION_EXIT"]))
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    save({"kind":"probe", "args":args,
          "environment":{key:os.environ.get(key) for key in probe_environment}})
    if os.environ.get("MODEX_TEST_CODEX_HELP_OVERSIZE"):
        sys.stdout.buffer.write(b"Codex app-server " + b"0" * (1024 * 1024))
        raise SystemExit(0)
    if os.environ["MODEX_LAUNCH_SCENARIO"] == "app-server-help-failure":
        raise SystemExit(7)
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    save({"kind":"preflight", "pid":os.getpid(), "args":args})
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request: continue
        save({"kind":"request", "method":request["method"], "params":request.get("params")})
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "split-utf8-noise" and request["method"] == "initialize":
            noise = b"not json\n" + json.dumps({"id": 999, "result": {}}).encode() + b"\n"
            frame = json.dumps({"id": request["id"], "result": {"message": "雪"}}, ensure_ascii=False).encode() + b"\n"
            payload = noise + frame
            split = payload.index("雪".encode()) + 1
            sys.stdout.buffer.write(payload[:split])
            sys.stdout.flush()
            time.sleep(0.1)
            sys.stdout.buffer.write(payload[split:])
            sys.stdout.flush()
            continue
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "legacy" and request["method"] == "hooks/list":
            print(json.dumps({"id":request["id"],"error":{"code":-32601,"message":"Method not found"}}),flush=True)
            time.sleep(30)
        if (os.environ["MODEX_LAUNCH_SCENARIO"] == "invalid-utf8" or
                (os.environ["MODEX_LAUNCH_SCENARIO"] == "invalid-utf8-later" and request["method"] == "hooks/list")):
            sys.stdout.buffer.write(bytes([255, 10]))
            sys.stdout.flush()
            time.sleep(30)
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "closed-input":
            os.close(0)
            time.sleep(0.2)
            print(json.dumps({"id":request["id"],"result":{}}), flush=True)
            time.sleep(30)
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "closed-output":
            os.close(1)
            time.sleep(30)
        print(json.dumps({"id":request["id"],"result":{"data":[]}}), flush=True)
        if request["id"] == 4: time.sleep(30)
    raise SystemExit(0)
home = pathlib.Path(os.environ["CODEX_HOME"])
config = {}
for index, arg in enumerate(args[:-1]):
    if arg == "-c":
        key, value = args[index+1].split("=",1)
        try: value = json.loads(value)
        except ValueError: pass
        config[key] = value
children = pathlib.Path(f"/proc/{os.getppid()}/task/{os.getppid()}/children")
save({"kind":"launch","pid":os.getpid(),"mode":home.stat().st_mode & 0o777,"args":args,"config":config,
      "catalog":json.loads(pathlib.Path(config["model_catalog_json"]).read_text()) if "model_catalog_json" in config else None,
      "runtime_config":(home/"config.toml").read_text() if (home/"config.toml").exists() else None,
      "auth":json.loads((home/"auth.json").read_text()),"children":children.read_text().split(),
      "environment":{key:os.environ.get(key) for key in ("CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT","PRODEX_RUNTIME_LOCAL_KEY","CODEX_SANDBOX_SENTINEL")}})
(home/"sessions"/"synthetic-session.jsonl").write_text('{"synthetic":true}\n')
scenario = os.environ["MODEX_LAUNCH_SCENARIO"]
if scenario in ("kill-relay", "kill-relay-ignores-term"):
    def terminate(signum, frame):
        save({"kind":"terminated", "pid":os.getpid(), "signal":signum})
        if scenario == "kill-relay": raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
if scenario == "exit-seven": raise SystemExit(7)
if scenario == "extra-state":
    (home/"synthetic-user-state").write_text("preserve this data")
    raise SystemExit(0)
if scenario in ("slow-partial", "slow-partial-body", "slow-partial-fragmented-header",
                "slow-partial-body-limit", "slow-partial-flood", "slow-partial-overflow-completes",
                "truncated-header-eof", "truncated-body-eof",
                "truncated-small-body-eof", "empty-request-body") or scenario.startswith("request-head-"):
    import select
    import socket
    target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
    host, port = target.hostname, target.port
    path = target.path.rstrip("/") + "/responses"
    def read_status(connection, timeout):
        received = bytearray()
        deadline = time.monotonic() + timeout
        while b"\r\n\r\n" not in received:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([connection], [], [], remaining)[0]:
                return None
            chunk = connection.recv(65536)
            if not chunk:
                return None
            received.extend(chunk)
        return int(bytes(received).split(b"\r\n", 1)[0].split()[1])
    body = json.dumps({"model":"deepseek-chat","input":"synthetic slow-partial probe"},separators=(",",":")).encode()
    request = (f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
               f"Content-Type: application/json\r\nAuthorization: Bearer synthetic-codex-key\r\n"
               f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body
    if scenario in (
        "truncated-header-eof", "truncated-body-eof", "truncated-small-body-eof",
        "empty-request-body",
    ):
        connection = socket.create_connection((host, port), timeout=5)
        if scenario == "truncated-header-eof":
            connection.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                                "Content-Length: 2\r\nX-Slow-Partial: eof\r\n").encode())
            connection.shutdown(socket.SHUT_WR)
        elif scenario in ("truncated-body-eof", "truncated-small-body-eof"):
            declared_length = 2048 if scenario == "truncated-body-eof" else 1024
            connection.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                                "Content-Type: application/json\r\n"
                                "Authorization: Bearer synthetic-codex-key\r\n"
                                f"Content-Length: {declared_length}\r\n"
                                "Connection: close\r\n\r\n{").encode())
            connection.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(connection)
            try:
                response.begin()
                body = response.read()
                status = response.status
            except (ConnectionError, OSError, http.client.HTTPException):
                status, body = None, b""
            save({"kind":scenario, "status":status, "body":body.hex()})
            connection.close()
            print("synthetic-client-complete")
            raise SystemExit(0)
        else:
            connection.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                                "Content-Type: application/json\r\n"
                                "Authorization: Bearer synthetic-codex-key\r\n"
                                "Content-Length: 0\r\nConnection: close\r\n\r\n").encode())
        status = read_status(connection, 3)
        save({"kind":scenario, "status":status})
        connection.close()
        print("synthetic-client-complete")
        raise SystemExit(0)
    if scenario == "slow-partial-fragmented-header":
        healthy = socket.create_connection((host, port), timeout=5)
        parts = [
            f"POST {path} HTTP/1.1\r\n".encode(),
            f"Host: {host}:{port}\r\nContent-Type: application/json\r\n".encode(),
            b"Authorization: Bearer synthetic-codex-key\r\n",
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r".encode(),
            b"\n" + body,
        ]
        started = time.monotonic()
        for part in parts:
            healthy.sendall(part)
            time.sleep(0.025)
        status = read_status(healthy, 5)
        save({"kind":scenario, "fragments":len(parts), "status":status,
              "elapsed_ms":round((time.monotonic()-started)*1000)})
        healthy.close()
        print("synthetic-client-complete")
        raise SystemExit(0 if status == 200 else 1)
    if scenario == "slow-partial-body-limit":
        oversized = socket.create_connection((host, port), timeout=5)
        oversized.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                           f"Content-Length: {64 * 1024 * 1024 + 1}\r\nConnection: close\r\n\r\n").encode())
        started = time.monotonic()
        status = read_status(oversized, 3)
        save({"kind":scenario, "declared_bytes":64 * 1024 * 1024 + 1, "status":status,
              "elapsed_ms":round((time.monotonic()-started)*1000)})
        oversized.close()
        print("synthetic-client-complete")
        raise SystemExit(0 if status == 413 else 1)
    if scenario.startswith("request-head-"):
        body = json.dumps({"model":"deepseek-chat","input":"synthetic large-header probe"},separators=(",",":")).encode()
        def make_header(head_bytes):
            prefix = (f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n").encode()
            suffix = (f"Content-Type: application/json\r\nAuthorization: Bearer synthetic-codex-key\r\n"
                      f"Content-Length: {len(body)}\r\nConnection: close").encode()
            padding_bytes = head_bytes - len(prefix) - len(suffix)
            field_prefix = b"X-Pad: "
            field_overhead = len(field_prefix) + 2
            max_value_bytes = 60 * 1024 - field_overhead
            if padding_bytes < field_overhead: raise ValueError("request head target is too short")
            field_count = (padding_bytes + max_value_bytes + field_overhead - 1) // (max_value_bytes + field_overhead)
            value_bytes = padding_bytes - field_count * field_overhead
            fields = []
            for _ in range(field_count):
                value_length = min(max_value_bytes, value_bytes)
                fields.append(field_prefix + b"x" * value_length + b"\r\n")
                value_bytes -= value_length
            if value_bytes: raise ValueError("request head padding did not fit")
            header = prefix + b"".join(fields) + suffix + b"\r\n\r\n"
            if header.index(b"\r\n\r\n") != head_bytes: raise ValueError("request head target did not match")
            return header
        if scenario == "request-head-80k":
            head_bytes = 80 * 1024
            connection = socket.create_connection((host, port), timeout=5)
            started = time.monotonic()
            connection.sendall(make_header(head_bytes) + body)
            status = read_status(connection, 5)
            elapsed_ms = round((time.monotonic()-started)*1000)
            save({"kind":scenario, "head_bytes":head_bytes, "status":status,
                  "elapsed_ms":elapsed_ms, "fragments":1})
            connection.close()
            print("synthetic-client-complete")
            raise SystemExit(0 if status == 200 else 1)
        if scenario == "request-head-near-limit-fragmented":
            head_bytes = 2 * 1024 * 1024
            large = socket.create_connection((host, port), timeout=10)
            header = make_header(head_bytes)
            large.sendall(header[:512])
            healthy = socket.create_connection((host, port), timeout=5)
            started = time.monotonic()
            healthy.sendall(request)
            healthy_status = None
            healthy_elapsed_ms = None
            fragments = 0
            for offset in range(512, len(header), 512):
                large.sendall(header[offset:offset+512])
                fragments += 1
                if healthy_status is None and fragments % 32 == 0 and time.monotonic() - started < 0.75:
                    healthy_status = read_status(healthy, 0.002)
                    if healthy_status is not None:
                        healthy_elapsed_ms = round((time.monotonic()-started)*1000)
                time.sleep(0.0002)
            large_header_complete_ms = round((time.monotonic()-started)*1000)
            large.sendall(body)
            large_status = read_status(large, 10)
            large_response_ms = round((time.monotonic()-started)*1000)
            healthy_before_large_complete = healthy_status is not None
            if healthy_status is None:
                healthy_status = read_status(healthy, 5)
                if healthy_status is not None:
                    healthy_elapsed_ms = round((time.monotonic()-started)*1000)
            save({"kind":scenario, "head_bytes":head_bytes, "status":large_status,
                  "healthy_status":healthy_status, "healthy_elapsed_ms":healthy_elapsed_ms,
                  "healthy_before_large_complete":healthy_before_large_complete,
                  "large_header_complete_ms":large_header_complete_ms,
                  "large_response_ms":large_response_ms, "fragments":fragments + 1,
                  "fragment_bytes":512})
            large.close()
            healthy.close()
            print("synthetic-client-complete")
            raise SystemExit(0 if large_status == 200 and healthy_status == 200 else 1)
        if scenario == "request-head-over-limit":
            head_bytes = 2 * 1024 * 1024 + 1
            connection = socket.create_connection((host, port), timeout=10)
            started = time.monotonic()
            connection.sendall(make_header(head_bytes) + body)
            status = read_status(connection, 10)
            save({"kind":scenario, "head_bytes":head_bytes, "status":status,
                  "elapsed_ms":round((time.monotonic()-started)*1000)})
            connection.close()
            print("synthetic-client-complete")
            raise SystemExit(0 if status is not None else 1)
        raise ValueError(f"unknown request-head scenario: {scenario}")
    if scenario == "slow-partial-body":
        partials = []
        for index in range(16):
            partial = socket.create_connection((host, port), timeout=5)
            partial.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                             f"Content-Type: application/json\r\nContent-Length: 2048\r\n"
                             f"Connection: close\r\nX-Slow-Body: {index}\r\n\r\n{{").encode())
            partials.append(partial)
            time.sleep(0.01)
        time.sleep(0.1)
        healthy = socket.create_connection((host, port), timeout=5)
        started = time.monotonic()
        healthy.sendall(request)
        before_release = read_status(healthy, 0.25)
        for partial in partials:
            partial.shutdown(socket.SHUT_WR)
        partial_status = read_status(partials[0], 3)
        status = before_release if before_release is not None else read_status(healthy, 5)
        save({"kind":scenario, "clients":len(partials), "hold_ms":250,
              "responded_before_release":before_release is not None,
              "before_release_status":before_release, "cancelled_status":partial_status,
              "status":status, "elapsed_ms":round((time.monotonic()-started)*1000)})
        for partial in partials:
            partial.close()
        healthy.close()
        print("synthetic-client-complete")
        raise SystemExit(0 if status == 200 else 1)
    if scenario == "slow-partial-flood":
        partials = []
        count = int(os.environ["MODEX_SLOW_PARTIAL_HEADER_COUNT"])
        for index in range(count):
            partial = socket.create_connection((host, port), timeout=5)
            partial.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                             f"Content-Length: 2\r\nX-Slow-Partial: {index}\r\n").encode())
            partials.append(partial)
        time.sleep(0.25)
        healthy = socket.create_connection((host, port), timeout=5)
        started = time.monotonic()
        healthy.sendall(request)
        before_release = read_status(healthy, 1.0)
        before_release_elapsed = round((time.monotonic() - started) * 1000)
        for partial in partials:
            partial.close()
        status = before_release if before_release is not None else read_status(healthy, 5.0)
        save({"kind":scenario, "partial_clients":count,
              "before_release_status":before_release,
              "before_release_elapsed_ms":before_release_elapsed,
              "status":status})
        healthy.close()
        print("synthetic-client-complete")
        raise SystemExit(0 if status == 200 else 1)
    if scenario == "slow-partial-overflow-completes":
        partials = []
        count = int(os.environ["MODEX_SLOW_PARTIAL_HEADER_COUNT"])
        head = (f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                f"Content-Type: application/json\r\nAuthorization: Bearer synthetic-codex-key\r\n"
                f"Content-Length: {len(body)}\r\nConnection: keep-alive\r\n")

        response_buffer = bytearray()
        def read_complete_response(connection, response_buffer, timeout):
            deadline = time.monotonic() + timeout
            while b"\r\n\r\n" not in response_buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([connection], [], [], remaining)[0]:
                    return None
                chunk = connection.recv(65536)
                if not chunk:
                    return None
                response_buffer.extend(chunk)
            header_end = response_buffer.index(b"\r\n\r\n")
            header = bytes(response_buffer[:header_end])
            response_headers = header.split(b"\r\n")[1:]
            content_lengths = [
                line.split(b":", 1)[1].strip() for line in response_headers
                if line.lower().startswith(b"content-length:")
            ]
            if len(content_lengths) != 1 or any(
                line.lower().startswith(b"transfer-encoding:") for line in response_headers
            ):
                raise AssertionError("keep-alive probe expected a single Content-Length response")
            content_length = int(content_lengths[0])
            response_end = header_end + 4 + content_length
            while len(response_buffer) < response_end:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([connection], [], [], remaining)[0]:
                    return None
                chunk = connection.recv(65536)
                if not chunk:
                    return None
                response_buffer.extend(chunk)
            status = int(header.split(b"\r\n", 1)[0].split()[1])
            del response_buffer[:response_end]
            return status

        for index in range(count):
            partial = socket.create_connection((host, port), timeout=5)
            connection = "close" if index == 0 else "keep-alive"
            partial.sendall((head.replace("keep-alive", connection) + f"X-Slow-Partial: {index}\r\n").encode())
            partials.append(partial)
        time.sleep(0.25)
        partials[0].sendall(b"\r\n" + body)
        freed_parked_status = read_complete_response(partials[0], bytearray(), 1.0)
        started = time.monotonic()
        partials[128].sendall(b"\r\n" + body)
        overflow_status = read_complete_response(partials[128], response_buffer, 1.0)
        partials[128].sendall(request.replace(b"Connection: close", b"Connection: keep-alive"))
        reused_overflow_status = read_complete_response(partials[128], response_buffer, 1.0)
        healthy = socket.create_connection((host, port), timeout=5)
        healthy.sendall(request)
        healthy_status = read_complete_response(healthy, bytearray(), 1.0)
        for partial in partials:
            partial.close()
        healthy.close()
        save({"kind":scenario, "partial_clients":count,
              "freed_parked_status":freed_parked_status,
              "completed_overflow_status":overflow_status,
              "reused_overflow_status":reused_overflow_status,
              "healthy_status":healthy_status,
              "elapsed_ms":round((time.monotonic()-started)*1000)})
        print("synthetic-client-complete")
        raise SystemExit(0 if freed_parked_status == 200 and overflow_status == 200 and reused_overflow_status == 200
                         and healthy_status == 200 else 1)
    partials = []
    for index in range(8):
        partial = socket.create_connection((host, port), timeout=5)
        partial.sendall((f"POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                         f"Content-Length: 2\r\nX-Slow-Partial: {index}\r\n").encode())
        partials.append(partial)
    time.sleep(0.1)
    healthy = socket.create_connection((host, port), timeout=10)
    started = time.monotonic()
    healthy.sendall(request)
    hold_until = time.monotonic() + 1.0
    before_release = read_status(healthy, hold_until - time.monotonic())
    status_elapsed_ms = round((time.monotonic()-started)*1000) if before_release is not None else None
    remaining = hold_until - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)
    for partial in partials:
        partial.close()
    status = before_release if before_release is not None else read_status(healthy, 5.0)
    if status_elapsed_ms is None:
        status_elapsed_ms = round((time.monotonic()-started)*1000)
    save({"kind":"slow-partial", "clients":len(partials), "hold_ms":1000,
          "responded_before_release":before_release is not None, "before_release_status":before_release,
          "status":status, "elapsed_ms":status_elapsed_ms})
    healthy.close()
    print("synthetic-client-complete")
    raise SystemExit(0 if status == 200 else 1)
if scenario in ("kill-relay", "kill-relay-ignores-term"):
    for pid in children.read_text().split():
        if int(pid) != os.getpid(): os.kill(int(pid), 9)
    time.sleep(30)
    raise SystemExit(1)
passthrough = scenario == "passthrough"
target = urlsplit(config["model_providers.prodex-deepseek.base_url"] + ("/chat/completions?synthetic=1" if passthrough else "/responses"))
body = b"\x00synthetic\xff" if passthrough else json.dumps({"model":"deepseek-chat","input":"synthetic prompt","stream":scenario == "stream"},separators=(",",":")).encode()
connection = http.client.HTTPConnection(target.hostname,target.port,timeout=10)
connection.request("POST",target.path+("?"+target.query if target.query else ""),body,
                   {"Content-Type":"application/x-synthetic" if passthrough else "application/json","Authorization":"Bearer synthetic-codex-key","Connection":"close"})
response=connection.getresponse()
response_body=response.read()
save({"kind":"response","status":response.status,"headers":{name.lower():value for name,value in response.getheaders()},"body":response_body.hex()})
connection.close()
if scenario in ("anthropic-buffered-tool-history", "anthropic-buffered-tool-history-array-output", "anthropic-buffered-tool-history-mixed") and response.status == 200:
    call_id = "call_lookup" if scenario == "anthropic-buffered-tool-history-mixed" else "call_tool_use"
    tool_output = "lookup result" if scenario == "anthropic-buffered-tool-history-mixed" else "synthetic tool result"
    if scenario == "anthropic-buffered-tool-history-array-output":
        tool_output = ["first", {"input_text":"second"}, {"output_text":"third"}, 4, None, {"ok":True}]
    second_input = [
        {"type":"function_call_output","call_id":call_id,"output":tool_output},
        {"type":"message","role":"user","content":"Continue."},
    ]
    second_body=json.dumps({"model":"deepseek-chat","input":second_input,"stream":False,"tools":[{"type":"web_search_preview"}]},separators=(",",":")).encode()
    second_connection=http.client.HTTPConnection(target.hostname,target.port,timeout=10)
    second_connection.request("POST",target.path+("?"+target.query if target.query else ""),second_body,
                              {"Content-Type":"application/json","Authorization":"Bearer synthetic-codex-key","Connection":"close"})
    second=second_connection.getresponse()
    second_body=second.read()
    save({"kind":"response","status":second.status,"headers":{name.lower():value for name,value in second.getheaders()},"body":second_body.hex()})
    second_connection.close()
    print("synthetic-client-complete")
    raise SystemExit(0 if second.status == 200 else 1)
print("synthetic-client-complete")
raise SystemExit(0 if response.status == 200 else 1)
'''


def event_names(payload):
    return [line[7:] for line in bytes.fromhex(payload).decode().splitlines() if line.startswith("event: ")]


def normalized_app_server_args(arguments):
    normalized = []
    for argument in arguments:
        argument = re.sub(r"(?:/[^/\r\n]+)*/modex-super-launch-[^/\r\n]+", "/tmp/modex-super-launch-<root>", argument)
        argument = re.sub(r"(?<=\.prodex-overlay-)[^/]+", "<overlay>", argument)
        argument = re.sub(r"(http://127\.0\.0\.1:)\d+", r"\1<port>", argument)
        normalized.append(argument)
    return normalized


def normalized_codex_path(output):
    return re.sub(
        rb"(?:/[^/\r\n]+)*/modex-super-launch-[^/\r\n]+/codex",
        b"<CODEX>",
        output,
    )


def _anthropic_image_stop_events(scenario):
    def block(index, kind, **fields):
        return {"type": "content_block_start", "index": index,
                "content_block": {"type": kind, **fields}}

    def delta(index, kind, **fields):
        return {"type": "content_block_delta", "index": index,
                "delta": {"type": kind, **fields}}

    def stop(index):
        return {"type": "content_block_stop", "index": index}

    def image_start(index):
        return block(index, "image", source={
            "type": "base64", "media_type": "image/png", "data": "SYNTHETIC_IMAGE_BLOCK_DATA",
        })

    def image_delta(index):
        return delta(index, "image_delta", data="SYNTHETIC_IMAGE_DELTA_SECRET")

    def text_delta(index, value):
        return delta(index, "text_delta", text=value)

    start = {"type": "message_start", "message": {
        "id": "msg_image_stop", "role": "assistant", "model": "deepseek-chat",
        "usage": {"input_tokens": 3, "output_tokens": 0},
    }}
    message_stop = {"type": "message_stop"}

    def end(reason="end_turn"):
        return [
            {"type": "message_delta", "delta": {"stop_reason": reason},
             "usage": {"output_tokens": 5}},
            message_stop,
        ]

    text_start = block(0, "text", text="")
    if scenario == "anthropic-image-stop-text-collision":
        return [start, text_start, text_delta(0, "before image"), image_start(0),
                image_delta(0), stop(0), text_delta(0, " after image"), stop(0), *end()]
    if scenario == "anthropic-image-stop-text-repeated":
        return [start, text_start, text_delta(0, "before image"), image_start(0), image_start(0),
                image_delta(0), stop(0), stop(0), text_delta(0, " after image"), stop(0), *end()]
    if scenario == "anthropic-image-stop-text-delta-before-stop":
        return [start, text_start, text_delta(0, "before image"), image_start(0),
                text_delta(0, " between blocks"), stop(0), text_delta(0, " after image stop"),
                stop(0), *end()]
    if scenario in ("anthropic-image-stop-string-index", "anthropic-image-stop-fractional-index"):
        image_index = "1" if scenario.endswith("string-index") else 1.5
        return [start, text_start, text_delta(0, "before image"), image_start(image_index),
                image_delta(image_index), stop(image_index), text_delta(0, " after image"), stop(0), *end()]
    if scenario == "anthropic-image-stop-tool-collision":
        return [start, block(0, "tool_use", id="toolu_image_collision", name="lookup", input={}),
                image_start(0), image_delta(0), stop(0),
                delta(0, "input_json_delta", partial_json='{"query":"release"}'), stop(0),
                *end("tool_use")]
    if scenario == "anthropic-image-stop-tool-delta-before-stop":
        return [start, block(0, "tool_use", id="toolu_image_delta_before_stop", name="lookup", input={}),
                image_start(0), image_delta(0), delta(0, "input_json_delta", partial_json='{"query":'),
                stop(0), delta(0, "input_json_delta", partial_json='"release"}'), stop(0),
                *end("tool_use")]
    if scenario == "anthropic-image-stop-search-delta-before-stop":
        search_id = "search_image_delta_before_stop"
        return [start, block(0, "server_tool_use", id=search_id, name="web_search", input={}),
                image_start(0), image_delta(0), delta(0, "input_json_delta", partial_json='{"query":'),
                stop(0), delta(0, "input_json_delta", partial_json='"release"}'), stop(0),
                block(1, "web_search_tool_result", tool_use_id=search_id, content=[{
                    "type": "web_search_result", "url": "https://example.test/release", "title": "Release",
                }]), stop(1), block(2, "text", text=""), text_delta(2, "Found it."), stop(2), *end()]
    if scenario == "anthropic-image-stop-result-collision":
        search_id = "search_image_result_collision"
        return [start, block(0, "server_tool_use", id=search_id, name="web_search",
                             input={"query": "release"}), stop(0),
                block(1, "web_search_tool_result", tool_use_id=search_id, content=[{
                    "type": "web_search_result", "url": "https://example.test/release", "title": "Release",
                }]), image_start(1), image_delta(1), stop(1),
                text_delta(1, "visible after result stop"), stop(1), block(2, "text", text=""),
                text_delta(2, "Found it."), stop(2), *end()]
    raise AssertionError(f"unknown Anthropic image stop fixture: {scenario}")


def _sse_data_event(value):
    return b"data: " + json.dumps(value, separators=(",", ":")).encode() + b"\n\n"


@contextmanager
def private_tempdir():
    with tempfile.TemporaryDirectory(prefix="modex probe private tmpdir ") as root:
        directory = Path(root) / "private"
        directory.mkdir(mode=0o700)
        yield directory


def run_private_launch(binary=MODEX, **kwargs):
    with private_tempdir() as temporary_directory:
        return SuperLaunchTests().run_launch(
            binary, temporary_directory=temporary_directory, **kwargs
        )


def check_safe_exec_flags(test, oracle):
    cases = (
        ("exec", "--json", "synthetic prompt"),
        ("exec", "--color", "never", "synthetic prompt"),
        ("exec", "--json", "--color=always", "synthetic prompt"),
        ("exec", "--skip-git-repo-check", "--", "--json"),
        ("exec", "--json", "-"),
        ("exec", "--json", "--", "-c", "model_provider=literal"),
        ("exec", "--cd", "/tmp/synthetic worktree", "synthetic prompt"),
        ("exec", "--cd=/tmp/synthetic worktree", "synthetic prompt"),
        ("exec", "-C", "/tmp/synthetic worktree", "synthetic prompt"),
        ("exec", "-C/tmp/synthetic worktree", "synthetic prompt"),
        ("exec", "--output-last-message", "answer.txt", "synthetic prompt"),
        ("exec", "-o", "answer.txt", "synthetic prompt"),
        ("exec", "-oanswer.txt", "synthetic prompt"),
        ("exec", "--output-last-message=answer.txt", "synthetic prompt"),
        ("exec", "--output-schema", "schema.json", "synthetic prompt"),
        ("exec", "--output-schema=schema.json", "synthetic prompt"),
        ("exec", "--output-last-message", "-", "synthetic prompt"),
        ("exec", "--ephemeral", "synthetic prompt"),
        ("exec", "--image", "synthetic.png", "synthetic prompt"),
        ("exec", "--image=synthetic.png", "synthetic prompt"),
        ("exec", "-i", "one.png,two.png", "synthetic prompt"),
        ("exec", "-ione.png", "synthetic prompt"),
        ("exec", "-i", "one.png", "--image", "two.png", "synthetic prompt"),
    )
    for arguments in cases:
        with test.subTest(arguments=arguments):
            captures = []
            for binary in (oracle, MODEX):
                result, records, upstream, state = run_private_launch(
                    binary, scenario="exit-seven", codex_arguments=arguments,
                )
                test.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                test.assertEqual((upstream, state["leftovers"]), ([], []))
                test.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                launch = next(record for record in records if record["kind"] == "launch")
                captures.append(normalized_app_server_args(launch["args"]))
            test.assertEqual(captures[0], captures[1])


def check_explicit_full_access(test, oracle):
    cases = (
        {"super_arguments": ("--full-access",)},
        {"codex_arguments": ("exec", "--full-access", "--", "synthetic prompt")},
    )
    for case in cases:
        with test.subTest(case=case):
            captures = []
            for binary in (oracle, MODEX):
                result, records, upstream, state = run_private_launch(
                    binary, scenario="buffered", **case,
                )
                test.assertEqual(result.returncode, 0, result.stderr)
                test.assertEqual(len(upstream), 1)
                test.assertEqual(state["leftovers"], [])
                test.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                launch = next(record for record in records if record["kind"] == "launch")
                captures.append((normalized_app_server_args(launch["args"]), upstream[0]["path"], upstream[0]["body"]))
            test.assertEqual(captures[0], captures[1])


def check_no_proxy(test, oracle):
    environment = {
        "HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1",
        "ALL_PROXY": "http://127.0.0.1:1", "NO_PROXY": "", "no_proxy": "",
    }
    for case in (
        {"super_arguments": ("--no-proxy",)},
        {"codex_arguments": ("exec", "--no-proxy", "--", "synthetic prompt")},
    ):
        with test.subTest(case=case):
            captures = []
            for binary in (oracle, MODEX):
                result, records, upstream, state = run_private_launch(
                    binary, scenario="buffered", environment_overrides=environment, **case,
                )
                test.assertEqual(result.returncode, 0, result.stderr)
                test.assertEqual(len(upstream), 1)
                test.assertEqual(state["leftovers"], [])
                test.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                launch = next(record for record in records if record["kind"] == "launch")
                captures.append((normalized_app_server_args(launch["args"]), upstream[0]["path"], upstream[0]["body"]))
            test.assertEqual(captures[0], captures[1])


def app_server_config(arguments):
    return "\n".join(
        arguments[index + 1]
        for index, argument in enumerate(arguments[:-1])
        if argument == "-c"
    )


class SuperLaunchTests(unittest.TestCase):
    def run_launch(
        self, binary=MODEX, scenario="stream", existing=False, model="deepseek-chat",
        super_arguments=(), environment_overrides=None, base_path="/v1", sub_agent=False,
        temporary_directory=None, stderr_tty=False, codex_mode="explicit", codex_binary=None,
        codex_arguments=("exec", "--", "synthetic prompt"), shared_config=None, shared_setup=None,
    ):
        with tempfile.TemporaryDirectory(prefix="modex-super-launch-", dir=temporary_directory) as directory:
            root = Path(directory)
            for name in ("home", "state", "shared", "work"):
                (root / name).mkdir(mode=0o700)
            (root / "state/update-check.json").write_text(json.dumps({"source": "GitHub", "latest_version": "0.439.2", "checked_at": int(time.time())}))
            codex = root / "codex"
            if codex_binary is None:
                codex.write_text("#!" + sys.executable + "\n" + CODEX)
                codex.chmod(0o700)
            else:
                codex.symlink_to(Path(codex_binary).resolve())
            path_dir = root / "work/bin"
            if codex_mode in ("path", "command", "relative-path", "command-relative-path", "path-skips-wrapper"):
                path_dir.mkdir()
                os.symlink(codex, path_dir / "codex")
            path = "/usr/bin:/bin"
            codex_setting = str(codex)
            if codex_mode == "relative":
                codex_setting = "../codex"
            elif codex_mode == "symlink":
                os.symlink(codex, root / "codex-alias")
                codex_setting = "../codex-alias"
            elif codex_mode in ("path", "command"):
                path = str(path_dir)
                codex_setting = "" if codex_mode == "path" else "codex"
            elif codex_mode in ("relative-path", "command-relative-path"):
                path = "bin"
                codex_setting = "codex" if codex_mode == "command-relative-path" else ""
            elif codex_mode == "command-cwd":
                os.symlink(codex, root / "work/codex")
                path = ""
                codex_setting = "codex"
            elif codex_mode == "path-skips-wrapper":
                wrapper_dir = root / "shim"
                wrapper_dir.mkdir()
                wrapper = wrapper_dir / "codex"
                wrapper.write_text('#!/bin/sh\nexec prodex "$@"\n')
                wrapper.chmod(0o700)
                path = f"{wrapper_dir}:{path_dir}"
                codex_setting = ""
            elif codex_mode == "missing":
                missing_dir = root / "empty-path"
                missing_dir.mkdir()
                path = str(missing_dir)
                codex_setting = ""
            elif codex_mode != "explicit":
                raise ValueError(f"unknown Codex selection fixture: {codex_mode}")
            capture = root / "capture.jsonl"
            native_capture = root / "native-capture.jsonl"
            if existing:
                (root / "shared/config.toml").write_text('model="preserve-me"\n')
                (root / "shared/auth.json").write_text('{"synthetic":"preserve-me"}\n')
            if shared_config is not None:
                (root / "shared/config.toml").write_text(shared_config)
                (root / "shared/config.toml").chmod(0o600)
            if shared_setup is not None:
                shared_setup(root)
            observed = []

            class Upstream(BaseHTTPRequestHandler):
                def do_POST(peer):
                    body = peer.rfile.read(int(peer.headers["Content-Length"]))
                    observed.append({"path": peer.path, "headers": dict(peer.headers), "body": body.hex()})
                    status = 200
                    if scenario.startswith("error-"):
                        status = int(scenario.rsplit("-", 1)[1])
                        payload = b'{"error":{"type":"synthetic_error","message":"synthetic upstream failure"}}'
                        content_type = "application/json"
                        if scenario.startswith("error-stream-"):
                            payload = b"data: " + payload + b"\n\n"
                            content_type = "text/event-stream"
                    elif scenario == "stream-error":
                        payload = b'data: {"error":{"message":"synthetic upstream failure","type":"rate_limit_exceeded"}}\n\n'
                        content_type = "text/event-stream"
                    elif scenario == "anthropic-buffered":
                        payload = json.dumps({
                            "id": "msg_search",
                            "type": "message",
                            "role": "assistant",
                            "model": "deepseek-chat",
                            "content": [
                                {"type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {"query": "current release"}},
                                {"type": "web_search_tool_result", "tool_use_id": "search_1", "content": [{"type": "web_search_result", "url": "https://example.test/release", "title": "Release"}]},
                                {"type": "text", "text": "Found it."},
                            ],
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 3, "output_tokens": 5},
                        }, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario in (
                        "anthropic-buffered-orphan-result",
                        "anthropic-buffered-orphan-result-only",
                    ):
                        content = [{
                            "type": "web_search_tool_result",
                            "tool_use_id": "missing_search",
                            "content": [{
                                "type": "web_search_result",
                                "url": "https://example.test/orphan",
                                "title": "Orphan",
                            }],
                        }]
                        if scenario != "anthropic-buffered-orphan-result-only":
                            content.insert(0, {"type": "text", "text": "Before orphan result."})
                        payload = json.dumps({
                            "id": "msg_orphan_result",
                            "type": "message",
                            "role": "assistant",
                            "model": "deepseek-chat",
                            "content": content,
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 3, "output_tokens": 5},
                        }, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario.startswith("anthropic-buffered-tool-use") or scenario in (
                        "anthropic-buffered-tool-history",
                        "anthropic-buffered-tool-history-array-output",
                        "anthropic-buffered-tool-history-mixed",
                    ):
                        tool_use = {"type": "tool_use", "id": "call_tool_use", "name": "functions--lookup", "input": {"query": "release"}}
                        if scenario == "anthropic-buffered-tool-use-missing-input":
                            tool_use.pop("input")
                        elif scenario == "anthropic-buffered-tool-use-scalar":
                            tool_use["input"] = 7
                        elif scenario == "anthropic-buffered-tool-use-array":
                            tool_use["input"] = [1, "two"]
                        if scenario in ("anthropic-buffered-tool-use-mixed", "anthropic-buffered-tool-history-mixed"):
                            content = [
                                {"type": "text", "text": "Found "},
                                {"type": "text", "text": "it."},
                                {"type": "tool_use", "id": "call_lookup", "name": "functions--lookup", "input": {"query": "release"}},
                                {"type": "text", "text": "Next "},
                                {"type": "text", "text": "step."},
                                {"type": "tool_use", "id": "call_count", "name": "functions--count", "input": [1, "two"]},
                                {"type": "text", "text": "Done."},
                            ]
                        else:
                            content = [{"type": "text", "text": "Found it."}, tool_use]
                        payload_fields = {
                            "id": "msg_tool_use",
                            "type": "message",
                            "role": "assistant",
                            "model": "deepseek-chat",
                            "content": content,
                            "stop_reason": "tool_use",
                            "usage": {"input_tokens": 3, "output_tokens": 5},
                        }
                        if scenario == "anthropic-buffered-tool-use-stop-missing":
                            payload_fields.pop("stop_reason")
                        elif scenario == "anthropic-buffered-tool-use-stop-null":
                            payload_fields["stop_reason"] = None
                        elif scenario == "anthropic-buffered-tool-use-stop-numeric":
                            payload_fields["stop_reason"] = 5
                        payload = json.dumps(payload_fields, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario == "anthropic-buffered-citations":
                        payload = json.dumps({
                            "id": "msg_citations", "type": "message", "role": "assistant",
                            "model": "deepseek-chat",
                            "content": [
                                {"type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {"query": "current release"}},
                                {"type": "web_search_tool_result", "tool_use_id": "search_1", "content": [{"type": "web_search_result", "url": "https://example.test/release", "title": "Release"}]},
                                {"type": "text", "text": "Found it.", "citations": [{"type": "web_search_result_location", "url": "https://example.test/release", "title": "Release", "cited_text": "Found it."}]},
                            ],
                            "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 5},
                        }, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario == "anthropic-buffered-thinking":
                        payload = json.dumps({
                            "id": "msg_unknown", "type": "message", "role": "assistant",
                            "model": "deepseek-chat",
                            "content": [
                                {"type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {"query": "current release"}},
                                {"type": "web_search_tool_result", "tool_use_id": "search_1", "content": [{"type": "web_search_result", "url": "https://example.test/release", "title": "Release"}]},
                                {"type": "text", "text": "Found it."},
                                {"type": "thinking", "thinking": "additional content"},
                            ],
                            "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 5},
                        }, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario == "anthropic-buffered-image":
                        payload = json.dumps({
                            "id": "msg_image", "type": "message", "role": "assistant",
                            "model": "deepseek-chat",
                            "content": [
                                {"type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {"query": "current release"}},
                                {"type": "web_search_tool_result", "tool_use_id": "search_1", "content": [{"type": "web_search_result", "url": "https://example.test/release", "title": "Release"}]},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "SYNTHETIC_IMAGE_BLOCK_DATA"}},
                                {"type": "text", "text": "Found it."},
                            ],
                            "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 5},
                        }, separators=(",", ":")).encode()
                        content_type = "application/json"
                    elif scenario == "anthropic-stream":
                        payload = b"".join((
                            b'data: {"type":"message_start","message":{"id":"msg_search","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                            b'event: ping\ndata: {"type":"ping"}\n\n',
                            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"server_tool_use","id":"search_1","name":"web_search","input":{}}}\n\n',
                            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":\\"current release\\"}"}}\n\n',
                            b'data: {"type":"content_block_stop","index":0}\n\n',
                            b'data: {"type":"content_block_start","index":1,"content_block":{"type":"web_search_tool_result","tool_use_id":"search_1","content":[{"type":"web_search_result","url":"https://example.test/release","title":"Release"}]}}\n\n',
                            b'data: {"type":"content_block_stop","index":1}\n\n',
                            b'data: {"type":"content_block_start","index":2,"content_block":{"type":"text","text":""}}\n\n',
                            b'data: {"type":"content_block_delta","index":2,"delta":{"type":"text_delta","text":"Found it."}}\n\n',
                            b'data: {"type":"content_block_stop","index":2}\n\n',
                            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":5}}\n\n',
                            b'data: {"type":"message_stop"}\n\n',
                        ))
                        content_type = "text/event-stream"
                    elif scenario == "anthropic-tool-use":
                        payload = b"".join((
                            b'data: {"type":"message_start","message":{"id":"msg_tool","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_lookup","name":"lookup","input":{}}}\n\n',
                            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":"}}\n\n',
                            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"\\"current release\\"}"}}\n\n',
                            b'data: {"type":"content_block_stop","index":0}\n\n',
                            b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":5}}\n\n',
                            b'data: {"type":"message_stop"}\n\n',
                        ))
                        content_type = "text/event-stream"
                    elif scenario in ("anthropic-tool-use-mixed", "anthropic-tool-use-text-after"):
                        def event(value):
                            return b"data: " + json.dumps(value, separators=(",", ":")).encode() + b"\n\n"

                        chunks = [event({"type": "message_start", "message": {
                            "id": "msg_tool_mixed", "role": "assistant", "model": "deepseek-chat",
                            "usage": {"input_tokens": 3, "output_tokens": 0},
                        }})]
                        if scenario == "anthropic-tool-use-mixed":
                            chunks.extend((
                                event({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                                event({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Found "}}),
                                event({"type": "content_block_stop", "index": 0}),
                            ))
                        tool_blocks = [
                            (1, "toolu_lookup", "lookup", ['{"query":', '"release"}']),
                            (2, "toolu_count", "count", ['{"n":1}']),
                        ]
                        if scenario == "anthropic-tool-use-text-after":
                            tool_blocks[0] = (0, "toolu_lookup", "lookup", ['{"query":', '"release"}'])
                        for index, call_id, name, fragments in tool_blocks:
                            chunks.append(event({"type": "content_block_start", "index": index, "content_block": {
                                "type": "tool_use", "id": call_id, "name": name, "input": {},
                            }}))
                            chunks.extend(event({"type": "content_block_delta", "index": index, "delta": {
                                "type": "input_json_delta", "partial_json": fragment,
                            }}) for fragment in fragments)
                            chunks.append(event({"type": "content_block_stop", "index": index}))
                            if scenario == "anthropic-tool-use-text-after" and index == 0:
                                chunks.extend((
                                    event({"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
                                    event({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Found "}}),
                                    event({"type": "content_block_stop", "index": 1}),
                                ))
                        chunks.extend((
                            event({"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 5}}),
                            event({"type": "message_stop"}),
                        ))
                        payload = b"".join(chunks)
                        content_type = "text/event-stream"
                    elif scenario in (
                        "anthropic-tool-use-open-text",
                        "anthropic-tool-use-after-message-delta",
                        "anthropic-tool-use-after-message-stop",
                    ):
                        def event(value):
                            return b"data: " + json.dumps(value, separators=(",", ":")).encode() + b"\n\n"

                        chunks = [event({"type": "message_start", "message": {
                            "id": "msg_tool_boundary", "role": "assistant", "model": "deepseek-chat",
                            "usage": {"input_tokens": 3, "output_tokens": 0},
                        }}), event({"type": "content_block_start", "index": 0, "content_block": {
                            "type": "tool_use", "id": "toolu_lookup", "name": "lookup", "input": {},
                        }})]
                        if scenario == "anthropic-tool-use-open-text":
                            chunks.extend((
                                event({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"query":'}}),
                                event({"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
                                event({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Found "}}),
                                event({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '"release"}'}}),
                                event({"type": "content_block_stop", "index": 0}),
                                event({"type": "content_block_stop", "index": 1}),
                            ))
                        else:
                            chunks.extend((
                                event({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "{}"}}),
                                event({"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 5}}),
                                event({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": " "}}),
                                event({"type": "content_block_stop", "index": 0}),
                                event({"type": "message_stop"}),
                            ))
                            if scenario == "anthropic-tool-use-after-message-stop":
                                chunks.append(event({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "late"}}))
                        if scenario == "anthropic-tool-use-open-text":
                            chunks.extend((
                                event({"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 5}}),
                                event({"type": "message_stop"}),
                            ))
                        payload = b"".join(chunks)
                        content_type = "text/event-stream"
                    elif scenario.startswith("anthropic-tool-use-"):
                        start = b'data: {"type":"message_start","message":{"id":"msg_tool","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n'
                        tool = b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_lookup","name":"lookup","input":{}}}\n\n'
                        other_tool = b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_other","name":"other","input":{}}}\n\n'
                        args = b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":\\"current release\\"}"}}\n\n'
                        wrong_args = b'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":\\"current release\\"}"}}\n\n'
                        stop = b'data: {"type":"content_block_stop","index":0}\n\n'
                        wrong_stop = b'data: {"type":"content_block_stop","index":1}\n\n'
                        message_delta = b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":5}}\n\n'
                        message_stop = b'data: {"type":"message_stop"}\n\n'
                        scenarios = {
                            "anthropic-tool-use-orphan-delta": (start, args, stop, message_delta, message_stop),
                            "anthropic-tool-use-mismatched-index": (start, tool, wrong_args, wrong_stop, message_delta, message_stop),
                            "anthropic-tool-use-duplicate-index": (start, tool, other_tool, args, stop, message_delta, message_stop),
                            "anthropic-tool-use-duplicate-stop": (start, tool, args, stop, stop, message_delta, message_stop),
                            "anthropic-tool-use-missing-stop": (start, tool, args, message_delta, message_stop),
                            "anthropic-tool-use-orphan-stop": (start, stop, b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":5}}\n\n', message_stop),
                            "anthropic-tool-use-mismatched-stop": (start, tool, args, wrong_stop, message_delta, message_stop),
                            "anthropic-tool-use-delta-after-stop": (start, tool, args, stop, args, message_delta, message_stop),
                            "anthropic-tool-use-reopened-index": (start, tool, args, stop, other_tool, message_delta, message_stop),
                        }
                        payload = b"".join(scenarios[scenario])
                        content_type = "text/event-stream"
                    elif scenario == "anthropic-stream-unknown-content":
                        payload = b"".join((
                            b'data: {"type":"message_start","message":{"id":"msg_search","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"server_tool_use","id":"search_1","name":"web_search","input":{"query":"current release"}}}\n\n',
                            b'data: {"type":"content_block_stop","index":0}\n\n',
                            b'data: {"type":"content_block_start","index":1,"content_block":{"type":"web_search_tool_result","tool_use_id":"search_1","content":[{"type":"web_search_result","url":"https://example.test/release","title":"Release"}]}}\n\n',
                            b'data: {"type":"content_block_stop","index":1}\n\n',
                            b'data: {"type":"content_block_start","index":2,"content_block":{"type":"image","source":{"type":"base64","media_type":"image/png","data":"SYNTHETIC_IMAGE_BLOCK_DATA"}}}\n\n',
                            b'data: {"type":"message_stop"}\n\n',
                        ))
                        content_type = "text/event-stream"
                    elif scenario.startswith("anthropic-image-stop-"):
                        payload = b"".join(_sse_data_event(item) for item in _anthropic_image_stop_events(scenario))
                        content_type = "text/event-stream"
                    elif scenario in ("anthropic-stream-image-interleaved", "anthropic-stream-image-missing-index"):
                        image_start = b'data: {"type":"content_block_start","index":1,"content_block":{"type":"image","source":{"type":"base64","media_type":"image/png","data":"U1lOVEhFVElDX0lNQUdFX0JZVEVT"}}}\n\n'
                        image_delta = b'data: {"type":"content_block_delta","index":1,"delta":{"type":"image_delta","data":"SYNTHETIC_IMAGE_DELTA_SECRET"}}\n\n'
                        image_stop = b'data: {"type":"content_block_stop","index":1}\n\n'
                        if scenario == "anthropic-stream-image-missing-index":
                            image_start = b'data: {"type":"content_block_start","content_block":{"type":"image","source":{"type":"base64","media_type":"image/png","data":"U1lOVEhFVElDX0lNQUdFX0JZVEVT"}}}\n\n'
                            image_delta = b'data: {"type":"content_block_delta","delta":{"type":"image_delta","data":"SYNTHETIC_IMAGE_DELTA_SECRET"}}\n\n'
                            image_stop = b'data: {"type":"content_block_stop"}\n\n'
                        payload = b"".join((
                            b'data: {"type":"message_start","message":{"id":"msg_image","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
                            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"before image"}}\n\n',
                            image_start, image_delta, image_stop,
                            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" after image"}}\n\n',
                            b'data: {"type":"content_block_stop","index":0}\n\n',
                            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
                            b'data: {"type":"message_stop"}\n\n',
                        ))
                        content_type = "text/event-stream"
                    elif scenario == "anthropic-stream-error":
                        payload = b'data: {"type":"message_start","message":{"id":"msg_error","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\ndata: {"type":"error","error":{"type":"rate_limit_error","message":"synthetic Anthropic failure"}}\n\n'
                        content_type = "text/event-stream"
                    elif scenario.startswith("anthropic-stop-"):
                        chunks = [
                            b'data: {"type":"message_start","message":{"id":"msg_search","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"server_tool_use","id":"search_1","name":"web_search","input":{"query":"current release"}}}\n\n',
                            b'data: {"type":"content_block_stop","index":0}\n\n',
                            b'data: {"type":"content_block_start","index":1,"content_block":{"type":"web_search_tool_result","tool_use_id":"search_1","content":[{"type":"web_search_result","url":"https://example.test/release","title":"Release"}]}}\n\n',
                            b'data: {"type":"content_block_stop","index":1}\n\n',
                            b'data: {"type":"content_block_start","index":2,"content_block":{"type":"text","text":""}}\n\n',
                            b'data: {"type":"content_block_delta","index":2,"delta":{"type":"text_delta","text":"Found it."}}\n\n',
                            b'data: {"type":"content_block_stop","index":2}\n\n',
                        ]
                        if scenario != "anthropic-stop-missing-message-delta":
                            variants = {
                                "anthropic-stop-sequence": {"stop_reason": "stop_sequence", "stop_sequence": "synthetic"},
                                "anthropic-stop-null-reason": {"stop_reason": None, "stop_sequence": None},
                                "anthropic-stop-end-turn-sequence": {"stop_reason": "end_turn", "stop_sequence": "synthetic"},
                                "anthropic-stop-tool-use": {"stop_reason": "tool_use", "stop_sequence": None},
                                "anthropic-stop-max-tokens": {"stop_reason": "max_tokens", "stop_sequence": None},
                                "anthropic-stop-unknown-reason": {"stop_reason": "synthetic_future_reason", "stop_sequence": None},
                                "anthropic-stop-missing-reason": {"stop_sequence": None},
                                "anthropic-stop-invalid-reason": {"stop_reason": 5, "stop_sequence": None},
                                "anthropic-stop-invalid-sequence": {"stop_reason": "end_turn", "stop_sequence": 5},
                                "anthropic-stop-unknown-event": {"stop_reason": "end_turn", "stop_sequence": None},
                            }
                            delta = json.dumps({"type": "message_delta", "delta": variants[scenario], "usage": {"output_tokens": 5}}, separators=(",", ":"))
                            chunks.append(("data: " + delta + "\n\n").encode())
                            if scenario == "anthropic-stop-unknown-event":
                                chunks.append(b'data: {"type":"future_event","future_field":"ignored"}\n\n')
                        chunks.append(b'data: {"type":"message_stop"}\n\n')
                        payload = b"".join(chunks)
                        content_type = "text/event-stream"
                    elif scenario == "passthrough":
                        payload, content_type = b"\x00synthetic upstream\xff", "application/x-synthetic"
                    elif scenario == "stream":
                        chunk = {"id": "synthetic-chat", "model": "deepseek-chat", "choices": [{"index": 0, "delta": {"content": "synthetic greeting"}, "finish_reason": None}]}
                        final = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                        payload = b"data: " + json.dumps(chunk).encode() + b"\n\ndata: " + json.dumps(final).encode() + b"\n\ndata: [DONE]\n\n"
                        content_type = "text/event-stream"
                    else:
                        payload = json.dumps({"id": "synthetic-chat", "model": "deepseek-chat", "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic greeting"}, "finish_reason": "stop"}]}).encode()
                        content_type = "application/json"
                    peer.send_response(status)
                    peer.send_header("Content-Type", content_type)
                    peer.send_header("Content-Length", str(len(payload)))
                    for name, value in (("limit-requests", "100"), ("remaining-requests", "40"),
                                        ("limit-tokens", "80"), ("remaining-tokens", "60"),
                                        ("reset-requests", "1700000000000"), ("reset-tokens", "1700000000000")):
                        peer.send_header("x-ratelimit-" + name, value)
                    peer.send_header("Connection", "X-Synthetic-Hop, close")
                    peer.send_header("X-Synthetic-Hop", "synthetic-private-hop")
                    peer.end_headers()
                    peer.wfile.write(payload)

                def log_message(self, *_args): pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            environment = {"HOME": str(root / "home"), "PATH": path, "TERM": "dumb", "NO_COLOR": "1",
                           "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
                           "MODEX_LAUNCH_CAPTURE": str(capture),
                           "MODEX_LAUNCH_SCENARIO": scenario, "CODEX_SANDBOX_SENTINEL": "remove-from-child", "TMPDIR": str(root),
                           **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")}}
            if codex_binary is not None:
                environment["MODEX_NATIVE_CODEX_LOG"] = str(native_capture)
            if codex_setting:
                environment["PRODEX_CODEX_BIN"] = codex_setting
            environment.update(environment_overrides or {})
            command = [str(binary), "super", "--provider", "deepseek", "--api-key", "synthetic-provider-key",
                       "--base-url", f"http://127.0.0.1:{server.server_port}{base_path}", "--model", model,
                       "--no-presidio", "--sub-agent" if sub_agent else "--no-sub-agent", "--skip-quota-check", *super_arguments,
                       *codex_arguments]
            try:
                if stderr_tty:
                    master, slave = os.openpty()
                    try:
                        try:
                            process = subprocess.run(
                                command, env=environment, cwd=root / "work", stdout=subprocess.PIPE,
                                stderr=slave, stdin=subprocess.DEVNULL, timeout=40,
                            )
                        finally:
                            os.close(slave)
                        captured_stderr = bytearray()
                        while True:
                            try:
                                chunk = os.read(master, 65536)
                            except OSError as error:
                                if error.errno == errno.EIO:
                                    break
                                raise
                            if not chunk:
                                break
                            captured_stderr.extend(chunk)
                    finally:
                        os.close(master)
                    result = subprocess.CompletedProcess(
                        command, process.returncode, process.stdout, bytes(captured_stderr)
                    )
                else:
                    result = subprocess.run(command, env=environment, cwd=root / "work", capture_output=True, timeout=40)
            finally:
                server.shutdown()
                worker.join(2)
                server.server_close()
            records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
            if native_capture.exists():
                records = [json.loads(line) for line in native_capture.read_text().splitlines()]
            saved = root / "shared/sessions/synthetic-session.jsonl"
            overlays = list((root / "state/profiles").glob("*"))
            state = {"leftovers": [str(path) for path in overlays], "session": saved.read_text() if saved.exists() else None,
                     "extra": [(path / "synthetic-user-state").read_text() for path in overlays if (path / "synthetic-user-state").exists()],
                     "config": (root / "shared/config.toml").read_text() if (root / "shared/config.toml").exists() else None,
                     "managed": sorted(str(path.relative_to(root)) for name in ("home", "state", "shared")
                                       for path in (root / name).rglob("*") if not path.is_socket())}
            for record in records:
                for pid in ([record["pid"]] if "pid" in record else []) + [int(pid) for pid in record.get("children", [])]:
                    try: os.kill(pid, 0)
                    except ProcessLookupError: continue
                    self.fail(f"synthetic launch left direct child {pid} alive")
            return result, records, observed, state

    def test_real_cli_streams_and_preserves_session_after_private_overlay_cleanup(self):
        result, records, upstream, state = self.run_launch()
        self.assertEqual((result.returncode, result.stdout), (0, b"synthetic-client-complete\n"), result.stderr)
        launch = next(record for record in records if record["kind"] == "launch")
        response = next(record for record in records if record["kind"] == "response")
        self.assertEqual(launch["mode"], 0o700)
        self.assertEqual(launch["auth"]["OPENAI_API_KEY"], "prodex-runtime-provider")
        self.assertIsNone(launch["environment"]["PRODEX_RUNTIME_LOCAL_KEY"])
        self.assertIsNone(launch["environment"]["CODEX_SANDBOX_SENTINEL"])
        self.assertEqual(launch["environment"]["CODEX_TUI_DISABLE_KEYBOARD_ENHANCEMENT"], "1")
        self.assertEqual([record["method"] for record in records if record["kind"] == "request"], ["initialize", "hooks/list", "hooks/list"])
        self.assertEqual(response["status"], 200)
        self.assertIn("response.completed", event_names(response["body"]))
        self.assertIn(b"synthetic greeting", bytes.fromhex(response["body"]))
        self.assertEqual({key.lower(): value for key, value in upstream[0]["headers"].items()}["authorization"], "Bearer synthetic-provider-key")
        self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
        self.assertEqual(state["leftovers"], [])
        self.assertEqual(state["session"], '{"synthetic":true}\n')
        self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)

    def test_buffered_and_binary_passthrough(self):
        for scenario in ("buffered", "passthrough"):
            with self.subTest(scenario=scenario):
                result, records, upstream, state = self.run_launch(scenario=scenario)
                self.assertEqual(result.returncode, 0, result.stderr)
                response = next(record for record in records if record["kind"] == "response")
                self.assertEqual(response["status"], 200)
                if scenario == "passthrough":
                    self.assertEqual(bytes.fromhex(response["body"]), b"\x00synthetic upstream\xff")
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions?synthetic=1")
                    self.assertEqual(upstream[0]["headers"]["Content-Type"], "application/x-synthetic")
                    self.assertEqual(bytes.fromhex(upstream[0]["body"]), b"\x00synthetic\xff")
                self.assertEqual(state["leftovers"], [])

    def test_child_exit_and_preflight_failure_cleanup(self):
        for scenario, code in (("exit-seven", 7), ("closed-input", 1), ("kill-relay", 1)):
            with self.subTest(scenario=scenario):
                result, records, upstream, state = self.run_launch(scenario=scenario)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(upstream, [])
                self.assertEqual(state["leftovers"], [])
                if scenario == "closed-input": self.assertIn(b"Broken pipe (os error 32)", result.stderr)
                if scenario == "kill-relay":
                    self.assertEqual([record["signal"] for record in records if record["kind"] == "terminated"], [signal.SIGTERM])

    def test_relay_failure_escalates_after_grace_period_for_ignoring_child(self):
        started = time.monotonic()
        result, records, upstream, state = self.run_launch(scenario="kill-relay-ignores-term")
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(upstream, [])
        self.assertEqual(state["leftovers"], [])
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertLess(elapsed, 12)
        self.assertEqual([record["signal"] for record in records if record["kind"] == "terminated"], [signal.SIGTERM])

    def test_unexpected_codex_state_is_retained(self):
        result, _, upstream, state = self.run_launch(scenario="extra-state")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(upstream, [])
        self.assertEqual(state["extra"], ["preserve this data"])
        self.assertIn(b"Modex retained Codex runtime data", result.stderr)

    def test_legacy_hook_bypass_uses_the_baseline_cli_flag(self):
        result, records, _, state = self.run_launch(scenario="legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = next(record for record in records if record["kind"] == "launch")
        self.assertEqual(launch["args"][0], "--dangerously-bypass-hook-trust")
        self.assertNotIn("hooks.disable_untrusted_hooks", launch["config"])
        self.assertEqual(state["leftovers"], [])

    def test_idle_relay_exits_when_its_parent_channel_closes(self):
        with tempfile.TemporaryDirectory(prefix="modex-relay-parent-") as directory:
            environment = {"HOME": directory, "PATH": "/usr/bin:/bin", "TMPDIR": directory,
                           "PRODEX_RUNTIME_LOCAL_UPSTREAM": "http://127.0.0.1:1/v1",
                           "PRODEX_RUNTIME_LOCAL_KEY": "synthetic-provider-key"}
            process = subprocess.Popen([str(MODEX), "__modex-local-rewrite"], env=environment,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                ready = process.stdout.readline()
                self.assertTrue(ready.startswith(b"127.0.0.1:"), ready)
                stdout, stderr = process.communicate(timeout=3)
                self.assertEqual((process.returncode, stdout, stderr), (0, b"", b""))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_parent_eof_closes_parked_and_overflow_connections(self):
        import socket

        with tempfile.TemporaryDirectory(prefix="modex-relay-overflow-parent-") as directory:
            environment = {"HOME": directory, "PATH": "/usr/bin:/bin", "TMPDIR": directory,
                           "PRODEX_RUNTIME_LOCAL_UPSTREAM": "http://127.0.0.1:1/v1",
                           "PRODEX_RUNTIME_LOCAL_KEY": "synthetic-provider-key"}
            process = subprocess.Popen([str(MODEX), "__modex-local-rewrite"], env=environment,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            clients = []
            try:
                ready = process.stdout.readline()
                self.assertTrue(ready.startswith(b"127.0.0.1:"), ready)
                host, port = ready.decode("ascii").strip().rsplit(":", 1)
                for index in range(137):
                    client = socket.create_connection((host, int(port)), timeout=5)
                    client.settimeout(1)
                    client.sendall((f"POST /v1/chat/completions HTTP/1.1\r\nHost: {host}:{port}\r\n"
                                    f"Content-Length: 2\r\nX-Slow-Partial: {index}\r\n").encode())
                    clients.append(client)
                time.sleep(0.1)
                process.stdin.close()
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(process.stdout.read(), b"")
                self.assertEqual(process.stderr.read(), b"")
                for client in clients:
                    try:
                        self.assertEqual(client.recv(1), b"")
                    except ConnectionResetError:
                        pass
            finally:
                for client in clients:
                    client.close()
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_existing_codex_data_is_preserved_before_child_or_network(self):
        result, records, upstream, state = self.run_launch(existing=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(records, [])
        self.assertEqual(upstream, [])
        self.assertEqual(state["config"], 'model="preserve-me"\n')
        self.assertIn("shared/auth.json", state["managed"])
        self.assertEqual(state["leftovers"], [])

    def test_unsafe_beta_url_fails_before_profile_or_codex_launch(self):
        result, records, upstream, state = self.run_launch(
            scenario="buffered",
            environment_overrides={
                "PRODEX_DEEPSEEK_STRICT_TOOLS": "true",
                "PRODEX_DEEPSEEK_BETA_BASE_URL": (
                    "http://synthetic-user:synthetic-secret@127.0.0.1:1234/beta"
                ),
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b"synthetic-secret", result.stdout + result.stderr)
        self.assertEqual(records, [])
        self.assertEqual(upstream, [])
        self.assertEqual(state["leftovers"], [])

    def test_live_pinned_release_data_plane(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        for scenario in ("stream", "buffered", "passthrough"):
            with self.subTest(scenario=scenario):
                baseline, before_records, before_upstream, _ = self.run_launch(ORACLE, scenario)
                native, after_records, after_upstream, _ = self.run_launch(MODEX, scenario)
                self.assertEqual((native.returncode, native.stdout), (baseline.returncode, baseline.stdout))
                before = next(record for record in before_records if record["kind"] == "response")
                after = next(record for record in after_records if record["kind"] == "response")
                before_launch = next(record for record in before_records if record["kind"] == "launch")
                after_launch = next(record for record in after_records if record["kind"] == "launch")
                for key, value in after_launch["config"].items():
                    if key not in ("projects", "model_catalog_json") and not key.endswith(".base_url"):
                        self.assertEqual(value, before_launch["config"][key], key)
                self.assertEqual(after_launch["catalog"], before_launch["catalog"])
                self.assertEqual(after["status"], before["status"])
                self.assertEqual(after_upstream[0]["path"], before_upstream[0]["path"])
                self.assertEqual(after_upstream[0]["body"], before_upstream[0]["body"])
                if scenario == "stream": self.assertEqual(event_names(after["body"]), event_names(before["body"]))
                if scenario == "passthrough": self.assertEqual(after["body"], before["body"])

    def test_launch_progress_and_probe_errors_match_historical_release(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = (
            ("minimum-version", "exit-seven", {"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1"}, 1),
            ("capability-probe", "app-server-help-failure", {}, 1),
            ("child-start", "exit-seven", {"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.2"}, 7),
        )
        for label, scenario, environment, exit_code in cases:
            with self.subTest(label=label):
                observations = []
                states = []
                for binary in (ORACLE, MODEX):
                    result, records, upstream, state = self.run_launch(
                        binary=binary,
                        scenario=scenario,
                        environment_overrides=environment,
                    )
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    probes = [record["args"] for record in records if record["kind"] == "probe"]
                    self.assertEqual(probes[0], ["--version"])
                    if label != "minimum-version":
                        self.assertEqual(probes[1], ["app-server", "--help"])
                    expected_kinds = {
                        "minimum-version": ["probe"],
                        "capability-probe": ["probe", "probe"],
                        "child-start": ["probe", "probe", "preflight", "request", "request", "request", "launch"],
                    }[label]
                    self.assertEqual([record["kind"] for record in records], expected_kinds)
                    observations.append((
                        result.returncode,
                        result.stdout,
                        normalized_codex_path(result.stderr),
                        tuple(record["args"] for record in records if record["kind"] == "probe"),
                        tuple(record["kind"] for record in records),
                    ))
                    states.append(state)
                self.assertEqual(observations[0], observations[1])
                self.assertEqual(
                    tuple(states[0][name] for name in ("leftovers", "session", "extra", "config")),
                    tuple(states[1][name] for name in ("leftovers", "session", "extra", "config")),
                )

                # 0.439.2 creates these runtime locks/housekeeping files; Modex does not yet.
                oracle_managed = set(states[0]["managed"])
                modex_managed = set(states[1]["managed"])
                self.assertEqual(modex_managed - oracle_managed, set())
                oracle_only = oracle_managed - modex_managed
                broker_locks = {
                    path for path in oracle_only
                    if path.startswith("state/runtime-broker-live-runtime-")
                    and path.endswith(".json.lock")
                }
                self.assertEqual(len(broker_locks), 1)
                expected_oracle_only = {
                    "state/profile-lifecycle.json.lock",
                    "state/runtime-housekeeping.last-run",
                    "state/runtime-housekeeping.lock",
                }
                if label == "child-start":
                    expected_oracle_only.update({
                        "shared/sessions/.prodex-maintenance.lock",
                        "state/runtime-local-proxy-leases",
                    })
                self.assertEqual(oracle_only - broker_locks, expected_oracle_only)

    def test_codex_binary_selection_against_04392_matches_shebang_paths(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        canonical = "<canonical>/codex"
        oracle_child_argv0 = {
            "relative": "../codex",
            "symlink": "../codex-alias",
            "command": "<path>/codex",
            "command-cwd": "codex",
            "command-relative-path": "bin/codex",
            "path": canonical,
            "relative-path": canonical,
            "path-skips-wrapper": canonical,
        }

        def script_path(path):
            if not path.startswith("/"):
                return path
            if path.endswith("/work/bin/codex"):
                return "<path>/codex"
            if path.endswith("/codex"):
                return canonical
            return path

        for mode, oracle_child in oracle_child_argv0.items():
            with self.subTest(mode=mode):
                traces = []
                outputs = []
                for binary in (ORACLE, MODEX):
                    result, records, upstream, state = self.run_launch(
                        binary=binary,
                        scenario="exit-seven",
                        codex_mode=mode,
                        environment_overrides={"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.2"},
                    )
                    self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                    self.assertEqual(upstream, [])
                    self.assertEqual(state["leftovers"], [])
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertNotIn(b"synthetic-codex-key", result.stdout + result.stderr)
                    outputs.append((
                        result.returncode,
                        result.stdout,
                        normalized_codex_path(result.stderr),
                    ))
                    self.assertEqual(
                        [record["args"] for record in records if record["kind"] == "probe"],
                        [["--version"], ["app-server", "--help"]],
                    )
                    self.assertEqual(
                        [record["kind"] for record in records],
                        ["probe", "probe", "preflight", "request", "request", "request", "launch"],
                    )
                    traces.append([
                        (record["kind"], script_path(record["script_argv0"]))
                        for record in records
                        if record["kind"] in ("probe", "preflight", "launch")
                    ])

                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(
                    traces[0],
                    [("probe", canonical), ("probe", canonical),
                     ("preflight", oracle_child), ("launch", oracle_child)],
                )
                self.assertEqual(
                    traces[1],
                    [("probe", canonical), ("probe", canonical),
                     ("preflight", oracle_child), ("launch", oracle_child)],
                )

    def test_normal_tty_does_not_receive_the_text_fallback(self):
        result, records, upstream, state = self.run_launch(
            scenario="exit-seven",
            environment_overrides={
                "MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1",
                "TERM": "xterm-256color",
            },
            stderr_tty=True,
        )
        self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
        self.assertEqual([record["args"] for record in records if record["kind"] == "probe"], [["--version"]])
        self.assertEqual((upstream, state["leftovers"]), ([], []))
        self.assertNotIn(b"Prodex launch:", result.stderr)
        self.assertNotIn(b"[ Runtime Provider ]", result.stderr)
        self.assertNotIn(b"\x1b[", result.stderr)
        self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)

    def test_model_catalog_selection_and_metadata_match_release(self):
        for model in ("deepseek-v4-pro", "deepseek-flash", "deepseek-v4-flash", "auto", "flash", "deepseek-chat", "deepseek-reasoner", "synthetic-model-\"quoted\"", "synthetic\\model", "DEEPSEEK-CHAT", "deepsee\u212a-chat"):
            with self.subTest(model=model):
                baseline, before_records, _, _ = self.run_launch(ORACLE, "exit-seven", model=model)
                native, after_records, _, _ = self.run_launch(MODEX, "exit-seven", model=model)
                self.assertEqual((native.returncode, baseline.returncode), (7, 7))
                before = next(record for record in before_records if record["kind"] == "launch")
                after = next(record for record in after_records if record["kind"] == "launch")
                self.assertEqual(after["catalog"], before["catalog"])

    def test_release_catalog_retains_compatibility_models(self):
        for binary in (ORACLE, MODEX):
            result, records, upstream, _ = self.run_launch(binary, scenario="exit-seven", model="deepseek-flash")
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(upstream, [])
            launch = next(record for record in records if record["kind"] == "launch")
            models = {row["slug"]: row for row in launch["catalog"]["models"]}
            self.assertEqual(models["deepseek-flash"]["description"],
                             "DeepSeek model routed through the Prodex Responses adapter.")
            self.assertEqual(models["flash"]["description"],
                             "Prodex DeepSeek Flash alias routed through DeepSeek V4 Flash.")
            for name in ("deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"):
                self.assertEqual([level["effort"] for level in models[name]["supported_reasoning_levels"]],
                                 ["low", "medium", "high", "xhigh"])

    def test_oversized_model_fails_before_child_or_upstream(self):
        result, records, upstream, state = self.run_launch(model="m" * 4097)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"model identifier exceeds 4096 bytes", result.stderr)
        self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))

    def test_error_quota_headers_match_pinned_dispatch_without_post_replay(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        for scenario in ("error-401", "error-403", "error-429", "error-503", "error-stream-429", "stream-error"):
            with self.subTest(scenario=scenario):
                responses = []
                for binary in (ORACLE, MODEX):
                    result, records, upstream, _ = self.run_launch(binary, scenario)
                    self.assertEqual(result.returncode, 0 if scenario == "stream-error" else 1, result.stderr)
                    self.assertEqual(len(upstream), 1)
                    response = next(record for record in records if record["kind"] == "response")
                    self.assertNotIn("x-synthetic-hop", response["headers"])
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    responses.append(response)
                baseline, actual = responses
                self.assertEqual(actual["status"], baseline["status"])
                self.assertEqual(actual["headers"]["content-type"], baseline["headers"]["content-type"])
                for name in ("x-deepseek-requests-primary-used-percent", "x-deepseek-tokens-primary-used-percent",
                             "x-deepseek-requests-primary-reset-at", "x-deepseek-tokens-primary-reset-at"):
                    self.assertEqual(actual["headers"].get(name), baseline["headers"].get(name))
                    self.assertEqual(name in actual["headers"], scenario == "stream-error")
                if scenario == "stream-error":
                    self.assertEqual(event_names(actual["body"]), event_names(baseline["body"]))
                    self.assertIn("response.failed", event_names(actual["body"]))
                else:
                    self.assertEqual(actual["body"], baseline["body"])
                    self.assertEqual(actual["headers"].get("x-ratelimit-limit-requests"), "100")

    def test_context_and_compaction_limits_match_release_config_and_catalog(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = (
            (("--context-window", "32768"), 32768, 32767),
            (("--auto-compact-token-limit", "12000"), 1048576, 12000),
            (("--local-context-window", "+00032768", "--local-auto-compact-token-limit", "999999"), 32768, 32767),
            (("--context-window", "0", "--auto-compact-token-limit", "0"), 1048576, 900000),
            (("--context-window", "1"), 1048576, 900000),
            (("--context-window", "2"), 2, 1),
            (("--context-window", "3"), 3, 2),
            (("--auto-compact-token-limit", "1"), 1048576, 1),
            (("--context-window", "18446744073709551615", "--auto-compact-token-limit", "18446744073709551615"),
             18446744073709551615, 18446744073709551614),
        )
        for arguments, context, compact in cases:
            with self.subTest(arguments=arguments):
                launches = []
                for binary in (ORACLE, MODEX):
                    result, records, upstream, _ = self.run_launch(binary, "buffered", super_arguments=arguments)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(len(upstream), 1)
                    launch = next(record for record in records if record["kind"] == "launch")
                    self.assertEqual(launch["config"]["model_context_window"], context)
                    self.assertEqual(launch["config"]["model_auto_compact_token_limit"], compact)
                    launches.append(launch)
                self.assertEqual(launches[0]["catalog"], launches[1]["catalog"])
                for row in launches[1]["catalog"]["models"]:
                    self.assertEqual((row["context_window"], row["max_context_window"], row["auto_compact_token_limit"]),
                                     (1048576, 1048576, 900000))


if __name__ == "__main__": unittest.main()
