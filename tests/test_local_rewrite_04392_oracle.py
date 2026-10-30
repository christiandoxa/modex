"""Exercise the local HTTP relay against released Prodex 0.439.2."""

import hashlib
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from test_cli import MODEX
import test_local_rewrite_01651_oracle as transport


ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
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

    def test_websocket_body_capture_order_matches_both_releases(self):
        if not transport.ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {transport.ORACLE}")
        if hashlib.sha256(transport.ORACLE.read_bytes()).hexdigest() != transport.ORACLE_SHA256:
            raise AssertionError("Prodex oracle checksum does not match pinned 0.165.1")
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            def header(*fields):
                return (
                    b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    + b"".join(field + b"\r\n" for field in fields)
                    + b"\r\n"
                )

            cases = []
            for size in (0, 1, 1024, 1025):
                request_head = header(
                    b"Upgrade: websocket",
                    b"Content-Length: " + str(size).encode("ascii"),
                )
                body = b"x" * size
                complete = {
                    "name": f"websocket_body_{size}_complete",
                    "request": request_head + body,
                    "request_parts": [request_head] if not body else [request_head, body],
                    "request_part_delay_ms": 500 if body else 0,
                }
                cases.append((complete, 426, transport.WEBSOCKET_FALLBACK, "", [], 1 if size == 0 or size > 1024 else 2))
                if size:
                    partial = body[:-1]
                    truncated = {
                        "name": f"websocket_body_{size}_truncated",
                        "request": request_head + partial,
                        "request_parts": [request_head] if not partial else [request_head, partial],
                        "half_close": True,
                    }
                    cases.append((
                        truncated,
                        426 if size > 1024 else None,
                        transport.WEBSOCKET_FALLBACK if size > 1024 else b"",
                        "" if size > 1024 else "RemoteDisconnected",
                        [],
                        None,
                    ))

            cases.append((
                CASES["websocket_truncated_declared_body"], None, b"", "RemoteDisconnected", [], None,
            ))
            cases.extend((
                ({
                    "name": "websocket_expect_continue_without_connection_upgrade",
                    "request": header(b"Upgrade: websocket", b"Expect: 100-continue", b"Content-Length: 1"),
                    "expect_handshake": True,
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_unsupported_expect_without_connection_upgrade",
                    "request": header(b"Upgrade: websocket", b"Expect: 100-wait", b"Content-Length: 1"),
                }, 417, b"", "", [], None),
                ({
                    "name": "websocket_chunked_without_connection_upgrade",
                    "request": header(b"Upgrade: websocket", b"Transfer-Encoding: chunked"),
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_connection_upgrade_truncated_body",
                    "request": header(b"Connection: Upgrade", b"Upgrade: websocket", b"Content-Length: 1"),
                    "half_close": True,
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_conflicting_lengths_without_connection_upgrade",
                    "request": header(b"Upgrade: websocket", b"Content-Length: 0", b"Content-Length: 1"),
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_conflicting_framing_without_connection_upgrade",
                    "request": header(b"Upgrade: websocket", b"Content-Length: 0", b"Transfer-Encoding: chunked"),
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_connection_upgrade_substring",
                    "request": header(b"Connection: preupgradepost", b"Upgrade: websocket", b"Content-Length: 1"),
                    "half_close": True,
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_connection_upgrade_comma_token",
                    "request": header(b"Connection: keep-alive, Upgrade", b"Upgrade: websocket", b"Content-Length: 1"),
                    "half_close": True,
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
                ({
                    "name": "websocket_first_connection_field_does_not_upgrade",
                    "request": header(
                        b"Connection: keep-alive", b"Connection: Upgrade",
                        b"Upgrade: websocket", b"Content-Length: 1",
                    ),
                    "half_close": True,
                }, None, b"", "RemoteDisconnected", [], None),
                ({
                    "name": "websocket_first_connection_field_upgrades",
                    "request": header(
                        b"Connection: Upgrade", b"Connection: keep-alive",
                        b"Upgrade: websocket", b"Content-Length: 1",
                    ),
                    "half_close": True,
                }, 426, transport.WEBSOCKET_FALLBACK, "", [], None),
            ))

            for case, status, body, read_error, interim, sent_parts in cases:
                for label, binary in (
                    ("0.165.1", transport.ORACLE),
                    ("0.439.2", ORACLE),
                    ("Modex", transport.MODEX),
                ):
                    with self.subTest(case=case["name"], binary=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], status)
                        self.assertEqual(response["body"], body)
                        self.assertEqual(response["read_error"], read_error)
                        self.assertEqual(response["interim_statuses"], interim)
                        self.assertEqual(records, [])
                        if sent_parts is not None:
                            self.assertEqual(response["request_parts_sent_at_response"], sent_parts)
                        if status is None:
                            self.assertEqual(response["raw_response_head"], b"")
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_positive_first_conflicting_websocket_length_stays_fail_closed(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            request = (
                b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Upgrade: websocket\r\nContent-Length: 2\r\nContent-Length: 1\r\n\r\nx"
            )
            case = {
                "name": "websocket_positive_first_conflicting_length_half_close",
                "request": request,
                "half_close": True,
            }
            expected = {
                "0.165.1": (None, b"", "RemoteDisconnected"),
                "0.439.2": (None, b"", "RemoteDisconnected"),
                "Modex": (426, transport.WEBSOCKET_FALLBACK, ""),
            }
            for label, binary in (
                ("0.165.1", transport.ORACLE),
                ("0.439.2", ORACLE),
                ("Modex", transport.MODEX),
            ):
                with self.subTest(binary=label):
                    response, records = transport.run_probe(binary, case, upstream)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(
                        (response["status"], response["body"], response["read_error"]),
                        expected[label],
                    )
                    if response["status"] is None:
                        self.assertEqual(response["raw_response_head"], b"")
                    self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_websocket_body_wait_keeps_one_idle_and_partial_client(self):
        partial = (
            b"POST /v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Upgrade: websocket\r\nContent-Length: 1\r\n\r\n"
        )
        healthy = transport.request_bytes(( ("Connection", "close"), ))
        case = {
            "name": "websocket_partial_body_keeps_idle_client",
            "request": healthy,
            "preconnected_idle": True,
            "preconnected_partial_count": 1,
            "preconnected_partial_request": partial,
            "preconnected_healthy_request": healthy,
            "preconnected_complete_partial": b"x",
            "preconnected_settle_ms": 50,
            "preconnected_flood_settle_ms": 100,
            "preconnected_resource_sample_ms": 100,
            "environment_overrides": {"PRODEX_RUNTIME_PROXY_WORKER_COUNT": "4"},
        }
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for label, binary in (
                ("0.165.1", transport.ORACLE),
                ("0.439.2", ORACLE),
                ("Modex", transport.MODEX),
            ):
                with self.subTest(binary=label):
                    response, records = transport.run_probe(binary, case, upstream)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual((response["status"], response["body"]), (200, transport.RESPONSES_RESPONSE))
                    self.assertEqual(response["preconnected_partial_status"], 426)
                    self.assertEqual(
                    transport.base64.b64decode(response["preconnected_partial_body_base64"]),
                        transport.WEBSOCKET_FALLBACK,
                    )
                    self.assertEqual(len(records), 1)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_bodyless_invalid_target_expect_can_reuse_connection(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            valid_request = transport.request_bytes(
                (("Connection", "close"),), body=transport.REQUEST_BODY,
            )
            for framing in (b"", b"Content-Length: 0\r\n"):
                bad_request = (
                    b"POST http://example.test/v1/responses HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\nExpect: 100-continue\r\n"
                    + framing + b"\r\n"
                )
                case = {
                    "name": "bodyless_invalid_target_expect_reuse",
                    "request": bad_request,
                    "process_timeout": 15,
                }
                for mode, requests in (
                    ("sequential", {"sequential_requests": [bad_request, valid_request]}),
                    ("pipelined", {"pipelined_requests": [bad_request, valid_request]}),
                ):
                    case.update(requests)
                    for label, binary in (
                        ("0.439.2", ORACLE),
                        ("Modex", transport.MODEX),
                    ):
                        with self.subTest(framing=framing, mode=mode, binary=label):
                            response, records = transport.run_probe(binary, case, upstream)
                            self.assertEqual(response["process_exit"], 0, response["stderr"])
                            self.assertEqual(response["read_error"], "")
                            observed = response[f"{mode}_responses"]
                            self.assertEqual(
                                [(item["status"], item["body"]) for item in observed],
                                [
                                    (400, transport.INVALID_REQUEST_TARGET_BODY),
                                    (200, transport.RESPONSES_RESPONSE),
                                ],
                            )
                            self.assertEqual(len(records), 1)
                            self.assertEqual(records[0]["path"], "/v1/chat/completions")
                    case.pop("sequential_requests", None)
                    case.pop("pipelined_requests", None)

            unsafe_cases = (
                (
                    "nonzero_expect_body",
                    b"POST http://example.test/v1/responses HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\nExpect: 100-continue\r\nContent-Length: 40\r\n\r\n",
                    True,
                ),
                (
                    "chunked_body",
                    b"POST http://example.test/v1/responses HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
                    False,
                ),
            )
            for name, request, expect_handshake in unsafe_cases:
                case = {
                    "name": name,
                    "request": request,
                    "expect_handshake": expect_handshake,
                    "check_close": True,
                    "process_timeout": 15,
                }
                for label, binary in (
                    ("0.439.2", ORACLE),
                    ("Modex", transport.MODEX),
                ):
                    with self.subTest(case=name, binary=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], 400)
                        self.assertEqual(response["body"], transport.INVALID_REQUEST_TARGET_BODY)
                        self.assertEqual(response["interim_statuses"], [])
                        if name == "chunked_body" and label == "0.439.2":
                            # HTTPResponse may buffer the trailing empty 400 before the close sample.
                            pass
                        else:
                            self.assertEqual(response["connection_closed"], label == "Modex")
                        self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_chunked_invalid_target_release_wire_has_bounded_second_400(self):
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        request = (
            b"POST http://example.test/v1/responses HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n"
        )
        case = {
            "name": "chunked_body",
            "request": request,
            "raw_response": True,
            "raw_response_timeout_ms": 2500,
            "process_timeout": 15,
        }
        try:
            response, records = transport.run_probe(ORACLE, case, upstream)
            wire = response["wire_body"]
            self.assertEqual(response["process_exit"], 0, response["stderr"])
            self.assertLessEqual(len(wire), 1024)
            self.assertTrue(response["connection_closed"])
            self.assertEqual(records, [])
            messages = []
            offset = 0
            while offset < len(wire):
                head_end = wire.find(b"\r\n\r\n", offset)
                self.assertGreaterEqual(head_end, 0, wire[offset:])
                head = wire[offset:head_end]
                headers = {
                    name.lower(): value.strip()
                    for name, value in (
                        line.split(b":", 1) for line in head.split(b"\r\n")[1:]
                    )
                }
                length = int(headers[b"content-length"])
                body_start = head_end + 4
                body_end = body_start + length
                self.assertLessEqual(body_end, len(wire))
                messages.append((head.split(b"\r\n", 1)[0], wire[body_start:body_end]))
                offset = body_end
            self.assertEqual(messages, [
                (b"HTTP/1.1 400 Bad Request", transport.INVALID_REQUEST_TARGET_BODY),
                (b"HTTP/1.1 400 Bad Request", b""),
            ])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_two_codex_requests_overlap_at_the_provider(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_two_codex_requests_overlap_at_the_provider(self)

    def test_worker_count_controls_parallel_provider_stalls(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_worker_count_controls_parallel_provider_stalls(self)

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

    def test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed(self)

    def test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade(self):
        with patch.object(transport, "ORACLE", ORACLE):
            transport.LocalRewrite01651OracleTests.test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade(self)

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

    def test_exact_four_mib_head_exposes_release_and_modex_bounds(self):
        self.assertEqual(
            hashlib.sha256(transport.ORACLE_01651.read_bytes()).hexdigest(),
            transport.ORACLE_SHA256,
        )
        upstream = transport.LargeHeaderUpstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            case = transport.large_request_head_case(4 * 1024 * 1024)
            self.assertEqual(case["request"].index(b"\r\n\r\n"), 4 * 1024 * 1024)
            for label, binary, expected_status in (
                ("0.165.1", transport.ORACLE_01651, 200),
                ("0.439.2", ORACLE, 200),
                ("Modex", transport.MODEX, 502),
            ):
                with self.subTest(binary=label):
                    response, records = transport.run_probe(binary, case, upstream)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(response["status"], expected_status)
                    if expected_status == 200:
                        self.assertEqual(response["body"], case["expected_body"])
                        self.assertEqual(len(records), 1)
                        self.assertEqual(
                            records[0]["pad_headers"],
                            transport.expected_pad_headers(case["request"]),
                        )
                        self.assertGreater(records[0]["head_bytes"], 4 * 1024 * 1024)
                    else:
                        self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_chat_passthrough_request_header_parity(self):
        transport.assert_chat_request_header_parity(self, ORACLE, transport.MODEX)

    def test_chat_passthrough_response_framing(self):
        transport.assert_chat_response_framing(self, ORACLE, transport.MODEX)

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

    def test_http_2_and_3_tokens_preserve_observed_release_wire_behavior(self):
        self.assertEqual(
            hashlib.sha256(transport.ORACLE_01651.read_bytes()).hexdigest(),
            transport.ORACLE_SHA256,
        )
        second = transport.request_bytes(
            (("Connection", "close"),), body=transport.REQUEST_BODY,
        )
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            controls = (
                CASES["http_0_9_request_uses_request_version"],
                CASES["http_1_0_buffered_responses_keep_request_version"],
                {
                    "name": "http_1_1_supported_control",
                    "request": transport.request_bytes(
                        (("Connection", "close"),), version=b"HTTP/1.1",
                    ),
                    "expected_status": 200,
                    "expected_response_line": "HTTP/1.1 200 OK",
                    "expected_wire_response_line": "HTTP/1.1 200 OK",
                    "expected_body": transport.RESPONSES_RESPONSE,
                    "upstream": True,
                    "check_close": True,
                },
                CASES["http_1_2_request_line_is_malformed"],
            )
            for case in controls:
                for label, binary in (
                    ("0.165.1", transport.ORACLE_01651),
                    ("0.439.2", ORACLE),
                    ("Modex", transport.MODEX),
                ):
                    with self.subTest(control=case["name"], binary=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["status"], case["expected_status"])
                        self.assertEqual(response["response_line"], case["expected_response_line"])
                        self.assertEqual(
                            response["raw_response_head"].split(b"\r\n", 1)[0].decode("ascii"),
                            case.get("expected_wire_response_line", case["expected_response_line"]),
                        )
                        self.assertEqual(response["body"], case["expected_body"])
                        self.assertEqual(response["read_error"], "")
                        self.assertTrue(response["connection_closed"])
                        self.assertEqual(len(records), int(case["upstream"]))

            for version in (b"HTTP/2.0", b"HTTP/3.0"):
                first = (
                    b"POST /v1/responses " + version
                    + b"\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\n\r\n"
                )
                case = {
                    "name": "unsupported-version-" + version.decode("ascii"),
                    "request": first,
                    "pipelined_requests": [first, second],
                    "raw_response": True,
                    "raw_response_timeout_ms": 1200,
                    "check_close": True,
                    "process_timeout": 20,
                }
                for label, binary in (
                    ("0.165.1", transport.ORACLE_01651),
                    ("0.439.2", ORACLE),
                    ("Modex", transport.MODEX),
                ):
                    with self.subTest(version=version, binary=label):
                        response, records = transport.run_probe(binary, case, upstream)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(response["request_parts_sent_at_response"], 2)
                        self.assertEqual(response["wire_body_probe_complete"], True)
                        self.assertEqual(records, [])
                        if label != "Modex":
                            self.assertEqual(response["wire_body"], b"")
                            self.assertFalse(response["connection_closed"])
                            continue
                        raw_head, separator, body = response["wire_body"].partition(b"\r\n\r\n")
                        self.assertTrue(separator)
                        self.assertEqual(raw_head.split(b"\r\n", 1)[0], b"HTTP/1.1 400 Bad Request")
                        headers = {
                            name.strip().lower(): value.strip()
                            for name, value in (
                                line.split(b":", 1) for line in raw_head.split(b"\r\n")[1:]
                            )
                        }
                        self.assertEqual(headers[b"content-length"], b"0")
                        self.assertEqual(body, b"")
                        self.assertTrue(response["connection_closed"])
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

    def test_nonstandard_ascii_method_matches_pinned_tinyhttp(self):
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
            binaries = (
                ("0.439.2", ORACLE),
                ("Modex", transport.MODEX),
            )
            for label, binary in binaries:
                with self.subTest(method="G@T", binary=label):
                    before = time.time()
                    response, records = transport.run_probe(binary, non_token_method, upstream)
                    after = time.time()
                    transport.assert_response_headers(self, response, before, after, label)
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(
                        (response["status"], response["response_line"], response["body"]),
                        (404, "HTTP/1.0 404 Not Found", transport.UNSUPPORTED_ROUTE_BODY),
                        label,
                    )
                    self.assertEqual(records, [], label)
                    self.assertTrue(response["connection_closed"], label)

            supported_route = {
                "name": "nonstandard_method_supported_route",
                "request": transport.request_bytes(
                    headers=(("X-Oracle-Response", "json"),),
                    body=transport.REQUEST_BODY,
                    target=b"/v1/chat/completions",
                    method=b"G@T",
                    version=b"HTTP/1.0",
                ),
                "check_close": True,
                "upstream": True,
            }
            with patch.object(
                transport.UpstreamHandler,
                "do_G@T",
                transport.UpstreamHandler._serve_request,
                create=True,
            ):
                for label, binary in binaries:
                    with self.subTest(method="G@T", route="supported", binary=label):
                        before = time.time()
                        response, records = transport.run_probe(binary, supported_route, upstream)
                        after = time.time()
                        transport.assert_response_headers(self, response, before, after, label)
                        self.assertEqual(response["process_exit"], 0, response["stderr"])
                        self.assertEqual(
                            (response["status"], response["response_line"], response["body"]),
                            (502, "HTTP/1.0 502 Bad Gateway", b"upstream request failed"),
                            label,
                        )
                        self.assertEqual(records, [], label)
                        self.assertTrue(response["connection_closed"], label)
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
