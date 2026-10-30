"""Compare TinyHTTP header whitespace through the real isolated relay."""

import hashlib
import os
import threading
import unittest
from pathlib import Path

from test_cli import MODEX
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
import test_local_rewrite_01651_oracle as transport


BODY = transport.REQUEST_BODY
ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
COMMON = (
    b"POST /v1/responses HTTP/1.1\r\n"
    b"Host: 127.0.0.1\r\n"
    b"Content-Type: application/json\r\n"
    b"Authorization: Bearer synthetic-codex-key\r\n"
)
PRODUCTS = (
    ("0.165.1", ORACLE_01651),
    ("0.439.2", ORACLE_04392),
    ("Modex", MODEX),
)


def raw_request(headers=b"", framing=None, body=BODY):
    if framing is None:
        framing = b"Content-Length: " + str(len(body)).encode() + b"\r\n"
    return COMMON + headers + framing + b"Connection: close\r\n\r\n" + body


class RawHeaderHandler(transport.UpstreamHandler):
    def _serve_request(self):
        raw_headers = list(self.headers.raw_items())
        with self.server.records_lock:
            before = len(self.server.records)
            super()._serve_request()
            if len(self.server.records) > before:
                self.server.records[-1]["raw_headers"] = raw_headers


class RawHeaderUpstream(transport.Upstream):
    def __init__(self):
        super().__init__()
        self.records_lock = threading.RLock()
        self.RequestHandlerClass = RawHeaderHandler


class LoopbackHeaderWhitespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for label, path, expected in (
            ("Prodex 0.165.1", ORACLE_01651, ORACLE_01651_SHA256),
            ("Prodex 0.439.2", ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"{label} oracle checksum mismatch")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def _run(self, binary, name, request, upstream, **options):
        case = {"name": name, "request": request, "process_timeout": 15, **options}
        response, records = transport.run_probe(
            binary, case, upstream,
        )
        self.assertEqual(response["process_exit"], 0, response["stderr"])
        return response, records

    def test_boundary_ascii_whitespace_matches_both_releases(self):
        whitespace = (b" ", b"\t", b"\n", b"\v", b"\f", b"\r")
        cases = [
            (
                f"boundary_{byte.hex()}",
                byte + b"X-Boundary: " + byte + b"value" + byte + b"\r\n",
                b"Content-Length: " + byte + str(len(BODY)).encode() + byte + b"\r\n",
            )
            for byte in whitespace
        ]
        cases.append(("crlf_starts_a_separate_header", b"X-Boundary: value\r\nX-Injected: yes\r\n", None))
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, headers, framing in cases:
                with self.subTest(case=name):
                    captures = {}
                    for label, binary in PRODUCTS:
                        response, records = self._run(binary, name, raw_request(headers, framing), upstream)
                        self.assertEqual((response["status"], response["body"]), (200, transport.RESPONSES_RESPONSE), label)
                        self.assertEqual(len(records), 1, label)
                        self.assertEqual(records[0]["path"], "/v1/chat/completions", label)
                        captures[label] = records[0]["headers"]
                    for label, headers_seen in captures.items():
                        self.assertEqual(headers_seen["x-boundary"], "value", label)
                    if name == "crlf_starts_a_separate_header":
                        for label, headers_seen in captures.items():
                            self.assertEqual(headers_seen["x-injected"], "yes", label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_embedded_controls_fail_before_upstream_like_both_releases(self):
        cases = (
            ("embedded_vt", b"X-Embedded: left\x0bright\r\n"),
            ("embedded_ff", b"X-Embedded: left\x0cright\r\n"),
            ("embedded_cr", b"X-Embedded: left\rright\r\n"),
            ("embedded_lf", b"X-Embedded: left\nright\r\n"),
        )
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, header in cases:
                with self.subTest(case=name):
                    for label, binary in PRODUCTS:
                        response, records = self._run(binary, name, raw_request(header), upstream)
                        self.assertEqual((response["status"], response["body"]), (502, b"upstream request failed"), label)
                        self.assertEqual(records, [], label)

            response, records = self._run(
                MODEX, "embedded_header_name_whitespace",
                raw_request(b"X-\x0bEmbedded: value\r\n"), upstream,
            )
            self.assertEqual((response["status"], response["body"]), (400, b""))
            self.assertEqual(records, [])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_non_ascii_header_bytes_close_without_response_like_releases(self):
        cases = (
            ("non_ascii_header_name", b"X-\xc2\xa0Boundary: value\r\n", False, False),
            ("non_ascii_header_value", b"X-Boundary: value\xc2\xa0\r\n", False, False),
            ("fragmented_non_ascii_header_value", b"X-Boundary: value\xc2\xa0\r\n", True, False),
            ("half_closed_non_ascii_header_value", b"X-Boundary: value\xc2\xa0\r\n", False, True),
        )
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, header, fragmented, half_close in cases:
                request = raw_request(header)
                options = {"half_close": True} if half_close else {}
                if fragmented:
                    split = request.index(b"\xc2") + 1
                    options["request_parts"] = [request[:split], request[split:]]
                    options["request_part_delay_ms"] = 5
                for label, binary in PRODUCTS:
                    with self.subTest(case=name, product=label):
                        upstream.reset_records()
                        response, records = self._run(
                            binary, name, request, upstream, **options,
                        )
                        self.assertIsNone(response["status"], label)
                        self.assertEqual(response["read_error"], "RemoteDisconnected", label)
                        self.assertEqual(response["raw_response_head"], b"", label)
                        self.assertEqual(response["process_exit"], 0, label)
                        self.assertEqual(records, [], label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_non_ascii_header_after_valid_pipelined_request_gets_no_response(self):
        first = (
            COMMON
            + b"Content-Length: " + str(len(BODY)).encode() + b"\r\n\r\n"
            + BODY
        )
        invalid = raw_request(b"X-Boundary: value\xc2\xa0\r\n")
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for label, binary in PRODUCTS:
                with self.subTest(product=label):
                    upstream.reset_records()
                    response, records = transport.run_probe(
                        binary,
                        {
                            "name": "valid_then_non_ascii_pipeline",
                            "request": first,
                            "pipelined_requests": [first, invalid],
                            "process_timeout": 15,
                        },
                        upstream,
                    )
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(response["read_error"], "RemoteDisconnected", label)
                    self.assertEqual(
                        [item["status"] for item in response["pipelined_responses"]],
                        [200], label,
                    )
                    self.assertEqual(response["pipelined_responses"][0]["body"], transport.RESPONSES_RESPONSE, label)
                    self.assertEqual(len(records), 1, label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_equal_numeric_content_length_duplicates_are_safe_and_pipeline(self):
        duplicate_length = (
            b"Content-Length: \x0b" + str(len(BODY)).encode() + b"\x0c\r\n"
            b"content-length: " + str(len(BODY)).encode() + b"\r\n"
        )
        length = str(len(BODY)).encode()
        numeric_duplicate_length = b"Content-Length: 0" + length + b"\r\nContent-Length: " + length + b"\r\n"
        reverse_numeric_duplicate_length = b"Content-Length: " + length + b"\r\nContent-Length: 0" + length + b"\r\n"
        single_length = b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
        zero_length = (
            b"GET /unsupported HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: 0\r\ncontent-length: 0\r\n"
            b"Connection: close\r\n\r\n"
        )
        upstream = RawHeaderUpstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for label, binary in PRODUCTS:
                response, records = self._run(
                    binary, "duplicate_zero_content_length", zero_length, upstream,
                )
                self.assertEqual(
                    (response["status"], response["body"]),
                    (404, transport.UNSUPPORTED_ROUTE_BODY),
                    label,
                )
                self.assertEqual(records, [], label)

            for name, framing, fragmented in (
                ("duplicate_content_length", duplicate_length, False),
                ("numeric_duplicate_content_length", numeric_duplicate_length, False),
                ("reverse_numeric_duplicate_content_length", reverse_numeric_duplicate_length, False),
                ("fragmented_numeric_duplicate_content_length", numeric_duplicate_length, True),
            ):
                forwarded_bodies = {}
                request = raw_request(framing=framing)
                options = {}
                if fragmented:
                    split = request.index(b"Content-Length: 0") + len(b"Content-Length: 0")
                    options = {
                        "request_parts": [request[:split], request[split:]],
                        "request_part_delay_ms": 5,
                    }
                for label, binary in PRODUCTS:
                    upstream.reset_records()
                    response, records = self._run(binary, name, request, upstream, **options)
                    self.assertEqual(
                        (response["status"], response["body"]),
                        (200, transport.RESPONSES_RESPONSE),
                        label,
                    )
                    self.assertEqual(len(records), 1, label)
                    outbound_lengths = [
                        value for header, value in records[0]["raw_headers"]
                        if header.lower() == "content-length"
                    ]
                    self.assertEqual(outbound_lengths, [str(len(records[0]["body"]))], label)
                    forwarded_bodies[label] = records[0]["body"]
                self.assertEqual(forwarded_bodies["0.165.1"], forwarded_bodies["0.439.2"])
                self.assertEqual(forwarded_bodies["0.439.2"], forwarded_bodies["Modex"])

            for name, first_framing, second_framing in (
                ("duplicate_first", duplicate_length, single_length),
                ("duplicate_second", single_length, duplicate_length),
                ("numeric_duplicate_first", numeric_duplicate_length, single_length),
                ("numeric_duplicate_reverse", reverse_numeric_duplicate_length, single_length),
            ):
                first = COMMON + first_framing + b"\r\n" + BODY
                second = COMMON + second_framing + b"Connection: close\r\n\r\n" + BODY
                pipelined_bodies = {}
                for label, binary in PRODUCTS:
                    upstream.reset_records()
                    response, records = transport.run_probe(
                        binary,
                        {
                            "name": f"pipelined_{name}",
                            "request": first,
                            "pipelined_requests": [first, second],
                            "process_timeout": 15,
                        },
                        upstream,
                    )
                    self.assertEqual(response["process_exit"], 0, response["stderr"])
                    self.assertEqual(
                        [(item["status"], item["body"]) for item in response["pipelined_responses"]],
                        [(200, transport.RESPONSES_RESPONSE)] * 2,
                        label,
                    )
                    self.assertEqual(len(records), 2, label)
                    for record in records:
                        outbound_lengths = [
                            value for header, value in record["raw_headers"]
                            if header.lower() == "content-length"
                        ]
                        self.assertEqual(outbound_lengths, [str(len(record["body"]))], label)
                    pipelined_bodies[label] = [record["body"] for record in records]
                self.assertEqual(pipelined_bodies["0.165.1"], pipelined_bodies["0.439.2"])
                self.assertEqual(pipelined_bodies["0.439.2"], pipelined_bodies["Modex"])

            for name, framing in (
                ("truncated_duplicate_content_length", duplicate_length),
                ("truncated_numeric_duplicate_content_length", numeric_duplicate_length),
            ):
                truncated = raw_request(framing=framing, body=BODY[:-1])
                for label, binary in PRODUCTS:
                    upstream.reset_records()
                    response, records = self._run(
                        binary, name, truncated, upstream, half_close=True,
                    )
                    self.assertIsNone(response["status"], label)
                    self.assertEqual(records, [], label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)

    def test_ambiguous_framing_release_dispatch_remains_modex_fail_closed(self):
        mismatched_lengths = (
            (
                "conflicting_numeric_values",
                b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
                b"Content-Length: " + str(len(BODY) + 1).encode() + b"\r\n",
            ),
        )
        chunked_body = format(len(BODY), "X").encode() + b"\r\n" + BODY + b"\r\n0\r\n\r\n"
        conflicting_framing = (
            b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
            b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
            b"Transfer-Encoding: chunked\r\n"
        )
        duplicate_transfer_encoding = (
            b"Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n"
        )
        upstream = RawHeaderUpstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for name, framing in mismatched_lengths:
                for label, binary in PRODUCTS[:2]:
                    upstream.reset_records()
                    response, records = self._run(
                        binary, name, raw_request(framing=framing), upstream,
                    )
                    self.assertEqual(response["status"], 200, label)
                    self.assertEqual(len(records), 1, label)
                    outbound_lengths = [
                        value for header, value in records[0]["raw_headers"]
                        if header.lower() == "content-length"
                    ]
                    self.assertEqual(outbound_lengths, [str(len(records[0]["body"]))], label)
                response, records = self._run(
                    MODEX, name, raw_request(framing=framing), upstream,
                )
                self.assertEqual(
                    (response["status"], response["body"]),
                    (502, b"gateway request capture failed"),
                )
                self.assertEqual(records, [])

            for name, framing in (
                ("duplicate_content_length_and_transfer_encoding", conflicting_framing),
                ("duplicate_transfer_encoding", duplicate_transfer_encoding),
            ):
                request = raw_request(framing=framing, body=chunked_body)
                options = {}
                if name == "duplicate_content_length_and_transfer_encoding":
                    split = request.index(b"Transfer-Encoding: chunked") + len(b"Transfer-Encoding: chunked") - 3
                    options = {
                        "request_parts": [request[:split], request[split:]],
                        "request_part_delay_ms": 5,
                    }
                for label, binary in PRODUCTS:
                    upstream.reset_records()
                    response, records = self._run(
                        binary, name, request, upstream, **options,
                    )
                    if label == "Modex":
                        self.assertEqual(
                            (response["status"], response["body"]),
                            (502, b"gateway request capture failed"),
                            label,
                        )
                        self.assertEqual(records, [], label)
                    else:
                        self.assertEqual(
                            (response["status"], response["body"]),
                            (200, transport.RESPONSES_RESPONSE),
                            label,
                        )
                        self.assertEqual(len(records), 1, label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
