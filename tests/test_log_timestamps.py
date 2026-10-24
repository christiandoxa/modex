"""Oracle comparisons for timestamps rendered by `log last`."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


TIMESTAMPS = [
    "2024-03-10T06:59:59Z",
    "2024-03-10T07:00:00Z",
    "2024-11-03T05:59:59.9999Z",
    "2024-11-03T06:00:00Z",
    "2016-12-31T23:59:60Z",
    "2016-12-31T23:59:60.0Z",
    "2016-12-31T23:59:60.123456789Z",
    "0000-01-01T00:00:60Z",
    "2026-06-20T01:02:03.1Z",
    "2026-06-20T01:02:03.12Z",
    "2026-06-20T01:02:03.123Z",
    "2026-06-20T01:02:03.123456789Z",
    "2026-06-20T12:00:00.004+07:00",
    "2026-06-20 12:00:00 +07:00",
    "2026-06-20 12:00:00.004 +07:00",
    "+10000-01-01 00:00:00 +00:00",
    "-0001-01-01 00:00:00 +00:00",
    "2024-2-3 4:5:6 +00:00",
    "2024-01-01 00:00:00    +00:00",
    "2024-01-01 00:00:00\t+00:00",
    "2024-01-01 00:00:00 +00:00 ",
    "2024-01-01T00:00:00.123456789123Z",
    "2024-01-01t00:00:00z",
    "2024-01-01T00:00:00-00:00",
    "2024-01-01T00:00:00+00:99",
    "2024-01-01T00:00:00+99:00",
    "2024-01-01T+1:02:03Z",
    "-001-01-01T00:00:00Z",
    "2024-01-01T01:02:03++1:00",
    "10000-01-01 00:00:00 +00:00",
    "02026-01-01 00:00:00 +00:00",
    "1-1-1 0:0:0 +0000",
    "-1-1-1 0:0:0 +0000",
    "+1-1-1 0:0:0 +0000",
    "2024-01-0100:00:00+0000",
    " 2024-01-01 00:00:00+0000",
    "2024-01-01 00:00:00Z",
    "2024-1-1 0:0:0Z",
    "2024-01-01\u200300:00:00 +00:00",
    "2024-01-01 00:00:00\u2003+00:00",
    "\u20032024-01-01 00:00:00+0000",
    "2024-01-01\u200300:00:00\u2003+0000",
    "+00000002024-01-01 00:00:00+0000",
    "2024- 1- 1  0: 0: 0 +0000",
    "2024-01-01 00:00:00 +00 :00",
    "2024-01-01 00:00:00 +00\u200300",
    "2024-01-01 00:00:00\u2003Z",
    "+262142-12-31 23:59:59+0000",
    "-262143-01-01 00:00:00+0000",
    "-262143-01-01 00:00:00+0100",
    "+262142-12-31 23:59:59-0100",
    "1700000000",
    "-",
    "2024-2-3T4:5:6Z",
    "+010000-01-01T00:00:00Z",
    "0000-01-01T00:00:00Z",
    "2024-01-01T00:00:00+7:00",
    "2024-02-30T00:00:00Z",
    " 2024-01-01T00:00:00Z",
]
TIMEZONES = ("UTC", "Asia/Jakarta", "America/New_York")


class LogTimestampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def invoke(self, binary, timezone, timestamp, source, arguments):
        with tempfile.TemporaryDirectory(prefix="modex-log-timestamp-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            (root / ".prodex").mkdir(mode=0o700)
            runtime = root / "runtime"
            runtime.mkdir()

            if source == "runtime":
                record = {"timestamp": timestamp, "event": "token_usage", "fields": {
                    "input_tokens": "73", "output_tokens": "4"}}
                (runtime / "prodex-runtime-timestamp.log").write_text(json.dumps(record) + "\n")
            else:
                session = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
                session.parent.mkdir(parents=True)
                record = {"timestamp": timestamp, "type": "event_msg", "payload": {
                    "type": "user_message", "message": "timestamp-transcript-marker"}}
                session.write_text(json.dumps(record) + "\n")

            result = subprocess.run(
                sandbox_command(
                    binary,
                    root,
                    arguments,
                    argv0="prodex" if binary == ORACLE else "modex",
                    timezone=timezone,
                    environment={"PRODEX_RUNTIME_LOG_DIR": str(runtime)},
                ),
                capture_output=True,
                timeout=10,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr

    def test_runtime_and_transcript_timestamps_match_oracle_across_zones(self):
        for timezone in TIMEZONES:
            for timestamp in TIMESTAMPS:
                for source in ("runtime", "transcript"):
                    for arguments in (("log", "last", "--json"), ("log", "last")):
                        with self.subTest(timezone=timezone, timestamp=timestamp,
                                          source=source, arguments=arguments):
                            expected = self.invoke(ORACLE, timezone, timestamp, source, list(arguments))
                            actual = self.invoke(MODEX, timezone, timestamp, source, list(arguments))
                            self.assertEqual(actual, expected)
                            self.assertEqual(actual[0], 0, actual[2])
                            is_json = arguments[-1] == "--json"
                            marker = (b'"input_tokens":73' if is_json else b"input=73") if source == "runtime" else b"timestamp-transcript-marker"
                            self.assertIn(marker, actual[1])

    def test_historical_offsets_and_leap_seconds_match_oracle(self):
        cases = [
            ("Europe/Amsterdam", "1900-01-01T00:00:00Z"),
            ("Europe/Amsterdam", "1900-01-01T00:00:60.123Z"),
            ("Europe/Amsterdam", "1960-01-01T00:00:00Z"),
            ("Africa/Monrovia", "1960-01-01T00:00:00Z"),
            ("XXX-0:00:30", "1900-01-01T00:00:00Z"),
            ("XXX0:00:30", "1900-01-01T00:00:00Z"),
        ]
        for timezone, timestamp in cases:
            for source in ("runtime", "transcript"):
                for arguments in (("log", "last", "--json"), ("log", "last")):
                    with self.subTest(timezone=timezone, timestamp=timestamp,
                                      source=source, arguments=arguments):
                        expected = self.invoke(ORACLE, timezone, timestamp, source, list(arguments))
                        actual = self.invoke(MODEX, timezone, timestamp, source, list(arguments))
                        self.assertEqual(actual, expected)
                        self.assertEqual(actual[0], 0, actual[2])


if __name__ == "__main__":
    unittest.main()
