"""Compare repeated Anthropic search IDs with both pinned releases."""

import hashlib
import unittest

from test_cli import (
    MODEX,
    ORACLE as ORACLE_04392,
    ORACLE_SHA256 as ORACLE_04392_SHA256,
)
from test_deepseek_continuation import observe_turns
from test_provider_stream_01651_characterization import (
    ORACLE_01651,
    ORACLE_01651_SHA256,
)
from test_provider_tools_04392_characterization import _normalized_events
from provider_stream_search_cases import repeated_search_case


class HistoricalRepeatedAnthropicSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE_01651.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE_01651}")
        if hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.165.1")
        if not ORACLE_04392.is_file():
            raise AssertionError(f"Historical Prodex 0.439.2 oracle is missing: {ORACLE_04392}")
        if hashlib.sha256(ORACLE_04392.read_bytes()).hexdigest() != ORACLE_04392_SHA256:
            raise AssertionError("The historical Prodex oracle does not match release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def observe_case(self, *, shared_id):
        request, reply = repeated_search_case(shared_id=shared_id)
        captures = []
        for binary in (ORACLE_01651, ORACLE_04392, MODEX):
            posts, responses = observe_turns(binary, [request], [reply])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(responses), 1)
            self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
            self.assertEqual(responses[0]["status"], 200)
            captures.append((posts[0], _normalized_events(bytes.fromhex(responses[0]["body"]))))
        active, historical, actual = captures
        self.assertEqual(historical[0]["body"], active[0]["body"])
        self.assertEqual(actual[0]["body"], active[0]["body"])
        self.assertEqual(historical[1], active[1])
        self.assertEqual(actual[1], active[1])
        return active[1]

    def test_two_serial_searches_with_distinct_ids_match_releases(self):
        events = self.observe_case(shared_id=False)
        self.assertEqual(events[-1][0], "response.completed")
        output = events[-1][1]["response"]["output"]
        self.assertEqual([item["id"] for item in output[:2]], ["search_1", "search_2"])
        self.assertEqual([item["action"]["queries"] for item in output[:2]], [["first"], ["second"]])
        self.assertEqual(
            [item["action"]["sources"][0]["url"] for item in output[:2]],
            ["https://one.example.test", "https://two.example.test"],
        )

    def test_reused_search_id_matches_release_completion_policy(self):
        events = self.observe_case(shared_id=True)
        completed = [
            event[1] for event in events
            if event[0] == "response.output_item.done"
            and event[1].get("item", {}).get("type") == "web_search_call"
        ]
        self.assertEqual([event["output_index"] for event in completed], [0, 2])
        self.assertEqual([event["item"]["id"] for event in completed], ["shared_search"] * 2)
        self.assertEqual(completed[0]["item"]["action"]["queries"], ["first"])
        self.assertEqual(
            completed[0]["item"]["action"]["sources"][0]["url"],
            "https://one.example.test",
        )
        self.assertEqual(completed[1]["item"]["action"]["queries"], ["second"])
        self.assertEqual(completed[1]["item"]["action"]["sources"], [])
        response = events[-1][1]["response"]
        searches = [item for item in response["output"] if item["type"] == "web_search_call"]
        self.assertEqual([item["action"]["sources"] for item in searches], [
            [{"type": "url", "url": "https://one.example.test", "title": "One"}],
            [],
        ])
