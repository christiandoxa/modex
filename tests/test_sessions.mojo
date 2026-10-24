from std.testing import assert_equal, assert_false, assert_true

from modex.cli import jaro_similarity, parse_session_options, unsigned_value
from modex.json import JsonDocument
from modex.session_time import integer_timestamp, timestamp_key
from modex.sessions import SessionReport, starts_session
from modex.text import character_width, fit_cell, pad_cell, section_header, text_width, trim_text, wrap_text


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
    assert_equal(fit_cell("abc", 0), "")
    assert_equal(fit_cell("abcd", 3), "...")
    assert_equal(fit_cell("abcdef", 5), "ab...")
    assert_equal(pad_cell("abc", 5), "abc  ")
    assert_equal(section_header("Sessions", 14), "[ Sessions ] =")
    assert_equal(wrap_text("abc abcdef abc", 4), ["abc", "abcd", "ef", "abc"])
    assert_equal(character_width(0x754C), 2)
    assert_equal(character_width(0xAD), 0)
    assert_equal(text_width("Cafe" + chr(0x301)), 4)
    assert_equal(text_width(chr(0x754C) + chr(0x754C)), 4)
    assert_equal(fit_cell(chr(0x754C) + "abc", 4), "...")
    assert_equal(fit_cell(chr(0x301), 0), "")
    assert_equal(pad_cell(chr(0x754C), 3), chr(0x754C) + " ")
    assert_equal(wrap_text("first\n\nnext\n", 8), ["first", "", "next"])
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
    var resumed = parse_session_options(["modex", "session", "resume", "--", "--help"])
    assert_equal(resumed.output, "resume")
    assert_equal(resumed.query, "--help")
    var current = parse_session_options(["modex", "session", "current", "--json"])
    assert_false(current.directory)
    var relative = parse_session_options(["modex", "session", "current", "--cwd=relative", "--json"])
    assert_equal(relative.directory.value(), "relative")
    assert_true(0.94444 < jaro_similarity("abcXYZ", "bcaXYZ") < 0.94445)
    assert_equal(jaro_similarity("same", "same"), Float64(1))
    assert_equal(jaro_similarity("", "other"), Float64(0))
    var rejected = False
    try:
        var invalid = parse_session_options(["modex", "session", "list", "--json", "--id-only"])
    except:
        rejected = True
    assert_true(rejected)
    print("session metadata, filters, timestamps, text and argument checks: PASS")
