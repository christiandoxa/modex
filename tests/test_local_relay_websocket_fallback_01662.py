"""Compare the local relay's 426 fallback reuse with Prodex 0.166.2."""

import hashlib
import threading
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from manual_real_codex_01660_route_comparison import require_isolated_environment
import test_local_rewrite_01651_oracle as transport


class LocalRelayWebSocketFallback01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_identical_duplicate_upgrade_fields_reuse_only_unambiguous_pipeline(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            followup = transport.request_bytes(
                (("Connection", "close"),), body=transport.REQUEST_BODY,
            )
            cases = (
                (
                    "duplicate_connection_keep_alive",
                    transport.request_bytes(
                        (("Connection", "keep-alive"), ("Connection", "keep-alive"),
                         ("Upgrade", "websocket")),
                        body=transport.REQUEST_BODY,
                    ),
                ),
                (
                    "duplicate_upgrade_websocket",
                    transport.request_bytes(
                        (("Connection", "keep-alive"), ("Upgrade", "websocket"),
                         ("Upgrade", "websocket")),
                        body=transport.REQUEST_BODY,
                    ),
                ),
            )
            for name, first in cases:
                case = {
                    "name": name,
                    "request": first + followup,
                    "pipelined_requests": [first, followup],
                    "pipelined_response_count": 2,
                    "process_timeout": 20,
                }
                for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                    with self.subTest(case=name, product=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["read_error"], "")
                        self.assertEqual(
                            [(item["status"], item["body"])
                             for item in response["pipelined_responses"]],
                            [
                                (426, transport.WEBSOCKET_FALLBACK),
                                (200, transport.RESPONSES_RESPONSE),
                            ],
                        )
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]["method"], "POST")
                        self.assertEqual(records[0]["path"], "/v1/chat/completions")
                        self.assertIn(b"synthetic raw transport probe", records[0]["body"])
                        self.assertNotIn(b"synthetic-codex-key", response["stdout"])
                        self.assertNotIn(b"synthetic-codex-key", response["stderr"])

            controls = (
                (
                    "conflicting_connection_values_close",
                    transport.request_bytes(
                        (("Connection", "keep-alive"), ("Connection", "close"),
                         ("Upgrade", "websocket")),
                        body=transport.REQUEST_BODY,
                    ),
                    [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                    1,
                ),
                (
                    "conflicting_upgrade_values_close",
                    transport.request_bytes(
                        (("Connection", "keep-alive"), ("Upgrade", "websocket"),
                         ("Upgrade", "h2c")),
                        body=transport.REQUEST_BODY,
                    ),
                    [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                    1,
                ),
                (
                    "missing_content_length_remains_closed_in_modex",
                    transport.request_bytes(
                        (("Upgrade", "websocket"),), body=b"",
                    ).replace(b"Content-Length: 0\r\n", b""),
                    [(426, transport.WEBSOCKET_FALLBACK), (200, transport.RESPONSES_RESPONSE)],
                    1,
                ),
                (
                    "chunked_body_remains_closed_in_modex",
                    b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    b"Authorization: Bearer synthetic-codex-key\r\n"
                    b"Upgrade: websocket\r\nTransfer-Encoding: chunked\r\n\r\n"
                    + f"{len(transport.REQUEST_BODY):x}\r\n".encode("ascii")
                    + transport.REQUEST_BODY + b"\r\n0\r\n\r\n",
                    [(426, transport.WEBSOCKET_FALLBACK), (400, b"")],
                    0,
                ),
                (
                    "conflicting_content_lengths_close",
                    transport.request_bytes(
                        (("Upgrade", "websocket"), ("Content-Length", "0")),
                        body=transport.REQUEST_BODY,
                    ),
                    [(426, transport.WEBSOCKET_FALLBACK), (400, b"")],
                    0,
                ),
            )
            for name, first, oracle_responses, oracle_dispatches in controls:
                case = {
                    "name": name,
                    "request": first + followup,
                    "pipelined_requests": [first, followup],
                    "pipelined_response_count": 2,
                    "process_timeout": 20,
                }
                for label, binary in (("oracle", ORACLE), ("Modex", MODEX)):
                    with self.subTest(case=name, product=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        observed = [
                            (item["status"], item["body"])
                            for item in response["pipelined_responses"]
                        ]
                        if label == "oracle":
                            self.assertEqual(observed, oracle_responses)
                            self.assertEqual(len(records), oracle_dispatches)
                            if records:
                                self.assertEqual(records[0]["method"], "POST")
                                self.assertEqual(records[0]["path"], "/v1/chat/completions")
                                self.assertIn(b"synthetic raw transport probe", records[0]["body"])
                        else:
                            self.assertEqual(observed, [(426, transport.WEBSOCKET_FALLBACK)])
                            self.assertEqual(response["read_error"], "RemoteDisconnected")
                            self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)
