"""Native loopback regression for source-traced DeepSeek call-ID mapping."""

import json
import unittest

import test_provider_deepseek_transport as transport
from test_local_rewrite import json_bytes, serving


class ProviderRequestMessagesTests(unittest.TestCase):
    def test_continuation_output_keeps_matching_history_with_default_call_id(self):
        history = [{"role": "assistant", "content": "", "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }]}]
        request = {"model": "deepseek-chat", "previous_response_id": "resp_previous",
                   "input": [{"type": "function_call_output", "call_id": None,
                              "tool_call_id": "call_alias", "output": "ok"}]}
        reply = {"status": 200, "content_type": "application/json", "body": json_bytes({
            "id": "synthetic-chat", "created": 42, "choices": [{
                "message": {"role": "assistant", "content": "synthetic"}, "finish_reason": "stop",
            }],
        })}
        with serving([reply]) as server:
            output, _, _ = transport.ProviderDeepSeekTransportTests().run_native(
                server, {"request": request, "history": history},
            )
        self.assertEqual(len(server.records), 1)
        sent = server.records[0]
        self.assertEqual(sent["path"], "/v1/chat/completions")
        self.assertEqual(sent["headers"]["authorization"], "Bearer synthetic-provider-key")
        self.assertEqual(json.loads(sent["body"])["messages"], history + [
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ])
        self.assertEqual([record["type"] for record in output], ["headers", "buffered", "done"])


if __name__ == "__main__":
    unittest.main()
