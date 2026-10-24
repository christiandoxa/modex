"""Record the unapproved stream_payload redaction difference from the oracle."""

import json
from pathlib import Path
import tempfile
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess, runtime_record


RECORDS = (
    {
        "timestamp": "2026-10-24T01:02:03Z",
        "event": "stream_payload",
        "fields": {
            "source": "startup-source-marker Authorization: Bearer synthetic-bearer-startup api_key=synthetic-api-startup",
            "stream": "startup-text-marker Authorization: Bearer synthetic-bearer-startup api_key=synthetic-api-startup",
        },
    },
    {
        "timestamp": "2026-10-24T01:02:04Z",
        "event": "stream_payload",
        "fields": {
            "source": "append-source-marker Authorization: Bearer synthetic-bearer-append api_key=synthetic-api-append",
            "stream": "append-text-marker Authorization: Bearer synthetic-bearer-append api_key=synthetic-api-append",
        },
    },
)
SECRETS = (
    "synthetic-bearer-startup", "synthetic-api-startup",
    "synthetic-bearer-append", "synthetic-api-append",
)
VISIBLE_MARKERS = (
    "startup-source-marker", "startup-text-marker",
    "append-source-marker", "append-text-marker",
)


def record_bytes(record):
    return runtime_record(record["event"], record["fields"], record["timestamp"])


def capture_trace(binary, mode):
    with tempfile.TemporaryDirectory(prefix="modex-log-stream-redaction-") as directory:
        follower = StreamProcess(binary, mode, Path(directory), b"", record_bytes(RECORDS[0]))
        try:
            follower.require_marker(VISIBLE_MARKERS[1])
            follower.require_quiet(2.2)  # Allow the documented runtime path reconciliation interval.
            with follower.log.open("ab") as stream:
                stream.write(record_bytes(RECORDS[1]))
            follower.require_marker(VISIBLE_MARKERS[3])
            follower.require_quiet(0.2)
        finally:
            output = follower.stop()
        return {
            "returncode": follower.process.returncode,
            "stdout": output["stdout"],
            "stderr": output["stderr"],
        }


class LogStreamRedactionDifferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_stream_payload_masks_synthetic_secrets_and_records_oracle_difference(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                baseline = capture_trace(ORACLE, mode)
                actual = capture_trace(MODEX, mode)
                baseline_bytes = baseline["stdout"] + baseline["stderr"]
                actual_bytes = actual["stdout"] + actual["stderr"]

                for marker in VISIBLE_MARKERS:
                    self.assertIn(marker.encode("utf-8"), baseline_bytes)
                    self.assertIn(marker.encode("utf-8"), actual_bytes)
                for secret in SECRETS:
                    encoded = secret.encode("utf-8")
                    self.assertIn(encoded, baseline_bytes)
                    self.assertNotIn(encoded, actual_bytes)
                self.assertNotEqual(actual["stdout"], baseline["stdout"])

                if mode == "json":
                    baseline_events = [json.loads(line) for line in baseline["stdout"].splitlines()]
                    actual_events = [json.loads(line) for line in actual["stdout"].splitlines()]
                    self.assertEqual(len(baseline_events), 2)
                    self.assertEqual(len(actual_events), 2)
                    for index, event in enumerate(actual_events):
                        self.assertIn(VISIBLE_MARKERS[index * 2], event["source"])
                        self.assertIn(VISIBLE_MARKERS[index * 2 + 1], event["text"])


if __name__ == "__main__":
    unittest.main()
