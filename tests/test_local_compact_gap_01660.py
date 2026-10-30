"""Differentially verify DeepSeek's local compact fallback against 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns


class LocalCompactGap01660Tests(unittest.TestCase):
    def test_compact_fallback_matches_active_baseline(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        retained_input = [
            {"type": "message", "role": "user", "content": f"message-{index}"}
            for index in range(26)
        ]
        cases = [
            {"model": "deepseek-chat", "input": []},
            {"model": "deepseek-chat", "input": [{
                "type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "synthetic compact message"},
                ],
            }]},
            {"model": "deepseek-chat", "input": [
                {"type": "message", "content": "   ", "text": "must not surface"},
                "plain input", 17, None,
                {"type": "function_call", "name": "run", "call_id": "c1",
                 "arguments": {"command": "ignored", "text": "selected"}},
                {"type": "function_call_output", "call_id": "c2",
                 "output": ["first", {"text": "second"}, "   "]},
                {"type": "custom_tool_call", "name": "patch", "call_id": "c3", "input": "diff"},
                {"type": "local_shell_call", "call_id": "c4", "action": {"commands": ["pwd", "ls"]}},
                {"type": "web_search_call", "action": {"query": "mojo"}},
                {"type": "reasoning", "summary": "think"},
                {"type": "reasoning", "summary": "   ", "text": "must not surface"},
                {"type": "other", "payload": {"query": "nested state"}},
            ]},
            {"model": "deepseek-chat", "input": retained_input},
            {"model": "deepseek-chat", "input": [{
                "type": "message", "role": "user", "content": "月" * 1_000,
            }]},
            {"model": "月" * 9_000, "input": []},
            {"model": (" " * (4 * 1024 * 1024)) + ("月" * 9_000) + (" " * (4 * 1024 * 1024)), "input": []},
            {"model": "deepseek-chat", "input": [], "_raw_body": "not-json"},
        ]
        nested = {"text": "deep nested state"}
        for _ in range(96):
            nested = [nested]
        cases.append({"model": "deepseek-chat", "input": [{"type": "other", "payload": nested}]})
        large_collection = [
            {"type": "message", "role": "user", "content": f"large-{index:05d}"}
            for index in range(20_000)
        ]
        cases.append({"model": "deepseek-chat", "input": large_collection})
        turns = [dict(case, _path="/v1/responses/compact") for case in cases]
        observed = {}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [], latest_version="0.166.0", concurrent=True,
                )
                self.assertEqual(upstream, [])
                self.assertEqual(len(responses), len(cases))
                observed[binary] = responses

        baseline_responses = observed[ORACLE]
        modex_responses = observed[MODEX]
        for baseline, modex in zip(baseline_responses, modex_responses):
            self.assertEqual(modex["status"], baseline["status"])
            self.assertEqual(json.loads(bytes.fromhex(modex["body"])),
                             json.loads(bytes.fromhex(baseline["body"])))
            for response in (baseline, modex):
                headers = {name.lower(): value for name, value in response["headers"].items()}
                self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
                self.assertEqual(headers["x-prodex-compact-mode"], "local-fallback")
                self.assertEqual(headers["x-prodex-compact-provider"], "deepseek")
                self.assertEqual(headers["x-prodex-compact-degraded"], "true")
                self.assertEqual(headers["x-prodex-compact-reason"], "local-policy")

        def summary(response):
            text = json.loads(bytes.fromhex(response["body"]))["output"][0]["content"][0]["text"]
            return text.split("\n\n", 1)[1]

        self.assertIn("Original input items: 0\nRetained recent items: 0", summary(modex_responses[0]))
        self.assertIn("user message: synthetic compact message", summary(modex_responses[1]))
        nested = summary(modex_responses[2])
        self.assertIn("unknown message with no text content", nested)
        self.assertNotIn("must not surface", nested)
        self.assertNotIn("plain input", nested)
        self.assertNotIn("17", nested)
        self.assertNotIn("tool call run (c1): ignored", nested)
        self.assertIn("tool call run (c1): selected", nested)
        self.assertIn("tool output c2: first\n  second", nested)
        self.assertIn("custom tool call patch (c3): diff", nested)
        self.assertIn("local shell call c4: pwd\n  ls", nested)
        self.assertIn("web search: mojo", nested)
        self.assertIn("reasoning summary: think", nested)
        self.assertNotIn("must not surface", nested)
        self.assertIn("other: nested state", nested)
        retained = summary(modex_responses[3])
        self.assertIn("Original input items: 26\nRetained recent items: 24", retained)
        self.assertNotIn("- user message: message-0\n", retained)
        self.assertNotIn("- user message: message-1\n", retained)
        self.assertIn("message-2", retained)
        self.assertIn("message-25", retained)
        long_snippet = summary(modex_responses[4]).split("Recent conversation and tool state:\n", 1)[1].strip()
        self.assertTrue(long_snippet.endswith("[truncated]"))
        snippet_text = long_snippet.removeprefix("- ").replace("\n  ", "\n")
        self.assertLessEqual(len(snippet_text.encode()), 768)
        long_summary = summary(modex_responses[5])
        self.assertLessEqual(len(long_summary.encode()), 24 * 1024)
        self.assertTrue(long_summary.endswith("[truncated]"))
        large_model_summary = summary(modex_responses[6])
        self.assertLessEqual(len(large_model_summary.encode()), 24 * 1024)
        self.assertIn("\n\nModel: 月", large_model_summary)
        self.assertTrue(large_model_summary.endswith("[truncated]"))
        self.assertEqual(summary(modex_responses[7]),
                         "Local Prodex compact fallback could not parse the compact request body.")
        self.assertIn("other: deep nested state", summary(modex_responses[8]))
        large_collection_summary = summary(modex_responses[9])
        self.assertIn("Original input items: 20000\nRetained recent items: 24", large_collection_summary)
        self.assertNotIn("- user message: large-00000\n", large_collection_summary)
        self.assertIn("- user message: large-19976\n", large_collection_summary)
        self.assertIn("- user message: large-19999", large_collection_summary)

    def test_route_controls_match_active_baseline(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        turns = [
            {"model": "deepseek-chat", "input": ["x"],
             "_path": "/v1/responses/compact?synthetic=1"},
            {"model": "deepseek-chat", "input": ["x"],
             "_path": "/v1/responses/compact", "_method": "GET"},
            {"model": "deepseek-chat", "input": ["x"],
             "_path": "/v1/responses/compact/extra"},
            {"model": "deepseek-chat", "input": [{"type": "message", "content": "x"}],
             "_path": "/v1/responses/compact",
             "_headers": {"Authorization": "Bearer synthetic-invalid-token"}},
        ]
        observed = {}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [], latest_version="0.166.0", concurrent=True,
                )
                self.assertEqual(upstream, [])
                self.assertEqual(len(responses), len(turns))
                observed[binary] = responses
        baseline_responses = observed[ORACLE]
        modex_responses = observed[MODEX]
        for baseline, modex in zip(baseline_responses[:3], modex_responses[:3]):
            self.assertEqual((modex["status"], modex["body"]),
                             (baseline["status"], baseline["body"]))
        self.assertEqual(modex_responses[0]["status"], 200)
        self.assertEqual(modex_responses[1]["status"], 200)
        self.assertEqual(modex_responses[2]["status"], 404)
        self.assertEqual(modex_responses[3]["status"], 401)
        # The active release lacks this Modex client-token boundary.
        self.assertEqual(baseline_responses[3]["status"], 200)


if __name__ == "__main__":
    unittest.main()
