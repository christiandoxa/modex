"""Exercise the local HTTP relay against released Prodex 0.439.2."""

import hashlib
import threading
import time
import unittest
from unittest.mock import patch

from test_cli import ORACLE, ORACLE_SHA256
import test_local_rewrite_01651_oracle as transport


CASE_NAMES = (
    "leading_request_line_whitespace_is_trimmed",
    "http_1_2_request_line_is_malformed",
    "http_0_9_request_uses_request_version",
    "http_0_9_malformed_header_uses_request_version",
    "http_0_9_expect_continue_uses_request_version",
    "http_0_9_truncated_declared_body_closes",
    "duplicate_request_versions_keep_first_version",
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
    "successful_get_chat_completions_sse",
    "head_chat_completions_200_sse_framing",
    "head_chat_completions_200_sse_framing_http_1_0",
    "head_chat_completions_204_sse_framing",
    "head_chat_completions_204_sse_framing_http_1_0",
    "head_chat_completions_304_sse_framing",
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

    def test_two_codex_requests_overlap_at_the_provider(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_two_codex_requests_overlap_at_the_provider(self)

    def test_parent_eof_interrupts_a_stalled_provider_request(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_parent_eof_interrupts_a_stalled_provider_request(self)

    def test_partial_reused_request_does_not_block_second_client(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_partial_reused_request_does_not_block_second_client(self)

    def test_pipelined_requests_match_oracle_across_framing_and_responses(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_pipelined_requests_match_oracle_across_framing_and_responses(self)

    def test_http_0_9_keepalive_and_pipelined_requests_match_oracle(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_http_0_9_keepalive_and_pipelined_requests_match_oracle(self)

    def test_connection_keep_alive_selection_matches_pinned_tinyhttp_rules(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_connection_keep_alive_selection_matches_pinned_tinyhttp_rules(self)

    def test_duplicate_expect_and_framing_rejections_remain_fail_closed(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_duplicate_expect_and_framing_rejections_remain_fail_closed(self)

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

    def test_large_request_head_boundaries_match_released_oracle(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for head_bytes in (65535, 65536, 65537):
                case = transport.large_request_head_case(head_bytes)
                with self.subTest(head_bytes=head_bytes):
                    oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
                    modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
                    for label, response, records in (
                        ("oracle", oracle, oracle_records),
                        ("modex", modex, modex_records),
                    ):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(
                            (response["status"], response["body"]),
                            (200, transport.RESPONSES_RESPONSE),
                            label,
                        )
                        self.assertEqual(len(records), 1, label)
                        expected_pad = case["request"].split(b"X-Pad: ", 1)[1].split(b"\r\n", 1)[0]
                        self.assertEqual(len(records[0]["headers"]["x-pad"]), len(expected_pad), label)
                    self.assertEqual(modex_records[0]["body"], oracle_records[0]["body"])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_large_request_heads_use_bounded_linear_capture(self):
        transport.assert_large_request_head_cases(self, ORACLE, transport.MODEX)

    def test_invalid_target_precedes_chunked_body_capture(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name in (
                "invalid_target_precedes_malformed_chunked_trailer",
                "invalid_target_precedes_missing_chunk_terminator",
            ):
                with self.subTest(case=name):
                    case = CASES[name]
                    for binary in (ORACLE, transport.MODEX):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], 400)
                        self.assertEqual(response["body"], transport.INVALID_REQUEST_TARGET_BODY)
                        self.assertEqual(response["read_error"], "")
                        self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_http_responses_and_stream_controls_match_released_oracle(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name in CASE_NAMES:
                case = CASES[name]
                with self.subTest(case=name):
                    before = time.time()
                    oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
                    modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
                    after = time.time()
                    transport.assert_response_headers(self, oracle, before, after, "oracle")
                    transport.assert_response_headers(self, modex, before, after, "modex")
                    self.assertEqual(
                        {name for name in (b"server", b"date") if name in transport.response_header_values(oracle)},
                        {name for name in (b"server", b"date") if name in transport.response_header_values(modex)},
                        case["name"],
                    )
                    for label, response in (("oracle", oracle), ("modex", modex)):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], case["expected_status"], label)
                        self.assertEqual(response["reason"], case.get("expected_reason", response["reason"]), label)
                        if "expected_response_line" in case:
                            self.assertEqual(response["response_line"], case["expected_response_line"], label)
                        raw_lines = response["raw_response_head"].split(b"\r\n")
                        if "expected_response_line" in case:
                            self.assertEqual(raw_lines[0].decode("iso-8859-1"), case.get("expected_wire_response_line", case["expected_response_line"]), label)
                        if case["expected_status"] is None:
                            self.assertEqual(response["raw_response_head"], b"", label)
                        else:
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

    def test_head_sse_terminal_chunk_preserves_pipelined_response(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            first = transport.request_bytes(
                (("X-Oracle-Response", "sse"),),
                target=b"/v1/chat/completions",
                method=b"HEAD",
            )
            second = transport.request_bytes(
                (("Connection", "close"),),
                body=b'{"model":"deepseek-chat","input":"pipeline-followup"}',
            )
            case = {
                "name": "pipelined_head_sse_then_responses",
                "request": first,
                "pipelined_requests": [first, second],
            }
            results = {
                label: transport.run_probe(binary, case, upstream)
                for label, binary in (("oracle", ORACLE), ("modex", transport.MODEX))
            }
            for label, (response, records) in results.items():
                with self.subTest(label=label):
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(
                        [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                        [(200, b""), (200, transport.RESPONSES_RESPONSE)],
                    )
                    self.assertEqual(
                        response["pipelined_responses"][0]["head_wire_body"],
                        b"0\r\n\r\n",
                    )
                    self.assertCountEqual(
                        [(record["method"], record["path"]) for record in records],
                        [("HEAD", "/v1/chat/completions"), ("POST", "/v1/chat/completions")],
                    )
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_method_admission_mismatch_remains_visible(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            case = CASES["http_1_0_buffered_responses_keep_request_version"]
            before = time.time()
            oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
            modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
            after = time.time()
            transport.assert_response_headers(self, oracle, before, after, "oracle")
            transport.assert_response_headers(self, modex, before, after, "modex")
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
            self.assertIn(b"Server: tiny-http (Rust)", modex_headers)
            self.assertTrue(any(line.startswith(b"Date: ") for line in modex_headers))
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

    def test_response_header_overrides_filtering_and_invalid_values_match_release(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for control in (
                "custom", "filtered", "invalid", "invalid-date", "folded", "folded-server",
            ):
                case = transport.response_header_control_case(control)
                with self.subTest(control=control):
                    before = time.time()
                    oracle, oracle_records = transport.run_probe(ORACLE, case, upstream)
                    modex, modex_records = transport.run_probe(transport.MODEX, case, upstream)
                    after = time.time()
                    for label, response in (("oracle", oracle), ("modex", modex)):
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["read_error"], "", label)
                    self.assertEqual(oracle["status"], modex["status"])
                    self.assertEqual(oracle["body"], modex["body"])
                    self.assertEqual(
                        {name for name in (b"server", b"date") if name in transport.response_header_values(oracle)},
                        {name for name in (b"server", b"date") if name in transport.response_header_values(modex)},
                        control,
                    )
                    self.assertEqual(len(oracle_records), 1)
                    self.assertEqual(len(modex_records), 1)

                    if control == "custom":
                        for response in (oracle, modex):
                            values = transport.response_header_values(response)
                            self.assertEqual(values.get(b"server"), [
                                b"synthetic-server-one", b"synthetic-server-two",
                            ])
                            self.assertEqual(values.get(b"date"), [
                                b"Sat, 01 Jan 2000 00:00:00 GMT",
                                b"Sun, 02 Jan 2000 00:00:00 GMT",
                            ])
                    else:
                        transport.assert_response_headers(self, oracle, before, after, "oracle")
                        transport.assert_response_headers(self, modex, before, after, "modex")
                        for response in (oracle, modex):
                            names = [line.partition(b":")[0].lower() for line in response["raw_response_head"].split(b"\r\n")]
                            self.assertNotIn(b"x-injected", names)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
