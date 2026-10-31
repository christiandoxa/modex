"""Exercise the native Super hook-trust state machine against oracle captures."""

import copy
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from session_oracle import sandbox_command

DRIVER = Path(os.environ.get("MODEX_SUPER_HOOKS_DRIVER", ROOT / "build/tests/super_hooks_driver"))
FIXTURE = ROOT / "tests/fixtures/super_hooks/historical-0.439.2.json"
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
BASELINE_COMMIT = "72b77478a5198fc5da6b4d2253137f9cdbf43be9"
SANITIZED_ORACLE_EXECUTABLE = "<SANITIZED_ORACLE_EXECUTABLE>"

EXPECTED = {
    "empty_hooks": (0, "Trusted"),
    "untrusted_hook_write": (0, "Trusted"),
    "already_trusted": (0, "Trusted"),
    "batch_write_ok_overridden": (0, "Trusted"),
    "legacy_hooks_list": (0, "LegacyBypass"),
    "legacy_batch_write": (0, "LegacyBypass"),
    "initialize_method_not_found": (
        1, "Error: Codex hook-trust initialize failed (-32601): Method not found: initialize",
    ),
    "hooks_list_error": (
        1, "Error: Codex hook-trust hooks/list failed (-32000): Synthetic hook discovery failed",
    ),
    "verification_method_not_found": (
        1, "Error: Codex hook-trust hooks/list verification failed (-32601): Method not found: hooks/list",
    ),
    "batch_write_error_status": (
        1, "Error: Codex hook-trust config write did not report a successful status: error",
    ),
    "verification_untrusted": (
        1, "Error: Codex hook remained untrusted after Super preflight: "
        "<ROOT>/prodex/profiles/.prodex-overlay-<ID>-0/config.toml:pre_tool_use:0:0",
    ),
    "diagnostics_warning": (
        1, "Error: Codex hooks/list reported warnings: Synthetic hook warning",
    ),
    "missing_hook_key": (
        1, "Error: Codex hooks/list returned a trustable hook without key",
    ),
    "rpc_timeout": (
        1, "Error: Codex hook-trust preflight initialize failed: timed out waiting on channel",
    ),
}

EXPECTED_METHODS = {
    "empty_hooks": ["initialize", "hooks/list", "hooks/list"],
    "untrusted_hook_write": ["initialize", "hooks/list", "config/batchWrite", "hooks/list"],
    "already_trusted": ["initialize", "hooks/list", "hooks/list"],
    "batch_write_ok_overridden": ["initialize", "hooks/list", "config/batchWrite", "hooks/list"],
    "legacy_hooks_list": ["initialize", "hooks/list"],
    "legacy_batch_write": ["initialize", "hooks/list", "config/batchWrite"],
    "initialize_method_not_found": ["initialize"],
    "hooks_list_error": ["initialize", "hooks/list"],
    "verification_method_not_found": ["initialize", "hooks/list", "hooks/list"],
    "batch_write_error_status": ["initialize", "hooks/list", "config/batchWrite"],
    "verification_untrusted": ["initialize", "hooks/list", "config/batchWrite", "hooks/list"],
    "diagnostics_warning": ["initialize", "hooks/list"],
    "missing_hook_key": ["initialize", "hooks/list"],
    "rpc_timeout": ["initialize"],
}


def normalize(value, root):
    if isinstance(value, str):
        return value.replace(str(root), "<ROOT>")
    if isinstance(value, list):
        return [normalize(item, root) for item in value]
    if isinstance(value, dict):
        return {normalize(key, root): normalize(item, root) for key, item in value.items()}
    return value


def current_requests(app_server):
    requests = [copy.deepcopy(event["request"]) for event in app_server["trace"]]
    if requests and requests[0]["method"] == "initialize":
        identity = requests[0]["params"]["clientInfo"]
        if identity != {"name": "prodex-hook-trust", "version": "0.439.2"}:
            raise AssertionError("historical fixture identity changed")
        identity["version"] = "0.166.1"
    return requests


def driver_environment(root):
    home = root / "home"
    home.mkdir(mode=0o700, exist_ok=True)
    return {
        "HOME": str(home), "TMPDIR": str(root), "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
    }


def start_driver(root, workspace, *, sandbox=False):
    environment = driver_environment(root)
    if sandbox:
        command = sandbox_command(
            DRIVER, root, [str(workspace)], timezone="UTC", environment=environment,
        )
    else:
        command = [str(DRIVER), str(workspace)]
    return subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment, bufsize=0,
    )


def run_driver(case, extra_frames=()):
    app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
    replies = [entry["response"] for entry in app_server["trace"]]
    frames = []
    for reply in replies:
        frames.extend(extra_frames)
        if reply is not None:
            frames.append(json.dumps(reply, ensure_ascii=False, separators=(",", ":")))
    with tempfile.TemporaryDirectory(prefix="modex-hook-trust-driver-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        result = subprocess.run(
            [str(DRIVER), str(workspace)],
            input=("\n".join(frames) + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=driver_environment(root),
            timeout=5,
            check=False,
        )
        output = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines() if line]
        return result.returncode, output, result.stderr.decode("utf-8").strip(), normalize(output, root)


def read_request_line(process, timeout=5):
    return read_request(process, timeout)[0]


def read_request(process, timeout=5):
    ready, _, _ = select.select([process.stdout], [], [], timeout)
    if not ready:
        raise TimeoutError("native hook-trust driver did not emit its next request")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError(f"native hook-trust driver exited before its next request: {process.poll()}")
    return json.loads(line.decode("utf-8")), line


def run_interactive_peer(case, *, sandbox=False):
    app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
    with tempfile.TemporaryDirectory(prefix="modex-hook-trust-interactive-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        process = start_driver(root, workspace, sandbox=sandbox)
        observed = []
        try:
            for event in app_server["trace"]:
                observed.append(read_request_line(process))
                frames = (
                    "malformed frame",
                    json.dumps({"jsonrpc": "2.0", "id": 999, "result": {}}, separators=(",", ":")),
                    json.dumps(event["response"], ensure_ascii=False, separators=(",", ":")),
                )
                for frame in frames:
                    process.stdin.write((frame + "\n").encode("utf-8"))
                    process.stdin.flush()
            process.stdin.close()
            returncode = process.wait(timeout=5)
            trailing = process.stdout.read().decode("utf-8")
            stderr = process.stderr.read().decode("utf-8").strip()
            process.stdout.close()
            process.stderr.close()
            observed.extend(json.loads(line) for line in trailing.splitlines() if line)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            if not process.stdin.closed:
                process.stdin.close()
            if not process.stdout.closed:
                process.stdout.close()
            if not process.stderr.closed:
                process.stderr.close()
        return returncode, stderr, normalize(observed, root)


def run_sustained_noise_timeout():
    with tempfile.TemporaryDirectory(prefix="modex-hook-trust-timeout-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        process = start_driver(root, workspace)
        request = read_request_line(process)
        noise = b'{"jsonrpc":"2.0","id":999,"result":{}}\n'
        started = time.monotonic()
        while process.poll() is None and time.monotonic() - started < 20:
            try:
                process.stdin.write(noise)
                process.stdin.flush()
            except BrokenPipeError:
                break
            time.sleep(0.05)
        elapsed = time.monotonic() - started
        if process.poll() is None:
            process.kill()
        returncode = process.wait(timeout=3)
        process.stdin.close()
        trailing = process.stdout.read().decode("utf-8")
        stderr = process.stderr.read().decode("utf-8").strip()
        process.stdout.close()
        process.stderr.close()
        requests = [request]
        requests.extend(json.loads(line) for line in trailing.splitlines() if line)
        return returncode, stderr, elapsed, normalize(requests, root)


def rpc_result(request, value):
    return {"jsonrpc": "2.0", "id": request["id"], "result": value}


def send_frame(process, frame):
    process.stdin.write((json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    process.stdin.flush()


def run_large_batch_write():
    hook_count = 7500
    current_hash = "sha256:" + "a" * 64
    hooks = [
        {"key": f"synthetic-hook-{index:05d}", "currentHash": current_hash, "trustStatus": "untrusted"}
        for index in range(hook_count)
    ]
    with tempfile.TemporaryDirectory(prefix="modex-hook-trust-large-write-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        process = start_driver(root, workspace)
        requests = []
        try:
            request, _ = read_request(process)
            requests.append(request)
            send_frame(process, rpc_result(request, {}))

            request, _ = read_request(process)
            requests.append(request)
            send_frame(process, rpc_result(request, {
                "data": [{"cwd": str(workspace), "hooks": hooks, "warnings": [], "errors": []}],
            }))

            request, write_line = read_request(process, timeout=10)
            requests.append(request)
            written = request["params"]["edits"][0]["value"]
            if len(written) != hook_count:
                raise AssertionError(f"large config write contained {len(written)} of {hook_count} hooks")
            if any(value != {"trusted_hash": current_hash} for value in written.values()):
                raise AssertionError("large config write changed a trusted hook hash")
            send_frame(process, rpc_result(request, {
                "status": "ok", "version": "synthetic-version", "filePath": str(workspace / "config.toml"),
                "overriddenMetadata": None,
            }))

            request, _ = read_request(process, timeout=10)
            requests.append(request)
            trusted = [{"trustStatus": "trusted"} for _ in range(hook_count)]
            send_frame(process, rpc_result(request, {
                "data": [{"cwd": str(workspace), "hooks": trusted, "warnings": [], "errors": []}],
            }))
            process.stdin.close()
            returncode = process.wait(timeout=10)
            trailing = process.stdout.read()
            stderr = process.stderr.read().decode("utf-8").strip()
            if trailing:
                requests.extend(json.loads(line) for line in trailing.decode("utf-8").splitlines() if line)
            batch_write_bytes = len(write_line)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            if not process.stdin.closed:
                process.stdin.close()
            process.stdout.close()
            process.stderr.close()
        return returncode, stderr, batch_write_bytes, normalize(requests, root)


class SuperHooksRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.is_file():
            raise AssertionError(f"build the native Super hook-trust driver first: {DRIVER}")
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if cls.fixture["oracle_sha256"] != ORACLE_SHA256:
            raise AssertionError("fixture does not identify the pinned Prodex oracle")
        if cls.fixture["baseline_commit"] != BASELINE_COMMIT:
            raise AssertionError("fixture does not identify the frozen baseline commit")
        if cls.fixture.get("sanitized_fields") != {"cases[*].argv[0]": SANITIZED_ORACLE_EXECUTABLE}:
            raise AssertionError("fixture must label the sanitized oracle executable path")
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}
        if set(cls.cases) != set(EXPECTED):
            raise AssertionError("oracle fixture case inventory changed; update native expectations explicitly")
        if any(not case.get("argv") or case["argv"][0] != SANITIZED_ORACLE_EXECUTABLE for case in cls.cases.values()):
            raise AssertionError("fixture retained an unsanitized oracle executable path")

    def test_oracle_synthetic_peer_captures_success_and_failure_paths(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertEqual(case["returncode"], EXPECTED[name][0])
                self.assertEqual(case["upstream_requests"], [])
                app_server = [item for item in case["child_invocations"] if item["mode"] == "app_server"]
                runtime = [item for item in case["child_invocations"] if item["mode"] == "runtime"]
                self.assertEqual(len(app_server), 1)
                methods = [event["request"]["method"] for event in app_server[0]["trace"]]
                self.assertEqual(methods, EXPECTED_METHODS[name])
                self.assertEqual(app_server[0]["argv"][-2:], ["app-server", "--stdio"])
                self.assertEqual(bool(runtime), EXPECTED[name][0] == 0)
                if EXPECTED[name][0]:
                    self.assertEqual(case["stderr"].splitlines()[-1], EXPECTED[name][1])
                if name in ("legacy_hooks_list", "legacy_batch_write"):
                    self.assertTrue(runtime[0]["bypass_hook_trust"])
                elif runtime:
                    self.assertFalse(runtime[0]["bypass_hook_trust"])

    def test_native_driver_matches_observed_oracle_requests_and_results(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                if name == "rpc_timeout":
                    returncode, status, elapsed, normalized_requests = run_sustained_noise_timeout()
                    self.assertGreaterEqual(elapsed, 11.5)
                    self.assertLess(elapsed, 20)
                else:
                    returncode, _, status, normalized_requests = run_driver(case)
                app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
                expected_requests = current_requests(app_server)
                self.assertEqual(normalized_requests, expected_requests)
                self.assertEqual((returncode, status), EXPECTED[name])

    def test_untrusted_hook_is_written_then_verified_without_bypass(self):
        case = self.cases["untrusted_hook_write"]
        app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
        listed = app_server["trace"][1]["response"]["result"]["data"][0]["hooks"][0]
        write = app_server["trace"][2]["request"]["params"]["edits"][0]
        verified = app_server["trace"][3]["response"]["result"]["data"][0]["hooks"][0]
        self.assertEqual(listed["trustStatus"], "untrusted")
        self.assertEqual(write["keyPath"], "hooks.state")
        self.assertEqual(write["mergeStrategy"], "upsert")
        self.assertEqual(write["value"], {listed["key"]: {"trusted_hash": listed["currentHash"]}})
        self.assertEqual(verified["trustStatus"], "trusted")
        self.assertEqual(case["returncode"], 0)

    def test_interactive_peer_replies_after_each_actual_request(self):
        case = self.cases["untrusted_hook_write"]
        returncode, status, requests = run_interactive_peer(case)
        app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
        expected = current_requests(app_server)
        self.assertEqual(returncode, 0)
        self.assertEqual(status, "Trusted")
        self.assertEqual(requests, expected)

    def test_clean_runtime_interactive_peer_preserves_inherited_channels(self):
        if not shutil.which("bwrap"):
            self.skipTest("bubblewrap is unavailable; clean-runtime inherited channels not verified")
        case = self.cases["untrusted_hook_write"]
        returncode, status, requests = run_interactive_peer(case, sandbox=True)
        app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
        expected = current_requests(app_server)
        self.assertEqual(returncode, 0)
        self.assertEqual(status, "Trusted")
        self.assertEqual(requests, expected)

    def test_large_batch_write_handles_pipe_backpressure(self):
        returncode, status, request_bytes, requests = run_large_batch_write()
        self.assertEqual(returncode, 0)
        self.assertEqual(status, "Trusted")
        self.assertGreater(request_bytes, 700 * 1024)
        self.assertEqual([request["method"] for request in requests], [
            "initialize", "hooks/list", "config/batchWrite", "hooks/list",
        ])

    def test_timeout_message_matches_frozen_recv_timeout_error(self):
        case = self.cases["rpc_timeout"]
        app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
        self.assertEqual(len(app_server["trace"]), 1)
        self.assertEqual(app_server["trace"][0]["request"]["method"], "initialize")
        self.assertIsNone(app_server["trace"][0]["response"])
        self.assertEqual(case["returncode"], 1)
        self.assertEqual(case["stderr"].splitlines()[-1], EXPECTED["rpc_timeout"][1])

    def test_native_driver_ignores_malformed_and_unmatched_peer_frames(self):
        case = self.cases["empty_hooks"]
        unrelated = json.dumps({
            "jsonrpc": "2.0", "id": 99, "result": {"ignored": True},
        }, separators=(",", ":"))
        returncode, _, status, requests = run_driver(
            case, extra_frames=("not json", unrelated),
        )
        app_server = next(item for item in case["child_invocations"] if item["mode"] == "app_server")
        expected = current_requests(app_server)
        self.assertEqual((returncode, status), EXPECTED["empty_hooks"])
        self.assertEqual(requests, expected)


if __name__ == "__main__":
    unittest.main()
