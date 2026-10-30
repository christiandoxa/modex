"""Active Prodex 0.166.0 characterization for Anthropic SSE edge ordering."""

import hashlib
import json
import unittest

from provider_stream_search_cases import (
    overlapping_search_result_case,
    repeated_search_case,
    search_started_during_result_case,
)
from test_active_baseline_01660 import MODEX, ORACLE
from test_deepseek_continuation import observe_turns
from test_provider_tools_04392_characterization import _normalized_events, _run
from test_anthropic_text_stream_04392 import START, STOP


ORACLE_SHA256 = "349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735"
SYNTHETIC_API_KEY = "synthetic-provider-key"


class _ObjectPairs(list):
    pass


def _canonical_json(raw):
    """Ignore object member order; preserve values, arrays, and duplicate detection."""
    if isinstance(raw, str):
        raw = bytes.fromhex(raw)
    value = json.loads(raw, object_pairs_hook=_ObjectPairs)

    def normalize(item, path="$", duplicate_paths=None):
        if duplicate_paths is None:
            duplicate_paths = []
        if isinstance(item, _ObjectPairs):
            keys = [key for key, _ in item]
            if len(keys) != len(set(keys)):
                duplicate_paths.append(path)
            result = tuple(sorted(
                (key, normalize(child, path + "." + key, duplicate_paths))
                for key, child in item
            ))
            return ("object", result)
        if isinstance(item, list):
            return ("array", tuple(
                normalize(child, path + f"[{index}]", duplicate_paths)
                for index, child in enumerate(item)
            ))
        if item is None:
            return ("null",)
        if isinstance(item, bool):
            return ("bool", item)
        if isinstance(item, (int, float)):
            return ("number", item)
        return ("string", item)

    duplicates = []
    canonical = normalize(value, duplicate_paths=duplicates)
    if duplicates:
        raise AssertionError(f"duplicate provider request object keys at {duplicates}")
    return canonical


def _response_bytes(body):
    return body if isinstance(body, bytes) else bytes.fromhex(body)


def _events(reply):
    return [
        json.loads(line[6:])
        for line in reply["body"].splitlines()
        if line.startswith(b"data: ")
    ]


def _stream(events):
    return b"".join(
        b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        for event in events
    )


class AnthropicStream01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (not ORACLE.is_file()
                or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def _assert_process_pair(self, reference, actual):
        self.assertEqual(len(reference[0]), len(actual[0]))
        self.assertEqual(len(reference[1]), len(actual[1]))
        for expected_post, observed_post in zip(reference[0], actual[0]):
            self.assertEqual(expected_post["path"], "/anthropic/v1/messages")
            self.assertEqual(observed_post["path"], expected_post["path"])
            expected_headers = {
                key.lower(): value for key, value in expected_post["headers"].items()
            }
            observed_headers = {
                key.lower(): value for key, value in observed_post["headers"].items()
            }
            self.assertEqual(expected_headers["x-api-key"], SYNTHETIC_API_KEY)
            self.assertEqual(observed_headers["x-api-key"], SYNTHETIC_API_KEY)
            self.assertNotIn("authorization", expected_headers)
            self.assertNotIn("authorization", observed_headers)
            self.assertEqual(
                _canonical_json(expected_post["body"]),
                _canonical_json(observed_post["body"]),
            )
        for expected_response, observed_response in zip(reference[1], actual[1]):
            self.assertEqual(expected_response["status"], 200)
            self.assertEqual(observed_response["status"], 200)
            self.assertEqual(
                _normalized_events(_response_bytes(observed_response["body"])),
                _normalized_events(_response_bytes(expected_response["body"])),
            )

    def test_interleaved_search_results_and_partial_errors_match_active_release(self):
        cases = [
            ("overlapping result blocks", *overlapping_search_result_case()),
            ("search starts during result", *search_started_during_result_case()),
            ("duplicate search IDs", *repeated_search_case(shared_id=True)),
        ]
        request, reply = repeated_search_case()
        base_events = _events(reply)
        invalid_delta = {
            "type": "content_block_delta", "index": 1, "delta": {"type": None},
        }
        cases.extend((
            ("error before message start", request, {
                **reply, "body": _stream([invalid_delta, START, STOP]),
            }),
            ("error after search result", request, {
                **reply, "body": _stream(base_events[:6] + [invalid_delta] + base_events[6:]),
            }),
        ))
        after_message_delta = base_events.copy()
        message_delta_index = next(
            index for index, event in enumerate(after_message_delta)
            if event.get("type") == "message_delta"
        )
        after_message_delta.insert(message_delta_index + 1, invalid_delta)
        cases.append(("error after message delta", request, {
            **reply, "body": _stream(after_message_delta),
        }))

        for name, request, reply in cases:
            observations = []
            for binary in (ORACLE, MODEX):
                upstream, responses = observe_turns(
                    binary, [request], [reply], latest_version="0.166.0",
                )
                self.assertEqual(len(upstream), 1, name)
                self.assertEqual(len(responses), 1, name)
                observations.append((upstream, responses))
            with self.subTest(case=name):
                self._assert_process_pair(*observations)

    def test_search_mode_environment_and_toml_match_active_release(self):
        request, reply = overlapping_search_result_case()
        configurations = (
            ("environment", "anthropic", None),
            ("TOML", None, '[deepseek]\nweb_search_mode = "anthropic"\n'),
            ("TOML overrides environment", "openai_chat",
             '[deepseek]\nweb_search_mode = "anthropic"\n'),
        )
        for name, mode, config in configurations:
            observations = []
            for binary in (ORACLE, MODEX):
                options = {
                    "scenario": "anthropic-custom-events",
                    "anthropic_events": _events(reply),
                }
                if mode is not None:
                    options["mode_override"] = mode
                if config is not None:
                    options["strict_config"] = config
                result = _run(binary, request, **options)
                self.assertEqual((result["exit_code"], result["status"]), (0, 200), name)
                self.assertEqual(len(result["upstream"]), 1, name)
                observations.append((
                    result["upstream"],
                    [{"status": result["status"], "body": result["response_body"]}],
                ))
            with self.subTest(configuration=name):
                self._assert_process_pair(*observations)


if __name__ == "__main__":
    unittest.main()
