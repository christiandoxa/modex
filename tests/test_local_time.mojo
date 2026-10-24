from std.collections import List
from std.os import setenv
from std.testing import assert_equal, assert_true

from modex.local_time import TimeZone, ZoneType, calendar_time, format_local_epoch, signed_be


def main() raises:
    var utc = ZoneType(0, "UTC")
    assert_equal(calendar_time(0, utc), "1970-01-01 00:00:00 +00:00")
    assert_equal(calendar_time(-1, utc), "1969-12-31 23:59:59 +00:00")
    assert_equal(calendar_time(951782400, utc), "2000-02-29 00:00:00 +00:00")
    assert_equal(calendar_time(-62167219200, utc), "0000-01-01 00:00:00 +00:00")
    assert_equal(calendar_time(253402300800, utc), "+10000-01-01 00:00:00 +00:00")
    assert_equal(calendar_time(Int.MAX, utc), String(Int.MAX))
    assert_equal(signed_be([255, 255, 255, 255], 0, 4), -1)
    assert_equal(signed_be([255, 255, 255, 255, 255, 255, 255, 255], 0, 8), -1)
    assert_true(setenv("TZ", "UTC"))
    assert_equal(format_local_epoch(0), "1970-01-01 00:00:00 +00:00")
    assert_true(setenv("TZ", "Asia/Jakarta"))
    assert_equal(format_local_epoch(1792800000), "2026-10-24 07:00:00 +07:00")
    assert_true(setenv("TZ", "America/New_York"))
    assert_equal(format_local_epoch(1767225600), "2025-12-31 19:00:00 -05:00")
    assert_equal(format_local_epoch(1782864000), "2026-06-30 20:00:00 -04:00")
    var minimal = List[UInt8](length=54, fill=0)
    minimal[0] = 84
    minimal[1] = 90
    minimal[2] = 105
    minimal[3] = 102
    minimal[39] = 1
    minimal[43] = 4
    minimal[50] = 85
    minimal[51] = 84
    minimal[52] = 67
    var synthetic = TimeZone(minimal)
    assert_equal(synthetic.at(0).offset, 0)
    assert_equal(synthetic.at(0).name, "UTC")
    for change in range(5):
        var bytes = minimal.copy()
        if change == 0:
            bytes[3] = 0
        elif change == 1:
            bytes[39] = 0
        elif change == 2:
            bytes[43] = 255
        elif change == 3:
            bytes[48] = 2
        else:
            bytes[53] = 65
        var invalid_rejected = False
        try:
            var invalid = TimeZone(bytes)
        except:
            invalid_rejected = True
        assert_true(invalid_rejected)
    var rejected = False
    try:
        var malformed = TimeZone(List[UInt8](length=44, fill=0))
    except:
        rejected = True
    assert_true(rejected)
    print("TZif parsing, signed epochs, Gregorian calendar and local-time checks: PASS")
