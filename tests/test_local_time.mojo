from std.collections import List
from std.os import setenv
from std.testing import assert_equal, assert_true

from modex.local_time import PosixZone, TimeZone, ZoneType, calendar_time, civil_days, civil_fields, format_local_epoch, signed_be


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
    for year in [-262143, -400, -1, 0, 1, 1900, 2000, 2050, 2100, 262142]:
        var fields = civil_fields(civil_days(year, 1, 1) * 86400)
        assert_equal(fields[0], year)
        assert_equal(fields[1], 1)
        assert_equal(fields[2], 1)
    var eastern = PosixZone("EST5EDT,M3.2.0,M11.1.0")
    var spring = civil_days(2050, 3, 13) * 86400 + 7 * 3600
    assert_equal(eastern.at(spring - 1).offset, -18000)
    assert_equal(eastern.at(spring).offset, -14400)
    var autumn = civil_days(2050, 11, 6) * 86400 + 6 * 3600
    assert_equal(eastern.at(autumn - 1).offset, -14400)
    assert_equal(eastern.at(autumn).offset, -18000)
    var southern = PosixZone("AEST-10AEDT,M10.1.0,M4.1.0/3")
    assert_equal(southern.at(civil_days(2050, 1, 1) * 86400).offset, 39600)
    assert_equal(southern.at(civil_days(2050, 7, 1) * 86400).offset, 36000)
    var julian = PosixZone("XST0XDT,J60/0,J300/0")
    var ordinal = PosixZone("XST0XDT,59/0,300/0")
    var leap_day = civil_days(2024, 2, 29) * 86400
    assert_equal(julian.at(leap_day).offset, 0)
    assert_equal(ordinal.at(leap_day).offset, 3600)
    var permanent = PosixZone("EST5EDT,0/0,J365/25")
    for epoch in [civil_days(2050, 1, 1) * 86400 + 5 * 3600 - 1,
                  civil_days(2050, 1, 1) * 86400 + 5 * 3600,
                  civil_days(2050, 7, 1) * 86400]:
        assert_equal(permanent.at(epoch).offset, -14400)
    var invalid_rules: List[String] = ["", "UT0", "UTC", "UTC25", "UTC0:60", "UTC0:0:60",
        "<bad name>0", "<ABC0", "XST0XDT,J0,J300", "XST0XDT,366,300",
        "XST0XDT,M0.1.0,M11.1.0", "XST0XDT,M3.0.0,M11.1.0",
        "XST0XDT,M3.6.0,M11.1.0", "XST0XDT,M3.2.7,M11.1.0",
        "XST0XDT,M3.2.0/168,M11.1.0", "XST0XDT,M3.2.0,M11.1.0,trailing"]
    for text in invalid_rules:
        var invalid_rejected = False
        try:
            var invalid = PosixZone(text)
        except:
            invalid_rejected = True
        assert_true(invalid_rejected, text)
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
    var leap_data = List[UInt8]()
    for index in range(44):
        leap_data.append(minimal[index])
    leap_data[31] = 1
    leap_data[35] = 1
    leap_data[39] = 2
    leap_data[43] = 8
    leap_data.extend([UInt8(0), 0, 0, 102, 1,
        0, 0, 0, 0, 0, 0, 0, 0, 14, 16, 1, 4,
        83, 84, 68, 0, 68, 83, 84, 0, 0, 0, 0, 100, 0, 0, 0, 1])
    var positive_leap = TimeZone(leap_data)
    assert_equal(positive_leap.at(100).offset, 0)
    assert_equal(positive_leap.at(101).offset, 3600)
    for index in range(73, 77):
        leap_data[index] = 255
    var negative_leap = TimeZone(leap_data)
    assert_equal(negative_leap.at(102).offset, 0)
    assert_equal(negative_leap.at(103).offset, 3600)
    leap_data[73] = 0
    leap_data[74] = 0
    leap_data[75] = 0
    for correction in [0, 2]:
        leap_data[76] = UInt8(correction)
        var invalid_rejected = False
        try:
            var invalid = TimeZone(leap_data)
        except:
            invalid_rejected = True
        assert_true(invalid_rejected)
    var overflow_rejected = False
    try:
        var overflow = positive_leap.at(Int.MAX)
    except:
        overflow_rejected = True
    assert_true(overflow_rejected)
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
