"""Compare production DeepSeek quota headers with the pinned ASCII header contract."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from test_local_rewrite import RunningLocalRewrite, json_bytes, post_relay, serving


class RawHeaderServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, headers, body):
        self.response_headers = headers
        self.response_body = body
        super().__init__(("127.0.0.1", 0), RawHeaderHandler)


class RawHeaderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        response = bytearray(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n")
        response.extend(b"Content-Length: " + str(len(self.server.response_body)).encode() + b"\r\n")
        response.extend(b"Connection: close\r\n")
        for name, value in self.server.response_headers:
            response.extend(name + b": " + value + b"\r\n")
        response.extend(b"\r\n")
        response.extend(self.server.response_body)
        self.wfile.write(response)
        self.close_connection = True

    def log_message(self, *_args):
        pass


class ProviderRateLimitDifferentialTests(unittest.TestCase):
    def test_bounded_http_errors_preserve_raw_quota_headers_without_projection(self):
        body = b'{"error":{"message":"synthetic limit"}}'
        for status in (401, 403, 429, 503):
            for streaming in (False, True):
                with self.subTest(status=status, streaming=streaming):
                    payload = b"data: " + body + b"\n\n" if streaming else body
                    with serving([{
                        "status": status, "body": payload, "chunked": True, "chunk_size": 7,
                        "response_headers": [
                            ("Content-Type", "text/event-stream" if streaming else "application/json"),
                            ("x-ratelimit-limit-requests", "100"),
                            ("x-ratelimit-remaining-requests", "0"),
                            ("Connection", "X-Synthetic-Hop"),
                            ("X-Synthetic-Hop", "synthetic-private-hop"),
                        ],
                    }]) as server:
                        with RunningLocalRewrite(server.server_port) as relay:
                            actual_status, headers, actual_body = post_relay(
                                relay.address, json_bytes({"model": "deepseek-chat", "input": "synthetic request", "stream": True}),
                            )
                    self.assertEqual((actual_status, actual_body), (status, payload))
                    self.assertEqual(headers.get("x-ratelimit-limit-requests"), "100")
                    self.assertFalse(any(name.startswith("x-deepseek-") for name in headers))
                    self.assertNotIn("x-synthetic-hop", headers)
                    self.assertNotIn("transfer-encoding", headers)
                    self.assertEqual(headers["content-length"], str(len(payload)))
                    self.assertEqual(len(server.records), 1)

    def test_oversized_error_returns_sanitized_gateway_failure_without_quota_headers(self):
        with serving([{
            "status": 429, "body": b"x" * (4 * 1024 * 1024 + 1),
            "response_headers": [("Content-Type", "text/event-stream"),
                                 ("x-ratelimit-limit-requests", "100"),
                                 ("x-ratelimit-remaining-requests", "0")],
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, body = post_relay(
                    relay.address, json_bytes({"model": "deepseek-chat", "input": "synthetic request"}),
                )
        self.assertEqual((status, body), (502, b"upstream request failed"))
        self.assertFalse(any("ratelimit" in name or name.startswith("x-deepseek-") for name in headers))
        self.assertEqual(len(server.records), 1)

    def test_unicode_reset_matches_prodex_header_value_rejection(self):
        body = (
            b'{"id":"chatcmpl_limits","model":"deepseek-chat",'
            b'"created":1700000000,"choices":[{"message":{"content":"ok"},'
            b'"finish_reason":"stop"}]}'
        )
        whitespace = "\u2003".encode("utf-8")
        self.assertTrue(any(byte > 126 for byte in whitespace))
        server = RawHeaderServer([
            (b"x-ratelimit-limit-requests", b"100"),
            (b"x-ratelimit-remaining-requests", b"40"),
            (b"x-ratelimit-reset-requests", whitespace + b"1700000000000" + whitespace),
            (b"x-ratelimit-limit-tokens", b"80"),
            (b"x-ratelimit-remaining-tokens", b"60"),
            (b"x-ratelimit-reset-tokens", b"1700000000000"),
        ], body)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, response = post_relay(
                    relay.address,
                    json_bytes({"model": "deepseek-chat", "input": "synthetic request"}),
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-deepseek-requests-primary-used-percent"), "60")
        self.assertIsNone(headers.get("x-deepseek-requests-primary-reset-at"))
        self.assertEqual(headers.get("x-deepseek-tokens-primary-used-percent"), "25")
        self.assertEqual(headers.get("x-deepseek-tokens-primary-reset-at"), "1700000000")
        self.assertEqual(json.loads(response)["output"][0]["content"][0]["text"], "ok")

    def test_malformed_reset_duration_is_not_projected_by_production_relay(self):
        body = (
            b'{"id":"chatcmpl_limits","model":"deepseek-chat",'
            b'"created":1700000000,"choices":[{"message":{"content":"ok"},'
            b'"finish_reason":"stop"}]}'
        )
        with serving([{
            "status": 200,
            "body": body,
            "response_headers": [
                ("Content-Type", "application/json"),
                ("x-ratelimit-limit-requests", "100"),
                ("x-ratelimit-remaining-requests", "40"),
                ("x-ratelimit-reset-requests", "1.2.3s"),
            ],
        }]) as server:
            with RunningLocalRewrite(server.server_port) as relay:
                status, headers, response = post_relay(
                    relay.address,
                    json_bytes({"model": "deepseek-chat", "input": "synthetic request"}),
                )

        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-deepseek-requests-primary-used-percent"), "60")
        self.assertIsNone(headers.get("x-deepseek-requests-primary-reset-at"))
        self.assertEqual(json.loads(response)["output"][0]["content"][0]["text"], "ok")


if __name__ == "__main__":
    unittest.main()
