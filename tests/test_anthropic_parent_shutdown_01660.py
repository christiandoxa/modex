"""Characterize Anthropic stream parent shutdown against Prodex 0.166.0."""

import hashlib
import json
from pathlib import Path
import signal
import unittest

from parent_shutdown_support import _observe_parent_shutdown
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from provider_stream_search_cases import repeated_search_case


def _stream(events):
    body = b"".join(
        b"data: " + json.dumps(event, separators=(",", ":")).encode() + b"\n\n"
        for event in events
    )
    return {"body": body}


class AnthropicParentShutdown01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError(f"pinned active Prodex oracle is missing: {ORACLE}")
        digest = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
        if digest != ORACLE_SHA256:
            raise AssertionError(f"pinned active Prodex oracle checksum mismatch: {ORACLE}: {digest}")
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")

    def test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"]
        reply = {**fixture, "body": body, "chunked": True,
                 "hold_open": True, "hold_open_timeout": 30}
        observations = {}
        for label, binary in (
            ("active 0.166.0", ORACLE),
            ("Modex", MODEX),
        ):
            observations[label] = _observe_parent_shutdown(
                binary, request, reply, pipeline_body_bytes=1024,
            )

        summary = {
            label: {
                "held": result["held"],
                "parent_returncode": result["parent_returncode"],
                "parent_alive_before_shutdown": result["parent_alive_before_shutdown"],
                "shutdown_sent": result["shutdown_sent"],
                "children_alive_after_2s": result["children_alive_after_2s"],
                "pipelined_records": result["pipelined_records"],
                "body_errors": [row["error"] for row in result["body_errors"]],
                "upstream_client_closed": result["upstream_client_closed"],
                "upstream_hold_timed_out": result["upstream_hold_timed_out"],
            }
            for label, result in observations.items()
        }
        for label, result in observations.items():
            with self.subTest(binary=label):
                self.assertTrue(result["held"], (label, summary))
                self.assertTrue(result["parent_alive_before_shutdown"], (label, summary))
                self.assertTrue(result["shutdown_sent"], (label, summary))
                self.assertEqual(result["parent_returncode"], -signal.SIGTERM, (label, summary))
                self.assertFalse(result["parent_timed_out"], (label, summary))
                self.assertEqual(result["children_alive_after_2s"], [], (label, summary))
                self.assertTrue(result["upstream_client_closed"], (label, summary))
                self.assertFalse(result["upstream_hold_timed_out"], (label, summary))
                self.assertEqual(
                    [(row["bytes"], row["write_open"]) for row in result["pipelined_records"]],
                    [(1024, True)],
                    (label, summary),
                )
                self.assertTrue(result["body_errors"], (label, summary))
                self.assertIn(
                    b"event: response.failed\r\n",
                    bytes.fromhex(result["held_records"][0]["body"]),
                    (label, summary),
                )

    def test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized(self):
        request, fixture = repeated_search_case()
        base = [
            json.loads(line[6:])
            for line in fixture["body"].splitlines()
            if line.startswith(b"data: ")
        ]
        failed = {"type": "content_block_delta", "index": 1, "delta": {"type": None}}
        body = _stream(base[:6] + [failed])["body"] + b": \xff\n\n" + _stream(base[6:])["body"]
        reply = {**fixture, "body": body, "chunked": True}
        observations = {}
        for label, binary in (
            ("active 0.166.0", ORACLE),
            ("Modex", MODEX),
        ):
            observations[label] = _observe_parent_shutdown(
                binary, request, reply, pipeline_body_bytes=1024,
                hold_client_until_shutdown=True,
            )

        summary = {
            label: {
                "held": result["held"],
                "parent_returncode": result["parent_returncode"],
                "parent_alive_before_shutdown": result["parent_alive_before_shutdown"],
                "shutdown_sent": result["shutdown_sent"],
                "client_waiting_for_shutdown": result["client_waiting_for_shutdown"],
                "parent_timed_out": result["parent_timed_out"],
                "children_alive_after_2s": result["children_alive_after_2s"],
                "pipelined_records": result["pipelined_records"],
                "body_errors": [row["error"] for row in result["body_errors"]],
            }
            for label, result in observations.items()
        }
        for label, result in observations.items():
            with self.subTest(binary=label):
                self.assertTrue(result["held"], (label, summary))
                self.assertFalse(result["parent_timed_out"], (label, summary))
                self.assertTrue(result["client_waiting_for_shutdown"], (label, summary))
                self.assertTrue(result["parent_alive_before_shutdown"], (label, summary))
                self.assertTrue(result["shutdown_sent"], (label, summary))
                self.assertEqual(result["parent_returncode"], -signal.SIGTERM, (label, summary))
                self.assertEqual(result["children_alive_after_2s"], [], (label, summary))
                self.assertEqual(
                    [(row["bytes"], row["write_open"]) for row in result["pipelined_records"]],
                    [(1024, True)],
                    (label, summary),
                )
                pipeline = result["pipelined_records"][0]
                pipeline_head = bytes.fromhex(pipeline["head_hex"])
                self.assertEqual(pipeline["wire_bytes"], len(pipeline_head) + 1024, (label, summary))
                self.assertTrue(pipeline_head.endswith(b"\r\n\r\n"), (label, summary))
                self.assertIn(b"Content-Length: 1048576\r\n", pipeline_head, (label, summary))
                self.assertIn(b"Connection: keep-alive\r\n", pipeline_head, (label, summary))
                self.assertTrue(result["body_errors"], (label, summary))
                self.assertIn(
                    b"event: response.failed\r\n",
                    bytes.fromhex(result["held_records"][0]["body"]),
                    (label, summary),
                )
