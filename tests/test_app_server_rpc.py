"""Run the compiled Modex RPC transport against isolated synthetic Codex peers."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/app_server_rpc_driver"


def make_codex(path):
    path.write_text("#!" + sys.executable + "\n" + textwrap.dedent('''
        import json, os, sys, time

        capture = os.environ["MODEX_RPC_CAPTURE"]
        scenario = os.environ["MODEX_RPC_SCENARIO"]
        args = sys.argv[1:]

        def save(record):
            with open(capture, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\\n")

        save({"kind": "spawn", "pid": os.getpid(), "args": args, "cwd": os.getcwd(),
              "codex_home": os.environ.get("CODEX_HOME"),
              "marker": os.environ.get("MODEX_RPC_MARKER")})
        sys.stderr.write("synthetic-child-stderr-sentinel\\n")
        sys.stderr.flush()

        def send(frame):
            sys.stdout.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\\n")
            sys.stdout.flush()

        for line in sys.stdin:
            request = json.loads(line)
            save({"kind": "request", "request": request})
            method = request["method"]
            if scenario == "timeout" and method == "initialize":
                time.sleep(30)
                break
            if scenario == "closed_stdin_live" and method == "initialize":
                os.close(0)
                time.sleep(0.2)
                send({"id": request["id"], "result": {}})
                time.sleep(30)
                break
            if scenario == "oversized" and method == "initialize":
                sys.stdout.buffer.write(b"x" * (16_777_216 + 1) + b"\\n")
                sys.stdout.flush()
                time.sleep(30)
                break
            if method == "initialize":
                sys.stdout.write("not json\\n{\\"id\\":999,\\"result\\":{}}\\n")
                sys.stdout.flush()
                response = {"id": request["id"], "result": {}}
            elif method == "hooks/list" and request["id"] == 2:
                if scenario == "legacy":
                    response = {"id": request["id"], "error": {
                        "code": -32601, "message": "Method not found",
                    }}
                else:
                    response = {"id": request["id"], "result": {"data": [{"hooks": [
                        {"key": "synthetic-hook", "currentHash": "sha256:synthetic", "trustStatus": "untrusted"}
                    ], "warnings": [], "errors": []}]}}
            elif method == "config/batchWrite":
                response = {"id": request["id"], "result": {"status": "okOverridden"}}
            elif method == "hooks/list":
                response = {"id": request["id"], "result": {"data": [{"hooks": [
                    {"key": "synthetic-hook", "currentHash": "sha256:synthetic", "trustStatus": "trusted"}
                ], "warnings": [], "errors": []}]}}
            else:
                response = {"id": request["id"], "result": {}}
            save({"kind": "response", "response": response})
            send(response)
            if scenario == "close_after_initialize" and request["id"] == 1:
                break
            if request["id"] == 4 or (scenario == "legacy" and request["id"] == 2):
                time.sleep(30)
                break
    '''), encoding="utf-8")
    path.chmod(0o700)


class AppServerRpcTests(unittest.TestCase):
    def run_case(self, scenario, *, timeout=8, mismatched_workspace=False):
        with tempfile.TemporaryDirectory(prefix="modex-app-server-rpc-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace-雪"
            workspace.mkdir(mode=0o700)
            requested_workspace = workspace
            if mismatched_workspace:
                requested_workspace = root / "other-workspace"
                requested_workspace.mkdir(mode=0o700)
            home = root / "home"
            codex_home = root / "codex-home"
            home.mkdir(mode=0o700)
            codex_home.mkdir(mode=0o700)
            capture = root / "capture.jsonl"
            binary = root / "codex"
            make_codex(binary)
            values = {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home),
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "TMPDIR": str(root),
                "MODEX_RPC_CAPTURE": str(capture),
                "MODEX_RPC_SCENARIO": scenario,
                "MODEX_RPC_MARKER": "synthetic-environment-value",
            }
            env = {key: values[key] for key in ("HOME", "PATH", "LANG", "LC_ALL", "TMPDIR")}
            result = subprocess.run(
                [str(DRIVER), str(binary), str(requested_workspace), *(f"{key}={value}" for key, value in values.items())],
                cwd=workspace,
                env=env,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            records = [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()] if capture.exists() else []
            return result, records, workspace, codex_home

    def assert_child_reaped(self, records):
        pid = next(record["pid"] for record in records if record["kind"] == "spawn")
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_stdio_preflight_runs_exact_rpc_sequence_and_cleans_up(self):
        result, records, workspace, codex_home = self.run_case("success")
        self.assertNotIn(b"synthetic-child-stderr-sentinel", result.stderr)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"Trusted\n", b""))
        self.assertEqual([record["kind"] for record in records], [
            "spawn", "request", "response", "request", "response", "request", "response", "request", "response",
        ])
        self.assertEqual(records[0]["args"], ["-c", 'model="fixture-model"', "app-server", "--stdio"])
        self.assertEqual(records[0]["cwd"], str(workspace))
        self.assertEqual(records[0]["codex_home"], str(codex_home))
        self.assertEqual(records[0]["marker"], "synthetic-environment-value")
        requests = [record["request"] for record in records if record["kind"] == "request"]
        self.assertEqual([request["method"] for request in requests], [
            "initialize", "hooks/list", "config/batchWrite", "hooks/list",
        ])
        self.assertEqual(requests[0]["params"]["clientInfo"], {
            "name": "prodex-hook-trust", "version": "0.166.0",
        })
        self.assertEqual(requests[2]["params"]["edits"][0]["value"], {
            "synthetic-hook": {"trusted_hash": "sha256:synthetic"},
        })
        self.assert_child_reaped(records)

    def test_method_not_found_returns_legacy_bypass(self):
        result, records, _workspace, _codex_home = self.run_case("legacy")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"LegacyBypass\n", b""))
        self.assertEqual([record["request"]["method"] for record in records if record["kind"] == "request"], [
            "initialize", "hooks/list",
        ])
        self.assert_child_reaped(records)

    def test_per_rpc_deadline_terminates_unresponsive_app_server(self):
        started = time.monotonic()
        result, records, _workspace, _codex_home = self.run_case("timeout", timeout=17)
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Codex hook-trust preflight initialize failed: timed out waiting on channel", result.stderr)
        self.assertGreaterEqual(elapsed, 11.5)
        self.assertLess(elapsed, 17)
        self.assert_child_reaped(records)

    def test_oversized_rpc_line_is_rejected_and_child_is_terminated(self):
        result, records, _workspace, _codex_home = self.run_case("oversized", timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Codex hook-trust preflight stdout line exceeds its supported size", result.stderr)
        self.assert_child_reaped(records)

    def test_closed_request_pipe_returns_error_and_reaps_child(self):
        result, records, _workspace, _codex_home = self.run_case("close_after_initialize")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Codex hook-trust preflight hooks/list failed", result.stderr)
        self.assert_child_reaped(records)

    def test_live_peer_closing_stdin_reports_error_without_sigpipe(self):
        result, records, _workspace, _codex_home = self.run_case("closed_stdin_live")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Broken pipe (os error 32)", result.stderr)
        self.assert_child_reaped(records)

    def test_workspace_mismatch_fails_before_codex_spawn(self):
        result, records, _workspace, _codex_home = self.run_case("success", mismatched_workspace=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"workspace must match current working directory", result.stderr)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
