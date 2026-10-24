"""Compose native SSE assembly and chat chunk decoding without provider traffic."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_provider_sse import run


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/provider_chat_chunk_driver"


class ProviderChatSSETests(unittest.TestCase):
    def test_chat_decoder_with_only_its_native_runtime_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="modex-provider-chat-runtime-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            result = subprocess.run(sandbox_command(DRIVER, root, []),
                                    input=b'{"error":{"code":429,"detail":"retry later"}}\n',
                                    capture_output=True, timeout=10, check=False)
            self.assertEqual((result.returncode, result.stderr), (0, b""))
            self.assertEqual(json.loads(result.stdout), {
                "choice": None,
                "metadata": {"finish_reason": None, "logprobs": None},
                "delta": {"annotations": [], "content": None, "reasoning_content": None,
                          "refusal": None, "tool_calls": []},
                "error": {"code": "429", "message": "retry later"},
            })

    def test_fragmented_sse_values_reach_native_chat_decoder(self):
        delta = {"reasoning_content": "reason", "refusal": "refusal", "annotations": [],
                 "content": "héllo", "tool_calls": [{"index": 0, "unknown": True}]}
        choice = {"delta": delta, "logprobs": {"token": -2}, "finish_reason": "stop",
                  "unknown": "preserved in the raw choice"}
        chunk = {"choices": [choice, {"delta": {"content": "ignored"}}]}
        source = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
        split = source.index('"delta"')
        payload = ("data: " + source[:split] + "\ndata: " + source[split:]
                   + "\n\ndata: [DONE]\n\n").encode() + b"data: \xff\n\n"
        cut = payload.index("é".encode()) + 1
        _, records = run("json", payload, chunks=[payload[:cut], payload[cut:]])
        self.assertEqual(records[-1], ("EOF", None))
        values = [value for kind, value in records if kind == "VALUE"]
        self.assertEqual([json.loads(value) for value in values], [chunk])

        # Reframe the assembled values onto the test driver's JSONL transport.
        lines = [json.dumps(json.loads(value), ensure_ascii=False) for value in values]
        result = subprocess.run([str(DRIVER)], input=("\n".join(lines) + "\n").encode(),
                                capture_output=True, timeout=10, check=False)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual([json.loads(line) for line in result.stdout.splitlines()], [{
            "choice": choice,
            "metadata": {"logprobs": {"token": -2}, "finish_reason": "stop"},
            "delta": delta,
            "error": None,
        }])


if __name__ == "__main__":
    unittest.main()
