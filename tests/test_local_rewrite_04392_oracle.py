"""Exercise the local HTTP relay against released Prodex 0.439.2."""

import hashlib
import threading
import unittest

from test_cli import ORACLE, ORACLE_SHA256
import test_local_rewrite_01651_oracle as transport


CASE_NAMES = (
    "malformed_request_line_missing_version",
    "http_1_0_request_line_extra_token_keeps_request_version",
    "http_1_0_buffered_responses_keep_request_version",
    "http_1_0_head_response_keeps_request_version",
    "http_1_0_unsupported_route_error_keeps_request_version",
    "http_1_0_invalid_target_keeps_request_version",
    "http_1_0_fragment_target_keeps_request_version",
    "http_1_0_malformed_header_keeps_request_version",
    "http_1_0_expect_continue_uses_http_1_0_interim",
    "http_1_0_unsupported_expect_returns_417",
    "http_1_0_sse_stream_starts_before_upstream_eof",
    "head_chat_completions_204_sse_framing_http_1_0",
    "head_chat_completions_304_sse_framing_http_1_0",
    "http_1_0_chat_completions_status_302",
    "http_1_0_chat_completions_status_404",
    "http_1_0_chat_completions_status_503",
)
CASES = {case["name"]: case for case in transport.CASES}


class LocalRewrite04392OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.439.2 oracle is missing: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.439.2")
        if not transport.MODEX.is_file():
            raise AssertionError(f"Build Modex first: {transport.MODEX}")
        missing = set(CASE_NAMES) - CASES.keys()
        if missing:
            raise AssertionError(f"Local relay oracle cases are missing: {sorted(missing)}")

    def test_non_websocket_connection_upgrade_reads_through_eof(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for case in transport.upgrade_eof_cases():
                with self.subTest(case=case["name"]):
                    oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
                    modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
                    for response in (oracle, modex):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], case["status"])
                        self.assertEqual(response["read_error"], "")
                        if "expected_request_parts_sent" in case:
                            self.assertEqual(response["request_parts_sent_at_response"], case["expected_request_parts_sent"])
                    self.assertEqual(modex["body"], oracle["body"])
                    self.assertEqual(len(oracle_records), int(case["status"] == 200))
                    self.assertEqual(len(modex_records), int(case["status"] == 200))
                    if oracle_records:
                        self.assertNotIn("upgrade", modex_records[0]["headers"])
                        self.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_http_1_0_responses_and_stream_controls_match_released_oracle(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name in CASE_NAMES:
                case = CASES[name]
                with self.subTest(case=name):
                    oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
                    modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
                    for label, response in (("oracle", oracle), ("modex", modex)):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], case["expected_status"], label)
                        self.assertEqual(response["reason"], case.get("expected_reason", response["reason"]), label)
                        self.assertEqual(response["response_line"], case["expected_response_line"], label)
                        raw_lines = response["raw_response_head"].split(b"\r\n")
                        self.assertEqual(
                            raw_lines[0].decode("iso-8859-1"),
                            case["expected_response_line"],
                            label,
                        )
                        self.assertEqual(raw_lines[-2:], [b"", b""], label)
                        raw_headers = {}
                        for raw_header in raw_lines[1:-2]:
                            raw_name, separator, value = raw_header.partition(b":")
                            self.assertTrue(separator, (label, raw_header))
                            raw_headers[raw_name.decode("ascii").lower()] = value.lstrip(b" \t").decode("iso-8859-1")
                        self.assertEqual(response["read_error"], case.get("expected_read_error", ""), label)
                        self.assertEqual(
                            response["interim_statuses"],
                            case.get("expected_interim_statuses", []),
                            label,
                        )
                        self.assertEqual(
                            response.get("interim_status_lines", []),
                            case.get(
                                "expected_interim_status_lines",
                                ["HTTP/1.1 100 Continue" for _ in case.get("expected_interim_statuses", [])],
                            ),
                            label,
                        )
                        if case["expected_body"] is not None:
                            self.assertEqual(response["body"], case["expected_body"], label)
                        else:
                            self.assertTrue(response["body"], label)
                        headers = {key.lower(): value for key, value in response["headers"]}
                        for key, value in case.get("expected_headers", {}).items():
                            self.assertEqual(headers.get(key), value, label)
                            self.assertEqual(raw_headers.get(key), value, label)
                        if case.get("check_close"):
                            expected_close = case["expected_connection_closed"][label]
                            self.assertEqual(response["connection_closed"], expected_close, label)
                        if case.get("response_before_upstream_eof_ms"):
                            limit = case["response_before_upstream_eof_ms"]
                            self.assertLess(response["response_headers_elapsed_ms"], limit, label)
                            self.assertLess(response["first_body_byte_elapsed_ms"], limit, label)
                        if name.startswith("head_chat_completions_"):
                            self.assertTrue(response["wire_body_probe_complete"], label)
                            self.assertEqual(
                                response["wire_body"],
                                case["expected_wire_body"][label],
                                label,
                            )
                    self.assertEqual(len(oracle_records), int(case["upstream"]), "oracle")
                    self.assertEqual(len(modex_records), int(case["upstream"]), "modex")
                    if case["upstream"]:
                        for label, records in (("oracle", oracle_records), ("modex", modex_records)):
                            record = records[0]
                            self.assertEqual(
                                (record["method"], record["path"]),
                                (
                                    case.get("expected_upstream_method", "POST"),
                                    case.get("expected_upstream_path", "/v1/chat/completions"),
                                ),
                                label,
                            )
                        if case.get("compare_upstream_request"):
                            self.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
                    if case.get("compare_response_body"):
                        self.assertEqual(
                            transport.normalize_response_body(case, oracle["body"]),
                            transport.normalize_response_body(case, modex["body"]),
                        )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_default_header_and_method_admission_mismatches_remain_visible(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            case = CASES["http_1_0_buffered_responses_keep_request_version"]
            oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
            modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
            self.assertEqual(oracle["response_line"], "HTTP/1.0 200 OK")
            self.assertEqual(modex["response_line"], "HTTP/1.0 200 OK")
            self.assertEqual(oracle["body"], modex["body"])
            self.assertEqual(len(oracle_records), 1)
            self.assertEqual(len(modex_records), 1)
            oracle_headers = oracle["raw_response_head"].split(b"\r\n")[1:-2]
            modex_headers = modex["raw_response_head"].split(b"\r\n")[1:-2]
            self.assertIn(b"Server: tiny-http (Rust)", oracle_headers)
            self.assertTrue(any(line.startswith(b"Date: ") for line in oracle_headers))
            self.assertNotIn(b"Connection: close", oracle_headers)
            self.assertFalse(any(line.lower().startswith((b"server:", b"date:")) for line in modex_headers))
            self.assertNotIn(b"Connection: close", modex_headers)

            non_token_method = {
                "name": "non_token_method_admission_gap",
                "request": b"G@T /v1/not-real HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n",
                "check_close": True,
                "upstream": False,
            }
            oracle, oracle_records = transport.run_probe(ORACLE, non_token_method, upstream)
            modex, modex_records = transport.run_probe(transport.MODEX, non_token_method, upstream)
            self.assertEqual((oracle["status"], oracle["response_line"], oracle["body"]), (
                404,
                "HTTP/1.0 404 Not Found",
                transport.UNSUPPORTED_ROUTE_BODY,
            ))
            self.assertEqual((modex["status"], modex["response_line"], modex["body"]), (
                400,
                "HTTP/1.1 400 Bad Request",
                b"",
            ))
            self.assertEqual((oracle_records, modex_records), ([], []))
            self.assertTrue(oracle["connection_closed"])
            self.assertTrue(modex["connection_closed"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
