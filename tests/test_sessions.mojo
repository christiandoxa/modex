from std.testing import assert_equal, assert_false, assert_true

from modex.cli import parse_session_options, unsigned_value
from modex.json import JsonDocument
from modex.session_time import integer_timestamp, timestamp_key
from modex.sessions import SessionReport, starts_session
from modex.text import trim_text


def main() raises:
    assert_equal(timestamp_key("1970-01-01T00:00:00Z").value(), 0)
    assert_equal(timestamp_key("1970-01-01T01:00:00+01:00").value(), 0)
    assert_equal(timestamp_key("1969-12-31T23:59:59Z").value(), -1)
    assert_equal(timestamp_key("2000-02-29T00:00:00Z").value(), 951782400)
    assert_false(timestamp_key("1900-02-29T00:00:00Z"))
    assert_false(timestamp_key("2026-01-01T24:00:00Z"))
    assert_false(timestamp_key("2026-01-01T00:00:00.Z"))
    assert_equal(integer_timestamp("-9223372036854775808").value(), Int.MIN)
    assert_false(integer_timestamp("9223372036854775808"))
    assert_equal(unsigned_value("18446744073709551615"), UInt64.MAX)
    assert_equal(trim_text(chr(0x2000) + " title " + chr(0xA0)), "title")
    assert_equal(trim_text("\x1cname\x1c"), "\x1cname\x1c")
    var metadata = JsonDocument("{\"type\":\"session_meta\",\"timestamp\":\"2026-10-24T00:00:00Z\",\"payload\":{\"id\":\"session-a\",\"timestamp\":\"2026-10-24T00:00:00Z\",\"cwd\":\"/workspace\",\"originator\":\"test\",\"cli_version\":\"0.162.0\",\"title\":\"  Test title  \"}}")
    assert_true(starts_session(metadata))
    var report = SessionReport("filename", "", "", "", "", "", "/fixture.jsonl", 0)
    report.apply(metadata)
    assert_equal(report.id, "session-a")
    assert_equal(report.thread_name, "Test title")
    var event = JsonDocument("{\"type\":\"event_msg\",\"payload\":{\"id\":\"event-id\",\"thread_name\":\"New title\"},\"timestamp\":\"2026-10-24T01:00:00Z\"}")
    report.apply(event)
    assert_equal(report.id, "session-a")
    assert_equal(report.thread_name, "New title")
    var empty_type = JsonDocument("{\"type\":\"\",\"id\":\"should-not-replace\"}")
    report.apply(empty_type)
    assert_equal(report.id, "session-a")
    assert_false(starts_session(empty_type))
    var options = parse_session_options(["modex", "session", "list", "--json", "--limit=0", "--parent-only"])
    assert_equal(options.output, "json")
    assert_equal(options.limit.value(), UInt64(0))
    assert_true(options.parent_only)
    var rejected = False
    try:
        var invalid = parse_session_options(["modex", "session", "list", "--json", "--id-only"])
    except:
        rejected = True
    assert_true(rejected)
    print("session metadata, filters, timestamps, text and argument checks: PASS")
