"""Transcript text projection checks and frozen release comparisons."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import ORACLE, ROOT


DRIVER = ROOT / "build/tests/log_text_driver"


def projection(method, text):
    request = json.dumps({"method": method, "text": text}, ensure_ascii=False) + "\n"
    result = subprocess.run([str(DRIVER)], input=request.encode(), capture_output=True,
                            timeout=10, check=False)
    if result.returncode != 0 or result.stderr:
        raise AssertionError((result.returncode, result.stderr.decode()))
    return json.loads(result.stdout)


def oracle_log_last(record_type, payload):
    with tempfile.TemporaryDirectory(prefix="modex-log-text-oracle-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        session = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
        session.parent.mkdir(parents=True)
        session.write_text(json.dumps({
            "timestamp": "2026-10-24T01:02:04Z",
            "type": record_type,
            "payload": payload,
        }, ensure_ascii=False) + "\n")
        result = subprocess.run(
            sandbox_command(ORACLE, root, ["log", "last", "--json"],
                            argv0="prodex", environment={"TZ": "UTC"}),
            capture_output=True, timeout=10, check=False,
        )
        if result.returncode != 0 or result.stderr:
            raise AssertionError((result.returncode, result.stderr.decode()))
        return [json.loads(line) for line in result.stdout.splitlines()]


class LogTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if not DRIVER.is_file():
            raise AssertionError("Build the log text driver with make unit")

    def test_safe_text_redacts_controls_and_bounds_utf8(self):
        self.assertEqual(projection("safe", 'api_key="synthetic-secret"\0\t表🙂'),
                         'api_key="<redacted>" \t表🙂')
        self.assertEqual(projection("safe", "a\u0085b\x7fc"), "a b c")
        text = "é" * 40_000
        result = projection("safe", text)
        self.assertTrue(result.endswith(" …[truncated]"))
        self.assertLessEqual(len(result.encode()), 65_536)
        self.assertTrue(result.endswith("é" * 7 + " …[truncated]"))

    def test_message_visibility_filters_attachment_paths_and_preserves_spacing(self):
        message = (
            "please compare  \n\n"
            "/home/test-user/.prodex/profiles/.prodex-overlay-123/attachments/a.png\n"
            "then summarize   \n"
        )
        self.assertEqual(projection("message", message), "please compare\n\nthen summarize")
        self.assertEqual(projection("message", "before\rafter\n\r\nafter\r"),
                         "before\rafter\n\nafter")

    def test_tool_visibility_strips_ansi_normalizes_cr_and_suppresses_binary(self):
        value = "\x1b[31mred\x1b[0m\r\nnext\rrow"
        self.assertEqual(projection("tool", value), "red\nnext\nrow")
        self.assertEqual(projection("tool", "before\x1b]0;title\x07after"), "beforeafter")
        self.assertEqual(projection("tool", "before\x1b🙂after"), "beforeafter")
        self.assertEqual(projection("tool", "\uFFFD\uFFFD\uFFFD\0bad"), "")
        self.assertEqual(projection("tool", "a" * 4096 + "\0tail"), "a" * 4096 + "\0tail")
        self.assertEqual(projection("tool", "a" * 4095 + "\0tail"), "")

    def test_tool_names_and_operation_values_are_bounded_and_safe(self):
        self.assertEqual(projection("tool_name", "mcp.模型:call"), "mcp.__:call")
        self.assertEqual(projection("tool_name", ""), "tool")
        self.assertEqual(projection("tool_name", "x" * 120), "x" * 96)
        self.assertEqual(projection("operation", "  visible  "), "  visible  ")
        self.assertEqual(projection("operation", " 　\t "), "")
        self.assertEqual(projection("operation", "bad\x85value"), "")
        self.assertEqual(projection("operation", "a" * 191 + "é-tail"), "a" * 191 + "é…")

    def test_visibility_matches_frozen_log_last(self):
        message = (
            "please compare  \n\n"
            "/home/test-user/.prodex/profiles/.prodex-overlay-123/attachments/a.png\n"
            "then summarize   \n"
        )
        baseline = oracle_log_last("event_msg", {"type": "user_message", "message": message})
        self.assertEqual(baseline[0]["text"], projection("message", message))

        output = "\x1b[31mred\x1b[0m\r\nnext\rrow"
        baseline = oracle_log_last("response_item", {
            "type": "function_call_output", "output": output,
        })
        self.assertEqual(baseline[0]["text"], projection("tool", output))
        for binary_output in ("\uFFFD\uFFFD\uFFFD\0bad", "a" * 4095 + "\0tail"):
            self.assertEqual(oracle_log_last("response_item", {
                "type": "function_call_output", "output": binary_output,
            }), [])
        readable_boundary = "a" * 4096 + "\0tail"
        baseline = oracle_log_last("response_item", {
            "type": "function_call_output", "output": readable_boundary,
        })
        self.assertEqual(baseline[0]["text"], projection("safe", projection("tool", readable_boundary)))

        name = "mcp.模型:call"
        baseline = oracle_log_last("response_item", {
            "type": "function_call", "name": name, "arguments": "raw arguments",
        })
        self.assertEqual(baseline[0]["source"], "tool-call:" + projection("tool_name", name))
        self.assertEqual(baseline[0]["text"], projection("operation", "raw arguments"))

        status = "a" * 191 + "é-tail"
        baseline = oracle_log_last("event_msg", {
            "type": "mcp_tool_call", "server": "srv", "status": status,
            "phase": "ready",
        })
        self.assertEqual(
            baseline[0]["text"],
            "server=srv status=" + projection("operation", status) + " phase=ready",
        )


if __name__ == "__main__":
    unittest.main()
