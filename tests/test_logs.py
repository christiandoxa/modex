"""Black-box comparisons for the detached log snapshot command."""

import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE, ROOT


def run(binary, arguments, *, runtime_dir=None):
    directory = tempfile.TemporaryDirectory(prefix="modex-log-test-")
    root = Path(directory.name)
    (root / "home").mkdir(mode=0o700)
    (root / "workspace").mkdir()
    environment = {"TZ": "UTC"}
    if runtime_dir is not None:
        environment["PRODEX_RUNTIME_LOG_DIR"] = str(runtime_dir)
    result = subprocess.run(sandbox_command(binary, root, arguments, argv0="prodex" if binary == ORACLE else "modex",
                                            environment=environment), capture_output=True, timeout=10, check=False)
    created = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                     if path not in (root / "home", root / "workspace"))
    directory.cleanup()
    return result, created


def session_fixture(root, message):
    path = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(value) for value in (
        {"timestamp": "2026-10-24T01:02:03Z", "type": "session_meta", "payload": {
            "id": "fixture", "cwd": str(root / "workspace")}},
        {"timestamp": "2026-10-24T01:02:04Z", "type": "event_msg", "payload": {
            "type": "user_message", "message": message}},
    )) + "\n")


class LogLastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_empty_text_and_json_match_release_and_create_private_root(self):
        for arguments in (["log", "last"], ["log", "last", "--json"], ["log", "--json", "last"]):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = run(ORACLE, arguments)
                modex, modex_created = run(MODEX, arguments)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual(baseline_created, ["home/.prodex"])
                self.assertEqual(modex_created, baseline_created)

    def test_transcript_json_and_native_redaction_match_release(self):
        sentinel = "synthetic-secret-token"
        outputs = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-log-transcript-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                session_fixture(root, "Authorization: Bearer " + sentinel)
                result = subprocess.run(sandbox_command(binary, root, ["log", "last", "--json"],
                                                        argv0="prodex" if binary == ORACLE else "modex",
                                                        environment={"TZ": "UTC"}),
                                        capture_output=True, timeout=10, check=False)
                outputs.append(result)
                self.assertEqual(result.returncode, 0)
                self.assertNotIn(sentinel.encode(), result.stdout)
                self.assertNotIn(sentinel.encode(), result.stderr)
        self.assertEqual((outputs[1].stdout, outputs[1].stderr),
                         (outputs[0].stdout, outputs[0].stderr))

    def test_transcript_text_matches_release(self):
        outputs = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-log-text-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                session_fixture(root, "synthetic hello")
                result = subprocess.run(sandbox_command(binary, root, ["log", "last"],
                                                        argv0="prodex" if binary == ORACLE else "modex",
                                                        environment={"TZ": "UTC"}),
                                        capture_output=True, timeout=10, check=False)
                outputs.append(result)
        self.assertEqual((outputs[1].returncode, outputs[1].stdout, outputs[1].stderr),
                         (outputs[0].returncode, outputs[0].stdout, outputs[0].stderr))

    def test_argument_diagnostics_match_release(self):
        for arguments in (["log", "invalid"], ["log", "last", "--invalid"],
                          ["log", "last", "--json", "--json"]):
            with self.subTest(arguments=arguments):
                baseline, _ = run(ORACLE, arguments)
                modex, _ = run(MODEX, arguments)
                expected_stderr = baseline.stderr.replace(b"prodex log", b"modex log")
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, expected_stderr))

    def test_unsafe_existing_app_root_reports_known_repair_gap(self):
        results = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-log-root-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "home/.prodex").mkdir(mode=0o755)
                (root / "home/.prodex").chmod(0o755)
                self.assertEqual((root / "home/.prodex").stat().st_mode & 0o777, 0o755)
                (root / "workspace").mkdir()
                result = subprocess.run(sandbox_command(binary, root, ["log", "last", "--json"],
                                                        argv0="prodex" if binary == ORACLE else "modex",
                                                        environment={"TZ": "UTC"}),
                                        capture_output=True, timeout=10, check=False)
                results.append((result.returncode, result.stderr))
        self.assertEqual(results[0], (0, b""))
        self.assertEqual(results[1], (1, b"Error: secure application-directory permission repair is not implemented\n"))

    def test_runtime_upstream_and_token_events_match_release(self):
        records = [
            {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": {
                "request": "7", "transport": "http", "route": "responses", "profile": "main",
                "bytes": "10", "logged_bytes": "10", "truncated": "false",
                "payload_b64": base64.b64encode(b'{"input":"hello"}').decode()}},
            {"timestamp": "2026-10-24T01:02:05Z", "event": "token_usage", "fields": {
                "request": "7", "transport": "http", "profile": "main", "source": "responses",
                "input_tokens": "12", "cached_input_tokens": "3", "output_tokens": "4",
                "reasoning_tokens": "1"}},
        ]
        outputs = []
        for binary in (ORACLE, MODEX):
            with tempfile.TemporaryDirectory(prefix="modex-log-runtime-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                runtime = root / "runtime"
                runtime.mkdir()
                (runtime / "prodex-runtime-fixture.log").write_text("\n".join(map(json.dumps, records)) + "\n")
                result = subprocess.run(sandbox_command(binary, root, ["log", "last", "--json"],
                                                        argv0="prodex" if binary == ORACLE else "modex",
                                                        environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(runtime)}),
                                        capture_output=True, timeout=10, check=False)
                outputs.append(result)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((outputs[1].stdout, outputs[1].stderr),
                         (outputs[0].stdout, outputs[0].stderr))


if __name__ == "__main__":
    unittest.main()
