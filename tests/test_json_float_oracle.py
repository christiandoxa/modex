"""Oracle comparisons for raw numeric upstream response statuses."""

from pathlib import Path
import tempfile
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess


NUMBERS = (
    "0", "1", "18446744073709551614", "18446744073709551615",
    "18446744073709551616", "18446744073709551617", "18446744073709551616.0",
    "18446744073709551616.0000001", "9007199254740993.0",
    "9007199254740993.0000001", "4.9406564584124654e-324",
    "2.2250738585072014e-308", "1.7976931348623157e308",
    "1.7976931348623158e308", "1.7976931348623159e308",
    "1e400", "1e999999999999999999999", "1e-400", "-1e-400",
    "1e-999999999999999999999", "0e999999999999999999999",
    "-0e-999999999999999999999", "01", "-01", "00.1", "01e2",
    "0." + "0" * 100000 + "1e100001",
)


def corpus():
    lines = [
        (f'{{"timestamp":"2026-10-24T01:02:03Z","event":"upstream_response",'
         f'"fields":{{"status":{number},"reason":"float-case-{index}"}}}}\n').encode()
        for index, number in enumerate(NUMBERS)
    ]
    marker = "json-float-boundary-end"
    lines.append((f'{{"timestamp":"2026-10-24T01:02:04Z","event":"upstream_response",'
                  f'"fields":{{"reason":"{marker}"}}}}\n').encode())
    return b"".join(lines), marker


def trace(binary):
    raw, marker = corpus()
    with tempfile.TemporaryDirectory(prefix="modex-json-float-") as directory:
        follower = StreamProcess(binary, "json", Path(directory), b"", b"invalid startup line\n")
        try:
            follower.require_marker("Waiting for transcript, upstream payload, or token events.")
            follower.require_quiet(2.2)
            with follower.log.open("ab") as stream:
                stream.write(raw)
            follower.require_marker(marker, timeout=8)
            follower.require_quiet(0.25)
            return follower.stop()
        finally:
            follower.stop()


class JsonFloatOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_raw_status_numbers_match_frozen_stream(self):
        expected = trace(ORACLE)
        actual = trace(MODEX)
        if actual != expected:
            mismatch_dir = Path(__file__).resolve().parents[1] / "test-results/json-float-boundaries"
            mismatch_dir.mkdir(parents=True, exist_ok=True)
            raw, _ = corpus()
            (mismatch_dir / "input.jsonl").write_bytes(raw)
            for label, output in (("oracle", expected), ("modex", actual)):
                (mismatch_dir / f"{label}.stdout").write_bytes(output["stdout"])
                (mismatch_dir / f"{label}.stderr").write_bytes(output["stderr"])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
