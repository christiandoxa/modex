"""Compare the public gateway CLI with the frozen Prodex behavior."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_GATEWAY_BINARY", ROOT / "build/modex"))
GATEWAY_FIXTURE = ROOT / "tests/fixtures/gateway/cases.json"
GATEWAY_MISMATCH_EVIDENCE = ROOT / "docs/evidence/gateway-mismatch.json"
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
BASELINE_COMMIT = "433aad44bb249d5c25a231a6b06c2fa522a39a1f"
EXPECTED_STARTUP_MISSING_ARTIFACTS = {
    "deepseek_empty_home": [
        {"path": "prodex-runtime.lock", "baseline_mode": "0600", "baseline_size": 0},
        {"path": "prodex/profile-lifecycle.json.lock", "baseline_mode": "0664", "baseline_size": 0},
        {"path": "prodex/runtime-housekeeping.last-run", "baseline_mode": "0664", "baseline_size": 0},
        {"path": "prodex/runtime-housekeeping.lock", "baseline_mode": "0664", "baseline_size": 0},
    ],
    "deepseek_profileless_codex_config": [
        {"path": "prodex-runtime.lock", "baseline_mode": "0600", "baseline_size": 0},
        {"path": "prodex/profile-lifecycle.json.lock", "baseline_mode": "0664", "baseline_size": 0},
        {"path": "prodex/runtime-housekeeping.last-run", "baseline_mode": "0664", "baseline_size": 11},
        {"path": "prodex/runtime-housekeeping.lock", "baseline_mode": "0664", "baseline_size": 0},
    ],
}


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


def filesystem_mismatches(baseline_delta, actual_delta):
    baseline = {item["path"]: item["after"] for item in baseline_delta}
    actual = {item["path"]: item["after"] for item in actual_delta}
    return [
        {
            "path": name,
            "baseline_after": baseline.get(name),
            "actual_after": actual.get(name),
        }
        for name in sorted(baseline.keys() | actual.keys())
        if baseline.get(name) != actual.get(name)
    ]


def mode_octal(metadata):
    return None if metadata is None else f"{metadata['mode']:04o}"


def environment_for(root):
    paths = {
        "HOME": root / "home",
        "PRODEX_HOME": root / "prodex",
        "PRODEX_SHARED_CODEX_HOME": root / "shared-codex",
        "XDG_CONFIG_HOME": root / "xdg-config",
        "XDG_CACHE_HOME": root / "xdg-cache",
        "TMPDIR": root,
    }
    for path in paths.values():
        path.mkdir(mode=0o700, exist_ok=True)
    return {
        **{name: str(path) for name, path in paths.items()},
        "PATH": "/usr/bin:/bin",
        "TERM": "dumb",
        "NO_COLOR": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def seed_update_cache(environment):
    path = Path(environment["PRODEX_HOME"]) / "update-check.json"
    path.write_text(json.dumps({
        "source": "GitHub",
        "latest_version": "0.439.0",
        "checked_at": int(time.time()),
    }, separators=(",", ":")) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run_case(case, config_mode=0o600):
    with tempfile.TemporaryDirectory(prefix="modex-gateway-public-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        environment = environment_for(root)
        seed_update_cache(environment)
        shared_config = case["synthetic_shared_config"]
        if shared_config is not None:
            config_path = Path(environment["PRODEX_SHARED_CODEX_HOME"]) / "config.toml"
            config_path.write_text(shared_config, encoding="utf-8")
            config_path.chmod(config_mode)

        server = ProbeServer() if case["class"] == "startup" else None
        thread = None
        if server is not None:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
        base_url = (
            f"http://127.0.0.1:{server.server_port}/v1"
            if server is not None else "http://127.0.0.1:1/v1"
        )
        arguments = [token.replace("{base_url}", base_url) for token in case["argv"][1:]]
        before = filesystem_snapshot(root)
        try:
            result = subprocess.run(
                [str(MODEX), *arguments], cwd=workspace, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise AssertionError(f"gateway case {case['name']} timed out") from error
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        after = filesystem_snapshot(root)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "stderr": result.stderr.decode("utf-8", "replace"),
            "upstream_requests": [] if server is None else server.requests,
            "filesystem_delta": filesystem_delta(before, after),
        }


class GatewayCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")
        cls.fixture = json.loads(GATEWAY_FIXTURE.read_text(encoding="utf-8"))
        if cls.fixture["oracle_sha256"] != ORACLE_SHA256:
            raise AssertionError("fixture does not identify the pinned Prodex oracle")
        if cls.fixture["baseline_commit"] != BASELINE_COMMIT:
            raise AssertionError("fixture does not identify the frozen baseline commit")
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def assert_case_outputs_match(self, name, actual=None):
        expected = self.cases[name]
        actual = run_case(expected) if actual is None else actual
        self.assertEqual(actual["returncode"], expected["returncode"], name)
        self.assertEqual(
            actual["stdout"], expected["stdout"].replace("Usage: prodex", "Usage: modex"), name,
        )
        self.assertEqual(
            actual["stderr"], expected["stderr"].replace("Usage: prodex", "Usage: modex"), name,
        )
        self.assertEqual(actual["upstream_requests"], expected["upstream_requests"], name)
        return actual

    def test_help_matches_frozen_gateway_help(self):
        self.assert_case_outputs_match("gateway_help")

    def test_parse_only_cases_match_frozen_cli_and_have_no_side_effects(self):
        parse_cases = [case for case in self.cases.values() if case["class"] == "parse_only"]
        self.assertGreaterEqual(len(parse_cases), 10)
        for case in parse_cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(case["filesystem_delta"], [], case["name"])
                self.assert_case_outputs_match(case["name"])

    def test_deepseek_startup_failures_match_frozen_output_and_upstream_behavior(self):
        for name in ("deepseek_empty_home", "deepseek_profileless_codex_config"):
            with self.subTest(case=name):
                self.assert_case_outputs_match(name)

    def test_retained_startup_filesystem_mismatch_is_exactly_documented(self):
        evidence = json.loads(GATEWAY_MISMATCH_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence["classification"], "RETAINED_PARITY_MISMATCH")
        self.assertFalse(evidence["parity_pass"])
        self.assertEqual(evidence["overall_status"], "FAIL")
        self.assertFalse(evidence["full_gateway_parity_claimed"])
        self.assertEqual(evidence["oracle"]["sha256"], ORACLE_SHA256)
        self.assertEqual(evidence["baseline_reference_commit"], BASELINE_COMMIT)
        documented = {case["name"]: case for case in evidence["cases"]}
        self.assertEqual(
            set(documented), {"deepseek_empty_home", "deepseek_profileless_codex_config"},
        )
        for name, record in documented.items():
            with self.subTest(case=name):
                baseline = self.cases[name]
                actual = run_case(baseline)
                self.assertEqual(record["status"], "FAIL")
                self.assertEqual(record["baseline"]["filesystem_delta"], baseline["filesystem_delta"])
                self.assertEqual(record["modex"]["filesystem_delta"], actual["filesystem_delta"])
                self.assertEqual(
                    record["filesystem_mismatches"],
                    filesystem_mismatches(baseline["filesystem_delta"], actual["filesystem_delta"]),
                )
                self.assertEqual(
                    record["missing_artifacts"], EXPECTED_STARTUP_MISSING_ARTIFACTS[name],
                )
                self.assertEqual(record["modex"]["returncode"], actual["returncode"])
                self.assertEqual(record["modex"]["stdout"], actual["stdout"])
                self.assertEqual(record["modex"]["stderr"], actual["stderr"])
                self.assertEqual(record["modex"]["upstream_requests"], actual["upstream_requests"])
                self.assertEqual(
                    record["comparisons"],
                    {
                        "exit_code": "PASS",
                        "stdout": "PASS",
                        "stderr": "PASS",
                        "upstream_requests": "PASS",
                        "filesystem_delta": "FAIL",
                    },
                )
                missing = [item for item in record["filesystem_mismatches"] if item["actual_after"] is None]
                self.assertEqual(
                    [
                        {
                            "path": item["path"],
                            "baseline_mode": mode_octal(item["baseline_after"]),
                            "baseline_size": item["baseline_after"]["size"],
                        }
                        for item in missing
                    ],
                    EXPECTED_STARTUP_MISSING_ARTIFACTS[name],
                )

    def test_group_writable_config_guard_remains_an_explicit_difference(self):
        report = json.loads((ROOT / "docs/evidence/gateway-permissions-mismatch.json").read_text(encoding="utf-8"))
        self.assertEqual(report["classification"], "UNAPPROVED_SAFE_DIFFERENCE")
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["parity_pass"])
        self.assertEqual(report["input_config_mode"], "0664")
        case = self.cases["deepseek_profileless_codex_config"]
        current = run_case(case, config_mode=0o664)
        self.assertEqual(current["returncode"], report["modex"]["returncode"])
        self.assertEqual(current["stderr"], report["modex"]["stderr"])
        self.assertEqual(current["upstream_requests"], [])
        self.assertNotEqual(current["stderr"], report["baseline"]["stderr"])


if __name__ == "__main__":
    unittest.main()
