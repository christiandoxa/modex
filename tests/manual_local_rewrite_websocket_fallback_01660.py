"""Manually compare WebSocket fallback connection reuse with active Prodex 0.166.0."""

import hashlib
from pathlib import Path
import sys
import threading
import unittest

import test_active_baseline_01660 as active
import test_local_rewrite_01651_oracle as transport
from manual_real_codex_01660_route_comparison import require_isolated_environment


MODEX = active.MODEX
ORACLE = active.ORACLE
ORACLE_SHA256 = active.ORACLE_SHA256


class LocalRewriteWebSocketFallback01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        private_tmp = Path("/tmp").resolve()
        for label, path in (
            ("workspace", active.ROOT),
            ("Modex", MODEX),
            ("Prodex oracle", ORACLE),
            ("Python", Path(sys.executable)),
        ):
            if path.resolve().is_relative_to(private_tmp):
                raise AssertionError(
                    f"{label} must be mounted outside private /tmp: {path}"
                )
        if not ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.166.0 oracle is missing: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.166.0")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_pipeline_reuses_only_complete_client_framing(self):
        followup = transport.request_bytes((('Connection', 'close'),), body=transport.REQUEST_BODY)
        fixed = transport.request_bytes((('Upgrade', 'websocket'),), body=transport.REQUEST_BODY)
        fixed_keep_alive = transport.request_bytes(
            (('Connection', 'keep-alive'), ('Upgrade', 'websocket')),
            body=transport.REQUEST_BODY,
        )
        fixed_body_start = fixed.index(b"\r\n\r\n") + 4
        fixed_split = fixed_body_start + len(transport.REQUEST_BODY) // 2
        zero = transport.request_bytes((('Upgrade', 'websocket'),), body=b"")
        zero_split = zero.index(b"Upgrade: websocket") + len(b"Upgrade: websocket") - 3
        complete_cases = (
            ("fixed_contiguous", fixed, []),
            ("fixed_fragmented", fixed, [fixed[:fixed_split], fixed[fixed_split:] + followup]),
            ("fixed_keep_alive_contiguous", fixed_keep_alive, []),
            ("zero_contiguous", zero, []),
            ("zero_fragmented", zero, [zero[:zero_split], zero[zero_split:] + followup]),
        )
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, first, parts in complete_cases:
                case = {
                    "name": "websocket_" + name,
                    "request": first + followup,
                    "pipelined_requests": [first, followup],
                    "pipelined_request_parts": parts,
                    "pipelined_request_delay_ms": 10,
                    "pipelined_response_count": 2,
                    "process_timeout": 15,
                }
                for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                    with self.subTest(case=name, product=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["read_error"], "")
                        self.assertEqual(
                            [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                            [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                        )
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]["path"], "/v1/chat/completions")

            unauthorized_followup = transport.request_bytes((
                ("Connection", "close"),
                ("Authorization", "Bearer synthetic-invalid-token"),
            ), body=transport.REQUEST_BODY)
            unauthorized_case = {
                "name": "websocket_unauthorized_followup",
                "request": fixed_keep_alive + unauthorized_followup,
                "pipelined_requests": [fixed_keep_alive, unauthorized_followup],
                "pipelined_response_count": 2,
                "process_timeout": 15,
            }
            for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                with self.subTest(case="unauthorized_followup", product=label):
                    response, records = transport.run_probe(binary, unauthorized_case, upstream)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    if label == "oracle":
                        self.assertEqual(
                            [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                            [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                        )
                        self.assertEqual(len(records), 1)
                    else:
                        self.assertEqual(
                            [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                            [(426, transport.WEBSOCKET_FALLBACK), (401, b"")],
                        )
                        self.assertEqual(records, [])

            ambiguous_cases = (
                ("duplicate_content_length", b"Content-Length: 0\r\nContent-Length: 100\r\n"),
                ("conflicting_content_length_transfer_encoding", b"Content-Length: 0\r\nTransfer-Encoding: chunked\r\n"),
                ("malformed_content_length", b"Content-Length: nope\r\n"),
            )
            for name, framing in ambiguous_cases:
                first = (
                    b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    b"Upgrade: websocket\r\n" + framing + b"\r\n"
                )
                case = {
                    "name": "websocket_" + name,
                    "request": first + followup,
                    "pipelined_requests": [first, followup],
                    "pipelined_response_count": 2,
                    "process_timeout": 15,
                }
                for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                    with self.subTest(case=name, product=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        if label == "oracle":
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                                [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                            )
                            self.assertEqual(len(records), 1)
                        else:
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                                [(426, transport.WEBSOCKET_FALLBACK)],
                            )
                            self.assertEqual(response["read_error"], "RemoteDisconnected")
                            self.assertEqual(records, [])

            truncated = (
                b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Authorization: Bearer synthetic-codex-key\r\nUpgrade: websocket\r\n"
                b"Content-Length: 10\r\n\r\nx"
            )
            truncated_case = {
                "name": "websocket_truncated_fixed_body",
                "request": truncated,
                "half_close": True,
                "process_timeout": 15,
            }
            for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                with self.subTest(case="truncated_fixed_body", product=label):
                    response, records = transport.run_probe(binary, truncated_case, upstream)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertIsNone(response["status"])
                    self.assertEqual(response["read_error"], "RemoteDisconnected")
                    self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)
