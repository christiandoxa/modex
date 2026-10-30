"""Capture frozen Prodex DeepSeek request translation with synthetic loopback traffic."""

import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import textwrap

ROOT = Path(__file__).resolve().parents[1]
ORACLE = Path(os.environ.get("PRODEX_ORACLE", str(Path.home() / ".cache/modex/oracles/0.439.0/prodex-x86_64-unknown-linux-gnu")))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
FIXTURES = ROOT / "tests/fixtures/provider-requests"
OUT = ROOT / "test-results/provider-request-oracle"

CASES = [
    {"name": "defaults", "request": {"model": "deepseek-chat", "input": "synthetic hello", "stream": False}},
    {"name": "reasoning", "request": {"model": "deepseek-reasoner", "input": "synthetic reasoning request", "stream": False}},
    {"name": "reasoning_high_effort", "request": {"model": "deepseek-reasoner", "input": "synthetic reasoning request", "reasoning": {"effort": "high"}, "max_output_tokens": 512}},
    {"name": "reasoning_medium_effort", "request": {"model": "deepseek-reasoner", "input": "synthetic reasoning request", "reasoning": {"effort": "medium"}}},
    {"name": "json_object", "request": {"model": "deepseek-chat", "input": "return JSON", "response_format": {"type": "json_object"}}},
    {"name": "json_schema", "request": {"model": "deepseek-chat", "input": "return structured data", "response_format": {"type": "json_schema", "name": "item", "strict": True, "schema": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}}}, "expected_response_metadata": {"deepseek": {"degraded_response_format": {"from": "json_schema", "reason": "DeepSeek response_format supports json_object but not native JSON Schema enforcement", "to": "json_object"}}}},
    {"name": "text_format_json_schema", "request": {"model": "deepseek-chat", "input": "return structured data", "text": {"format": {"type": "json_schema", "name": "item", "strict": True, "schema": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}}}}, "expected_response_metadata": {"deepseek": {"degraded_response_format": {"from": "json_schema", "reason": "DeepSeek response_format supports json_object but not native JSON Schema enforcement", "to": "json_object"}}}},
    {"name": "metadata", "request": {"model": "deepseek-chat", "input": "metadata", "metadata": {"trace": "synthetic"}, "temperature": 0.2, "top_p": 0.8, "max_output_tokens": 64}, "expected_response_metadata": {"trace": "synthetic"}},
    {"name": "metadata_reserved_key", "request": {"model": "deepseek-chat", "input": "metadata", "metadata": {"trace": "synthetic", "deepseek": {"client": "synthetic"}}}, "expected_response_metadata": {"trace": "synthetic", "deepseek": {"client": "synthetic"}}},
    {"name": "numeric_defaults", "request": {"model": "deepseek-chat", "input": "numeric", "temperature": 0, "top_p": 1, "max_output_tokens": 0}},
    {"name": "numeric_bounds", "request": {"model": "deepseek-chat", "input": "numeric", "temperature": 2, "top_p": 0, "max_output_tokens": 8192}},
    {"name": "message_history", "request": {"model": "deepseek-chat", "input": [{"role": "system", "content": "synthetic system"}, {"role": "user", "content": [{"type": "input_text", "text": "hello"}]}, {"role": "assistant", "content": [{"type": "output_text", "text": "hi"}]}, {"role": "user", "content": "continue"}]}},
    {"name": "tools", "request": {"model": "deepseek-chat", "input": "use tool", "tools": [{"type": "function", "name": "lookup", "description": "Look up synthetic data", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}], "tool_choice": "auto"}},
    {"name": "mcp_configs_selection", "request": {"model": "deepseek-chat", "input": "x", "tools": [{"type": "mcp", "server_label": "git tools", "configs": {"status": {"enabled": True}, "push": {"enabled": False}}}]}},
    {"name": "mcp_allowed_tools_strict", "request": {"model": "deepseek-chat", "input": "x", "tools": [{"type": "mcp", "server_label": "git tools", "allowed_tools": ["run"]}]}, "strict_tools": True},
    {"name": "mcp_function_schema", "request": {"model": "deepseek-chat", "input": "x", "tools": [{"type": "mcp_function", "name": "lookup", "input_schema": {"type": "object"}}]}},
    {"name": "mcp_toolset_multi_emission", "request": {"model": "deepseek-chat", "input": "x", "tools": [{"type": "mcp_toolset", "name": "mcp__git__direct", "server_label": "git", "schema": {}, "allowed_tools": ["run"]}]}},
    {"name": "namespace_trimmed_choice", "request": {"model": "deepseek-chat", "input": "x", "tools": [{"type": "namespace", "name": " mcp__srv_ ", "tools": [{"type": "function", "name": " _run "}]}], "tool_choice": {"type": "function", "namespace": " mcp__srv_ ", "name": " _run "}}},
    {"name": "custom_tool", "request": {"model": "deepseek-chat", "input": "call custom tool", "tools": [{"type": "custom", "name": "shell", "description": "synthetic custom tool", "format": {"type": "text"}}], "tool_choice": "auto"}},
    {"name": "web_search", "request": {"model": "deepseek-chat", "input": "search synthetic", "tools": [{"type": "web_search"}]}},
    {"name": "model_alias", "request": {"model": "deepseek-chat-v3", "input": "alias", "stream": False}},
    {"name": "invalid_model", "request": {"model": "unsupported-synthetic", "input": "reject me"}},
    {"name": "input_null", "request": {"model": "deepseek-chat", "input": None}},
    {"name": "input_number", "request": {"model": "deepseek-chat", "input": 7}},
    {"name": "input_boolean", "request": {"model": "deepseek-chat", "input": False}},
    {"name": "input_array", "request": {"model": "deepseek-chat", "input": ["first", "second"]}},
    {"name": "input_items", "request": {"model": "deepseek-chat", "input": [{"type": "input_text", "text": "valid"}, {"type": "unknown_synthetic", "value": "ignored"}, {"type": "input_text", "text": 9}]}},
]


def chat_response():
    return json.dumps({"id": "chatcmpl-synthetic", "object": "chat.completion", "created": 1700000000, "model": "deepseek-chat", "choices": [{"index": 0, "message": {"role": "assistant", "content": "synthetic response"}, "finish_reason": "stop"}]}, separators=(",", ":")).encode()


class Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.records.append({"destination": f"127.0.0.1:{self.server.server_port}", "path": self.path, "authorization": self.headers.get("Authorization"), "content_type": self.headers.get("Content-Type"), "body": body.decode("utf-8", "replace")})
        payload = chat_response()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

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
        open(os.environ["PRODEX_CAPTURE_PATH"] + ".json", "w").write(json.dumps({"status":response.status,"headers":dict(response.getheaders())}))
        conn.close()
    """).replace("#!__PYTHON__", "#!" + __import__("sys").executable))
    path.chmod(0o700)


def main():
    if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("missing or checksum-mismatched pinned Prodex oracle: " + str(ORACLE))
    FIXTURES.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = {"schema_version": 1, "baseline_commit": "433aad44bb249d5c25a231a6b06c2fa522a39a1f", "oracle_version": "0.439.0", "oracle_sha256": ORACLE_SHA256, "capture_harness": "tests/capture_provider_requests.py", "scope": "Observed upstream request bodies and local rejection responses from the frozen Prodex DeepSeek adapter.", "host_network_access": "available; child processes are not firewall-isolated", "runtime_claim": "each case uses isolated HOME, Prodex/Codex storage, request fixture, environment, and synthetic loopback port", "cases": []}
    with tempfile.TemporaryDirectory(prefix="provider-request-oracle-") as temporary:
        scratch = Path(temporary)
        for case in CASES:
            case_root = scratch / case["name"]
            case_root.mkdir(mode=0o700)
            home = case_root / "home"; home.mkdir(mode=0o700)
            prodex_home = case_root / "prodex"; prodex_home.mkdir(mode=0o700)
            shared = case_root / "shared-codex"; shared.mkdir(mode=0o700)
            codex = case_root / "codex"; fake_codex(codex)
            request_path = case_root / "request.json"; request_path.write_text(json.dumps(case["request"], separators=(",", ":")))
            capture = OUT / (case["name"] + ".local-response")
            capture.unlink(missing_ok=True)
            env = {"HOME":str(home), "PATH":"/usr/bin:/bin", "TERM":"dumb", "NO_COLOR":"1", "LANG":"C.UTF-8", "LC_ALL":"C.UTF-8", "TMPDIR":str(case_root), "PRODEX_HOME":str(prodex_home), "PRODEX_SHARED_CODEX_HOME":str(shared), "PRODEX_CODEX_BIN":str(codex), "PRODEX_REQUEST_PATH":str(request_path), "PRODEX_CAPTURE_PATH":str(capture)}
            server = HTTPServer(("127.0.0.1", 0), Upstream); server.records = []
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                if case.get("strict_tools"):
                    beta_url = f"http://127.0.0.1:{server.server_port}/beta"
                    (shared / "config.toml").write_text(f'[deepseek]\nstrict_tools = true\nbeta_base_url = "{beta_url}"\n')
                cmd = [str(ORACLE), "super", "--provider", "deepseek", "--api-key", "synthetic-provider-key", "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--skip-quota-check", "--no-presidio", "--model", "deepseek-chat", "exec", "--", "synthetic fixture request"]
                run = subprocess.run(cmd, cwd=case_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
                case_requests = server.records[:]
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)
            observed = case_requests[0] if len(case_requests) == 1 else None
            result = {"name": case["name"], "request": case["request"], "oracle_super_returncode": run.returncode, "oracle_stderr": run.stderr.decode("utf-8", "replace")}
            result["expected_response_metadata"] = case.get("expected_response_metadata")
            if case.get("strict_tools"):
                result["strict_tools"] = True
            if len(case_requests) > 1:
                result["capture_error"] = f"oracle sent {len(case_requests)} requests; one request per case is required"
            if observed:
                observed["destination"] = "127.0.0.1:<ephemeral>"
                result["upstream_request"] = observed
                result["upstream_body_sha256"] = hashlib.sha256(observed["body"].encode()).hexdigest()
            elif not result.get("capture_error"):
                result["capture_error"] = "oracle did not reach synthetic loopback upstream"
            if capture.is_file():
                response = capture.read_bytes(); meta = json.loads(Path(str(capture) + ".json").read_text())
                result["local_response"] = {"status":meta["status"], "body":response.decode("utf-8", "replace"), "sha256":hashlib.sha256(response).hexdigest()}
            if not case_requests and result.get("local_response", {}).get("status", 0) >= 400:
                result["oracle_observation"] = "local adapter rejected request before provider dispatch; detailed translator diagnostic unavailable"
                result.pop("capture_error", None)
            if observed:
                result["route_kind"] = "deepseek_chat" if observed["path"].endswith("/chat/completions") else "other_provider_path"
            catalog["cases"].append(result)
        (FIXTURES / "cases.json").write_text(json.dumps(catalog, indent=2) + "\n")
        (OUT / "manifest.json").write_text(json.dumps(catalog, indent=2) + "\n")
    failures = [c["name"] for c in catalog["cases"] if "capture_error" in c]
    for case in catalog["cases"]:
        if "upstream_request" in case:
            r = case["upstream_request"]
            if not r["destination"].startswith("127.0.0.1:") or r["authorization"] not in (None, "Bearer synthetic-provider-key"):
                raise SystemExit("unexpected upstream boundary in " + case["name"])
            print(f"{case['name']}: HTTP request captured ({len(r['body'])} bytes)")
        elif case.get("oracle_observation"):
            print(f"{case['name']}: observed {case['oracle_observation']} (HTTP {case['local_response']['status']})")
        else:
            print(f"{case['name']}: NO ORACLE OBSERVATION")
    if failures:
        raise SystemExit("missing oracle captures: " + ", ".join(failures))


if __name__ == "__main__":
    main()
