"""Compare port 80 handling in a verified private network namespace."""

import hashlib
import unittest

from manual_real_codex_01660_route_comparison import require_isolated_environment
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY


class DefaultPort01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file() or not ORACLE.is_file():
            raise AssertionError("Build Modex and set PRODEX_ORACLE")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match 0.166.0")

    def test_default_port_forms_use_canonical_host(self):
        for name, host, omit, ipv6 in (("omitted", "127.0.0.1", True, False),
                                       ("explicit", "127.0.0.1", False, False),
                                       ("empty", "127.0.0.1:", True, False),
                                       ("shorthand", "127.1", True, False),
                                       ("ipv6-omitted", "[::1]", True, True),
                                       ("ipv6-explicit", "[::1]", False, True),
                                       ("ipv6-empty", "[::1]:", True, True)):
            observed = []
            for binary in (ORACLE, MODEX):
                with self.subTest(form=name, reference=binary == ORACLE):
                    posts, responses = observe_turns(
                        binary, [{"model": "deepseek-chat", "input": "synthetic default port"}],
                        [buffered_reply()], base_host=host, base_port=80,
                        omit_base_port=omit, upstream_ipv6=ipv6, latest_version="0.166.0",
                    )
                    self.assertEqual([item["status"] for item in responses], [200])
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(posts[0]["path"], "/v1/chat/completions")
                    self.assertEqual(posts[0]["headers"]["host"], "[::1]" if ipv6 else "127.0.0.1")
                    self.assertEqual(posts[0]["headers"]["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                    observed.append(posts[0]["body"])
            if len(observed) == 2:
                self.assertEqual(*observed)


if __name__ == "__main__":
    unittest.main()
