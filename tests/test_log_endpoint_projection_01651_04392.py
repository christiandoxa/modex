"""Compare selected operational endpoint URL projections across releases."""

import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess, runtime_record


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
END_MARKER = "/end-marker"
URL_CASES = (
    ("custom URL without path", "custom://example.test", "path=upstream"),
    ("custom URL query without path", "custom://example.test?token=/hidden", "path=upstream"),
    ("custom URL with empty authority", "custom:///foo", "path=/foo"),
    ("custom URL with encoded dot segment", "custom:///%2e/foo", "path=/foo"),
    ("file URL backslash separator", "file://localhost/a\\b", "path=/a/b"),
    ("file URL backslash dot segments", "file://localhost/a\\..\\b", "path=/b"),
    ("file URL path keeps vertical bar", "file:///C|/a", "path=/C|/a"),
    ("file URL drive host with colon", "file://C:/a?token=/hidden", "path=/C:/a"),
    ("file URL drive host with vertical bar", "file://c|/a#fragment", "path=/c:/a"),
    ("file URL localhost path keeps vertical bar", "file://localhost/C|/a", "path=/C|/a"),
    ("invalid percent escape in host", "https://%zz/path", "path=upstream"),
    ("invalid percent encoded host delimiter", "https://foo%2Fbar/path", "path=upstream"),
    ("invalid percent encoded host credential delimiter", "https://a%40b/path", "path=upstream"),
    ("invalid unescaped host separator", "https://a|b/path", "path=upstream"),
    ("invalid unescaped host caret", "https://a^b/path", "path=upstream"),
    ("invalid percent encoded IDNA separator", "https://a%EF%BC%8Fb/path", "path=upstream"),
    ("invalid percent encoded UTF-8 host", "https://a%FFb/path", "path=upstream"),
    ("invalid percent encoded host whitespace", "https://a%C2%A0b/path", "path=upstream"),
    ("percent encoded valid host", "https://%65xample.test/path", "path=/path"),
    ("path vertical bar and redacted query", "https://example.test/a|b?token=synthetic-url-secret#fragment", "path=/a|b"),
    ("path caret", "https://example.test/a^b", "path=/a^b"),
    ("path reserved chars and query", "https://example.test/a;b,c=$&()+!@[]%/x?token=/hidden#fragment", "path=/a;b,c=$&()+!@[]%/x"),
    ("final marker", "https://example.test/end-marker", "path=/end-marker"),
)


def trace_urls(binary, argv0):
    records = []
    for index, (_, url, _) in enumerate(URL_CASES, 1):
        records.append(runtime_record(
            "upstream_start",
            {"request": str(index), "profile": "fixture", "route": "responses",
             "transport": "http", "url": url},
            f"2026-10-24T01:02:{index:02d}Z",
        ))
    with tempfile.TemporaryDirectory(prefix="modex-endpoint-projection-") as directory:
        follower = StreamProcess(
            binary, "plain", Path(directory), b"", b"", argv0=argv0,
        )
        try:
            follower.require_marker("Waiting for transcript, upstream payload, or token events.")
            follower.require_quiet(2.2)
            with follower.log.open("ab") as stream:
                stream.write(b"".join(records))
            follower.require_marker(END_MARKER)
            return follower.stop()
        finally:
            follower.stop()


class EndpointURLProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if (not ORACLE_01651.is_file()
                or hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256):
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")

    def test_non_special_empty_paths_and_file_backslashes_match_releases(self):
        expected = trace_urls(ORACLE_01651, "prodex")
        current = trace_urls(ORACLE, "prodex")
        actual = trace_urls(MODEX, "modex")
        self.assertEqual(expected, current)
        self.assertEqual(actual, expected)
        self.assertNotIn(b"synthetic-url-secret", actual["stdout"] + actual["stderr"])
        for label, _, display in URL_CASES:
            with self.subTest(case=label):
                self.assertIn(display.encode(), expected["stdout"])


if __name__ == "__main__":
    unittest.main()
