#!/usr/bin/env python3
"""Capture frozen Super hook-trust traffic against a synthetic app-server peer."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
from test_cli import ORACLE, ORACLE_SHA256

BASELINE_COMMIT = "72b77478a5198fc5da6b4d2253137f9cdbf43be9"
OUTPUT = Path(os.environ.get("MODEX_HOOK_CAPTURE_OUTPUT", ROOT / "tests/fixtures/super_hooks/historical-0.439.2.json"))

FAKE_CODEX = r'''#!__PYTHON__
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import tomllib

args = sys.argv[1:]
capture_path = Path(os.environ["PRODEX_HOOK_CAPTURE"])
case_name = os.environ["PRODEX_HOOK_CASE"]

def save(record):
    with capture_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

def save_app_server(trace, config_path, codex_home, args):
    trace_path = capture_path.with_suffix(".app-server.json")
    record = {"mode": "app_server", "argv": args, "cwd": os.getcwd(),
              "codex_home": str(codex_home), "config_path": str(config_path),
              "config_text": config_path.read_text(encoding="utf-8") if config_path.is_file() else "",
              "trace": trace}
    trace_path.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
                          encoding="utf-8")

if args == ["--version"]:
    print("codex-cli 0.153.2")
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    codex_home = Path(os.environ["CODEX_HOME"])
    shared_home = Path(os.environ["PRODEX_SHARED_CODEX_HOME"])
    config_path = next((path for path in (
        codex_home / "config.toml", shared_home / "config.toml",
    ) if path.is_file() and "[hooks" in path.read_text(encoding="utf-8")),
       shared_home / "config.toml")
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        config = {}
    groups = config.get("hooks", {}).get("PreToolUse", [])
    definitions = []
    for group_index, group in enumerate(groups):
        for hook_index, handler in enumerate(group.get("hooks", [])):
            identity = {
                "event_name": "pre_tool_use",
                "matcher": group.get("matcher"),
                "handler": handler,
            }
            current_hash = "sha256:" + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            key = f"{config_path}:pre_tool_use:{group_index}:{hook_index}"
            definitions.append({"key": key, "currentHash": current_hash, "handler": handler,
                                "matcher": group.get("matcher"), "group": group_index,
                                "index": hook_index, "sourcePath": str(config_path)})

    state = {}
    list_count = 0
    update_requested = False
    trace = []
    scenario = case_name
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(request, dict) or "id" not in request:
            continue
        method = request.get("method")
        params = request.get("params", {})
        if scenario == "rpc_timeout" and method == "initialize":
            trace.append({"request": request, "response": None})
            save_app_server(trace, config_path, codex_home, args)
            time.sleep(14)
            break
        if method == "initialize":
            if scenario == "initialize_method_not_found":
                response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32601, "message": "Method not found: initialize",
                }}
            else:
                response = {"jsonrpc": "2.0", "id": request["id"], "result": {
                    "userAgent": "codex-cli 0.153.2 (synthetic)",
                    "codexHome": str(codex_home), "platformFamily": "unix", "platformOs": "linux",
                }}
        elif method == "hooks/list":
            list_count += 1
            if scenario == "legacy_hooks_list" and request["id"] == 2:
                response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32601, "message": "Method not found: hooks/list",
                }}
            elif scenario == "hooks_list_error" and request["id"] == 2:
                response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32000, "message": "Synthetic hook discovery failed",
                }}
            elif scenario == "verification_method_not_found" and request["id"] == 4:
                response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32601, "message": "Method not found: hooks/list",
                }}
            else:
                hooks = []
                if scenario not in ("empty_hooks", "verification_method_not_found"):
                    for definition in definitions:
                        trusted_hash = state.get(definition["key"])
                        if scenario == "already_trusted":
                            trusted_hash = definition["currentHash"]
                        trust_status = (
                            "trusted" if trusted_hash == definition["currentHash"] else "untrusted"
                        )
                        if scenario == "verification_untrusted" and list_count > 1:
                            trust_status = "untrusted"
                        handler = definition["handler"]
                        hooks.append({
                            "key": definition["key"], "eventName": "preToolUse",
                            "handlerType": "command", "command": handler["command"],
                            "async": handler.get("async", False),
                            "matcher": definition["matcher"],
                            "timeoutSec": handler.get("timeout", 5),
                            "statusMessage": handler.get("statusMessage"),
                            "additionalContextLimit": handler.get("additionalContextLimit"),
                            "sourcePath": definition["sourcePath"], "source": "user",
                            "pluginId": None, "displayOrder": definition["index"],
                            "enabled": True, "isManaged": False,
                            "currentHash": definition["currentHash"], "trustStatus": trust_status,
                        })
                entry = {"cwd": params.get("cwds", [os.getcwd()])[0], "hooks": hooks,
                         "warnings": [], "errors": []}
                if scenario == "diagnostics_warning" and request["id"] == 2:
                    entry["warnings"] = ["Synthetic hook warning"]
                if scenario == "missing_hook_key" and hooks:
                    hooks[0].pop("key", None)
                response = {"jsonrpc": "2.0", "id": request["id"], "result": {"data": [entry]}}
        elif method == "config/batchWrite":
            update_requested = True
            if scenario == "legacy_batch_write" and request["id"] == 3:
                response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32601, "message": "Method not found: config/batchWrite",
                }}
            elif scenario == "batch_write_error_status":
                response = {"jsonrpc": "2.0", "id": request["id"], "result": {"status": "error"}}
            else:
                for edit in params.get("edits", []):
                    if edit.get("keyPath") == "hooks.state":
                        state.update({key: value.get("trusted_hash")
                                      for key, value in edit.get("value", {}).items()})
                response = {"jsonrpc": "2.0", "id": request["id"], "result": {
                    "status": "okOverridden" if scenario == "batch_write_ok_overridden" else "ok",
                    "version": "sha256:synthetic-config-v1",
                    "filePath": str(config_path), "overriddenMetadata": None,
                }}
        else:
            response = {"jsonrpc": "2.0", "id": request["id"], "error": {
                "code": -32601, "message": "Method not found",
            }}
        trace.append({"request": request, "response": response})
        save_app_server(trace, config_path, codex_home, args)
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    raise SystemExit(0)

save({"mode": "runtime", "argv": args, "cwd": os.getcwd(),
      "codex_home": os.environ.get("CODEX_HOME"),
      "bypass_hook_trust": "--dangerously-bypass-hook-trust" in args})
raise SystemExit(0)
'''

CASES = (
    {"name": "empty_hooks"},
    {"name": "untrusted_hook_write"},
    {"name": "already_trusted"},
    {"name": "batch_write_ok_overridden"},
    {"name": "legacy_hooks_list"},
    {"name": "legacy_batch_write"},
    {"name": "initialize_method_not_found"},
    {"name": "hooks_list_error"},
    {"name": "verification_method_not_found"},
    {"name": "batch_write_error_status"},
    {"name": "verification_untrusted"},
    {"name": "diagnostics_warning"},
    {"name": "missing_hook_key"},
    {"name": "rpc_timeout"},
)


HOOK_CONFIG = '''[features]
hooks = true

[[hooks.PreToolUse]]
matcher = "Bash"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "synthetic-hook-command"
timeout = 5
async = true
statusMessage = "synthetic hook fixture"
additionalContextLimit = 4096
'''


class LoopbackProbe(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.requests = []
        super().__init__(("127.0.0.1", 0), LoopbackHandler)


class LoopbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.requests.append({"method": self.command, "path": self.path,
                                     "body": self.rfile.read(length).hex()})
        body = b"{}"
        self.send_response(501)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def normalized(value, root):
    if isinstance(value, str):
        value = value.replace(str(root), "<ROOT>").replace(str(ORACLE), "<ORACLE>")
        value = re.sub(r"\.prodex-overlay-[0-9a-f]+-0", ".prodex-overlay-<ID>-0", value)
        return re.sub(r"http://127\.0\.0\.1:[0-9]+/v1", "http://127.0.0.1:<PORT>/v1", value)
    if isinstance(value, list):
        return [normalized(item, root) for item in value]
    if isinstance(value, dict):
        return {normalized(key, root): normalized(item, root) for key, item in value.items()}
    return value


def run_case(case):
    with tempfile.TemporaryDirectory(prefix="modex-super-hooks-oracle-") as temporary:
        root = Path(temporary)
        home = root / "home"
        prodex_home = root / "prodex"
        shared_home = root / "shared-codex"
        workspace = root / "workspace"
        for path in (home, prodex_home, shared_home, workspace):
            path.mkdir(mode=0o700)
        config_text = HOOK_CONFIG if case["name"] not in ("empty_hooks",) else "[features]\nhooks = true\n"
        config_path = shared_home / "config.toml"
        config_path.write_text(config_text, encoding="utf-8")
        config_path.chmod(0o600)
        cache_path = prodex_home / "update-check.json"
        cache_path.write_text(json.dumps({
            "source": "GitHub", "latest_version": "0.439.2", "checked_at": int(time.time()),
        }, separators=(",", ":")) + "\n", encoding="utf-8")
        cache_path.chmod(0o600)
        codex_path = root / "codex"
        codex_path.write_text(FAKE_CODEX.replace("#!__PYTHON__", "#!" + sys.executable), encoding="utf-8")
        codex_path.chmod(0o700)
        trace_path = root / "capture.jsonl"
        upstream = LoopbackProbe()
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        environment = {
            "HOME": str(home),
            "PRODEX_HOME": str(prodex_home),
            "PRODEX_SHARED_CODEX_HOME": str(shared_home),
            "PRODEX_CODEX_BIN": str(codex_path),
            "PRODEX_HOOK_CAPTURE": str(trace_path),
            "PRODEX_HOOK_CASE": case["name"],
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "TMPDIR": str(root),
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            Path(environment[name]).mkdir(mode=0o700)
        arguments = [
            str(ORACLE), "super", "--provider", "deepseek", "--api-key",
            "synthetic-provider-key", "--base-url",
            f"http://127.0.0.1:{upstream.server_port}/v1", "--skip-quota-check",
            "--no-presidio", "--model", "synthetic-hook-model", "exec", "--",
            "synthetic hook trust fixture",
        ]
        try:
            result = subprocess.run(
                arguments, cwd=workspace, env=environment, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=45, check=False,
            )
            records = []
            if trace_path.is_file():
                records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
            app_server_path = trace_path.with_suffix(".app-server.json")
            if app_server_path.is_file():
                records.insert(0, json.loads(app_server_path.read_text(encoding="utf-8")))
            upstream_requests = list(upstream.requests)
        finally:
            upstream.shutdown()
            upstream.server_close()
            thread.join(timeout=2)
        return normalized({
            "name": case["name"],
            "argv": arguments,
            "synthetic_config": config_text,
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "stderr": result.stderr.decode("utf-8", "replace"),
            "upstream_requests": upstream_requests,
            "child_invocations": records,
        }, root)


def main():
    if not ORACLE.is_file():
        raise SystemExit(f"pinned Prodex oracle is missing: {ORACLE}")
    oracle_sha256 = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
    if oracle_sha256 != ORACLE_SHA256:
        raise SystemExit(f"pinned Prodex oracle checksum mismatch: {oracle_sha256}")
    cases = [run_case(case) for case in CASES]
    document = {
        "schema_version": 1,
        "baseline_commit": BASELINE_COMMIT,
        "oracle_version": "0.439.2",
        "oracle_sha256": oracle_sha256,
        "capture_harness": "tests/capture_super_hooks.py",
        "scope": "Frozen Super hook-trust JSON-RPC behavior against isolated synthetic Codex app-server peers.",
        "protocol_sources": [
            "Frozen Prodex 0.439.2 crates/prodex-app/src/runtime_tools/hook_trust.rs",
            "Codex app-server/tests/suite/v2/hooks_list.rs:77-113, 190-237",
            "Codex app-server-protocol/src/protocol/v2/plugin.rs:52-64, 512-575",
            "Codex app-server-protocol/src/protocol/v2/config.rs:337-357",
        ],
        "runtime_claim": (
            "Synthetic Codex child implements app-server --stdio and records each actual request/reply. "
            "All launches use isolated storage, a synthetic provider key, and an ephemeral loopback endpoint; "
            "the endpoint receives no traffic. The synthetic peer computes a stable test currentHash from its "
            "fixture config and models config/batchWrite in memory. Captures do not verify production Codex hook execution."
        ),
        "cases": cases,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"captured {len(cases)} Super hook-trust cases into {OUTPUT}")
    failed = []
    for case in cases:
        app_servers = [item for item in case["child_invocations"] if item["mode"] == "app_server"]
        runtime = [item for item in case["child_invocations"] if item["mode"] == "runtime"]
        if not app_servers or not app_servers[0]["trace"]:
            failed.append(case["name"])
            print(f"FAIL {case['name']}: synthetic app-server saw no RPC handshake")
            continue
        print(f"{case['name']}: exit={case['returncode']} rpc={len(app_servers[0]['trace'])} runtime={bool(runtime)} upstream={len(case['upstream_requests'])}")
    if failed:
        raise SystemExit("synthetic app-server did not complete handshake for: " + ", ".join(failed))


if __name__ == "__main__":
    main()
