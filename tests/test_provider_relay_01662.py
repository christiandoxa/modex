"""Pin selected provider relay routes and bodyless framing to Prodex 0.166.2."""

import hashlib
import textwrap
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_super_launch import CODEX
import test_provider_passthrough_01660 as historical


def _route_wire_client(path, method, body):
    script = CODEX[:CODEX.index("passthrough = scenario")] + textwrap.dedent(f'''\
        import socket
        target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
        path = {path!r}
        method = {method!r}
        body = bytes.fromhex({body.hex()!r})
        request = (f"{{method}} {{path}} HTTP/1.1\\r\\nHost: {{target.hostname}}:{{target.port}}\\r\\n"
                   f"Authorization: {{authorization}}\\r\\nContent-Type: application/json\\r\\n"
                   f"Content-Length: {{len(body)}}\\r\\nConnection: close\\r\\n\\r\\n").encode() + body
        connection = socket.create_connection((target.hostname, target.port), timeout=5)
        connection.settimeout(2)
        connection.sendall(request)
        wire = bytearray()
        eof = False
        timed_out = False
        while True:
            try:
                chunk = connection.recv(65536)
            except TimeoutError:
                timed_out = True
                break
            if not chunk:
                eof = True
                break
            wire.extend(chunk)
        connection.close()
        save({{"kind": "wire-response", "wire": bytes(wire).hex(), "eof": eof,
              "timed_out": timed_out}})
        print("synthetic-wire-complete")
        raise SystemExit(0)
    ''')
    return script


def _route_wire(binary, path, method="GET", body=b""):
    return historical.observe_response_wire(
        binary,
        {"status": 200, "content_type": "application/json", "body": b"unused"},
        client_script=_route_wire_client(path, method, body),
    )


def _expect_continue_wire_client(body):
    return CODEX[:CODEX.index("passthrough = scenario")] + textwrap.dedent(f'''\
        import socket
        target = urlsplit(config["model_providers.prodex-deepseek.base_url"])
        body = bytes.fromhex({body.hex()!r})
        request = (f"POST /v1/chat/completions HTTP/1.1\\r\\nHost: {{target.hostname}}:{{target.port}}\\r\\n"
                   f"Authorization: {{authorization}}\\r\\nContent-Type: application/json\\r\\n"
                   f"Expect: 100-continue\\r\\nContent-Length: {{len(body)}}\\r\\nConnection: close\\r\\n\\r\\n").encode()
        connection = socket.create_connection((target.hostname, target.port), timeout=3)
        connection.settimeout(2)
        connection.sendall(request)
        wire = bytearray()
        head = bytearray()
        while b"\\r\\n\\r\\n" not in head:
            chunk = connection.recv(4096)
            if not chunk:
                break
            head.extend(chunk)
        if b"\\r\\n\\r\\n" in head:
            first, _, remainder = bytes(head).partition(b"\\r\\n\\r\\n")
            wire.extend(first + b"\\r\\n\\r\\n" + remainder)
            if int(first.split(b" ", 2)[1]) == 100:
                connection.sendall(body)
        eof = False
        timed_out = False
        while True:
            try:
                chunk = connection.recv(65536)
            except TimeoutError:
                timed_out = True
                break
            if not chunk:
                eof = True
                break
            wire.extend(chunk)
        connection.close()
        save({{"kind": "wire-response", "wire": bytes(wire).hex(), "eof": eof,
              "timed_out": timed_out}})
        print("synthetic-wire-complete")
        raise SystemExit(0)
    ''')


def _response_header_lines(wire):
    head, separator, _ = wire.partition(b"\r\n\r\n")
    if not separator:
        raise AssertionError(f"response has no header terminator: {wire!r}")
    return [(name.decode("ascii"), value.decode("ascii").strip())
            for name, value in (line.split(b":", 1) for line in head.split(b"\r\n")[1:])]


class ProviderRelay01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")
        cls.original_reference = (historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256)
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = MODEX, ORACLE, ORACLE_SHA256

    @classmethod
    def tearDownClass(cls):
        historical.MODEX, historical.ORACLE, historical.ORACLE_SHA256 = cls.original_reference

    def test_models_catalog_aliases_methods_queries_and_errors_match_active_release(self):
        historical.ProviderBufferedMetadata01660Tests.test_models_catalog_aliases_methods_queries_and_errors_match_active_release(self)

    def test_bodyless_sse_connection_header_preserves_observed_reuse(self):
        historical.ProviderBufferedMetadata01660Tests.test_bodyless_sse_connection_header_preserves_observed_reuse(self)

    def test_responses_empty_204_sse_and_bodyless_controls_match_active_wire(self):
        historical.ProviderBufferedMetadata01660Tests.test_responses_empty_204_sse_and_bodyless_controls_match_active_wire(self)

    def test_model_catalog_forwarding_preserves_custom_base_path_and_query(self):
        body = b'{"synthetic":true}'
        turn = [{"_method": "POST", "_path": "/models?trace=synthetic",
                 "_raw_body": body.decode("ascii")}]
        reply = [{"status": 200, "content_type": "application/json", "body": body}]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary, turn, reply, base_path="/tenant/api/v9", latest_version="0.166.2",
            )
            self.assertEqual([(row["method"], row["path"], row["body"]) for row in upstream], [
                ("POST", "/tenant/api/v9/models?trace=synthetic", body),
            ])
            self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer synthetic-provider-key")
            self.assertEqual([(row["status"], bytes.fromhex(row["body"])) for row in responses], [(200, body)])
            observed.append((upstream[0]["path"], upstream[0]["body"], responses[0]["body"]))
        self.assertEqual(observed[0], observed[1])

    def test_local_provider_error_routes_preserve_oracle_wire_header_casing(self):
        cases = (
            ("/v1/unknown", "GET", b"", 404),
            ("/v1/%zz", "GET", b"", 400),
            ("/v1/responses", "POST", b"{", 502),
        )
        for path, method, body, expected_status in cases:
            observed = []
            for binary in (ORACLE, MODEX):
                with self.subTest(path=path, binary=str(binary)):
                    upstream, wire, eof, timed_out = _route_wire(binary, path, method, body)
                    self.assertEqual(upstream, [], "local errors must not reach the provider")
                    self.assertTrue(eof, "the local error response should close its client socket")
                    self.assertFalse(timed_out)
                    head, separator, response_body = wire.partition(b"\r\n\r\n")
                    self.assertTrue(separator)
                    status = int(head.split(b" ", 2)[1])
                    headers = _response_header_lines(wire)
                    self.assertEqual(status, expected_status)
                    content_type = "application/json" if expected_status != 502 else "text/plain; charset=utf-8"
                    self.assertIn(("Content-Type", content_type), headers)
                    observed.append((status, [row for row in headers if row[0].lower() != "date"], response_body))
            self.assertEqual(observed[0], observed[1])

    def test_expect_continue_interim_defaults_match_without_release_content_length(self):
        body = b'{"model":"deepseek-chat","messages":[]}'
        reply = {"status": 200, "content_type": "application/json", "body": b'{"id":"synthetic"}'}
        client = _expect_continue_wire_client(body)
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, wire, eof, timed_out = historical.observe_response_wire(
                    binary, reply, client_script=client,
                )
                self.assertEqual(len(upstream), 1)
                self.assertEqual(upstream[0]["body"], body)
                self.assertTrue(eof)
                self.assertFalse(timed_out)
                interim, separator, final = wire.partition(b"\r\n\r\n")
                self.assertTrue(separator)
                self.assertEqual(interim.split(b" ", 2)[:2], [b"HTTP/1.1", b"100"])
                headers = _response_header_lines(wire)
                self.assertEqual(headers[0], ("Server", "tiny-http (Rust)"))
                self.assertEqual(headers[1][0], "Date")
                self.assertRegex(
                    headers[1][1],
                    r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$",
                )
                if binary == ORACLE:
                    self.assertEqual(headers[2], ("Content-Length", "0"))
                else:
                    self.assertNotIn("content-length", [name.lower() for name, _ in headers])
                final_head, final_separator, final_body = final.partition(b"\r\n\r\n")
                self.assertTrue(final_separator)
                self.assertTrue(final_head.startswith(b"HTTP/1.1 200 OK\r\n"))
                self.assertEqual(final_body, b'{"id":"synthetic"}')


if __name__ == "__main__":
    unittest.main()
