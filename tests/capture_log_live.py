"""Capture pinned oracle behavior and Modex mismatches for live log sources."""

import hashlib
import json
import os
import platform
from pathlib import Path
import selectors
import shutil
import signal
import socketserver
import subprocess
import tempfile
import threading
import time
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit

import test_cli
from test_cli import MODEX, ORACLE


TOKEN = "synthetic-live-log-capability"
INSTANCE = "synthetic-live-log-instance"
RECORD = (
    "[2026-10-24 01:02:03.000 +00:00] token_usage request=1 "
    "transport=http profile=synthetic source=synthetic-live-log-marker input_tokens=10 "
    "output_tokens=4 generation_ms=1000 output_tokens_per_second=4.0 "
    "\n"
)
MAX_REQUEST_BYTES = 16 * 1024
ROOT = test_cli.ROOT


def token_event_count(output):
    count = 0
    for stream in output.values():
        for line in stream.splitlines():
            try:
                record = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            count += record.get("event") == "token_usage" and record.get("source") == "synthetic-live-log-marker"
    return count


class SnapshotServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.requests = []
        self.authentication_failures = 0
        self.reset_registry = None
        self.request_errors = []
        super().__init__(("127.0.0.1", 0), SnapshotHandler)


class SnapshotHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytearray()
        self.request.settimeout(1)
        try:
            while b"\r\n\r\n" not in data:
                chunk = self.request.recv(4096)
                if not chunk:
                    return
                data.extend(chunk)
                if len(data) > MAX_REQUEST_BYTES:
                    self.server.request_errors.append("request exceeded bounded header size")
                    self.request.sendall(b"HTTP/1.1 431 Request Header Fields Too Large\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                    return
        except (OSError, TimeoutError):
            self.server.request_errors.append("request header read timed out or failed")
            return
        headers = bytes(data).split(b"\r\n\r\n", 1)[0].split(b"\r\n")
        request = headers[0].decode("ascii")
        token = next((line.split(b":", 1)[1].strip() for line in headers[1:]
                      if line.split(b":", 1)[0].lower() == b"x-prodex-admin-token"), b"")
        self.server.requests.append(request)
        if token != TOKEN.encode("ascii"):
            self.server.authentication_failures += 1
            body = b"{}"
            self.request.sendall(
                b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 2\r\n"
                b"Connection: close\r\n\r\n{}"
            )
            return
        query = parse_qs(urlsplit(request.split()[1]).query)
        after = int(query.get("after", ["0"])[0])
        reset = self.server.reset_registry is not None and len(self.server.requests) == 2
        if reset:
            registry_path, capability_path = self.server.reset_registry
            registry = json.loads(registry_path.read_text())
            registry["instance_id"] = "synthetic-live-log-instance-next"
            registry_path.write_text(json.dumps(registry))
            capability_path.write_text(json.dumps({
                "version": 1,
                "instance_id": registry["instance_id"],
                "admin_token": TOKEN,
            }, separators=(",", ":")))
        first = after == 0
        body = json.dumps({
            "cursor": 1 if first else 2,
            "dropped": 2 if first else 4,
            "entries": ([{"sequence": 1, "line": RECORD}] if first else []),
        }, separators=(",", ":")).encode()
        self.request.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )


def process_birth(pid):
    stat = Path(f"/proc/{pid}/stat").read_text()
    start = stat.rsplit(") ", 1)[1].split()[19]
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return f"linux:{boot}:{start}"


def write_source(root, key, address, holder):
    prodex_home = root / "home/.prodex"
    prodex_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(prodex_home, 0o700)
    executable = Path(f"/proc/{holder.pid}/exe").resolve()
    registry = {
        "pid": holder.pid,
        "process_birth_identity": process_birth(holder.pid),
        "listen_addr": address,
        "started_at": int(time.time()),
        "upstream_base_url": "http://127.0.0.1/unused",
        "include_code_review": False,
        "upstream_no_proxy": False,
        "smart_context_enabled": key.startswith("live-"),
        "current_profile": "synthetic",
        "instance_id": INSTANCE,
        "prodex_version": "0.439.2",
        "executable_path": str(executable),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "openai_mount_path": "/v1",
        "realtime_ws_addr": None,
    }
    registry_path = prodex_home / f"runtime-broker-{key}.json"
    registry_path.write_text(json.dumps(registry))
    os.chmod(registry_path, 0o600)
    capability = {"version": 1, "instance_id": INSTANCE, "admin_token": TOKEN}
    capability_path = prodex_home / f"runtime-broker-{key}.capability"
    capability_path.write_text(
        json.dumps(capability, separators=(",", ":"))
    )
    os.chmod(capability_path, 0o600)
    return registry


class LiveLogCapture:
    def capture_live(self, binary, key, invalid=None, reset=False):
        with tempfile.TemporaryDirectory(prefix="modex-live-log-") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir(mode=0o700)
            work = root / "work"
            work.mkdir()
            holder_home = root / "holder-home"
            holder_home.mkdir(mode=0o700)
            holder = None
            process = None
            server = None
            server_thread = None
            selector = None
            output = {"stdout": bytearray(), "stderr": bytearray()}
            try:
                holder = subprocess.Popen(
                    [str(ORACLE), "log", "stream"], cwd=work,
                    env={"HOME": str(holder_home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1",
                         "PRODEX_RUNTIME_LOG_RECORD": "false"},
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True,
                )
                server = SnapshotServer()
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                address = f"127.0.0.1:{server.server_address[1]}"
                registry = write_source(root, key, address, holder)
                holder_identity = dict(registry)
                prodex_home = home / ".prodex"
                if reset:
                    server.reset_registry = (
                        prodex_home / f"runtime-broker-{key}.json",
                        prodex_home / f"runtime-broker-{key}.capability",
                    )
                if invalid in ("pid", "birth", "binary", "instance"):
                    registry_path = prodex_home / f"runtime-broker-{key}.json"
                    registry = json.loads(registry_path.read_text())
                    if invalid == "pid":
                        registry["pid"] = 4_294_967_295
                    elif invalid == "birth":
                        registry["process_birth_identity"] = "linux:stale"
                    elif invalid == "instance":
                        registry["instance_id"] = "different-live-log-instance"
                    else:
                        registry["executable_path"] = "/bin/true"
                    registry_path.write_text(json.dumps(registry))
                elif invalid == "capability":
                    capability_path = prodex_home / f"runtime-broker-{key}.capability"
                    capability_path.write_text("not a capability")
                process = subprocess.Popen(
                    [str(binary), "log", "stream", "--json"], cwd=work,
                    env={"HOME": str(home), "PATH": "", "TERM": "dumb", "NO_COLOR": "1",
                         "TZ": "UTC", "PRODEX_RUNTIME_LOG_RECORD": "false"},
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                selector = selectors.DefaultSelector()
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                deadline = time.monotonic() + (0.5 if invalid else 5)
                while time.monotonic() < deadline:
                    for event, _ in selector.select(0.1):
                        chunk = os.read(event.fileobj.fileno(), 65536)
                        if chunk:
                            output[event.data].extend(chunk)
                        else:
                            selector.unregister(event.fileobj)
                    marker_count = token_event_count(output)
                    cursor_sequence = [parse_qs(urlsplit(request.split()[1]).query)
                                       .get("after", [""])[0] for request in server.requests]
                    expected_cursors = ["0", "1", "0"] if reset else ["0", "1"]
                    complete_cursors = cursor_sequence[:len(expected_cursors)] == expected_cursors
                    expected_markers = 2 if reset else 1
                    if marker_count >= expected_markers and any(
                        b"dropped=2" in value for value in output.values()
                    ) and complete_cursors:
                        break
                    if process.poll() is not None and not selector.get_map():
                        break
                if binary == ORACLE:
                    if process.poll() is not None:
                        raise AssertionError("oracle follower exited before capture completed")
                if holder is None or holder.poll() is not None:
                    raise AssertionError("identity holder exited before capture completed")
                return ({name: bytes(value) for name, value in output.items()},
                        list(server.requests), process.poll(), server.authentication_failures,
                        process.poll() is None, {
                            "argv": [str(binary), "log", "stream", "--json"],
                            "working_directory": "<temporary-work>",
                            "environment": {"HOME": "<temporary-home>", "PATH": "",
                                            "TERM": "dumb", "NO_COLOR": "1", "TZ": "UTC",
                                            "PRODEX_RUNTIME_LOG_RECORD": "false"},
                            "holder_argv": [str(ORACLE), "log", "stream"],
                            "holder_pid": holder.pid,
                            "holder_birth_identity": holder_identity["process_birth_identity"],
                            "holder_executable_path": holder_identity["executable_path"],
                            "holder_executable_sha256": holder_identity["executable_sha256"],
                            "listen_addr": address,
                            "source_key": key,
                            "registry_path": f".prodex/runtime-broker-{key}.json",
                            "capability_path": f".prodex/runtime-broker-{key}.capability",
                            "registry": registry,
                            "capability": "version=1, matching instance, synthetic token; value omitted",
                            "snapshot_response_template": {
                                "after_0": {"cursor": 1, "dropped": 2,
                                            "entries": [{"sequence": 1, "line": RECORD}]},
                                "after_nonzero": {"cursor": 2, "dropped": 4,
                                                  "entries": []},
                                "reset": "registry and capability switch to a new matching instance before request 3",
                            },
                            "mutation": invalid,
                            "reset_instance_after_second_request": reset,
                        }, list(server.request_errors))
            finally:
                if selector is not None:
                    selector.close()
                for child in (process, holder):
                    if child is not None and child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait(timeout=2)
                if process is not None:
                    process.stdout.close()
                    process.stderr.close()
                if server is not None:
                    if server_thread is not None and server_thread.is_alive():
                        server.shutdown()
                    server.server_close()
                if server_thread is not None:
                    server_thread.join(timeout=2)

def capture_modex_mismatches():
    test_cli.CliTests.setUpClass()
    capture = LiveLogCapture()
    scenarios = [
        ("live-direct-test", None, False),
        ("broker-test", None, False),
        ("live-reset-test", None, True),
        *(('live-invalid-test', case, False) for case in
          ("pid", "birth", "capability", "instance", "binary")),
    ]
    observations = []
    for key, invalid, reset in scenarios:
        oracle = capture.capture_live(ORACLE, key, invalid, reset)
        (oracle_output, oracle_requests, oracle_exit, oracle_auth_failures,
         oracle_alive, oracle_fixture, oracle_request_errors) = oracle
        if oracle_exit is not None:
            raise AssertionError("oracle follower exited during live-log capture")
        if oracle_auth_failures or oracle_request_errors:
            raise AssertionError("oracle snapshot request failed synthetic-token validation")
        if invalid is not None and oracle_requests:
            raise AssertionError(f"oracle connected for rejected fixture {invalid}")
        expected_cursors = ["0", "1", "0"] if reset else ["0", "1"]
        oracle_cursors = [parse_qs(urlsplit(request.split()[1]).query)
                          .get("after", [""])[0] for request in oracle_requests]
        if invalid is None:
            if not any("after=0" in request and "limit=512" in request for request in oracle_requests):
                raise AssertionError("oracle omitted initial cursor/limit query")
            if not any("after=1" in request for request in oracle_requests):
                raise AssertionError("oracle omitted advanced cursor query")
            if b"dropped=2" not in oracle_output["stdout"] + oracle_output["stderr"]:
                raise AssertionError("oracle omitted bounded-buffer gap")
            if oracle_cursors[:len(expected_cursors)] != expected_cursors:
                raise AssertionError(f"oracle cursor trace incomplete: {oracle_cursors!r}")
            marker_count = token_event_count(oracle_output)
            if marker_count < (2 if reset else 1):
                raise AssertionError("oracle output did not include every expected marker")
        (modex_output, modex_requests, modex_exit, modex_auth_failures,
         modex_alive, modex_fixture, modex_request_errors) = capture.capture_live(
            MODEX, key, invalid, reset
        )
        modex_cursors = [parse_qs(urlsplit(request.split()[1]).query)
                         .get("after", [""])[0] for request in modex_requests]
        reasons = []
        if oracle_output != modex_output:
            reasons.append("stdout_or_stderr_differs")
        if oracle_requests != modex_requests:
            reasons.append("snapshot_request_trace_differs")
        if oracle_exit != modex_exit:
            reasons.append("exit_code_differs")
        if oracle_alive != modex_alive:
            reasons.append("process_survival_differs")
        if oracle_auth_failures != modex_auth_failures:
            reasons.append("snapshot_authentication_result_differs")
        if oracle_request_errors != modex_request_errors:
            reasons.append("snapshot_request_errors_differ")
        if invalid is None and modex_cursors[:len(expected_cursors)] != expected_cursors:
            reasons.append("cursor_trace_incomplete")
        if invalid is None and token_event_count(modex_output) < (2 if reset else 1):
            reasons.append("expected_marker_missing")
        if invalid is not None and modex_requests:
            reasons.append("rejected_fixture_connected")
        observations.append({
            "key": key,
            "invalid_fixture": invalid,
            "instance_reset": reset,
            "status": "FAIL" if reasons else "PASS",
            "failure_reasons": reasons,
            "oracle": {
                "exit_code_during_capture": oracle_exit,
                "stdout": oracle_output["stdout"].decode("utf-8", "replace"),
                "stderr": oracle_output["stderr"].decode("utf-8", "replace"),
                "requests": oracle_requests,
                "authentication_failures": oracle_auth_failures,
                "alive_during_capture": oracle_alive,
                "fixture": oracle_fixture,
                "cursor_trace": oracle_cursors,
                "request_errors": oracle_request_errors,
                "marker_event_count": token_event_count(oracle_output),
            },
            "modex": {
                "exit_code_during_capture": modex_exit,
                "stdout": modex_output["stdout"].decode("utf-8", "replace"),
                "stderr": modex_output["stderr"].decode("utf-8", "replace"),
                "requests": modex_requests,
                "authentication_failures": modex_auth_failures,
                "alive_during_capture": modex_alive,
                "fixture": modex_fixture,
                "cursor_trace": modex_cursors,
                "request_errors": modex_request_errors,
                "marker_event_count": token_event_count(modex_output),
            },
        })
    mojo = shutil.which("mojo")
    compiler = "unavailable"
    if mojo:
        version = subprocess.run([mojo, "--version"], capture_output=True,
                                 text=True, timeout=10, check=False)
        compiler = (version.stdout + version.stderr).strip()
    metadata = {
        "schema_version": 1,
        "compiler": compiler,
        "baseline_commit": "72b77478a5198fc5da6b4d2253137f9cdbf43be9",
        "baseline_version": "0.439.2",
        "baseline_oracle": str(ORACLE),
        "baseline_sha256": test_cli.ORACLE_SHA256,
        "modex_binary": str(test_cli.MODEX),
        "modex_binary_sha256": sha256(test_cli.MODEX.read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "isolation": "synthetic HOME and cwd; server binds 127.0.0.1; host PID namespace retained",
        "isolation_limit": "bwrap user/mount namespace prevents holder /proc/<pid>/exe inspection under host ptrace policy",
        "argv_templates": {
            "holder": [str(ORACLE), "log", "stream"],
            "tested_process": ["<binary>", "log", "stream", "--json"],
        },
        "modex_capture_command": "python3 tests/capture_log_live.py",
    }
    result = ROOT / "docs/evidence/log-live-mismatch.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps({"metadata": metadata, "observations": observations}, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(capture_modex_mismatches())
