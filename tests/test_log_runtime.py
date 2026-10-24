"""Black-box regressions for log last file limits and runtime event parsing."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def session_record(root, message):
    path = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"timestamp": "2026-10-24T01:02:03Z", "type": "session_meta",
                                "payload": {"id": "fixture", "cwd": str(root / "workspace")}}) + "\n" +
                    json.dumps({"timestamp": "2026-10-24T01:02:04Z", "type": "event_msg",
                                "payload": {"type": "user_message", "message": message}}) + "\n")


def token_event(value):
    return {"timestamp": "2026-10-24T01:02:04Z", "event": "token_usage", "fields": {
        "request": "7", "transport": "http", "profile": "main", "source": "responses",
        "input_tokens": value, "cached_input_tokens": "0", "output_tokens": "4",
        "reasoning_tokens": "1"}}


class LogRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def invoke(self, binary, prepare, *, arguments=None):
        with tempfile.TemporaryDirectory(prefix="modex-log-runtime-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            runtime = root / "runtime"
            runtime.mkdir()
            prepare(root, runtime)
            result = subprocess.run(sandbox_command(
                binary, root, arguments or ["log", "last", "--json"],
                argv0="prodex" if binary == ORACLE else "modex",
                environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(runtime)}),
                capture_output=True, timeout=10, check=False)
            return result.returncode, result.stdout, result.stderr

    def assert_matches_oracle(self, prepare):
        expected = self.invoke(ORACLE, prepare)
        actual = self.invoke(MODEX, prepare)
        self.assertEqual(actual, expected)
        return expected

    def test_reads_valid_final_session_event_after_two_mib(self):
        def prepare(root, runtime):
            path = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
            path.parent.mkdir(parents=True)
            filler = json.dumps({"timestamp": "2026-10-24T01:00:00Z", "type": "other", "payload": "x" * 4096})
            meta = {"timestamp": "2026-10-24T01:02:03Z", "type": "session_meta",
                    "payload": {"id": "fixture", "cwd": str(root / "workspace")}}
            final = {"timestamp": "2026-10-24T01:02:04Z", "type": "event_msg",
                     "payload": {"type": "user_message", "message": "final-session-event"}}
            path.write_text(json.dumps(meta) + "\n" + (filler + "\n") * 520 + json.dumps(final) + "\n")
        result = self.assert_matches_oracle(prepare)
        self.assertIn(b"final-session-event", result[1])

    def test_reads_valid_final_runtime_event_after_one_mib(self):
        def prepare(root, runtime):
            path = runtime / "prodex-runtime-fixture.log"
            filler = json.dumps({"timestamp": "2026-10-24T01:00:00Z", "event": "other", "fields": {"x": "y" * 4096}})
            path.write_text((filler + "\n") * 260 + json.dumps(token_event("12")) + "\n")
            session_record(root, "runtime-limit-session")
        self.assert_matches_oracle(prepare)

    def test_session_same_millisecond_mtimes_sort_ascending_by_path(self):
        def prepare(root, runtime):
            for name, message in (("a.jsonl", "path-a"), ("z.jsonl", "path-z")):
                path = root / "home/.codex/sessions/2026/10/24" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"timestamp": "2026-10-24T01:02:03Z", "type": "session_meta",
                                            "payload": {"id": name, "cwd": str(root / "workspace")}}) + "\n" +
                                json.dumps({"timestamp": "2026-10-24T01:02:04Z", "type": "event_msg",
                                            "payload": {"type": "user_message", "message": message}}) + "\n")
                ns = 1_798_000_000_123_100_000 if name.startswith("a") else 1_798_000_000_123_900_000
                os.utime(path, ns=(ns, ns))
        result = self.assert_matches_oracle(prepare)
        self.assertIn(b"path-a", result[1])

    def test_runtime_equal_mtimes_sort_descending_by_path(self):
        def prepare(root, runtime):
            for name, count in (("a.log", "11"), ("z.log", "22")):
                path = runtime / ("prodex-runtime-" + name)
                path.write_text(json.dumps(token_event(count)) + "\n")
                ns = 1_798_000_000_123_000_000
                os.utime(path, ns=(ns, ns))
            session_record(root, "runtime-order-session")
        result = self.assert_matches_oracle(prepare)
        self.assertIn(b'"input_tokens":11', result[1])

    def test_invalid_base64_payload_is_ignored(self):
        def prepare(root, runtime):
            event = {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": {
                "request": "7", "transport": "http", "route": "responses", "profile": "main",
                "bytes": "5", "logged_bytes": "5", "truncated": "false", "payload_b64": "aGVsbG8==="}}
            (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(event) + "\n")
            session_record(root, "invalid-base64-session")
        self.assert_matches_oracle(prepare)

    def test_upstream_payload_requires_payload_b64(self):
        def prepare(root, runtime):
            event = {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": {
                "request": "7", "transport": "http", "route": "responses", "profile": "main",
                "bytes": "5", "logged_bytes": "5", "truncated": "false",
                "payload": "aGVsbG8=", "payload_text": "hello"}}
            (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(event) + "\n")
            session_record(root, "payload-field-session")
        self.assert_matches_oracle(prepare)

    def test_malformed_input_token_count_rejects_runtime_record(self):
        def prepare(root, runtime):
            (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(token_event('1,"injected":true')) + "\n")
            session_record(root, "malformed-token-session")
        self.assert_matches_oracle(prepare)

    def test_token_defaults_rates_and_plain_metadata(self):
        cases = [
            {"input_tokens": "1"},
            {"input_tokens": 1, "output_tokens": 2},
            {"input_tokens": "0", "output_tokens": "0", "generation_ms": "1"},
            {"input_tokens": "+0001", "output_tokens": "+0002", "generation_ms": "+01000"},
            {"input_tokens": "18446744073709551615", "output_tokens": "18446744073709551615", "generation_ms": "1"},
            {"input_tokens": "1", "output_tokens": "2", "generation_ms": "3"},
            {"input_tokens": "1", "output_tokens": "2", "generation_ms": "1000", "output_tokens_per_second": "NaN"},
            {"input_tokens": "1", "output_tokens": "2", "generation_ms": "1000", "output_tokens_per_second": "+.5e1"},
            {"input_tokens": "1", "output_tokens": "2", "generation_ms": "0", "request": "invalid", "profile": ""},
            {"input_tokens": "1", "cached_input_tokens": "bad", "reasoning_tokens": "-1"},
        ]
        for fields in cases:
            def prepare(root, runtime):
                record = {"timestamp": "2026-10-24T01:02:04Z", "event": "token_usage", "fields": fields}
                (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(record) + "\n")
            for arguments in (["log", "last", "--json"], ["log", "last"]):
                with self.subTest(fields=fields, arguments=arguments):
                    self.assertEqual(self.invoke(MODEX, prepare, arguments=arguments),
                                     self.invoke(ORACLE, prepare, arguments=arguments))

    def test_duplicate_runtime_keys_keep_last_non_scalar_value(self):
        for last in ("null", "[]", "{}", '"2"'):
            def prepare(root, runtime):
                wire = '{"event":"token_usage","fields":{"input_tokens":"1","input_tokens":' + last + '}}\n'
                (runtime / "prodex-runtime-fixture.log").write_text(wire)
            with self.subTest(last=last):
                self.assert_matches_oracle(prepare)


if __name__ == "__main__":
    unittest.main()
