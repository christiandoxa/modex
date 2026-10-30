"""Capture buffered DeepSeek responses through frozen Prodex with synthetic loopback data."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading

ROOT = Path(__file__).resolve().parents[1]
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    str(Path.home() / ".cache/modex/oracles/0.439.0/prodex-x86_64-unknown-linux-gnu"),
))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
FIXTURE = ROOT / "tests/fixtures/provider-buffered/cases.json"
OUT = ROOT / "test-results/provider-buffered-oracle"

REQUEST = {
    "model": "deepseek-chat",
    "input": "buffered synthetic response",
    "metadata": {"trace": "synthetic"},
}
CASES = [
    {
        "name": "text_tool_usage_metadata",
        "upstream_status": 200,
        "upstream_body": {
            "id": "chatcmpl_buffered_1",
            "model": "deepseek-chat",
            "created": 1700000000,
            "choices": [{
                "message": {
                    "content": "こんにちは 🌋",
                    "reasoning_content": "考えています",
                    "refusal": "拒否",
                    "annotations": [{"type": "citation", "url": "https://example.invalid/source"}],
                    "tool_calls": [{
                        "id": "call_東京",
                        "function": {
                            "name": "functions.検索",
                            "arguments": "{\"query\":\"café 🍜\"}",
                        },
                    }],
                },
                "finish_reason": "tool_calls",
                "logprobs": {"tokens": ["ok"]},
            }],
            "system_fingerprint": "fp_buffered_1",
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
                "prompt_cache_hit_tokens": 5,
                "prompt_cache_miss_tokens": 6,
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
        },
    },
    {
        "name": "malformed_tool_arguments",
        "upstream_status": 200,
        "upstream_body": {
            "id": "chatcmpl_buffered_bad_tool",
            "model": "deepseek-chat",
            "created": 1700000001,
            "choices": [{
                "message": {
                    "content": "before error",
                    "tool_calls": [{
                        "id": "call_bad",
                        "function": {"name": "lookup", "arguments": "{bad"},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        },
    },
]


def tool_response_case(name, function_name, arguments, call_id="call_buffered", response_id=None):
    tool_call = {"function": {"name": function_name, "arguments": arguments}}
    if call_id is not None:
        tool_call["id"] = call_id
    return {
        "name": name,
        "upstream_status": 200,
        "upstream_body": {
            "id": response_id or "chatcmpl_" + name,
            "model": "deepseek-chat",
            "created": 1700000000,
            "choices": [{
                "message": {"content": "", "tool_calls": [tool_call]},
                "finish_reason": "tool_calls",
            }],
        },
    }


CASES.extend([
    {
        "name": "blank_provider_metadata",
        "upstream_status": 200,
        "upstream_body": {
            "id": "chatcmpl_blank_metadata",
            "model": "deepseek-chat",
            "created": 1700000002,
            "choices": [{
                "message": {
                    "content": "blank provider metadata",
                    "reasoning_content": "",
                    "annotations": [],
                },
                "finish_reason": None,
            }],
            "system_fingerprint": "",
        },
    },
    tool_response_case("standalone_name_trim", "  lookup  ", "{}"),
    tool_response_case("spaced_namespace_trim", " functions . lookup ", "{}"),
    tool_response_case(
        "shell_command_only", "functions.exec_command",
        '{"command":"cargo test"}',
    ),
    tool_response_case(
        "shell_cmd_rewrite", "functions.exec_command",
        '{"cmd":"cargo test"}',
    ),
    tool_response_case("wrong_type_arguments", "lookup", 7),
    tool_response_case("malformed_nested_trailing_comma", "lookup", '{"x":[1,]}'),
    tool_response_case("malformed_nested_eof", "lookup", '{"x":'),
    tool_response_case("malformed_nested_unicode", "lookup", '{\n"é": 1,\n"x":truX}'),
    tool_response_case("structural_invalid_literal", "lookup", "truX"),
    tool_response_case("tool_search_invalid_literal", "tool_search", "truX"),
    tool_response_case("empty_tool_search_whitespace", "tool_search", "   "),
    tool_response_case(
        "apply_patch_raw", "apply_patch",
        '{"patch":"*** Begin Patch\\n*** End Patch"}',
    ),
    tool_response_case(
        "missing_tool_call_id_sample_a", "lookup", "{}", call_id=None,
        response_id="chatcmpl_missing_tool_call_id",
    ),
    tool_response_case(
        "missing_tool_call_id_sample_b", "lookup", "{}", call_id=None,
        response_id="chatcmpl_missing_tool_call_id",
    ),
])


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, status, body):
        self.status = status
        self.body = body
        self.records = []
        super().__init__(("127.0.0.1", 0), UpstreamHandler)


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.records.append({
            "method": self.command,
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            "body": body.decode("utf-8", "replace"),
        })
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.server.body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(self.server.body)

    def log_message(self, *_args):
        pass


def fake_codex(path):
    path.write_text(textwrap.dedent("""\
        #!__PYTHON__
        import http.client, json, os, sys
        from pathlib import Path
        from urllib.parse import urlsplit
        args = sys.argv[1:]
        if args == ["--version"]: print("codex-cli 0.153.2"); raise SystemExit(0)
        if args == ["app-server", "--help"]: print("Codex app-server"); raise SystemExit(0)
        base = None
        for i, arg in enumerate(args[:-1]):
            if arg == "-c" and args[i + 1].startswith("model_providers.prodex-deepseek.base_url="):
                base = args[i + 1].split("=", 1)[1].strip('"')
        if not base: raise SystemExit("missing local provider URL")
        target = urlsplit(base.rstrip("/") + "/responses")
        token = json.loads((Path(os.environ["CODEX_HOME"]) / "auth.json").read_text(encoding="utf-8"))["OPENAI_API_KEY"]
        body = open(os.environ["PRODEX_REQUEST_PATH"], "rb").read()
        conn = http.client.HTTPConnection(target.hostname, target.port, timeout=20)
        conn.request("POST", target.path, body, {"Content-Type":"application/json", "Accept":"application/json", "Authorization":"Bearer " + token, "Connection":"close"})
        response = conn.getresponse(); payload = response.read()
        open(os.environ["PRODEX_CAPTURE_PATH"], "wb").write(payload)
        open(os.environ["PRODEX_CAPTURE_PATH"] + ".json", "w").write(__import__("json").dumps({"status":response.status,"content_type":response.getheader("Content-Type")}))
        conn.close()
    """).replace("#!__PYTHON__", "#!" + sys.executable))
    path.chmod(0o700)


def capture(case, scratch):
    root = scratch / case["name"]
    root.mkdir(mode=0o700)
    home = root / "home"
    home.mkdir(mode=0o700)
    prodex_home = root / "prodex"
    prodex_home.mkdir(mode=0o700)
    shared = root / "shared-codex"
    shared.mkdir(mode=0o700)
    codex = root / "codex"
    fake_codex(codex)
    request_path = root / "request.json"
    request = case.get("request", REQUEST)
    request_path.write_text(json.dumps(request, separators=(",", ":")), encoding="utf-8")
    out = OUT / (case["name"] + ".response")
    out.unlink(missing_ok=True)
    Path(str(out) + ".json").unlink(missing_ok=True)
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
        "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "TMPDIR": str(root), "PRODEX_HOME": str(prodex_home),
        "PRODEX_SHARED_CODEX_HOME": str(shared), "PRODEX_CODEX_BIN": str(codex),
        "PRODEX_REQUEST_PATH": str(request_path), "PRODEX_CAPTURE_PATH": str(out),
    }
    response_body = json.dumps(case["upstream_body"], separators=(",", ":")).encode()
    server = Upstream(case["upstream_status"], response_body)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = [
            str(ORACLE), "super", "--provider", "deepseek", "--api-key",
            "synthetic-provider-key", "--base-url",
            f"http://127.0.0.1:{server.server_port}/v1", "--skip-quota-check",
            "--no-presidio", "--model", "deepseek-chat", "exec", "--",
            "synthetic buffered fixture request",
        ]
        run = subprocess.run(
            command, cwd=root, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=False,
        )
        upstream_requests = server.records[:]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    if len(upstream_requests) != 1:
        raise RuntimeError(f"{case['name']}: oracle made {len(upstream_requests)} upstream requests")
    if not out.is_file() or not Path(str(out) + ".json").is_file():
        raise RuntimeError(f"{case['name']}: oracle did not return a buffered local response")
    local_body = out.read_bytes()
    local_meta = json.loads(Path(str(out) + ".json").read_text(encoding="utf-8"))
    observed = dict(upstream_requests[0])
    observed["destination"] = "127.0.0.1:<ephemeral>"
    observed["body_sha256"] = hashlib.sha256(observed["body"].encode()).hexdigest()
    return {
        "name": case["name"],
        "request": request,
        "upstream_request": observed,
        "upstream_response": {
            "status": case["upstream_status"],
            "content_type": "application/json",
            "body": response_body.decode(),
            "sha256": hashlib.sha256(response_body).hexdigest(),
        },
        "oracle_super_returncode": run.returncode,
        "oracle_stderr": run.stderr.decode("utf-8", "replace"),
        "oracle_response": {
            "status": local_meta["status"],
            "content_type": local_meta["content_type"],
            "body": local_body.decode("utf-8", "replace"),
            "sha256": hashlib.sha256(local_body).hexdigest(),
        },
    }


def main():
    if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("missing or checksum-mismatched pinned Prodex oracle: " + str(ORACLE))
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="provider-buffered-oracle-") as directory:
        scratch = Path(directory)
        for case in CASES:
            result = capture(case, scratch)
            cases.append(result)
            print(f"{case['name']}: captured HTTP {result['oracle_response']['status']} ({len(result['oracle_response']['body'])} response bytes)")
    catalog = {
        "schema_version": 1,
        "baseline_commit": "433aad44bb249d5c25a231a6b06c2fa522a39a1f",
        "oracle_version": "0.439.0",
        "oracle_sha256": ORACLE_SHA256,
        "capture_harness": "tests/capture_provider_buffered.py",
        "scope": "Actual buffered JSON response dispatch through the frozen DeepSeek adapter with synthetic loopback chat completions.",
        "runtime_claim": "Each case uses isolated HOME, Prodex/Codex storage, request files, environment and an ephemeral 127.0.0.1 upstream. The fake Codex client captures the local response; its incomplete app-server can leave the outer Super command nonzero.",
        "cases": cases,
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
