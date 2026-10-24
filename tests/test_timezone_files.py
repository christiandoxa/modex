"""Compare synthetic TZif files against the checksum-verified release."""

from datetime import datetime, timezone
import json
import os
import struct
import unittest

import test_cli
from test_sessions import compare_outputs


def timezone_fixture(leaps, *, transitions=((78796802, 1), (94694404, 0)), version=b"\0", footer=b""):
    # RFC 9636 section 3.2: transition, type, designation, leap and indicator arrays.
    def block(width, records, changes):
        time_format = ">i" if width == 4 else ">q"
        header = b"TZif" + version + b"\0" * 15 + struct.pack(">6I", 2, 2, len(records), len(changes), 2, 8)
        body = b"".join(struct.pack(time_format, epoch) for epoch, _ in changes)
        body += bytes(index for _, index in changes)
        body += struct.pack(">iBB", 0, 0, 0) + struct.pack(">iBB", 3600, 1, 4) + b"STD\0DST\0"
        body += b"".join(struct.pack(time_format, epoch) + struct.pack(">i", correction)
                         for epoch, correction in records)
        return header + body + b"\1\1\1\1"
    if version == b"\0":
        return block(4, leaps, transitions)
    return block(4, [], []) + block(8, leaps, transitions) + b"\n" + footer + b"\n"


class TimezoneFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def compare_epoch(self, data, epoch, *, fallback_mtime=False):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            if fallback_mtime:
                metadata = json.loads(original.read_text().splitlines()[0])
                metadata["timestamp"] = metadata["payload"]["timestamp"] = ""
                original.write_text(json.dumps(metadata) + "\n")
                os.utime(original, (epoch, epoch))
            else:
                original.write_text(original.read_text() + json.dumps({"updated_at": epoch}) + "\n")
        baseline, modex = compare_outputs(["session", "list", "--json"], change, timezone_data=data)
        self.assertEqual(modex, baseline)
        return baseline[0]["updated_at"]

    def test_positive_negative_and_mixed_leap_transitions(self):
        records = ([(78796800, 1), (94694401, 2)], [(78796800, -1), (94694399, -2)],
                   [(78796800, 1), (94694401, 0)], [(78796800, 1), (81215999, 2)])
        epochs = (-1, 0, *range(78796798, 78796806), *range(94694397, 94694408))
        for version in (b"\0", b"2", b"3"):
            for leaps in records:
                data = timezone_fixture(leaps, version=version)
                for epoch in epochs:
                    with self.subTest(version=version, leaps=leaps, epoch=epoch):
                        self.compare_epoch(data, epoch)
        self.assertEqual(self.compare_epoch(timezone_fixture(records[0]), 78796801),
                         "1972-07-01 01:00:01 +01:00")
        self.assertEqual(self.compare_epoch(timezone_fixture(records[0]), 78796801, fallback_mtime=True),
                         "1972-07-01 01:00:01 +01:00")

    def test_64bit_transitions_and_future_rules(self):
        leaps = [(78796800, 1), (94694401, 2)]
        for version in (b"2", b"3"):
            data = timezone_fixture(leaps, transitions=((2147483649, 1),), version=version,
                                    footer=b"STD0DST,M10.1.0,M4.1.0/3")
            for epoch in range(2147483643, 2147483653):
                with self.subTest(version=version, epoch=epoch):
                    self.compare_epoch(data, epoch)
            data = timezone_fixture(leaps, version=version, footer=b"STD0DST,M3.2.0,M11.1.0")
            for month in (1, 7):
                epoch = int(datetime(2050, month, 1, tzinfo=timezone.utc).timestamp())
                with self.subTest(version=version, month=month):
                    self.compare_epoch(data, epoch)

    def test_invalid_leap_files_fall_back_to_utc(self):
        records = ([(-1, 1)], [(78796800, 0)], [(78796800, 2)], [(78796800, -2147483648)],
                   [(78796800, 1), (78796800, 2)], [(78796800, 1), (78796799, 2)],
                   [(78796800, 1), (81215998, 2)], [(78796800, 1), (94694401, 3)],
                   [(78796800, 1), (94694401, 1)])
        for version in (b"\0", b"2", b"3"):
            for leaps in records:
                with self.subTest(version=version, leaps=leaps):
                    self.assertEqual(self.compare_epoch(timezone_fixture(leaps, version=version), 78796810),
                                     "1972-07-01 00:00:10 +00:00")
        data = timezone_fixture([(78796800, 1)], version=b"2")
        invalid = [data[:size] for size in (0, 43, 44, 63, len(data) - 3)]
        invalid += [data[:-6] + b"\0" + data[-5:], timezone_fixture([(78796800, 1)], version=b"4")]
        for footer in (b"DST-1", b"STD0", b"STD0DST,M3.2.0,M11.1.0"):
            invalid.append(timezone_fixture([(78796800, 1)], transitions=((2147483649, 1),),
                                            version=b"3", footer=footer))
        for index, data in enumerate(invalid):
            with self.subTest(invalid=index):
                self.assertEqual(self.compare_epoch(data, 78796810), "1972-07-01 00:00:10 +00:00")

    def test_indicator_pairs_follow_release(self):
        original = timezone_fixture([(78796800, 1)], version=b"2")
        for standard in (0, 1, 2):
            for universal in (0, 1, 2):
                data = original[:-6] + bytes((standard, 1, universal, 1)) + original[-2:]
                with self.subTest(standard=standard, universal=universal):
                    expected = "+00:00" if (standard, universal) == (0, 1) else "+01:00"
                    self.assertTrue(self.compare_epoch(data, 78796810).endswith(expected))


if __name__ == "__main__":
    unittest.main()
