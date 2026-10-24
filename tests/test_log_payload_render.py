"""Payload presentation checks and frozen release comparisons."""

import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_cli import MODEX, ORACLE, ROOT

DRIVER = ROOT / "build/tests/log_payload_render_driver"


def render(payload, width=88):
    result = subprocess.run([str(DRIVER)], input=(str(width) + "\n").encode() + payload.encode(),
                            capture_output=True, check=True)
    return [json.loads(line) for line in result.stdout.splitlines()]


def log_last(binary, payload):
    with tempfile.TemporaryDirectory(prefix="modex-log-payload-render-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        runtime = root / "runtime"
        runtime.mkdir()
        payload_bytes = payload.encode()
        record = {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": {
            "request": "7", "transport": "http", "route": "responses", "profile": "main",
            "bytes": str(len(payload_bytes)), "logged_bytes": str(len(payload_bytes)),
            "truncated": "false", "payload_b64": base64.b64encode(payload_bytes).decode()}}
        (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(record) + "\n")
        command = sandbox_command(binary, root, ["log", "last"], argv0="prodex" if binary == ORACLE else "modex",
                                 environment={"PRODEX_RUNTIME_LOG_DIR": str(runtime), "PRODEX_TERM_COLUMNS": "88"})
        return subprocess.run(command, capture_output=True, timeout=10, check=False)


class LogPayloadRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_cli
        test_cli.CliTests.setUpClass()

    def test_structured_payload(self):
        payload = json.dumps({
            "model": "gpt-5-codex", "stream": True,
            "client_metadata": {"session_id": "session-1", "thread_id": "thread-1", "turn_id": "turn-1"},
            "input": [
                {"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "inspect the runtime log"}]},
                {"type": "function_call", "name": "exec_command", "arguments": "{\"cmd\":\"pwd\"}"}],
            "tools": [{"name": "exec_command"}, {"function": {"name": "view_image"}}],
        }, separators=(",", ":"))
        lines = render(payload)
        self.assertEqual(lines[0], "model=gpt-5-codex stream=true input_items=2 tools=2")
        self.assertEqual(lines[1], "client_metadata: session_id=session-1 thread_id=thread-1 turn_id=turn-1")
        self.assertIn("input[0] user:", lines)
        self.assertTrue(any(line.strip() == "inspect the runtime log" for line in lines))
        self.assertIn("input[1] tool-call:exec_command:", lines)
        self.assertTrue(any('"cmd": "pwd"' in line for line in lines))
        self.assertEqual(lines[-1], "tools: 2 exec_command, view_image")

    def test_pretty_fallback_and_json_string_arguments(self):
        self.assertEqual(render('{"outer":{"inner":"value"}}'), [
            "{", '"outer": {', '"inner": "value"', "}", "}"])
        payload = '{"input":[{"type":"function_call","name":"f","arguments":"{\\"x\\":1}"}]}'
        self.assertTrue(any('"x": 1' in line for line in render(payload)))

    def test_runtime_payload_display_matches_frozen_release(self):
        payload = json.dumps({"model": "fixture", "input": "hello"}, separators=(",", ":"))
        expected = log_last(ORACLE, payload)
        actual = log_last(MODEX, payload)
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                         (expected.returncode, expected.stdout, expected.stderr))


if __name__ == "__main__":
    unittest.main()
