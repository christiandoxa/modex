"""Process characterization for Anthropic search input streams on 0.166.0."""

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import unittest

from test_active_baseline_01660 import MODEX, ORACLE
from test_provider_tools_04392_characterization import _normalized_events, _run


ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"
REQUEST = {
    "model": "deepseek-chat",
    "input": "synthetic query",
    "stream": True,
    "tools": [{"type": "web_search_preview"}],
}
SEARCH_ID = "search_synthetic"


def search_events(initial_input, fragments, stop_before_fragments=False):
    events = [
        {"type": "message_start", "message": {
            "id": "msg_synthetic", "role": "assistant", "model": "deepseek-chat",
            "usage": {"input_tokens": 3, "output_tokens": 0},
        }},
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "server_tool_use", "id": SEARCH_ID, "name": "web_search",
            "input": initial_input,
        }},
    ]
    if stop_before_fragments:
        events.append({"type": "content_block_stop", "index": 0})
    for fragment in fragments:
        events.append({"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": fragment,
        }})
    if not stop_before_fragments:
        events.append({"type": "content_block_stop", "index": 0})
    events.extend((
        {"type": "content_block_start", "index": 1, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": SEARCH_ID,
            "content": [{"type": "web_search_result", "url": "https://example.test/release",
                         "title": "Release"}],
        }},
        {"type": "content_block_stop", "index": 1},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ))
    return events


def verify_oracle_context():
    if not ORACLE.is_absolute() or not ORACLE.is_file():
        raise AssertionError("PRODEX_ORACLE must be an absolute path to the 0.166.0 release binary")
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise AssertionError("The Prodex oracle does not match pinned release 0.166.0")
    if os.stat("/tmp").st_uid != os.geteuid() or not any(
        len(fields) > 2 and fields[1] == "/tmp" and fields[2] == "tmpfs"
        for fields in (line.split() for line in Path("/proc/mounts").read_text().splitlines())
    ):
        raise AssertionError("Run in a user-owned private tmpfs mounted at /tmp")
    temporary_root = Path("/tmp").resolve()
    for name in ("HOME", "TMPDIR"):
        directory = Path(os.environ.get(name, ""))
        try:
            directory.resolve().relative_to(temporary_root)
        except ValueError:
            raise AssertionError(f"{name} must stay inside private /tmp")
        if not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) != 0o700:
            raise AssertionError(f"{name} must be a private directory")
    for arguments in (
        ("-4", "route", "show", "default"),
        ("-6", "route", "show", "default"),
    ):
        result = subprocess.run(("/usr/sbin/ip", *arguments), capture_output=True, check=True)
        if result.stdout:
            raise AssertionError("Run without IPv4 or IPv6 default routes")
    interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    if interfaces != ["lo"]:
        raise AssertionError(f"Only loopback may exist in the network namespace: {interfaces}")
    links = subprocess.run(
        ("/usr/sbin/ip", "-o", "link", "show", "lo"),
        capture_output=True, text=True, check=True,
    ).stdout
    flags = links.split(":", 2)[2].split(">", 1)[0].split(",")
    if "UP" not in flags:
        raise AssertionError("Loopback must be enabled for the synthetic provider")


def oracle_run(events):
    verify_oracle_context()
    return _run(ORACLE, REQUEST, scenario="anthropic-custom-events", anthropic_events=events)


def completed_search_queries(result):
    events = _normalized_events(result["response_body"])
    for name, payload in events:
        item = payload.get("item", {})
        if name == "response.output_item.done" and item.get("type") == "web_search_call":
            return item["action"]["queries"]
    return []


class AnthropicStream01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_search_query_fragments_and_start_input_precedence(self):
        cases = (
            ("single fragment", {}, ('{"query":"release"}',), ["release"], False),
            ("split fragments", {}, ('{"que', 'ry":"release"}'), ["release"], False),
            # The same complete query appears in the start input and delta input.
            ("duplicate start and delta", {"query": "release"},
             ('{"query":"release"}',), ["release"], False),
            ("start query wins over different delta", {"query": "start"},
             ('{"query":"delta"}',), ["start"], False),
            ("start query wins over split delta fragments", {"query": "start"},
             ('{"query":', '"delta"}'), ["start"], False),
            ("truncated delta retains input bounds", {"query": "start"},
             ('{"query":',), [], False),
            ("missing start query ignores delta object", {"other": "start"},
             ('{"query":"delta"}',), [], False),
            ("null start query ignores delta object", {"query": None},
             ('{"query":"delta"}',), [], False),
            ("non-string start query ignores delta object", {"query": 7},
             ('{"query":"delta"}',), [], False),
            ("start query wins over consecutive delta objects", {"query": "start"},
             ('{"query":"first"}', '{"query":"second"}'), ["start"], False),
            ("first delta object wins over consecutive objects", {},
             ('{"query":"first"}', '{"query":"second"}'), ["first"], False),
            ("first object handles nested braces and quoted delimiters", {},
             (r'{"metadata":{"brace":"}\"{"},"query":"first"}',
              '{"query":"second"}'), ["first"], False),
            ("start query wins over malformed delta ending with brace", {"query": "start"},
             ("not-json}",), ["start"], False),
            ("string start input is ignored", "start",
             ('{"query":"delta"}',), ["delta"], False),
            ("array start input is ignored", ["start"],
             ('{"query":"delta"}',), ["delta"], False),
            ("null start input is ignored", None,
             ('{"query":"delta"}',), ["delta"], False),
            ("empty start fragment with trailing whitespace", {},
             ('{"query":"release"} ',), [], False),
            ("leading whitespace before delta object", {},
             (' {"query":"release"}',), [], False),
            ("surrounding whitespace around delta object", {},
             (' {"query":"release"} ',), [], False),
            ("whitespace inside delta object", {},
             ('{ "query" : "release" }',), ["release"], False),
            ("start and delta with trailing whitespace", {"query": "start"},
             ('{"query":"delta"} ',), [], False),
            ("delta after block stop", {}, ('{"query":"after stop"}',),
             ["after stop"], True),
        )
        for label, initial_input, fragments, expected_queries, stop_before_fragments in cases:
            with self.subTest(case=label):
                events = search_events(initial_input, fragments, stop_before_fragments)
                reference = oracle_run(events)
                actual = _run(MODEX, REQUEST, scenario="anthropic-custom-events",
                              anthropic_events=events)
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(actual["upstream"]), 1)
                self.assertEqual(reference["upstream"][0]["path"], "/anthropic/v1/messages")
                self.assertEqual(actual["upstream"][0]["path"], "/anthropic/v1/messages")
                self.assertEqual(actual["upstream"][0]["body"], reference["upstream"][0]["body"])
                reference_headers = {
                    key.lower(): value
                    for key, value in reference["upstream"][0]["headers"].items()
                }
                actual_headers = {
                    key.lower(): value
                    for key, value in actual["upstream"][0]["headers"].items()
                }
                self.assertEqual(reference_headers["x-api-key"], "synthetic-provider-key")
                self.assertEqual(actual_headers["x-api-key"], "synthetic-provider-key")
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(actual["state"]["leftovers"], [])
                self.assertEqual(completed_search_queries(reference), expected_queries)
                self.assertEqual(completed_search_queries(actual), expected_queries)
                self.assertEqual(
                    _normalized_events(actual["response_body"]),
                    _normalized_events(reference["response_body"]),
                )


if __name__ == "__main__":
    unittest.main()
