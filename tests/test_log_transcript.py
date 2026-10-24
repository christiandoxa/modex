"""Focused frozen-oracle checks for session transcript projection."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cli
from test_cli import MODEX, ORACLE, ROOT
from session_oracle import sandbox_command

DRIVER = ROOT / "build/tests/log_transcript_driver"


def project(record_type, payload):
    line = json.dumps({"timestamp": "2026-10-24T01:02:04Z", "type": record_type,
                       "payload": payload}, ensure_ascii=False) + "\n"
    result = subprocess.run([str(DRIVER)], input=line.encode(), capture_output=True,
                            timeout=10, check=False)
    if result.returncode or result.stderr:
        raise AssertionError((result.returncode, result.stderr.decode()))
    return json.loads(result.stdout)


def oracle(record_type, payload, binary=ORACLE, json_output=True, columns="110"):
    with tempfile.TemporaryDirectory(prefix="modex-transcript-oracle-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        session = root / "home/.codex/sessions/2026/10/24/fixture.jsonl"
        session.parent.mkdir(parents=True)
        session.write_text(json.dumps({"timestamp": "2026-10-24T01:02:04Z", "type": record_type,
                                       "payload": payload}, ensure_ascii=False) + "\n")
        arguments = ["log", "last", "--json"] if json_output else ["log", "last"]
        result = subprocess.run(sandbox_command(binary, root, arguments,
                                                argv0="prodex" if binary == ORACLE else "modex",
                                                environment={"TZ": "UTC", "PRODEX_TERM_COLUMNS": columns}),
                                capture_output=True, timeout=10, check=False)
        if result.returncode or result.stderr:
            raise AssertionError((result.returncode, result.stderr.decode()))
        return [json.loads(line) for line in result.stdout.splitlines()] if json_output else result.stdout


class TranscriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if not DRIVER.is_file():
            raise AssertionError("Build the focused driver with the canonical test build first")

    def test_messages_context_and_tools_match_frozen_log_last(self):
        cases = [
            ("event_msg", {"type": "user_message", "message": "hello\n\nworld"}),
            ("event_msg", {"type": "agent_reasoning", "text": "considering"}),
            ("event_msg", {"type": "mcp_tool_call", "server": "srv", "tool": "search",
                           "status": "running", "phase": "lookup"}),
            ("event_msg", {"type": "turn_failed", "status": "failed", "reason": "synthetic"}),
            ("event_msg", {"type": "command_status_update", "status": "error", "stdout": ["line", 2]}),
            ("event_msg", {"type": "subagent_started"}),
            ("session_meta", {"provider": "openai", "source": "cli"}),
            ("turn_context", {"model": "gpt-test", "effort": "high", "cwd": "/tmp"}),
            ("response_item", {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "answer"}]}),
            ("response_item", {"type": "message", "role": "developer", "content": [
                {"type": "other", "content": "fallback text"},
                {"type": "input_text", "text": 7, "content": "presence blocks fallback"}]}),
            ("response_item", {"type": "function_call", "name": "shell.exec", "arguments": "{}"}),
            ("response_item", {"type": "custom_tool_call", "input": "query", "name": ""}),
            ("response_item", {"type": "custom_tool_call", "input": "query"}),
            ("response_item", {"type": "shell_call", "name": "runner", "arguments": "second", "action": "third"}),
            ("response_item", {"type": "function_call_output", "output": "done\n"}),
            ("response_item", {"type": "reasoning", "summary": [{"text": "step one"},
                                                                     {"summary_text": "step two"}]}),
            ("response_item", {"type": "web_search_call", "status": "completed"}),
        ]
        for record_type, payload in cases:
            with self.subTest(record_type=record_type, payload=payload):
                expected = oracle(record_type, payload)
                actual = project(record_type, payload)
                self.assertEqual(len(expected), 1)
                self.assertEqual(actual[1:], [expected[0]["source"], expected[0]["text"]])

    def test_unknown_and_invisible_records_are_skipped(self):
        self.assertIsNone(project("event_msg", {"type": "unrecognized", "message": "hidden"}))
        payload = {"type": "user_message", "message": "/home/test/.prodex/profiles/.prodex-overlay-x/attachments/a.png"}
        self.assertEqual(oracle("event_msg", payload), [])
        self.assertIsNone(project("event_msg", payload))

    def test_operation_shapes_and_presence_match_oracle(self):
        cases = [
            ("response_item", {"type": "shell_call", "name": "", "command": " x "}),
            ("response_item", {"type": "shell_call", "command": None, "arguments": "blocked fallback"}),
            ("response_item", {"type": "shell_call", "command": {"z": 1e0, "a": [1, True]}}),
            ("response_item", {"type": "shell_call_output", "output": {"z": 1, "a": 2}}),
            ("response_item", {"type": "shell_call_output", "output": "x" * 200}),
            ("response_item", {"type": "function_call_output", "stdout": "ignored"}),
            ("response_item", {"type": "custom_tool_call", "name": None, "input": "query"}),
            ("response_item", {"type": "message", "role": "", "content": [{"text": "visible"}]}),
            ("response_item", {"type": "reasoning", "summary": " leading \n\ntrailing "}),
            ("response_item", {"type": "tool_call_unknown", "status": "ignored"}),
            ("event_msg", {"type": "computer_call", "status": "ignored"}),
            ("event_msg", {"type": "command_status_update", "stdout": "\x1b[31mhidden", "output": {"b": 2, "a": 1}}),
        ]
        for kind, payload in cases:
            with self.subTest(kind=kind, payload=payload):
                expected = oracle(kind, payload)
                actual = project(kind, payload)
                self.assertEqual(actual[1:] if actual is not None else None,
                                 [expected[0]["source"], expected[0]["text"]] if expected else None)

    def test_production_json_and_plain_labels_match_oracle(self):
        cases = [
            ("session_meta", {"base_instructions": {"text": "synthetic instructions"}}),
            ("session_meta", {"provider": "fixture", "source": "cli"}),
            ("turn_context", {"model": "synthetic", "effort": "high"}),
            ("event_msg", {"type": "mcp_tool_call", "server": "fixture", "status": "ready"}),
            ("event_msg", {"type": "turn_failed", "exit_code": 1, "message": "synthetic failure"}),
            ("response_item", {"type": "function_call", "name": "fixture", "arguments": "{}"}),
            ("response_item", {"type": "function_call_output", "output": "synthetic output"}),
            ("response_item", {"type": "message", "role": "developer", "content": [{"text": "synthetic text"}]}),
        ]
        for kind, payload in cases:
            for output in (True, False):
                for columns in ("22", "88", "110"):
                    with self.subTest(kind=kind, payload=payload, json_output=output, columns=columns):
                        self.assertEqual(oracle(kind, payload, MODEX, output, columns),
                                         oracle(kind, payload, ORACLE, output, columns))
        for record_type, payload in [
            ("response_item", {"type": "function_call", "name": "json", "arguments": {"x": [1, True]}}),
            ("response_item", {"type": "custom_tool_call", "input": {"q": "synthetic"}}),
            ("response_item", {"type": "function_call_output", "output": {"secret": "value"}}),
            ("response_item", {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "internal"}],
             "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["user.image"]}}),
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(oracle(record_type, payload), [])
                self.assertIsNone(project(record_type, payload))


if __name__ == "__main__":
    unittest.main()
