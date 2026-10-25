#!/usr/bin/env python3
"""Capture the frozen gateway CLI help and DeepSeek startup behavior."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ORACLE = Path("/home/doxa/.cache/modex/oracles/0.439.0/prodex-x86_64-unknown-linux-gnu")
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
BASELINE_COMMIT = "433aad44bb249d5c25a231a6b06c2fa522a39a1f"
OUTPUT = ROOT / "tests/fixtures/gateway/cases.json"


class ProbeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.requests = []
        super().__init__(("127.0.0.1", 0), ProbeHandler)


class ProbeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.requests.append({
            "method": self.command,
            "path": self.path,
            "body_hex": self.rfile.read(length).hex(),
        })
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def filesystem_snapshot(root):
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(root))
        payload = path.read_bytes()
        snapshot[relative] = {
            "mode": path.stat().st_mode & 0o777,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    return snapshot


def filesystem_delta(before, after):
    return [
        {
            "path": name,
            "before": before.get(name),
            "after": after.get(name),
        }
        for name in sorted(before.keys() | after.keys())
        if before.get(name) != after.get(name)
    ]


def run_case(name, args, *, shared_config=None, loopback=False, case_class="startup", config_mode=0o600):
    with tempfile.TemporaryDirectory(prefix="modex-gateway-oracle-") as temp:
        root = Path(temp)
        home = root / "home"
        prodex_home = root / "prodex"
        shared = root / "shared-codex"
        xdg_config = root / "xdg-config"
        xdg_cache = root / "xdg-cache"
        for path in (home, prodex_home, shared, xdg_config, xdg_cache):
            path.mkdir(mode=0o700)
        update_cache = prodex_home / "update-check.json"
        update_cache.write_text(json.dumps({
            "source": "GitHub",
            "latest_version": "0.439.0",
            "checked_at": int(time.time()),
        }, separators=(",", ":")) + "\n", encoding="utf-8")
        update_cache.chmod(0o600)
        if shared_config is not None:
            shared_config_path = shared / "config.toml"
            shared_config_path.write_text(shared_config, encoding="utf-8")
            shared_config_path.chmod(config_mode)

        server = ProbeServer() if loopback else None
        thread = None
        if server is not None:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

        base_url = (
            f"http://127.0.0.1:{server.server_port}/v1" if server is not None
            else "http://127.0.0.1:1/v1"
        )
        command = ["prodex", *args]
        command = [
            token.replace("{base_url}", base_url)
            for token in command
        ]
        environment = {
            "HOME": str(home),
            "PRODEX_HOME": str(prodex_home),
            "PRODEX_SHARED_CODEX_HOME": str(shared),
            "XDG_CONFIG_HOME": str(xdg_config),
            "XDG_CACHE_HOME": str(xdg_cache),
            "TMPDIR": str(root),
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        before = filesystem_snapshot(root)
        timed_out = False
        try:
            result = subprocess.run(
                command, executable=str(ORACLE), cwd=root, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5, check=False,
            )
            returncode = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            returncode = None
            stdout = error.stdout or b""
            stderr = error.stderr or b""
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        after = filesystem_snapshot(root)

        return {
            "name": name,
            "class": case_class,
            "argv": ["prodex", *args],
            "synthetic_shared_config": shared_config,
            "returncode": returncode,
            "timed_out": timed_out,
            "stdout": stdout.decode("utf-8", "replace"),
            "stderr": stderr.decode("utf-8", "replace"),
            "upstream_requests": [] if server is None else server.requests,
            "filesystem_before": before,
            "filesystem_after": after,
            "filesystem_delta": filesystem_delta(before, after),
        }


def main():
    if not ORACLE.is_file():
        raise SystemExit(f"frozen gateway oracle is missing: {ORACLE}")
    oracle_sha256 = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
    if oracle_sha256 != ORACLE_SHA256:
        raise SystemExit(f"frozen gateway oracle checksum mismatch: {oracle_sha256}")

    common = [
        "gateway", "--provider", "deepseek", "--base-url", "{base_url}",
        "--api-key", "synthetic-provider-key", "--no-presidio",
        "--listen", "127.0.0.1:0",
    ]
    parse_cases = [
        ("cli_missing_provider_value", ["gateway", "--provider"]),
        ("cli_missing_base_url_value", ["gateway", "--base-url"]),
        ("cli_missing_api_key_value", ["gateway", "--api-key"]),
        ("cli_missing_listen_value", ["gateway", "--listen"]),
        ("cli_duplicate_base_url_alias", [
            "gateway", "--base-url", "http://127.0.0.1:1",
            "--url", "http://127.0.0.1:2",
        ]),
        ("cli_conflicting_presidio", ["gateway", "--presidio", "--no-presidio"]),
        ("cli_invalid_provider", ["gateway", "--provider", "not-a-provider"]),
        ("cli_unexpected_argument", ["gateway", "unexpected"]),
        ("cli_help_before_unexpected_argument", ["gateway", "--help", "unexpected"]),
        ("cli_help_after_unexpected_argument", ["gateway", "unexpected", "--help"]),
    ]
    cases = [
        run_case("gateway_help", ["gateway", "--help"], case_class="help"),
        *[
            run_case(name, args, case_class="parse_only")
            for name, args in parse_cases
        ],
        run_case("deepseek_empty_home", common, loopback=True, case_class="startup"),
        run_case(
            "deepseek_profileless_codex_config", common,
            shared_config='model_provider = "prodex-deepseek"\n',
            loopback=True, case_class="startup",
        ),
    ]
    document = {
        "schema_version": 1,
        "baseline_commit": BASELINE_COMMIT,
        "oracle_version": "0.439.0",
        "oracle_sha256": oracle_sha256,
        "capture_harness": "tests/capture_gateway.py",
        "scope": "Frozen gateway CLI help, parse-only cases, and synthetic DeepSeek startup probes.",
        "runtime_claim": (
            "The explicit DeepSeek gateway cannot reach HTTP in the frozen build: "
            "empty state has no active profile; a synthetic profileless DeepSeek "
            "Codex config reaches the no-OpenAI-compatible-proxy error. Parse-only "
            "captures and filesystem deltas preserve CLI behavior without startup. "
            "Loopback records prove the startup failure cases send no upstream request."
        ),
        "cases": cases,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"captured {len(cases)} gateway oracle cases into {OUTPUT}")


if __name__ == "__main__":
    main()
