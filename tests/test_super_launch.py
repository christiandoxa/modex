"""Production Super CLI against isolated synthetic Codex and loopback providers."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
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
    with capture.open("a") as handle: handle.write(json.dumps(value) + "\n")
if args == ["--version"]:
    print("codex-cli 0.216.0")
    raise SystemExit(0)
if args == ["app-server", "--help"]:
    print("Codex app-server")
    raise SystemExit(0)
if "app-server" in args and "--stdio" in args:
    save({"kind":"preflight", "pid":os.getpid()})
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request: continue
        save({"kind":"request", "method":request["method"], "params":request.get("params")})
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "legacy" and request["method"] == "hooks/list":
            print(json.dumps({"id":request["id"],"error":{"code":-32601,"message":"Method not found"}}),flush=True)
            time.sleep(30)
        if os.environ["MODEX_LAUNCH_SCENARIO"] == "closed-input":
            os.close(0)
            time.sleep(0.2)
            print(json.dumps({"id":request["id"],"result":{}}), flush=True)
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
save({"kind":"response","status":response.status,"headers":{name.lower():value for name,value in response.getheaders()},"body":response.read().hex()})
connection.close()
print("synthetic-client-complete")
raise SystemExit(0 if response.status == 200 else 1)
'''


def event_names(payload):
    return [line[7:] for line in bytes.fromhex(payload).decode().splitlines() if line.startswith("event: ")]


class SuperLaunchTests(unittest.TestCase):
    def run_launch(self, binary=MODEX, scenario="stream", existing=False, model="deepseek-chat", super_arguments=()):
        with tempfile.TemporaryDirectory(prefix="modex-super-launch-") as directory:
            root = Path(directory)
            for name in ("home", "state", "shared", "work"):
                (root / name).mkdir(mode=0o700)
            (root / "state/update-check.json").write_text(json.dumps({"source": "GitHub", "latest_version": "0.439.5", "checked_at": int(time.time())}))
            codex = root / "codex"
            codex.write_text("#!" + sys.executable + "\n" + CODEX)
            codex.chmod(0o700)
            capture = root / "capture.jsonl"
            if existing:
                (root / "shared/config.toml").write_text('model="preserve-me"\n')
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
            environment = {"HOME": str(root / "home"), "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1",
                           "PRODEX_HOME": str(root / "state"), "PRODEX_SHARED_CODEX_HOME": str(root / "shared"),
                           "PRODEX_CODEX_BIN": str(codex), "MODEX_LAUNCH_CAPTURE": str(capture),
                           "MODEX_LAUNCH_SCENARIO": scenario, "CODEX_SANDBOX_SENTINEL": "remove-from-child", "TMPDIR": str(root),
                           **{key: str(root / "home") for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")}}
            command = [str(binary), "super", "--provider", "deepseek", "--api-key", "synthetic-provider-key",
                       "--base-url", f"http://127.0.0.1:{server.server_port}/v1", "--model", model,
                       "--no-presidio", "--no-sub-agent", "--skip-quota-check", *super_arguments,
                       "exec", "--", "synthetic prompt"]
            try:
                result = subprocess.run(command, env=environment, cwd=root / "work", capture_output=True, timeout=40)
            finally:
                server.shutdown()
                worker.join(2)
                server.server_close()
            records = [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []
            saved = root / "shared/sessions/synthetic-session.jsonl"
            overlays = list((root / "state/profiles").glob("*"))
            state = {"leftovers": [str(path) for path in overlays], "session": saved.read_text() if saved.exists() else None,
                     "extra": [(path / "synthetic-user-state").read_text() for path in overlays if (path / "synthetic-user-state").exists()],
                     "config": (root / "shared/config.toml").read_text() if existing else None}
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
                if scenario == "closed-input": self.assertIn(b"request write failed", result.stderr)
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

    def test_existing_codex_data_is_preserved_before_child_or_network(self):
        result, records, upstream, state = self.run_launch(existing=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(records, [])
        self.assertEqual(upstream, [])
        self.assertEqual(state["config"], 'model="preserve-me"\n')
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

    def test_model_catalog_selection_and_metadata_match_release(self):
        for model in ("deepseek-v4-pro", "deepseek-flash", "deepseek-v4-flash", "auto", "flash", "deepseek-chat", "deepseek-reasoner", "synthetic-model-\"quoted\"", "synthetic\\model", "DEEPSEEK-CHAT", "deepsee\u212a-chat"):
            with self.subTest(model=model):
                baseline, before_records, _, _ = self.run_launch(ORACLE, "exit-seven", model=model)
                native, after_records, _, _ = self.run_launch(MODEX, "exit-seven", model=model)
                self.assertEqual((native.returncode, baseline.returncode), (7, 7))
                before = next(record for record in before_records if record["kind"] == "launch")
                after = next(record for record in after_records if record["kind"] == "launch")
                self.assertEqual(after["catalog"], before["catalog"])

    def test_04394_deepseek_flash_catalog_matches_provider_model(self):
        result, records, upstream, _ = self.run_launch(scenario="exit-seven", model="deepseek-flash")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(upstream, [])
        launch = next(record for record in records if record["kind"] == "launch")
        models = {row["slug"]: row for row in launch["catalog"]["models"]}
        flash = models["deepseek-flash"]
        self.assertEqual(flash["display_name"], "DeepSeek V4.1 Flash")
        self.assertEqual(flash["description"], "Current DeepSeek Flash routed through the Prodex Responses adapter.")
        self.assertEqual((flash["context_window"], flash["max_context_window"]), (1048576, 1048576))
        self.assertEqual(flash["default_reasoning_level"], "high")
        self.assertEqual([level["effort"] for level in flash["supported_reasoning_levels"]], ["none", "low", "high", "max"])
        self.assertEqual(models["flash"]["description"], "Prodex DeepSeek Flash alias routed through current DeepSeek Flash.")
        compatibility = models["deepseek-v4-flash"]
        self.assertEqual(compatibility["description"], "DeepSeek V4 Flash routed through the Prodex Responses adapter.")
        self.assertEqual(compatibility["supported_reasoning_levels"], flash["supported_reasoning_levels"])

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
