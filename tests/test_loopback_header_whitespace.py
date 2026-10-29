"""Compare TinyHTTP header whitespace through the real isolated relay."""

import hashlib
import threading
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
import test_local_rewrite_01651_oracle as transport


BODY = transport.REQUEST_BODY
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

    def _run(self, binary, name, request, upstream):
        response, records = transport.run_probe(
            binary, {"name": name, "request": request, "process_timeout": 15}, upstream,
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

    def test_duplicate_and_conflicting_framing_stay_fail_closed(self):
        duplicate_length = (
            b"Content-Length: \x0b" + str(len(BODY)).encode() + b"\x0c\r\n"
            b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
        )
        chunked_body = str(len(BODY)).encode() + b"\r\n" + BODY + b"\r\n0\r\n\r\n"
        conflicting_framing = (
            b"Content-Length: \x0b" + str(len(BODY)).encode() + b"\x0c\r\n"
            b"Transfer-Encoding: \x0bchunked\x0c\r\n"
        )
        upstream = transport.Upstream()
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            for label, binary in PRODUCTS[:2]:
                response, records = self._run(
                    binary, "duplicate_content_length",
                    raw_request(framing=duplicate_length), upstream,
                )
                self.assertEqual(response["status"], 200, label)
                self.assertEqual(len(records), 1, label)
            response, records = self._run(
                MODEX, "duplicate_content_length",
                raw_request(framing=duplicate_length), upstream,
            )
            self.assertEqual((response["status"], response["body"]), (502, b"gateway request capture failed"))
            self.assertEqual(records, [])

            for label, binary in PRODUCTS:
                response, records = self._run(
                    binary, "content_length_and_transfer_encoding",
                    raw_request(framing=conflicting_framing, body=chunked_body), upstream,
                )
                self.assertEqual(records, [], label)
                if label == "Modex":
                    self.assertEqual(response["status"], 502, label)
                else:
                    self.assertIsNone(response["status"], label)
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
