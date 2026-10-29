"""Compare tolerant Anthropic stream metadata handling across both pinned releases."""

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
import test_deepseek_continuation as continuation
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, serving
from test_provider_tools_04392_characterization import _normalized_events
from provider_stream_search_cases import repeated_search_case


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
_GENERATED_CALL_ID = re.compile(
    r"call_deepseek_[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


def _stream(events):
    body = b"".join(
        b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        for event in events
    )
    return {"status": 200, "content_type": "text/event-stream", "body": body}


def _events():
    return [
        {"type": "message_start", "message": {
            "id": "msg_synthetic", "role": "assistant", "model": "deepseek-chat",
            "usage": {"input_tokens": 3, "output_tokens": 0},
        }},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "synthetic"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]


def _normalize_orphan_fallback_call_id(events):
    # This fixture has no tool start or provider ID; only its fallback UUID varies.
    normalized = copy.deepcopy(events)
    generated_id = None
    normalized_deltas = 0
    for name, payload in normalized:
        if name == "response.output_item.added":
            item = payload.get("item", {})
            if item.get("type") == "function_call" and item.get("name") == "tool_call":
                call_id = item.get("call_id")
                if not isinstance(call_id, str) or not _GENERATED_CALL_ID.fullmatch(call_id):
                    raise AssertionError("orphan tool fixture did not emit a generated UUIDv7 call_id")
                if generated_id is not None:
                    raise AssertionError("orphan tool fixture emitted multiple fallback calls")
                generated_id = call_id
                item["call_id"] = "<generated-call-id>"
        elif name == "response.function_call_arguments.delta":
            if payload.get("call_id") == generated_id and generated_id is not None:
                payload["call_id"] = "<generated-call-id>"
                normalized_deltas += 1
    if generated_id is None or normalized_deltas != 1:
        raise AssertionError("orphan tool fixture did not reuse its generated call_id in one delta")
    return normalized


def _observe_turns_with_read_errors(
    binary, turns, replies, *, idle_timeout_ms=None,
    disconnect_after_failed=False, half_close_request=False,
):
    client = continuation.CLIENT.replace("timeout=15)", "timeout=5)")
    if half_close_request:
        client = client.replace(
            "import http.client, json, os, pathlib, signal, sys, time",
            "import http.client, json, os, pathlib, signal, socket, sys, time",
        )
        marker = "    response = connection.getresponse()"
        client = client.replace(
            marker, "    connection.sock.shutdown(socket.SHUT_WR)\n" + marker,
        )
    if disconnect_after_failed:
        read_and_save = (
            'payload = bytearray()\n'
            '    while b"event: response.failed\\r\\n" not in payload:\n'
            '        piece = response.read1(4096)\n'
            '        if not piece: break\n'
            '        payload.extend(piece)\n'
            '    body_error = "client_closed_after_failure"\n'
            '    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),\n'
            '          "body": bytes(payload).hex(), "body_error": body_error, "started": started, "finished": int(time.time())})'
        )
    else:
        read_and_save = (
            'payload = bytearray()\n'
            '    body_error = None\n'
            '    try:\n'
            '        while True:\n'
            '            piece = response.read1(4096)\n'
            '            if not piece: break\n'
            '            payload.extend(piece)\n'
            '    except Exception as error:\n'
            '        body_error = type(error).__name__ + ": " + str(error)\n'
            '    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),\n'
            '          "body": bytes(payload).hex(), "body_error": body_error, "started": started, "finished": int(time.time())})'
        )
    client = client.replace(
        'payload = response.read()\n'
        '    save({"kind": "response", "status": response.status, "headers": dict(response.getheaders()),\n'
        '          "body": payload.hex(), "started": started, "finished": int(time.time())})',
        read_and_save,
    )
    if (
        client == continuation.CLIENT or "timeout=5)" not in client
        or "body_error" not in client
        or half_close_request and "socket.SHUT_WR" not in client
    ):
        raise AssertionError("synthetic client could not capture incomplete stream reads")
    original = continuation.CLIENT
    continuation.CLIENT = client
    try:
        return continuation.observe_turns(
            binary, turns, replies, idle_timeout_ms=idle_timeout_ms,
        )
    finally:
        continuation.CLIENT = original


def _capture_body_probe(
    request, reply, *, idle_timeout_ms=None, disconnect_after_failed=False,
    half_close_request=False,
):
    captures = {}
    for label, binary in (
        ("0.165.1", ORACLE_01651),
        ("0.439.2", ORACLE_04392),
        ("Modex", MODEX),
    ):
        posts, responses = _observe_turns_with_read_errors(
            binary, [request], [reply], idle_timeout_ms=idle_timeout_ms,
            disconnect_after_failed=disconnect_after_failed,
            half_close_request=half_close_request,
        )
        if len(posts) != 1 or posts[0]["path"] != "/anthropic/v1/messages":
            raise AssertionError((label, posts))
        headers = {key.lower(): value for key, value in posts[0]["headers"].items()}
        if headers.get("x-api-key") != "synthetic-provider-key" or "authorization" in headers:
            raise AssertionError((label, headers))
        if len(responses) != 1:
            raise AssertionError((label, responses))
        row = responses[0]
        transfer_encoding = next(
            (value for name, value in row["headers"].items()
             if name.lower() == "transfer-encoding"),
            None,
        )
        captures[label] = (
            row["status"], row.get("body_error"), transfer_encoding,
            _normalized_events(bytes.fromhex(row["body"])),
        )
    return captures


def _observe_parent_shutdown(
    binary, request, reply, pipeline_body_bytes=1048576, pipeline_head_bytes=None,
):
    client = continuation.CLIENT.replace(
        "    payload = response.read()",
        '    payload = bytearray()\n'
        '    while b"event: response.failed\\r\\n" not in payload:\n'
        '        piece = response.read1(4096)\n'
        '        if not piece: break\n'
        '        payload.extend(piece)\n'
        '    save({"kind":"held","body":bytes(payload).hex()})\n'
        '    try:\n'
        '        while True:\n'
        '            piece = response.read1(4096)\n'
        '            if not piece: break\n'
        '    except Exception as error:\n'
        '        save({"kind":"body_error","error":type(error).__name__ + ": " + str(error)})\n'
        '    payload = bytes(payload)',
    )
    marker = "    response = connection.getresponse()"
    pipeline = (
        f'    pipeline_body = b"x" * {pipeline_body_bytes}\n'
        '    pipeline = (\n'
        '        b"POST " + target.path.encode() + b" HTTP/1.1\\r\\n"\n'
        '        + b"Host: " + target.hostname.encode() + b":" + str(target.port).encode() + b"\\r\\n"\n'
        '        + b"Content-Type: application/json\\r\\nContent-Length: 1048576\\r\\n"\n'
        '        + b"Connection: keep-alive\\r\\n\\r\\n" + pipeline_body\n'
        '    )\n'
        + (f'    pipeline = pipeline[:{pipeline_head_bytes}]\n' if pipeline_head_bytes is not None else "")
        + '    connection.sock.sendall(pipeline)\n'
        + '    save({"kind":"pipelined","bytes":len(pipeline_body),"wire_bytes":len(pipeline),"write_open":True})\n'
    )
    client = client.replace(marker, pipeline + marker)
    if (
        client == continuation.CLIENT or '"kind":"held"' not in client
        or '"kind":"pipelined"' not in client
    ):
        raise AssertionError("synthetic client could not hold the stream open")
    with tempfile.TemporaryDirectory(prefix="modex-parent-shutdown-") as temporary:
        root = Path(temporary)
        for name in ("home", "state", "shared", "work"):
            (root / name).mkdir(mode=0o700)
        (root / "state/update-check.json").write_text(
            '{"source":"GitHub","latest_version":"0.439.2","checked_at":4102444800}'
        )
        codex = root / "codex"
        codex.write_text("#!" + sys.executable + "\n" + client)
        codex.chmod(0o700)
        capture = root / "capture.jsonl"
        turns_file = root / "turns.json"
        turns_file.write_text(json.dumps([request]))
        environment = {
            "HOME": str(root / "home"), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
            "PRODEX_HOME": str(root / "state"),
            "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
            "PRODEX_CODEX_BIN": str(codex),
            "MODEX_LAUNCH_CAPTURE": str(capture),
            "MODEX_LAUNCH_SCENARIO": "buffered",
            "MODEX_CONTINUATION_TURNS_FILE": str(turns_file),
            "TERM": "dumb", "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "XDG_CONFIG_HOME": str(root / "home"),
            "XDG_CACHE_HOME": str(root / "home"),
            "XDG_DATA_HOME": str(root / "home"),
        }
        with serving([reply]) as upstream:
            process = subprocess.Popen(
                [
                    str(binary), "super", "--provider", "deepseek", "--api-key",
                    SYNTHETIC_API_KEY, "--base-url",
                    f"http://127.0.0.1:{upstream.server_port}/v1", "--model",
                    "deepseek-chat", "--no-presidio", "--no-sub-agent",
                    "--skip-quota-check", "exec", "--", "synthetic",
                ],
                cwd=root / "work", env=environment,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            children = []
            held = False
            shutdown_sent = False
            parent_timed_out = False
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        rows = [
                            json.loads(line) for line in capture.read_text().splitlines()
                            if line
                        ] if capture.exists() else []
                    except json.JSONDecodeError:
                        rows = []
                    if any(row.get("kind") == "held" for row in rows):
                        held = True
                        break
                    time.sleep(0.02)
                try:
                    for value in Path(
                        f"/proc/{process.pid}/task/{process.pid}/children"
                    ).read_text().split():
                        pid = int(value)
                        try:
                            children.append((pid, os.pidfd_open(pid)))
                        except ProcessLookupError:
                            pass
                except FileNotFoundError:
                    pass
                if held:
                    try:
                        process.send_signal(signal.SIGTERM)
                        shutdown_sent = True
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    parent_timed_out = True
                    process.kill()
                    process.wait(timeout=2)
                deadline = time.monotonic() + 2
                alive_children = children.copy()
                while time.monotonic() < deadline:
                    alive_children = [
                        (pid, fd) for pid, fd in children
                        if not select.select([fd], [], [], 0)[0]
                    ]
                    if not alive_children:
                        break
                    time.sleep(0.02)
                for _, fd in alive_children:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if alive_children:
                    time.sleep(0.05)
                try:
                    rows = [
                        json.loads(line) for line in capture.read_text().splitlines()
                        if line
                    ] if capture.exists() else []
                except json.JSONDecodeError:
                    rows = []
                return {
                    "parent_returncode": process.returncode,
                    "shutdown_sent": shutdown_sent,
                    "parent_timed_out": parent_timed_out,
                    "children_alive_after_2s": [pid for pid, _ in alive_children],
                    "held": held or any(row.get("kind") == "held" for row in rows),
                    "held_records": [row for row in rows if row.get("kind") == "held"],
                    "pipelined_records": [row for row in rows if row.get("kind") == "pipelined"],
                    "body_errors": [row for row in rows if row.get("kind") == "body_error"],
                    "responses": [row for row in rows if row.get("kind") == "response"],
                }
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
                for _, fd in children:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finally:
                        os.close(fd)


def _observe_pipelined_disconnect(
    binary, request, failed_reply, followup_reply, close_mode,
    pad_bytes=32768, failure_count=8,
):
    marker = "previous = None\n"
    if marker not in continuation.CLIENT:
        raise AssertionError("synthetic client no longer exposes its target URL")
    client = continuation.CLIENT.split(marker, 1)[0] + f'''\
import socket, struct
turn = json.loads(pathlib.Path(os.environ["MODEX_CONTINUATION_TURNS_FILE"]).read_text())[0]
body = json.dumps(turn, separators=(",", ":")).encode()
host = target.hostname.encode()
request_bytes = (
    b"POST " + target.path.encode() + b" HTTP/1.1\\r\\nHost: " + host
    + b"\\r\\nContent-Type: application/json\\r\\n"
    + b"Authorization: Bearer synthetic-client-key\\r\\nContent-Length: "
    + str(len(body)).encode() + b"\\r\\nConnection: keep-alive\\r\\n\\r\\n" + body
)
pending_tail = (
    b"GET " + target.path.encode() + b" HTTP/1.1\\r\\nHost: " + host
    + b"\\r\\nConnection: keep-alive\\r\\nContent-Length: 0\\r\\nX-Pad: "
    + b"x" * {pad_bytes} + b"\\r\\n\\r\\n"
)
failure_marker = b"event: response.failed\\r\\n"
client_results = []
for index in range({failure_count}):
    started = time.monotonic()
    client = None
    try:
        client = socket.create_connection((target.hostname, target.port), timeout=5)
        client.settimeout(5)
        client.sendall(request_bytes + pending_tail)
        received = bytearray()
        while failure_marker not in received:
            piece = client.recv(4096)
            if not piece:
                break
            received.extend(piece)
        got_failure = failure_marker in received
        if got_failure:
            client.settimeout(0.1)
            try:
                while True:
                    piece = client.recv(4096)
                    if not piece:
                        break
                    received.extend(piece)
            except (socket.timeout, OSError):
                pass
        status = None
        if b"\\r\\n\\r\\n" in received:
            head = bytes(received).split(b"\\r\\n\\r\\n", 1)[0]
            try:
                status = int(head.split(b"\\r\\n", 1)[0].split()[1])
            except (IndexError, ValueError):
                pass
            first_connection = next(
                (line.split(b":", 1)[1].strip().decode("latin-1")
                 for line in head.split(b"\\r\\n")[1:]
                 if line.lower().startswith(b"connection:")),
                None,
            )
        else:
            first_connection = None
        client_results.append({{
            "got_failure": got_failure, "status": status,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": None if got_failure else "TimeoutError",
            "trailing_502": b"HTTP/1.1 502 Bad Gateway\\r\\n" in received,
            "first_connection": first_connection,
        }})
        if got_failure and {close_mode!r} == "rst":
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            client.close()
        elif got_failure and {close_mode!r} == "fin":
            client.shutdown(socket.SHUT_WR)
            client.close()
    except Exception as error:
        client_results.append({{
            "got_failure": False, "status": None,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": type(error).__name__,
        }})
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass

followup_status = None
followup_error = None
followup_body = b""
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
try:
    connection.request(
        "POST", target.path, json.dumps(turn, separators=(",", ":")).encode(),
        {{"Content-Type": "application/json", "Authorization": "Bearer synthetic-client-key"}},
    )
    response = connection.getresponse()
    followup_status = response.status
    followup_body = response.read()
except Exception as error:
    followup_error = type(error).__name__
finally:
    connection.close()
save({{
    "kind": "response", "status": followup_status, "headers": {{}},
    "body": followup_body.hex(), "close_mode": {close_mode!r},
    "failure_results": client_results,
    "failure_count": sum(1 for row in client_results if row and row["got_failure"]),
    "pipelined_bytes": len(pending_tail), "followup_error": followup_error,
}})
print("synthetic-continuation-complete")
'''
    original = continuation.CLIENT
    continuation.CLIENT = client
    try:
        return continuation.observe_turns(
            binary, [request], [failed_reply] * failure_count + [followup_reply],
        )
    finally:
        continuation.CLIENT = original


def _cases():
    cases = []
    for name, field, value in (
        ("start_id_missing", "id", "missing"),
        ("start_id_empty", "id", ""),
        ("start_id_wrong_type", "id", 42),
        ("start_role_missing", "role", "missing"),
        ("start_role_other", "role", "user"),
        ("start_model_missing", "model", "missing"),
        ("start_model_wrong_type", "model", None),
        ("start_type_other", "type", "future_message"),
    ):
        events = _events()
        if value == "missing":
            del events[0]["message"][field]
        elif field == "type":
            events[0]["message"][field] = value
        else:
            events[0]["message"][field] = value
        cases.append((name, events))

    extra = _events()
    extra[0]["message"]["future_field"] = {"value": "ignored"}
    extra[0]["future_event_field"] = True
    cases.append(("start_extra_fields", extra))

    for name, usage in (
        ("start_usage_missing", "missing"),
        ("start_usage_null", None),
        ("start_usage_wrong_type", "invalid"),
        ("start_usage_missing_input", {"output_tokens": 0}),
        ("start_usage_invalid_input", {"input_tokens": -1, "output_tokens": 0}),
    ):
        events = _events()
        if usage == "missing":
            del events[0]["message"]["usage"]
        else:
            events[0]["message"]["usage"] = usage
        cases.append((name, events))

    for name, usage in (
        ("delta_usage_missing", "missing"),
        ("delta_usage_null", None),
        ("delta_usage_wrong_type", 7),
        ("delta_usage_missing_output", {}),
        ("delta_usage_invalid_output", {"output_tokens": "five"}),
    ):
        events = _events()
        if usage == "missing":
            del events[4]["usage"]
        else:
            events[4]["usage"] = usage
        cases.append((name, events))

    extra = _events()
    extra[4]["future_event_field"] = True
    extra[4]["usage"]["future_usage_field"] = "ignored"
    cases.append(("delta_extra_fields", extra))

    for name, text in (
        ("text_delta_missing", "missing"),
        ("text_delta_null", None),
        ("text_delta_wrong_type", 42),
    ):
        events = _events()
        if text == "missing":
            del events[2]["delta"]["text"]
        else:
            events[2]["delta"]["text"] = text
        cases.append((name, events))

    extra = _events()
    extra[2]["future_event_field"] = True
    extra[2]["delta"]["future_delta_field"] = "ignored"
    cases.append(("text_delta_extra_fields", extra))
    return cases


class AnthropicOptionalMetadataSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not oracle.is_file():
                raise AssertionError(f"pinned Prodex oracle is missing: {oracle}")
            digest = hashlib.sha256(oracle.read_bytes()).hexdigest()
            if digest != expected:
                raise AssertionError(f"pinned Prodex oracle checksum mismatch: {oracle}: {digest}")
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")

    def test_orphan_fallback_call_id_normalization_is_field_scoped(self):
        generated_id = "call_deepseek_01a18668-fba1-718c-87a7-918623547f3a"
        events = [
            ("response.output_item.added", {"item": {
                "type": "function_call", "name": "tool_call", "call_id": generated_id,
                "arguments": "call_deepseek_argument_text",
            }}),
            ("response.function_call_arguments.delta", {
                "call_id": generated_id, "delta": "call_deepseek_user_text",
            }),
            ("response.output_text.delta", {"delta": "call_deepseek_visible_text"}),
            ("response.output_item.added", {"item": {
                "type": "function_call", "name": "lookup", "call_id": generated_id,
            }}),
        ]
        normalized = _normalize_orphan_fallback_call_id(events)
        self.assertEqual(normalized[0][1]["item"]["call_id"], "<generated-call-id>")
        self.assertEqual(normalized[1][1]["call_id"], "<generated-call-id>")
        self.assertEqual(normalized[0][1]["item"]["arguments"], "call_deepseek_argument_text")
        self.assertEqual(normalized[1][1]["delta"], "call_deepseek_user_text")
        self.assertEqual(normalized[2][1]["delta"], "call_deepseek_visible_text")
        self.assertEqual(normalized[3][1]["item"]["call_id"], generated_id)

    def test_optional_metadata_and_nonstrings_match_both_release_oracles(self):
        cases = _cases()
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, copy.deepcopy(turns), copy.deepcopy(replies))
            self.assertEqual(len(posts), len(cases), label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(row["path"] == "/anthropic/v1/messages" for row in posts), label)
            self.assertTrue(all(row["status"] == 200 for row in responses), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertEqual(headers["anthropic-version"], "2023-06-01", label)
                self.assertNotIn("authorization", headers, label)
            captures[label] = [
                (post["body"], response["status"],
                 _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]

        expected = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], expected)
        self.assertEqual(captures["Modex"], expected)
        for (name, _), (_, _, events) in zip(cases, expected):
            with self.subTest(case=name):
                self.assertEqual(events[-1][0], "response.completed")
                if name in ("text_delta_missing", "text_delta_null", "text_delta_wrong_type"):
                    self.assertNotIn("response.output_text.delta", [event for event, _ in events])
                else:
                    self.assertIn("synthetic", json.dumps(events[-1][1]["response"]["output"]))

    def test_input_json_delta_ignores_extra_root_fields_against_both_releases(self):
        request, reply = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        for event in events:
            if (
                event.get("type") == "content_block_delta"
                and event.get("delta", {}).get("type") == "input_json_delta"
            ):
                event["future_event_field"] = "ignored"
        reply = _stream(events)
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1, label)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages", label)
            headers = {key.lower(): value for key, value in posts[0]["headers"].items()}
            self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
            self.assertEqual((len(responses), responses[0]["status"]), (1, 200), label)
            captures[label] = (
                posts[0]["body"], _normalized_events(bytes.fromhex(responses[0]["body"]))
            )
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        self.assertIn(
            "Found both",
            json.dumps(captures["0.439.2"][1][-1][1]["response"]["output"]),
        )

    def test_unknown_delta_type_strings_ignore_extra_fields_against_both_releases(self):
        cases = []
        for delta_type in ("citation_delta", "signature_delta", "future_delta"):
            for extra_root_field in (False, True):
                events = _events()
                if delta_type == "citation_delta":
                    delta = {
                        "type": delta_type,
                        "citation": {
                            "type": "web_search_result_location",
                            "url": "https://example.test/source",
                            "title": "Source",
                            "cited_text": "synthetic",
                        },
                    }
                else:
                    delta = {
                        "type": delta_type, "future_payload": {"value": "ignored"},
                    }
                event = {"type": "content_block_delta", "index": 0, "delta": delta}
                if extra_root_field:
                    event["future_event_field"] = "ignored"
                events.insert(3, event)
                cases.append((f"{delta_type}_extra_{extra_root_field}", events))
        for name, index in (("missing_index", None), ("nonnumeric_index", "zero")):
            events = _events()
            event = {"type": "content_block_delta", "delta": {"type": "future_delta"}}
            if name == "nonnumeric_index":
                event["index"] = index
            events.insert(3, event)
            cases.append((f"future_delta_{name}", events))
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                self.assertEqual(events[-1][0], "response.completed")
                self.assertIn("synthetic", json.dumps(events[-1][1]["response"]["output"]))

    def test_missing_or_nonstring_delta_type_fails_closed_against_both_releases(self):
        cases = []
        for name, delta in (
            ("missing", {}),
            ("null", {"type": None}),
            ("number", {"type": 42}),
        ):
            for extra_root_field in (False, True):
                events = _events()
                events[2]["delta"] = delta.copy()
                if extra_root_field:
                    events[2]["future_event_field"] = "rejected"
                cases.append((f"{name}_extra_{extra_root_field}", events))
        for name, insertion in (
            ("after_text", 3),
            ("after_block_stop", 4),
            ("after_message_delta", 5),
        ):
            events = _events()
            events.insert(insertion, {
                "type": "content_block_delta", "index": 0, "delta": {"type": None},
            })
            cases.append((name, events))
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                _normalized_events(bytes.fromhex(response["body"])) for response in responses
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for label in ("0.165.1", "0.439.2", "Modex"):
            for (name, _), events in zip(cases, captures[label]):
                with self.subTest(label=label, case=name):
                    self.assertIn("response.failed", [event for event, _ in events])
                    self.assertNotIn("response.completed", [event for event, _ in events])

    def test_search_and_result_blocks_precede_delta_type_validation(self):
        request, reply = repeated_search_case()
        base_events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        cases = []
        for name, insertion, index, delta in (
            ("active_search_missing_type", 2, 0, {"type": None}),
            ("active_search_text_delta", 2, 0, {"type": "text_delta", "text": "ignored"}),
            ("stopped_search_missing_type", 4, 0, {"type": None}),
            ("open_result_missing_type", 5, 1, {"type": None}),
            ("open_result_text_delta", 5, 1, {"type": "text_delta", "text": "ignored"}),
        ):
            events = base_events.copy()
            events.insert(insertion, {"type": "content_block_delta", "index": index, "delta": delta})
            cases.append((name, events))
        events = base_events.copy()
        events.insert(2, {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "ignored"},
        })
        cases.append(("active_search_missing_index_text_delta", events))
        for name, delta in (
            ("reopened_result_missing_type", {"type": None}),
            ("reopened_result_text_delta", {"type": "text_delta", "text": "ignored"}),
        ):
            events = base_events.copy()
            events.insert(6, base_events[4].copy())
            events.insert(7, {"type": "content_block_delta", "index": 1, "delta": delta})
            events.insert(8, {"type": "content_block_stop", "index": 1})
            cases.append((name, events))
        turns = [dict(request, input=name) for name, _ in cases]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                names = [event for event, _ in events]
                self.assertIn("response.completed", names)
                self.assertNotIn("response.failed", names)
                if name.endswith("text_delta"):
                    self.assertNotIn("ignored", json.dumps(events))

    def test_closed_result_failure_continues_like_both_releases(self):
        request, reply = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        events.insert(6, {"type": "content_block_delta", "index": 1, "delta": {"type": None}})
        request["input"] = "closed result failure continuation"
        reply = _stream(events)
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1, label)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages", label)
            headers = {key.lower(): value for key, value in posts[0]["headers"].items()}
            self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
            self.assertNotIn("authorization", headers, label)
            self.assertEqual((len(responses), responses[0]["status"]), (1, 200), label)
            captures[label] = (
                posts[0]["body"], _normalized_events(bytes.fromhex(responses[0]["body"]))
            )
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"][0], captures["0.439.2"][0])
        reference = captures["0.439.2"][1]
        actual = captures["Modex"][1]
        self.assertEqual(
            [name for name, _ in reference],
            [
                "response.output_item.added", "response.output_item.done", "response.failed",
                "response.output_item.added", "response.output_item.done", "response.created",
                "response.output_item.added", "response.output_text.delta",
            ],
        )
        self.assertEqual(actual, reference)
        self.assertEqual(
            reference[2][1]["response"]["error"],
            {"code": "invalid_anthropic_stream", "message": "content delta type is missing"},
        )

    def test_closed_result_text_delta_matches_both_releases(self):
        request, reply = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        events.insert(6, {
            "type": "content_block_delta", "index": 1,
            "delta": {"type": "text_delta", "text": "after closed result"},
        })
        request["input"] = "closed result text delta"
        reply = _stream(events)
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1, label)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages", label)
            headers = {key.lower(): value for key, value in posts[0]["headers"].items()}
            self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
            self.assertNotIn("authorization", headers, label)
            self.assertEqual((len(responses), responses[0]["status"]), (1, 200), label)
            captures[label] = (
                posts[0]["body"], _normalized_events(bytes.fromhex(responses[0]["body"]))
            )
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"][0], captures["0.439.2"][0])
        reference = captures["0.439.2"][1]
        actual = captures["Modex"][1]
        self.assertEqual(
            [name for name, _ in reference],
            [
                "response.output_item.added", "response.output_item.done", "response.created",
                "response.output_item.added", "response.output_text.delta",
                "response.output_item.added", "response.output_item.done",
                "response.output_text.delta", "response.output_item.done", "response.completed",
            ],
        )
        self.assertEqual(actual, reference)
        self.assertIn("after closed result", json.dumps(actual))

    def test_failure_continues_until_message_stop_without_duplicate_events(self):
        request, reply = repeated_search_case()
        base_events = [
            json.loads(line[6:])
            for line in reply["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        repeated_failure = base_events.copy()
        repeated_failure.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        result_stop = next(
            index for index, event in enumerate(repeated_failure)
            if event.get("type") == "content_block_stop" and event.get("index") == 3
        )
        repeated_failure.insert(result_stop + 1, {
            "type": "content_block_delta", "index": 3, "delta": {"type": None},
        })
        after_created = base_events.copy()
        message_delta = next(
            index for index, event in enumerate(after_created)
            if event.get("type") == "message_delta"
        )
        after_created.insert(message_delta + 1, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        after_stop = base_events.copy() + [
            {"type": "content_block_start", "index": 5, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 5, "delta": {"type": "text_delta", "text": "after message_stop"}},
        ]
        terminal_stop_extra = base_events.copy()
        terminal_stop_extra.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        terminal_stop_extra.insert(7, {"type": "message_stop", "future_event_field": "ignored"})
        terminal_error_extra = base_events.copy()
        terminal_error_extra.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        terminal_error_extra.insert(7, {
            "type": "error", "error": {"type": "api_error", "message": "synthetic terminal error"},
            "future_event_field": "ignored",
        })
        terminal_stop_out_of_phase = base_events[:6].copy() + [
            {"type": "content_block_delta", "index": 1, "delta": {"type": None}},
            {"type": "content_block_start", "index": 5, "content_block": {"type": "text", "text": ""}},
            {"type": "message_stop"},
            base_events[0].copy(),
        ] + base_events[6:]
        after_error = [
            base_events[0],
            {"type": "error", "error": {"type": "api_error", "message": "synthetic terminal error"}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "after error"}},
            base_events[-1],
        ]
        missing_block_before_failure = base_events.copy()
        missing_block_before_failure.insert(6, {"type": "content_block_start", "index": 4})
        missing_block_after_failure = base_events.copy()
        missing_block_after_failure.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        missing_block_after_failure.insert(7, {"type": "content_block_start", "index": 4})
        missing_delta_after_failure = base_events.copy()
        missing_delta_after_failure.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        missing_delta_after_failure.insert(7, {"type": "content_block_delta", "index": 4})
        repeated_start_after_failure = base_events.copy()
        repeated_start_after_failure.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        repeated_start_after_failure.insert(7, base_events[0].copy())
        missing_block_in_final_frame = base_events[:-1].copy()
        missing_block_in_final_frame.insert(6, {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        })
        missing_block_in_final_frame.append({"type": "content_block_start", "index": 4})
        cases = [
            ("repeated closed-result failures", repeated_failure, False),
            ("failure after response.created", after_created, False),
            ("missing block before failure", missing_block_before_failure, False),
            ("missing block after failure", missing_block_after_failure, False),
            ("missing delta after failure", missing_delta_after_failure, False),
            ("repeated message_start after failure", repeated_start_after_failure, False),
            ("missing block in final frame", missing_block_in_final_frame, True),
            ("frames after message_stop", after_stop, False),
            ("frames after error", after_error, False),
            ("message_stop extra fields after failure", terminal_stop_extra, False),
            ("error extra fields after failure", terminal_error_extra, False),
            ("out-of-phase message_stop after failure", terminal_stop_out_of_phase, False),
        ]
        turns = [dict(request, input=name) for name, _, _ in cases]
        replies = []
        for _, events, truncated in cases:
            reply = _stream(events)
            if truncated:
                reply["body"] = reply["body"][:-2]
            replies.append(reply)
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                names = [event for event, _ in events]
                if name in (
                    "repeated closed-result failures", "failure after response.created",
                    "missing block before failure", "missing block after failure",
                    "missing delta after failure", "repeated message_start after failure",
                    "missing block in final frame",
                ):
                    self.assertEqual(names.count("response.failed"), 1)
                    self.assertEqual(names.count("response.completed"), 0)
                    self.assertEqual(names.count("response.created"), 1)
                    if name == "failure after response.created":
                        self.assertLess(names.index("response.created"), names.index("response.failed"))
                    else:
                        self.assertLess(names.index("response.failed"), names.index("response.created"))
                    if name == "missing block before failure":
                        self.assertEqual(
                            events[names.index("response.failed")][1]["response"]["error"],
                            {"code": "invalid_anthropic_stream", "message": "content block is missing"},
                        )
                elif name == "frames after message_stop":
                    self.assertEqual(names.count("response.completed"), 1)
                    self.assertNotIn("after message_stop", json.dumps(events))
                elif name in (
                    "message_stop extra fields after failure", "error extra fields after failure",
                    "out-of-phase message_stop after failure",
                ):
                    self.assertEqual(names, [
                        "response.output_item.added", "response.output_item.done", "response.failed",
                    ])
                else:
                    self.assertEqual(names, ["response.failed"])
                    self.assertEqual(
                        events[0][1]["response"]["error"]["code"], "api_error",
                    )
                    self.assertNotIn("after error", json.dumps(events))

    def test_invalid_utf8_after_response_failed_records_release_open_body(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"] + b": \xff\n\n" + _stream(base[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        captures = _capture_body_probe(request, reply)

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0], 200)
        self.assertTrue(baseline[1].startswith("TimeoutError:"))
        self.assertEqual(baseline[2], "chunked")
        self.assertEqual(captures["Modex"], baseline)
        self.assertEqual(
            [event for event, _ in baseline[3]],
            ["response.output_item.added", "response.output_item.done", "response.failed"],
        )
        failure = baseline[3][-1][1]["response"]["error"]
        self.assertEqual(failure, {
            "code": "invalid_anthropic_stream",
            "message": "content delta type is missing",
        })

    def test_request_half_close_preserves_response_body_after_failure(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"] + b": \xff\n\n" + _stream(base[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        captures = _capture_body_probe(request, reply, half_close_request=True)

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0], 200)
        self.assertTrue(baseline[1].startswith("IncompleteRead:"), repr(captures))
        self.assertEqual(baseline[2], "chunked")
        self.assertEqual(captures["Modex"], baseline)

    def test_parent_eof_cancels_failed_open_stream_with_truncated_pipeline_body(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"] + b": \xff\n\n" + _stream(base[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        observations = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            observations[label] = _observe_parent_shutdown(binary, request, reply, pipeline_body_bytes=1024)
        summary = {
            label: {
                "held": result["held"],
                "parent_returncode": result["parent_returncode"],
                "children_alive_after_2s": result["children_alive_after_2s"],
                "pipelined_records": result["pipelined_records"],
                "body_errors": [row["error"] for row in result["body_errors"]],
            }
            for label, result in observations.items()
        }

        for label in ("0.165.1", "0.439.2"):
            result = observations[label]
            self.assertTrue(result["held"], (label, result))
            self.assertTrue(result["shutdown_sent"], (label, result))
            self.assertFalse(result["parent_timed_out"], (label, result))
            self.assertEqual(result["children_alive_after_2s"], [], (label, result))
            self.assertEqual(
                [(row["bytes"], row["write_open"]) for row in result["pipelined_records"]],
                [(1024, True)],
                (label, result),
            )
            self.assertTrue(result["body_errors"], (label, result))
            self.assertIn(
                b"event: response.failed\r\n",
                bytes.fromhex(result["held_records"][0]["body"]),
            )

        modex = observations["Modex"]
        self.assertTrue(modex["held"], modex)
        self.assertTrue(modex["shutdown_sent"], modex)
        self.assertFalse(modex["parent_timed_out"], modex)
        self.assertEqual(modex["children_alive_after_2s"], [], summary)
        self.assertEqual(
            [(row["bytes"], row["write_open"]) for row in modex["pipelined_records"]],
            [(1024, True)],
            modex,
        )
        self.assertTrue(modex["body_errors"], modex)

    def test_complete_pipeline_body_after_failed_open_stream_leaves_no_children(self):
        request, fixture = repeated_search_case()
        events = [json.loads(line[6:]) for line in fixture["body"].splitlines()
                  if line.startswith(b"data: ")]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(events[:6] + [failed])["body"] + b": \xff\n\n" + _stream(events[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        for label, binary in (
            ("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392), ("Modex", MODEX),
        ):
            with self.subTest(binary=label):
                result = _observe_parent_shutdown(binary, request, reply)
                self.assertTrue(result["held"], (label, result))
                self.assertFalse(result["parent_timed_out"], (label, result))
                self.assertEqual(result["children_alive_after_2s"], [], (label, result))
                self.assertEqual(
                    [(row["bytes"], row["write_open"]) for row in result["pipelined_records"]],
                    [(1048576, True)],
                    (label, result),
                )
                self.assertTrue(result["body_errors"], (label, result))

    def test_parent_eof_with_truncated_pipeline_head_closes_cleanly(self):
        request, fixture = repeated_search_case()
        events = [json.loads(line[6:]) for line in fixture["body"].splitlines()
                  if line.startswith(b"data: ")]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(events[:6] + [failed])["body"] + b": \xff\n\n" + _stream(events[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        for label, binary in (
            ("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392), ("Modex", MODEX),
        ):
            with self.subTest(binary=label):
                result = _observe_parent_shutdown(
                    binary, request, reply, pipeline_body_bytes=0, pipeline_head_bytes=64,
                )
                self.assertTrue(result["held"], (label, result))
                self.assertTrue(result["shutdown_sent"], (label, result))
                self.assertFalse(result["parent_timed_out"], (label, result))
                self.assertEqual(result["children_alive_after_2s"], [], (label, result))
                self.assertEqual(
                    [(row["wire_bytes"], row["write_open"])
                     for row in result["pipelined_records"]],
                    [(64, True)],
                    (label, result),
                )
                self.assertTrue(result["body_errors"], (label, result))

    def test_complete_pipeline_after_failed_open_stream_matches_both_releases(self):
        request, fixture = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        failed_body = (
            _stream(events[:6] + [failed])["body"]
            + b": \xff\n\n"
            + _stream(events[6:])["body"]
        )
        failed_reply = {**fixture, "body": failed_body, "chunked": True}

        for close_mode in ("fin", "rst"):
            observations = {}
            for label, binary in (
                ("0.165.1", ORACLE_01651),
                ("0.439.2", ORACLE_04392),
                ("Modex", MODEX),
            ):
                with self.subTest(close_mode=close_mode, binary=label):
                    posts, responses = _observe_pipelined_disconnect(
                        binary, request, failed_reply, fixture, close_mode,
                        pad_bytes=128, failure_count=1,
                    )
                    self.assertEqual(len(responses), 1, label)
                    capture = responses[0]
                    self.assertEqual(capture["failure_count"], 1, (label, capture))
                    self.assertTrue(
                        all(row["got_failure"] and row["status"] == 200
                            and row["trailing_502"]
                            and row["first_connection"] == "close"
                            for row in capture["failure_results"]),
                        (label, capture["failure_results"]),
                    )
                    self.assertEqual(capture["status"], 200, (label, capture))
                    self.assertIsNone(capture["followup_error"], (label, capture))
                    self.assertEqual(len(posts), 2, (label, posts))
                    paths = tuple(post["path"] for post in posts)
                    self.assertEqual(paths, ("/anthropic/v1/messages",) * 2, label)
                    provider_headers = [
                        {name.lower(): value for name, value in post["headers"].items()}
                        for post in posts
                    ]
                    provider_auth = all(
                        headers.get("x-api-key") == "synthetic-provider-key"
                        and "authorization" not in headers
                        for headers in provider_headers
                    )
                    self.assertTrue(provider_auth, label)
                    observations[label] = (
                        tuple((row["got_failure"], row["status"], row["error"],
                               row["trailing_502"], row["first_connection"])
                              for row in capture["failure_results"]),
                        capture["status"], capture["followup_error"], paths, provider_auth,
                    )
            self.assertEqual(observations["0.165.1"], observations["0.439.2"])
            self.assertEqual(observations["Modex"], observations["0.439.2"])

    def test_pipelined_disconnect_releases_workers_after_failure_for_fin_and_rst(self):
        request, fixture = repeated_search_case()
        events = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        failed_body = (
            _stream(events[:6] + [failed])["body"]
            + b": \xff\n\n"
            + _stream(events[6:])["body"]
        )
        failed_reply = {**fixture, "body": failed_body, "chunked": True}

        for close_mode in ("fin", "rst"):
            observations = {}
            for label, binary in (
                ("0.165.1", ORACLE_01651),
                ("0.439.2", ORACLE_04392),
                ("Modex", MODEX),
            ):
                with self.subTest(close_mode=close_mode, binary=label):
                    posts, responses = _observe_pipelined_disconnect(
                        binary, request, failed_reply, fixture, close_mode,
                    )
                    self.assertEqual(len(responses), 1, label)
                    capture = responses[0]
                    self.assertEqual(capture["close_mode"], close_mode, label)
                    self.assertEqual(capture["failure_count"], 8, (label, capture))
                    self.assertEqual(len(capture["failure_results"]), 8, label)
                    self.assertTrue(
                        all(row["got_failure"] and row["status"] == 200
                            for row in capture["failure_results"]),
                        (label, capture["failure_results"]),
                    )
                    self.assertGreaterEqual(capture["pipelined_bytes"], 32768, label)
                    self.assertEqual(capture["status"], 200, (label, capture))
                    self.assertIsNone(capture["followup_error"], (label, capture))
                    self.assertEqual(len(posts), 9, (label, posts))
                    paths = tuple(post["path"] for post in posts)
                    self.assertEqual(paths, ("/anthropic/v1/messages",) * 9, label)
                    provider_headers = [
                        {name.lower(): value for name, value in post["headers"].items()}
                        for post in posts
                    ]
                    provider_auth = all(
                        headers.get("x-api-key") == "synthetic-provider-key"
                        and "authorization" not in headers
                        for headers in provider_headers
                    )
                    self.assertTrue(provider_auth, label)
                    self.assertGreaterEqual(
                        sum(row["trailing_502"] for row in capture["failure_results"]),
                        6,
                        (label, capture["failure_results"]),
                    )
                    observations[label] = (
                        tuple((row["got_failure"], row["status"], row["error"])
                              for row in capture["failure_results"]),
                        capture["status"], capture["followup_error"], paths, provider_auth,
                    )
            if len(observations) == 3:
                self.assertEqual(observations["0.165.1"], observations["0.439.2"])
                self.assertEqual(observations["Modex"], observations["0.439.2"])

    def test_upstream_eof_after_response_failed_closes_all_bodies(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        reply = {**fixture, "body": _stream(base[:6] + [failed])["body"], "chunked": True}
        captures = _capture_body_probe(request, reply)

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0:3], (200, None, "chunked"))
        self.assertEqual(captures["Modex"], baseline)
        self.assertEqual(
            [event for event, _ in baseline[3]],
            ["response.output_item.added", "response.output_item.done", "response.failed"],
        )

    def test_stalled_upstream_after_response_failed_keeps_body_open(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        reply = {
            **fixture, "body": _stream(base[:6] + [failed])["body"],
            "chunked": True, "hold_open": True,
        }
        captures = _capture_body_probe(request, reply, idle_timeout_ms=100)

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0], 200)
        self.assertTrue(baseline[1].startswith("TimeoutError:"))
        self.assertEqual(baseline[2], "chunked")
        self.assertEqual(captures["Modex"], baseline)

    def test_upstream_reset_after_response_failed_keeps_body_open(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        reply = {
            **fixture, "body": _stream(base[:6] + [failed])["body"],
            "chunked": True, "reset_after_body": True,
        }
        captures = _capture_body_probe(request, reply)

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0], 200)
        self.assertTrue(baseline[1].startswith("TimeoutError:"))
        self.assertEqual(baseline[2], "chunked")
        self.assertEqual(captures["Modex"], baseline)

    def test_downstream_disconnect_releases_open_body_after_failure(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"] + b": \xff\n\n" + _stream(base[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        captures = _capture_body_probe(
            request, reply, disconnect_after_failed=True,
        )

        baseline = captures["0.439.2"]
        self.assertEqual(captures["0.165.1"], baseline)
        self.assertEqual(baseline[0:3], (200, "client_closed_after_failure", "chunked"))
        self.assertEqual(captures["Modex"], baseline)
        self.assertEqual(
            [event for event, _ in baseline[3]],
            ["response.output_item.added", "response.output_item.done", "response.failed"],
        )

    def test_thinking_delta_matches_both_releases_in_and_out_of_order(self):
        message_start = {
            "type": "message_start",
            "message": {"id": "msg_reason", "role": "assistant", "model": "claude-sonnet-4-6"},
        }
        thinking_delta = {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "thinking_delta", "thinking": "considering"},
            "future_event_field": "ignored",
        }
        cases = [
            ("in_order", [
                message_start,
                {"type": "content_block_start", "index": 0,
                 "content_block": {"type": "thinking", "thinking": ""},
                 "future_event_field": "ignored"},
                thinking_delta,
                {"type": "content_block_stop", "index": 0, "future_event_field": "ignored"},
                {"type": "message_stop"},
            ]),
            ("out_of_order", [
                message_start, thinking_delta,
                {"type": "content_block_stop", "index": 0, "future_event_field": "ignored"},
                {"type": "message_stop"},
            ]),
        ]
        overlapping = [message_start]
        for index in range(256):
            overlapping.append({
                "type": "content_block_start", "index": index,
                "content_block": {"type": "thinking", "thinking": ""},
            })
        final_delta = dict(thinking_delta)
        final_delta["index"] = 255
        overlapping.append(final_delta)
        for index in range(256):
            overlapping.append({"type": "content_block_stop", "index": index})
        overlapping.append({"type": "message_stop"})
        cases.append(("many_overlapping_blocks", overlapping))
        overlapping_results = [message_start]
        result_indexes = []
        for index in range(128):
            search_index = index * 2
            result_index = search_index + 1
            search_id = f"search_{index}"
            overlapping_results.extend((
                {"type": "content_block_start", "index": search_index, "content_block": {
                    "type": "server_tool_use", "id": search_id, "name": "web_search",
                    "input": {"query": f"query {index}"},
                }},
                {"type": "content_block_stop", "index": search_index},
                {"type": "content_block_start", "index": result_index, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": search_id, "content": [],
                }},
                {"type": "content_block_delta", "index": result_index,
                 "delta": {"type": "thinking_delta", "thinking": "ignored"}},
            ))
            result_indexes.append(result_index)
        for index in reversed(result_indexes):
            overlapping_results.append({"type": "content_block_stop", "index": index})
        overlapping_results.append({"type": "message_stop"})
        cases.append(("overlapping_search_results", overlapping_results))
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                if name == "overlapping_search_results":
                    self.assertNotIn("response.reasoning_summary_text.delta", [event for event, _ in events])
                    self.assertNotIn("ignored", json.dumps(events))
                else:
                    self.assertIn("response.reasoning_summary_text.delta", [event for event, _ in events])
                    self.assertIn("considering", json.dumps(events))
                self.assertEqual(events[-1][0], "response.completed")

    def test_unmatched_content_block_stops_are_ignored_against_both_releases(self):
        message_start = {
            "type": "message_start",
            "message": {"id": "msg_stop", "role": "assistant", "model": "claude-sonnet-4-6"},
        }
        message_delta = {
            "type": "message_delta", "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        }
        cases = [
            ("orphan_extra_root", {"type": "content_block_stop", "index": 99,
                                    "future_event_field": "ignored"}),
            ("missing_index", {"type": "content_block_stop"}),
            ("nonnumeric_index", {"type": "content_block_stop", "index": "zero"}),
        ]
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [
            _stream([message_start, stop, message_delta, {"type": "message_stop"}])
            for _, stop in cases
        ]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = [
                (post["body"], _normalized_events(bytes.fromhex(response["body"])))
                for post, response in zip(posts, responses)
            ]
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                self.assertEqual(events[-1][0], "response.completed")

    def test_anthropic_search_edge_sequences_match_both_releases(self):
        message_start = {
            "type": "message_start",
            "message": {"id": "msg_search_edges", "role": "assistant", "model": "deepseek-chat",
                        "usage": {"input_tokens": 3, "output_tokens": 0}},
        }

        def search(index, search_id):
            return {"type": "content_block_start", "index": index, "content_block": {
                "type": "server_tool_use", "id": search_id, "name": "web_search",
                "input": {"query": search_id},
            }}

        def search_empty(index, search_id):
            return {"type": "content_block_start", "index": index, "content_block": {
                "type": "server_tool_use", "id": search_id, "name": "web_search", "input": {},
            }}

        def stop(index):
            return {"type": "content_block_stop", "index": index}

        def block(index, kind, **fields):
            return {"type": "content_block_start", "index": index,
                    "content_block": {"type": kind, **fields}}

        def delta(index, kind, **fields):
            return {"type": "content_block_delta", "index": index,
                    "delta": {"type": kind, **fields}}

        message_delta = {
            "type": "message_delta", "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        }
        result = {"type": "content_block_start", "index": 1, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": "s0", "content": [],
        }}
        cases = [
            ("pending_search_sequence", [
                message_start, search(0, "s0"), stop(0), message_delta, {"type": "message_stop"},
            ]),
            ("repeated_result_index_after_stop", [
                message_start, search(0, "s0"), stop(0), result, stop(1), result,
                {"type": "message_stop"},
            ]),
            ("decreasing_search_indexes", [
                message_start, search(4, "s4"), search(2, "s2"),
                {"type": "content_block_delta", "index": 2,
                 "delta": {"type": "thinking_delta", "thinking": "ignored"}},
                stop(2), stop(4), message_delta, {"type": "message_stop"},
            ]),
            ("text_image_index_reuse", [
                message_start, block(0, "text", text=""), delta(0, "text_delta", text="before"),
                block(0, "image", source={"data": "SYNTHETIC_IMAGE_BLOCK_SECRET"}),
                delta(0, "image_delta", data="SYNTHETIC_IMAGE_DELTA_SECRET"), stop(0),
                delta(0, "text_delta", text=" after"), stop(0), message_delta,
                {"type": "message_stop"},
            ]),
            ("tool_image_index_reuse", [
                message_start,
                block(0, "tool_use", id="toolu_reused", name="lookup", input={}),
                block(0, "image", source={"data": "SYNTHETIC_IMAGE_BLOCK_SECRET"}),
                delta(0, "image_delta", data="SYNTHETIC_IMAGE_DELTA_SECRET"), stop(0),
                delta(0, "input_json_delta", partial_json='{"query":"release"}'), stop(0),
                {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
                {"type": "message_stop"},
            ]),
            ("search_image_index_reuse", [
                message_start, search_empty(0, "s-image"),
                block(0, "image", source={"data": "SYNTHETIC_IMAGE_BLOCK_SECRET"}),
                delta(0, "image_delta", data="SYNTHETIC_IMAGE_DELTA_SECRET"), stop(0),
                delta(0, "input_json_delta", partial_json='{"query":"release"}'), stop(0),
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-image", "content": [],
                }}, stop(1), block(2, "text", text=""), delta(2, "text_delta", text="Found it."),
                stop(2), message_delta, {"type": "message_stop"},
            ]),
            ("result_image_index_reuse", [
                message_start, search(0, "s-result"), stop(0),
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-result", "content": [],
                }},
                block(1, "image", source={"data": "SYNTHETIC_IMAGE_BLOCK_SECRET"}),
                delta(1, "image_delta", data="SYNTHETIC_IMAGE_DELTA_SECRET"), stop(1),
                delta(1, "text_delta", text="visible after result stop"), stop(1),
                message_delta, {"type": "message_stop"},
            ]),
            ("duplicate_search_start_index", [
                message_start, search(0, "s-old"), search(0, "s-new"),
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-new", "content": [],
                }}, stop(1), message_delta, {"type": "message_stop"},
            ]),
            ("duplicate_result_start_index", [
                message_start, search(0, "s-repeat"), stop(0),
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-repeat", "content": [],
                }},
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-repeat", "content": [],
                }}, stop(1), delta(1, "text_delta", text="visible after duplicate result stop"),
                message_delta, {"type": "message_stop"},
            ]),
            ("missing_message_start", [
                search_empty(0, "s-no-start"),
                {"type": "content_block_start", "index": 1, "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": "s-no-start", "content": [],
                }}, stop(1), message_delta, {"type": "message_stop"},
            ]),
            ("text_delta_without_start", [
                message_start, delta(7, "text_delta", text="delta without text start"),
                message_delta, {"type": "message_stop"},
            ]),
            ("text_delta_missing_index", [
                message_start, {"type": "content_block_delta",
                                "delta": {"type": "text_delta", "text": "default index"}},
                message_delta, {"type": "message_stop"},
            ]),
            ("input_delta_without_tool_start", [
                message_start, delta(7, "input_json_delta", partial_json="{}"),
                {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
                {"type": "message_stop"},
            ]),
            ("unknown_block_start", [
                message_start,
                {"type": "content_block_start", "index": "bad", "future_event_field": "ignored",
                 "content_block": {"type": "future_block"}},
                delta(7, "text_delta", text="after unknown block"), message_delta,
                {"type": "message_stop"},
            ]),
        ]
        turns = [
            {"model": "deepseek-chat", "input": name, "stream": True,
             "tools": [{"type": "web_search_preview"}]}
            for name, _ in cases
        ]
        replies = [_stream(events) for _, events in cases]
        captures = {}
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            posts, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(posts), len(cases), label)
            self.assertEqual(len(responses), len(cases), label)
            self.assertTrue(all(post["path"] == "/anthropic/v1/messages" for post in posts), label)
            for post in posts:
                headers = {key.lower(): value for key, value in post["headers"].items()}
                self.assertEqual(headers["x-api-key"], "synthetic-provider-key", label)
                self.assertNotIn("authorization", headers, label)
            self.assertTrue(all(response["status"] == 200 for response in responses), label)
            captures[label] = []
            for (name, _), post, response in zip(cases, posts, responses):
                events = _normalized_events(bytes.fromhex(response["body"]))
                if name == "input_delta_without_tool_start":
                    events = _normalize_orphan_fallback_call_id(events)
                captures[label].append((post["body"], events))
        self.assertEqual(captures["0.165.1"], captures["0.439.2"])
        self.assertEqual(captures["Modex"], captures["0.439.2"])
        for (name, _), (_, events) in zip(cases, captures["0.439.2"]):
            with self.subTest(case=name):
                expected_terminal = "response.failed" if name in {
                    "input_delta_without_tool_start",
                } else "response.completed"
                self.assertEqual(events[-1][0], expected_terminal)
                self.assertNotIn("SYNTHETIC_IMAGE_BLOCK_SECRET", json.dumps(events))
                self.assertNotIn("SYNTHETIC_IMAGE_DELTA_SECRET", json.dumps(events))
                if name == "pending_search_sequence":
                    self.assertEqual(
                        [(event, payload["sequence_number"]) for event, payload in events],
                        [
                            ("response.output_item.added", 0),
                            ("response.created", 1),
                            ("response.output_item.done", 2),
                            ("response.completed", 3),
                        ],
                    )
                elif name == "repeated_result_index_after_stop":
                    self.assertEqual([event for event, _ in events].count("response.output_item.done"), 1)
                else:
                    self.assertNotIn(
                        "response.reasoning_summary_text.delta", [event for event, _ in events],
                    )


if __name__ == "__main__":
    unittest.main()
