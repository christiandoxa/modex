"""DeepSeek loopback base URL scheme comparison against Prodex 0.166.0."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class ProviderBaseUrlScheme01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if (not ORACLE.is_file()
                or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_http_scheme_is_case_insensitive_for_loopback_upstreams(self):
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(
                binary,
                [{"model": "deepseek-chat", "input": "synthetic uppercase scheme"}],
                [buffered_reply()],
                latest_version="0.166.0",
                base_scheme="HTTP",
            )
            self.assertEqual([response["status"] for response in responses], [200])
            self.assertEqual(len(upstream), 1)
            self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
            self.assertEqual(upstream[0]["headers"]["authorization"],
                             "Bearer synthetic-provider-key")
            observations.append(upstream[0]["body"])

        self.assertEqual(observations[0], observations[1])

    def test_backslash_path_separator_matches_active_release(self):
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    [{"model": "deepseek-chat", "input": "synthetic backslash path"}],
                    [buffered_reply()],
                    latest_version="0.166.0",
                    base_path="\\v1",
                )
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual([request["path"] for request in upstream], ["/v1/chat/completions"])
                self.assertEqual(upstream[0]["headers"]["authorization"],
                                 "Bearer synthetic-provider-key")

    def test_backslash_path_separator_preserves_anthropic_route(self):
        reply = {"status": 200, "content_type": "application/json", "body": (
            b'{"id":"msg_synthetic","type":"message","role":"assistant",'
            b'"model":"deepseek-chat","content":[{"type":"text","text":"synthetic reply"}],'
            b'"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
        )}
        turn = {"model": "deepseek-chat", "input": "synthetic", "stream": False,
                "tools": [{"type": "web_search_preview"}]}
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [turn], [reply], base_path="\\v1", latest_version="0.166.0",
                )
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual([request["path"] for request in upstream], ["/v1/anthropic/v1/messages"])
                self.assertEqual(upstream[0]["headers"]["x-api-key"], "synthetic-provider-key")

    def test_strict_beta_backslash_path_matches_active_release(self):
        shared_config = (
            "[deepseek]\n"
            "strict_tools = true\n"
            'beta_base_url = "http://127.0.0.1:{upstream_port}\\\\beta"\n'
        )
        turn = {
            "model": "deepseek-chat", "input": "synthetic strict beta path",
            "tools": [{"type": "function", "name": "lookup", "parameters": {
                "type": "object", "properties": {"query": {"type": "string"}},
            }}],
        }
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, [turn], [buffered_reply()], latest_version="0.166.0",
                    shared_config=shared_config,
                )
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual([request["path"] for request in upstream], ["/beta/chat/completions"])
                self.assertEqual(upstream[0]["headers"]["authorization"],
                                 "Bearer synthetic-provider-key")

    def test_backslash_path_does_not_weaken_loopback_or_credential_guards(self):
        for host in ("8.8.8.8", "127.0.0.1\\@attacker"):
            with self.subTest(host=host):
                try:
                    observe_turns(
                        MODEX,
                        [{"model": "deepseek-chat", "input": "synthetic rejected host"}],
                        [buffered_reply()],
                        latest_version="0.166.0",
                        base_host=host,
                        base_path="\\v1",
                    )
                except AssertionError as error:
                    status, _, stderr, _, upstream = error.args[0]
                    self.assertNotEqual(status, 0)
                    self.assertTrue(b"loopback" in stderr.lower()
                                    or b"credential-free" in stderr.lower())
                    self.assertEqual(upstream, [])
                else:
                    self.fail(f"Modex accepted unsafe authority {host!r}")

    def test_strict_beta_backslash_keeps_loopback_and_credential_guards(self):
        unsafe_beta_urls = (
            'http://8.8.8.8:{upstream_port}\\\\beta',
            'http://127.0.0.1:{upstream_port}\\\\@attacker/beta',
        )
        for beta_url in unsafe_beta_urls:
            shared_config = (
                "[deepseek]\nstrict_tools = true\n"
                f'beta_base_url = "{beta_url}"\n'
            )
            with self.subTest(beta_url=beta_url):
                try:
                    observe_turns(
                        MODEX,
                        [{"model": "deepseek-chat", "input": "synthetic rejected beta URL"}],
                        [buffered_reply()], latest_version="0.166.0",
                        shared_config=shared_config,
                    )
                except AssertionError as error:
                    status, _, stderr, _, upstream = error.args[0]
                    self.assertNotEqual(status, 0)
                    self.assertTrue(b"loopback" in stderr.lower()
                                    or b"credential-free" in stderr.lower())
                    self.assertEqual(upstream, [])
                else:
                    self.fail(f"Modex accepted unsafe beta URL {beta_url!r}")

    def test_spaces_in_loopback_upstream_paths_are_percent_encoded(self):
        cases = (
            ("/v1/hello world", "/v1/hello%20world/chat/completions"),
            ("/v1/ spaced /path", "/v1/%20spaced%20/path/chat/completions"),
            ("/v1/é space/", "/v1/%C3%A9%20space/chat/completions"),
            ("/v1/already%20encoded", "/v1/already%20encoded/chat/completions"),
        )
        for base_path, expected_path in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(base_path=base_path, reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic path"}],
                        [buffered_reply()], base_path=base_path, latest_version="0.166.0",
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([request["path"] for request in upstream], [expected_path])
                    self.assertEqual(upstream[0]["headers"]["authorization"],
                                     "Bearer synthetic-provider-key")

    def test_at_sign_in_path_matches_release_without_weakening_authority_guards(self):
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary,
                    [{"model": "deepseek-chat", "input": "synthetic at-sign path"}],
                    [buffered_reply()], latest_version="0.166.0", base_path="/v1/a@b",
                )
                self.assertEqual([row["status"] for row in responses], [200])
                self.assertEqual([row["path"] for row in upstream], ["/v1/a@b/chat/completions"])
                self.assertEqual(upstream[0]["headers"]["authorization"],
                                 "Bearer synthetic-provider-key")

        for host, path in (
            ("synthetic-user@127.0.0.1", "/v1"),
            ("synthetic-user%40name@127.0.0.1", "/v1"),
            ("127.0.0.1%40attacker", "/v1"),
            ("127.0.0.1", "\\@attacker/v1"),
        ):
            with self.subTest(rejected_host=host, rejected_path=path):
                try:
                    observe_turns(
                        MODEX,
                        [{"model": "deepseek-chat", "input": "synthetic rejected userinfo"}],
                        [buffered_reply()], latest_version="0.166.0", base_host=host,
                        base_path=path,
                    )
                except AssertionError as error:
                    status, _, stderr, _, upstream = error.args[0]
                    self.assertNotEqual(status, 0)
                    self.assertTrue(stderr)
                    self.assertEqual(upstream, [])
                else:
                    self.fail(f"Modex accepted credentialed host {host!r}")

    def test_spaces_in_anthropic_messages_upstream_paths_are_percent_encoded(self):
        reply = {"status": 200, "content_type": "application/json", "body": (
            b'{"id":"msg_synthetic","type":"message","role":"assistant",'
            b'"model":"deepseek-chat","content":[{"type":"text","text":"synthetic reply"}],'
            b'"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
        )}
        cases = (
            ("/v1/hello world", "/v1/hello%20world/anthropic/v1/messages"),
            ("/v1/é space/", "/v1/%C3%A9%20space/anthropic/v1/messages"),
        )
        for base_path, expected_path in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(base_path=base_path, reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic path", "stream": False,
                          "tools": [{"type": "web_search_preview"}]}],
                        [reply], base_path=base_path, latest_version="0.166.0",
                    )
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([request["path"] for request in upstream], [expected_path])
                    self.assertEqual(upstream[0]["headers"]["x-api-key"], "synthetic-provider-key")
