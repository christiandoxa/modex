"""Compare streamed DeepSeek function calls with Prodex 0.166.0."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes


def require_isolated_namespace():
    def ip_output(*arguments):
        try:
            return subprocess.run(
                ["ip", *arguments], check=True, capture_output=True, text=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise AssertionError("manual oracle test requires verifiable iproute2 state") from error

    interfaces = []
    for line in ip_output("-o", "link", "show").splitlines():
        fields = line.split(": ", 2)
        if len(fields) != 3:
            raise AssertionError("manual oracle test could not parse ip -o link output")
        interfaces.append(fields[1].split("@", 1)[0])
    if interfaces != ["lo"]:
        raise AssertionError("manual oracle test requires loopback as the only network interface")
    if ip_output("route", "show", "default").strip():
        raise AssertionError("manual oracle test requires no IPv4 default route")
    if ip_output("-6", "route", "show", "default").strip():
        raise AssertionError("manual oracle test requires no IPv6 default route")

    temporary = Path("/tmp")
    if temporary.resolve(strict=True) != temporary:
        raise AssertionError("manual oracle test requires a private /tmp mount")
    temporary_metadata = temporary.stat()
    if temporary_metadata.st_uid != os.getuid() or temporary_metadata.st_mode & 0o777 != 0o700:
        raise AssertionError("manual oracle test requires /tmp owned by this user with mode 700")
    mount_rows = [line.split() for line in Path("/proc/self/mounts").read_text().splitlines()]
    if not any(len(row) >= 3 and row[1] == "/tmp" and row[2] == "tmpfs" for row in mount_rows):
        raise AssertionError("manual oracle test requires /tmp to be a tmpfs mount")

    def require_private_directory(variable):
        configured = os.environ.get(variable)
        if not configured:
            raise AssertionError(f"manual oracle test requires {variable} inside private /tmp")
        path = Path(configured)
        try:
            resolved = path.resolve(strict=True)
            relative = resolved.relative_to(temporary)
        except (OSError, ValueError) as error:
            raise AssertionError(f"manual oracle test requires {variable} inside private /tmp") from error
        if not path.is_absolute() or path != resolved or not relative.parts:
            raise AssertionError(f"manual oracle test requires {variable} inside private /tmp")
        metadata = resolved.stat()
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o777 != 0o700:
            raise AssertionError(f"manual oracle test requires {variable} owned by this user with mode 700")
        return resolved

    home = require_private_directory("HOME")
    tempdir = require_private_directory("TMPDIR")
    if home == tempdir:
        raise AssertionError("manual oracle test requires distinct HOME and TMPDIR directories")


def streamed_tool_reply():
    def frame(delta, finish_reason=None, *, choices=True, usage=None):
        chunk = {
            "id": "synthetic-tool-stream",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "deepseek-chat",
            "choices": ([{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }] if choices else []),
        }
        if usage is not None:
            chunk["usage"] = usage
        return b"data: " + json_bytes(chunk) + b"\n\n"

    body = b"".join((
        frame({"role": "assistant"}),
        frame({"tool_calls": [{
            "index": 0,
            "id": "call_synthetic_tool",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"query":'},
        }]}),
        frame({"tool_calls": [{
            "index": 0,
            "function": {"arguments": '"synthetic"}'},
        }]}),
        frame({}, "tool_calls"),
        frame({}, choices=False, usage={
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "total_tokens": 7,
        }),
        b"data: [DONE]\n\n",
    ))
    return {"status": 200, "content_type": "text/event-stream", "body": body}


class DeepSeekToolStream01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_namespace()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_fragmented_function_call_stream_matches_active_release(self):
        turn = {
            "model": "deepseek-chat",
            "input": "synthetic streamed tool",
            "stream": True,
            "tools": [{
                "type": "function",
                "name": "lookup",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }],
        }
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, [turn], [streamed_tool_reply()], latest_version="0.166.0",
            )
            self.assertEqual(len(upstream), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0]["status"], 200)
            self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
            self.assertEqual(upstream[0]["headers"]["authorization"],
                             "Bearer " + SYNTHETIC_API_KEY)
            self.assertEqual(json.loads(upstream[0]["body"]), {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "synthetic streamed tool"}],
                "stream": True,
                "stream_options": {"include_usage": True},
                "tools": [{"type": "function", "function": {
                    "name": "lookup",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                }}],
            })
            body = bytes.fromhex(responses[0]["body"])
            headers = {name.lower(): value for name, value in responses[0]["headers"].items()}
            self.assertIn("text/event-stream", headers.get("content-type", ""))
            observations.append(body)

        self.assertEqual(observations[0], observations[1])
        frames = []
        event = None
        for line in observations[0].splitlines():
            if line.startswith(b"event: "):
                event = line[7:].decode()
            elif event and line.startswith(b"data: "):
                frames.append((event, json.loads(line[6:])))
                event = None
        self.assertEqual([name for name, _ in frames], [
            "response.created",
            "response.output_item.added",
            "response.function_call_arguments.delta",
            "response.function_call_arguments.delta",
            "response.output_item.done",
            "response.completed",
        ])
        self.assertEqual([frame["delta"] for name, frame in frames
                          if name == "response.function_call_arguments.delta"],
                         ['{"query":', '"synthetic"}'])
        completed = frames[-1][1]["response"]
        self.assertEqual(completed["output"], [{
            "type": "function_call",
            "call_id": "call_synthetic_tool",
            "name": "lookup",
            "arguments": '{"query":"synthetic"}',
        }])
        self.assertEqual(completed["usage"], {
            "input_tokens": 3, "output_tokens": 4, "total_tokens": 7,
        })


if __name__ == "__main__":
    unittest.main()
