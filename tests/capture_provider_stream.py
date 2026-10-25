"""Capture frozen Prodex DeepSeek stream behavior against a synthetic loopback upstream."""

import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import textwrap
import uuid


ROOT = Path(__file__).resolve().parents[1]
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    str(Path.home() / ".cache/modex/oracles/0.439.0/prodex-x86_64-unknown-linux-gnu"),
))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
OUT = ROOT / "test-results/provider-stream-oracle"


def sse_frame(value):
    return b"data: " + json.dumps(value, separators=(",", ":")).encode() + b"\n\n"


def chat_chunk(delta, finish_reason=None):
    return {
        "id": "chatcmpl-synthetic",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def seed_frame():
    return sse_frame(chat_chunk({"content": "synthetic hello"}))


def finish_frames(*frames, finish_reason="stop"):
    tail = sse_frame(chat_chunk({}, finish_reason)) if finish_reason else b""
    return seed_frame() + b"".join(frames) + tail + b"data: [DONE]\n\n"


def tool_arguments_case(name, arguments=None, missing_arguments=False):
    function = {"name": "inspect_value"}
    if not missing_arguments:
        function["arguments"] = arguments
    delta = {"tool_calls": [{
        "index": 0,
        "id": "call-" + name,
        "type": "function",
        "function": function,
    }]}
    stream = finish_frames(
        sse_frame(chat_chunk(delta)),
        sse_frame(chat_chunk({}, "tool_calls")),
        finish_reason=None,
    )
    return {"name": name, "upstream": stream}


def sse_events(payload):
    output = []
    for frame in payload.replace(b"\r\n", b"\n").split(b"\n\n"):
        lines = frame.splitlines()
        event = next((line[7:].decode("utf-8", "replace") for line in lines if line.startswith(b"event: ")), None)
        data = [line[6:].decode("utf-8", "replace") for line in lines if line.startswith(b"data: ")]
        if not data:
            continue
        try:
            value = json.loads("\n".join(data))
        except json.JSONDecodeError:
            value = None
        output.append({"event": event, "data": value})
    return output


def fixture_cases():
    seed = seed_frame()
    done = sse_frame(chat_chunk({}, "stop")) + b"data: [DONE]\n\n"
    large_exponent_tool = [{
        "index": 0, "id": "call-exp", "type": "function",
        "function": {"name": "check_scalar", "arguments": "1e999"},
    }]
    invalid_tool = [{
        "index": 0, "id": "call-invalid", "type": "function",
        "function": {"name": "lookup", "arguments": "{not-json"},
    }]
    missing_function_tool = [{"index": 0, "id": "call-missing", "type": "function"}]
    return [
        {"name": "text_done", "upstream": finish_frames()},
        {"name": "text_eof", "upstream": seed},
        {"name": "reasoning_delta", "upstream": finish_frames(sse_frame(chat_chunk({"reasoning_content": "synthetic reasoning"})))},
        {"name": "interleaved_tools", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [
                {"index": 0, "id": "call-lookup", "type": "function", "function": {"name": "lookup", "arguments": "{\"query\":"}},
            ]})),
            sse_frame(chat_chunk({"tool_calls": [
                {"index": 1, "id": "call-format", "type": "function", "function": {"name": "format_text", "arguments": "{\"text\":"}},
            ]})),
            sse_frame(chat_chunk({"tool_calls": [
                {"index": 0, "function": {"arguments": "\"synthetic\"}"}},
            ]})),
            sse_frame(chat_chunk({"tool_calls": [
                {"index": 1, "function": {"arguments": "\"hello\"}"}},
            ]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        tool_arguments_case("argument_missing", missing_arguments=True),
        tool_arguments_case("argument_empty", ""),
        tool_arguments_case("argument_unicode_whitespace", "\u2003"),
        tool_arguments_case("argument_whitespace_around_object", "\u2003{}\u2003"),
        tool_arguments_case("argument_max_f64", "1.7976931348623157e308"),
        tool_arguments_case("argument_over_f64", "1.7976931348623158e308"),
        tool_arguments_case("argument_over_f64_long_tail", "1.797693134862315799999e308"),
        tool_arguments_case("argument_zero_large_exponent", "0e999999"),
        {"name": "argument_large_exponent", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": large_exponent_tool})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "invalid_json_tool_arguments", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": invalid_tool})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "missing_new_function_object", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": missing_function_tool})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "embedded_error_after_seed", "upstream": seed + sse_frame({"error": {"code": "synthetic_error", "message": "fixture failure"}}) + b"data: [DONE]\n\n"},
        {"name": "invalid_utf8_after_seed", "upstream": seed + b"data: \xff\n\n" + done},
        {"name": "fragmented_json_data_lines", "upstream": seed + (
            lambda value: b"data: " + value[:value.index(b'\"choices\":') + len(b'\"choices\":[')]
            + b"\ndata: " + value[value.index(b'\"choices\":') + len(b'\"choices\":['):] + b"\n\n"
        )(json.dumps(chat_chunk({"content": "fragmented json"}), separators=(",", ":")).encode()) + sse_frame(chat_chunk({}, "stop")) + done},
        {"name": "apply_patch_tool", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-patch", "type": "function",
                "function": {"name": "apply_patch", "arguments": "{\"input\":\"synthetic patch\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "tool_search_tool", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-search", "type": "function",
                "function": {"name": "tool_search", "arguments": "{\"query\":\"synthetic\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "missing_call_id_multichunk", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "function": {"name": "shell", "arguments": "{\"cmd\":"},
            }]})),
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "function": {"arguments": "\"cargo test -q\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "tool_search_scalar_arguments", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-search-scalar", "type": "function",
                "function": {"name": "tool_search", "arguments": "\"needle\""},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "tool_search_array_arguments", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-search-array", "type": "function",
                "function": {"name": "tool_search", "arguments": "[\"one\",\"two\"]"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        *[{
            "name": "function_namespace_" + suffix,
            "upstream": finish_frames(
                sse_frame(chat_chunk({"tool_calls": [{
                    "index": 0, "id": "call-namespace-" + suffix, "type": "function",
                    "function": {"name": source, "arguments": "{\"value\":1}"},
                }]})),
                sse_frame(chat_chunk({}, "tool_calls")),
                finish_reason=None,
            ),
        } for suffix, source in [
            ("double_underscore", "functions__lookup"),
            ("dot", "functions.lookup"),
            ("slash", "functions/lookup"),
            ("api_v1_slash", "api.v1/lookup"),
        ]],
        {"name": "shell_rtk_arguments", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-shell-rtk", "type": "function",
                "function": {"name": "shell", "arguments": "{\"cmd\":\"cargo test -q login\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "exec_arguments", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-exec", "type": "function",
                "function": {"name": "exec", "arguments": "{\"cmd\":\"pwd\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "apply_patch_multiline_path_content", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-patch-multiline", "type": "function",
                "function": {"name": "apply_patch", "arguments": "{\"input\":\"*** Begin Patch\\n*** Add File: nested/note.txt\\n"},
            }]})),
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "function": {"arguments": "+first line\\n+second line\\n*** End Patch\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")),
            finish_reason=None,
        )},
        {"name": "apply_patch_json_empty_new", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-patch-json", "type": "function",
                "function": {"name": "apply_patch", "arguments": "{\"path\":\"note.txt\",\"old\":\"old\",\"new\":\"\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")), finish_reason=None,
        )},
        {"name": "apply_patch_leading_whitespace_crlf", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-patch-crlf", "type": "function",
                "function": {"name": "apply_patch", "arguments": "{\"input\":\"  *** Begin Patch\\r\\n*** Add File: note.txt\\r\\nhello\\r\\n*** End Patch\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")), finish_reason=None,
        )},
        {"name": "apply_patch_whitespace_file_path", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-patch-space", "type": "function",
                "function": {"name": "apply_patch", "arguments": "{\"input\":\"*** Begin Patch\\n*** Update File:    \\n\\n*** End Patch\\n\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")), finish_reason=None,
        )},
        {"name": "namespaced_server_trailing_space", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-server-space", "type": "function",
                "function": {"name": "server-- ", "arguments": "{\"cmd\":\"pwd\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")), finish_reason=None,
        )},
        {"name": "namespaced_mcp_double_underscore", "upstream": finish_frames(
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-mcp-ns", "type": "function",
                "function": {"name": "mcp__org__lookup", "arguments": "{\"query\":\"synthetic\"}"},
            }]})),
            sse_frame(chat_chunk({}, "tool_calls")), finish_reason=None,
        )},
        {"name": "late_metadata_usage", "upstream": seed +
            sse_frame(chat_chunk({"reasoning_content": "late synthetic reasoning"})) +
            sse_frame({
                "id": "chatcmpl-synthetic", "object": "chat.completion.chunk",
                "created": 1700000000, "model": "deepseek-chat", "choices": [],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }) +
            sse_frame(chat_chunk({}, "stop")) + b"data: [DONE]\n\n"},
        {"name": "choices_null_after_seed", "upstream": seed +
            sse_frame({"id": "chatcmpl-synthetic", "choices": None}) + b"data: [DONE]\n\n"},
        {"name": "choice_nonobject_after_seed", "upstream": seed +
            sse_frame({"id": "chatcmpl-synthetic", "choices": [7]}) + b"data: [DONE]\n\n"},
        {"name": "tool_nonobject_after_seed", "upstream": seed +
            sse_frame(chat_chunk({"tool_calls": [None]})) +
            sse_frame(chat_chunk({}, "tool_calls")) + b"data: [DONE]\n\n"},
        {"name": "failed_then_repeated_tool_finish", "upstream": seed +
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 0, "id": "call-bad", "type": "function",
                "function": {"name": "lookup", "arguments": "{bad"},
            }]})) +
            sse_frame(chat_chunk({"tool_calls": [{
                "index": 1, "id": "call-after-fail", "type": "function",
                "function": {"name": "lookup", "arguments": "{}"},
            }]})) +
            sse_frame(chat_chunk({}, "tool_calls")) +
            sse_frame(chat_chunk({}, "tool_calls")) + b"data: [DONE]\n\n"},
        {"name": "unfinished_json_done", "upstream": seed +
            b'data: {"id":"chatcmpl-synthetic","choices":[\n\ndata: [DONE]\n\n'},
        {"name": "unfinished_json_eof", "upstream": seed +
            b'data: {"id":"chatcmpl-synthetic","choices":[\n'},
    ]


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        case = self.server.cases[self.server.next_case]
        self.server.next_case += 1
        self.server.requests.append({
            "destination": f"127.0.0.1:{self.server.server_port}",
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            "body": body.decode("utf-8", "replace"),
            "case": case["name"],
        })
        payload = case["upstream"]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        # Split writes exercise real streaming reads while preserving one fixture transcript.
        for offset in range(0, len(payload), 37):
            self.wfile.write(payload[offset:offset + 37])
            self.wfile.flush()
        self.close_connection = True

    def log_message(self, *_args):
        pass


def fake_codex_executable(path):
    path.write_text(textwrap.dedent("""\
        #!__PYTHON__
        import http.client
        import json
        import os
        import sys
        from urllib.parse import urlsplit

        args = sys.argv[1:]
        if args == ["--version"]:
            print("codex-cli 0.153.2")
            raise SystemExit(0)
        if args == ["app-server", "--help"]:
            print("Codex app-server")
            raise SystemExit(0)
        base = None
        for index, arg in enumerate(args[:-1]):
            if arg == "-c":
                value = args[index + 1].strip('"')
                prefix = "model_providers.prodex-deepseek.base_url="
                if value.startswith(prefix):
                    base = value[len(prefix):].strip('"')
        if base is None:
            raise SystemExit("missing generated local provider base URL")
        target = urlsplit(base.rstrip("/") + "/responses")
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=20)
        body = json.dumps({
            "model": "deepseek-chat",
            "input": "return the fixed synthetic greeting",
            "stream": True,
        }, separators=(",", ":")).encode()
        connection.request("POST", target.path, body, {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": "Bearer synthetic-codex-key",
            "Connection": "close",
        })
        response = connection.getresponse()
        payload = response.read()
        capture = os.environ["PRODEX_CAPTURE_PATH"]
        with open(capture, "wb") as output:
            output.write(payload)
        with open(capture + ".json", "w", encoding="utf-8") as output:
            json.dump({"status": response.status, "headers": dict(response.getheaders()), "args": args}, output)
        connection.close()
        if response.status >= 400:
            raise SystemExit("local Codex request returned HTTP " + str(response.status))
    """).replace("#!__PYTHON__", "#!" + __import__("sys").executable))
    path.chmod(0o700)


def run_case(oracle, environment, scratch, case, upstream):
    capture = OUT / f"{case['name']}.oracle.sse"
    capture.unlink(missing_ok=True)
    case_environment = dict(environment)
    case_environment["PRODEX_CAPTURE_PATH"] = str(capture)
    command = [
        str(oracle), "super", "--provider", "deepseek", "--api-key", "synthetic-provider-key",
        "--base-url", f"http://127.0.0.1:{upstream.server_port}/v1",
        "--skip-quota-check", "--no-presidio", "--model", "deepseek-chat",
        "exec", "--", "synthetic fixture request",
    ]
    result = subprocess.run(command, cwd=scratch, env=case_environment, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30, check=False)
    if not capture.is_file():
        return {"status": None, "headers": {}, "body": b"", "super_returncode": result.returncode,
                "super_stderr": result.stderr.decode("utf-8", "replace"),
                "capture_error": "oracle Super exited before the synthetic Codex HTTP capture"}
    metadata = json.loads(Path(str(capture) + ".json").read_text())
    return {"status": metadata["status"], "headers": metadata["headers"], "body": capture.read_bytes(),
            "super_returncode": result.returncode, "super_stderr": result.stderr.decode("utf-8", "replace")}


def oracle_request_id(payload):
    for frame in payload.replace(b"\r\n", b"\n").split(b"\n\n"):
        data = next((line[6:] for line in frame.splitlines() if line.startswith(b"data: ")), None)
        if data is None:
            continue
        try:
            item = json.loads(data).get("item", {})
        except json.JSONDecodeError:
            continue
        item_id = item.get("id", "")
        if item_id.startswith("msg_deepseek_"):
            return int(item_id[len("msg_deepseek_"):])
    raise RuntimeError("oracle SSE did not include a DeepSeek text item id")


def compare_sse_bytes(expected, actual, allow_uuid7_nondeterminism=False):
    raw_equal = expected == actual
    first_diff = next((index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]), None)
    if first_diff is None and not raw_equal:
        first_diff = min(len(expected), len(actual))
    normalized_equal = False
    reason = None
    if not raw_equal and allow_uuid7_nondeterminism:
        def values(payload):
            return re.findall(rb'"call_id":"call_deepseek_([^"\\]+)"', payload)

        expected_ids = values(expected)
        actual_ids = values(actual)
        try:
            def canonical_uuid7(value):
                decoded = value.decode()
                parsed = uuid.UUID(decoded)
                return parsed.version == 7 and str(parsed) == decoded

            valid_ids = all(
                found and len(set(found)) == 1
                and all(canonical_uuid7(value) for value in found)
                for found in (expected_ids, actual_ids)
            )
        except ValueError:
            valid_ids = False
        if len(expected_ids) != len(actual_ids) or not valid_ids:
            reason = "fallback call IDs were not consistently UUIDv7 in both streams"
        else:
            pattern = re.compile(rb'"call_id":"call_deepseek_[^"\\]+"')
            left = pattern.sub(b'"call_id":"call_deepseek_<uuid7>"', expected)
            right = pattern.sub(b'"call_id":"call_deepseek_<uuid7>"', actual)
            normalized_equal = left == right
            if not normalized_equal:
                reason = "stream bytes differ outside the proven UUIDv7 call ID field"
    return {
        "raw_matches_oracle_bytes": raw_equal,
        "uuid7_normalized_match": normalized_equal,
        "matches_oracle_bytes": raw_equal or normalized_equal,
        "comparison": "exact" if raw_equal else "uuid7_normalized" if normalized_equal else "different",
        "first_different_byte": first_diff,
        "comparison_note": reason,
    }


def run_native_driver(driver, case, baseline, allow_uuid7_nondeterminism=False):
    request_id = oracle_request_id(baseline)
    header = json.dumps({
        "request_id": request_id,
        "response_id": f"resp_deepseek_{request_id}",
        "created_at": 0,
        "metadata": None,
    }, separators=(",", ":"))
    transcript = (header + "\n" + case["upstream"].hex() + "\n").encode()
    result = subprocess.run([str(driver)], input=transcript, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=10, check=False)
    native = result.stdout
    (OUT / f"{case['name']}.native.sse").write_bytes(native)
    comparison = compare_sse_bytes(baseline, native, allow_uuid7_nondeterminism)
    return {
        "native_response_sha256": hashlib.sha256(native).hexdigest(),
        "native_response_bytes": len(native),
        **comparison,
        "matches_oracle_bytes": comparison["matches_oracle_bytes"] and result.returncode == 0,
        "driver_returncode": result.returncode,
        "driver_stderr": result.stderr.decode("utf-8", "replace"),
    }


def main():
    if not ORACLE.is_file():
        raise SystemExit(f"missing pinned oracle: {ORACLE}")
    digest = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
    if digest != ORACLE_SHA256:
        raise SystemExit(f"pinned oracle checksum mismatch: {digest}")

    cases = fixture_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="provider-stream-oracle-") as scratch:
        scratch = Path(scratch)
        home = scratch / "home"
        home.mkdir(mode=0o700)
        os.chmod(home, 0o700)
        prodex_home = scratch / "prodex-state"
        shared_codex = scratch / "shared-codex"
        prodex_home.mkdir(mode=0o700)
        shared_codex.mkdir(mode=0o700)
        fake_codex = scratch / "codex-client"
        fake_codex_executable(fake_codex)
        log_dir = scratch / "runtime-logs"
        log_dir.mkdir()
        environment = {
            "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1",
            "PRODEX_HOME": str(prodex_home), "PRODEX_SHARED_CODEX_HOME": str(shared_codex),
            "PRODEX_CODEX_BIN": str(fake_codex), "PRODEX_RUNTIME_LOG_RECORD": "1",
            "PRODEX_RUNTIME_LOG_DIR": str(log_dir),
        }

        upstream = HTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream.cases = cases
        upstream.next_case = 0
        upstream.requests = []
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        results = {}
        try:
            for case in cases:
                results[case["name"]] = run_case(ORACLE, environment, scratch, case, upstream)
                if results[case["name"]]["status"] not in (None, 200):
                    raise RuntimeError(f"oracle stream returned HTTP {results[case['name']]['status']}")
            if {request["case"] for request in upstream.requests} != {case["name"] for case in cases}:
                raise RuntimeError("not every case reached the synthetic loopback upstream")
            if any(request["authorization"] != "Bearer synthetic-provider-key" for request in upstream.requests):
                raise RuntimeError("upstream received an unexpected authorization header")
            if any(request["path"] != "/v1/chat/completions" for request in upstream.requests):
                raise RuntimeError("DeepSeek adapter used an unexpected upstream path")
            if b"event: response.completed" not in results["text_done"]["body"]:
                raise RuntimeError("[DONE] fixture did not produce response.completed")
            eof_body = results["text_eof"]["body"]
            if b"event: response.failed" not in eof_body or b'"code":"provider_stream_error"' not in eof_body or b'"message":"unexpected end of stream"' not in eof_body:
                raise RuntimeError("EOF fixture did not produce the expected provider stream failure")
            driver = ROOT / "build/tests/provider_chat_stream_driver"
            catalog = json.loads((ROOT / "tests/fixtures/provider-stream/cases.json").read_text())
            catalog_cases = {item["name"]: item for item in catalog["cases"]}
            comparisons = {}
            if driver.is_file():
                for case in cases:
                    result = results[case["name"]]
                    if result["status"] is None:
                        comparisons[case["name"]] = {
                            "comparison": "oracle_capture_failed", "matches_oracle_bytes": False,
                            "raw_matches_oracle_bytes": False, "uuid7_normalized_match": False,
                            "first_different_byte": None, "comparison_note": result["capture_error"],
                        }
                    else:
                        comparisons[case["name"]] = run_native_driver(
                            driver, case, result["body"],
                            "observed_uuid7_samples" in catalog_cases.get(case["name"], {}),
                        )
            manifest = {
                "oracle_sha256": digest,
                "oracle_version": "0.439.0",
                "provider": "deepseek",
                "upstream": "synthetic loopback HTTP server",
                "observed_upstream_destinations": "loopback only",
                "host_network_access": "available; child processes are not firewall-isolated",
                "runtime_claim": "isolated HOME/config/environment; not a clean-runtime parity claim",
                "launch": "checksum-verified Prodex Super DeepSeek adapter with a synthetic Codex HTTP client",
                "super_child_note": "synthetic client completes the HTTP capture; Super exits 1 because the client does not implement the app-server protocol",
                "upstream_requests": upstream.requests,
                "native_driver_comparison": comparisons if comparisons else "driver binary unavailable at capture time",
                "cases": {},
            }
            for name, result in results.items():
                (OUT / f"{name}.upstream.sse").write_bytes(next(c["upstream"] for c in cases if c["name"] == name))
                (OUT / f"{name}.oracle.sse").write_bytes(result["body"])
                if result.get("capture_error"):
                    (OUT / f"{name}.oracle.error.log").write_text(result["super_stderr"])
                manifest["cases"][name] = {
                    "status": result["status"],
                    "headers": result["headers"],
                    "oracle_response_sha256": hashlib.sha256(result["body"]).hexdigest(),
                    "oracle_response_bytes": len(result["body"]),
                    "synthetic_codex_process_returncode": result["super_returncode"],
                    "error_body": result["body"].decode("utf-8", "replace") if result["status"] is not None and result["status"] >= 400 else None,
                    "oracle_events": [event["event"] for event in sse_events(result["body"])],
                    "oracle_errors": [
                        event["data"]["response"]["error"]
                        for event in sse_events(result["body"])
                        if isinstance(event["data"], dict)
                        and isinstance(event["data"].get("response"), dict)
                        and isinstance(event["data"]["response"].get("error"), dict)
                    ],
                    "capture_error": result.get("capture_error"),
                    "oracle_stderr": result["super_stderr"] if result.get("capture_error") else None,
                }
            for path in log_dir.glob("*.log"):
                destination = OUT / "runtime-logs" / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(path.read_bytes())
            (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"captured verified Prodex {digest} to {OUT}")
            for name, result in results.items():
                if result["status"] is None:
                    print(f"{name}: no oracle SSE ({result['capture_error']})")
                else:
                    print(f"{name}: HTTP {result['status']}, {len(result['body'])} response bytes")
            if comparisons:
                mismatches = []
                for name, result in comparisons.items():
                    status = {
                        "exact": "EXACT MATCH",
                        "uuid7_normalized": "UUIDv7-NORMALIZED MATCH",
                        "different": "FAIL",
                        "oracle_capture_failed": "NO ORACLE SSE",
                    }[result["comparison"]]
                    offset = result["first_different_byte"]
                    print(f"{name}: native comparison {status}" + (f" at byte {offset}" if offset is not None else ""))
                    if result["comparison_note"]:
                        print(f"  {result['comparison_note']}")
                    if not result["matches_oracle_bytes"]:
                        mismatches.append(name)
            else:
                mismatches = []
                print("native driver not built; recorded oracle/upstream bytes for later comparison")
            if mismatches:
                print("native comparison mismatches: " + ", ".join(mismatches))
                raise SystemExit(1)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=2)


if __name__ == "__main__":
    main()
