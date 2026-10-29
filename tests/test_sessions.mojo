from std.collections import List, Optional
from std.testing import assert_equal, assert_false, assert_true

from modex.cli import jaro_similarity, parse_session_options, unsigned_value
from modex.json import JsonDocument
from modex.session_time import integer_timestamp, timestamp_key
from modex.sessions import SessionReport, resolve_session_id, session_child_path, session_query_lowercase, starts_session
from modex.text import character_width, fit_cell, pad_cell, section_header, text_width, trim_text, wrap_text


def main() raises:
    assert_equal(timestamp_key("1970-01-01T00:00:00Z").value(), 0)
    assert_equal(timestamp_key("1970-01-01T01:00:00+01:00").value(), 0)
    assert_equal(timestamp_key("1969-12-31T23:59:59Z").value(), -1)
    assert_equal(timestamp_key("2000-02-29T00:00:00Z").value(), 951782400)
    assert_false(timestamp_key("1900-02-29T00:00:00Z"))
    assert_false(timestamp_key("2026-01-01T24:00:00Z"))
    assert_false(timestamp_key("2026-01-01T00:00:00.Z"))
    assert_false(timestamp_key("2026-01-01T+1:00:00Z"))
    assert_false(timestamp_key("2026-01-01T00:00:00++1:00"))
    assert_equal(timestamp_key("+17").value(), 17)
    assert_equal(integer_timestamp("-9223372036854775808").value(), Int.MIN)
    assert_false(integer_timestamp("9223372036854775808"))
    assert_equal(unsigned_value("18446744073709551615"), UInt64.MAX)
    assert_equal(trim_text(chr(0x2000) + " title " + chr(0xA0)), "title")
    assert_equal(trim_text("\x1cname\x1c"), "\x1cname\x1c")
    assert_equal(session_child_path("/", "sessions"), "/sessions")
    assert_equal(session_child_path("/tmp/shared//", "sessions"), "/tmp/shared//sessions")
    assert_equal(session_child_path("/tmp/shared", "sessions"), "/tmp/shared/sessions")
    assert_equal(session_query_lowercase("İ"), "i\u0307")
    assert_equal(session_query_lowercase("ΟΣ"), "ος")
    assert_equal(session_query_lowercase("Ο\u0301Σ"), "ο\u0301ς")
    assert_equal(session_query_lowercase("ΟΣ\u0301Α"), "οσ\u0301α")
    assert_equal(session_query_lowercase("ΑΣΣ"), "ασς")
    assert_equal(session_query_lowercase("Σ'Α"), "σ'α")
    for code in [0x1C89, 0xA7CC, 0xA7CE, 0xA7D2, 0xA7D4, 0xA7DA]:
        assert_equal(session_query_lowercase(chr(code)), chr(code + 1))
    assert_equal(session_query_lowercase(chr(0xA7CB)), chr(0x0264))
    assert_equal(session_query_lowercase(chr(0xA7DC)), chr(0x019B))
    for code in range(0x10D50, 0x10D66):
        assert_equal(session_query_lowercase(chr(code)), chr(code + 0x20))
    for code in range(0x16EA0, 0x16EB9):
        assert_equal(session_query_lowercase(chr(code)), chr(code + 0x1B))
    assert_equal(session_query_lowercase(String("A") * 1048576 + "Σ"), String("a") * 1048576 + "ς")
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
    assert_equal(character_width(0x1ACF), 0)
    assert_equal(character_width(0x11A3A), 1)
    assert_equal(character_width(0x17D8), 3)
    assert_equal(character_width(0x16D63), 1)
    assert_equal(character_width(0x16D67), 1)
    assert_equal(text_width("P" + chr(0x16D67) + "Q"), 3)
    assert_equal(text_width(chr(0x16D67) * 4097), 2049)
    assert_equal(text_width(chr(0x2D31) + (chr(0x200D) + chr(0x2D31)) * 4096), 2049)
    assert_equal(text_width(chr(0x2D31) + (chr(0x2D7F) + chr(0x2D31)) * 8), 9)
    assert_equal(character_width(9), 0)
    assert_equal(text_width("A\r\nB"), 3)
    assert_equal(text_width(chr(0x1F600)), 2)
    assert_equal(text_width(chr(0x1F600) + chr(0xFE0E)), 2)
    assert_equal(text_width(chr(0x1F469) + chr(0x200D) + chr(0x1F4BB)), 2)
    assert_equal(text_width(chr(0x1F44D) + chr(0x1F3FD)), 2)
    assert_equal(text_width("1" + chr(0xFE0F) + chr(0x20E3)), 2)
    assert_equal(text_width(chr(0x644) + chr(0x627)), 1)
    assert_equal(fit_cell(chr(0x754C) + "abc", 4), "...")
    assert_equal(fit_cell(chr(0x301), 0), "")
    assert_equal(pad_cell(chr(0x754C), 3), chr(0x754C) + " ")
    assert_equal(wrap_text("first\n\nnext\n", 8), ["first", "", "next"])
    var metadata = JsonDocument("{\"type\":\"session_meta\",\"timestamp\":\"2026-10-24T00:00:00Z\",\"payload\":{\"id\":\"session-a\",\"timestamp\":\"2026-10-24T00:00:00Z\",\"cwd\":\"/workspace\",\"originator\":\"test\",\"cli_version\":\"0.162.0\",\"title\":\"  Test title  \"}}")
    assert_true(starts_session(metadata))
    var report = SessionReport("filename", "", "", "", "", Optional[String](), "", "/fixture.jsonl", 0)
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
    var ids = List[String]()
    ids.append("019a1234-5678-7123-8123-0123456789ab")
    ids.append("019a1234-9999-7123-8123-0123456789ab")
    ids.append("019a1234-5678-7123-8123-0123456789ab-long")
    assert_equal(resolve_session_id(ids, "019A1234-5678-7123-8123-0123456789AB"), ids[0])
    assert_equal(resolve_session_id(ids, "019a1234-9999"), ids[1])
    var missing = False
    try:
        _ = resolve_session_id(ids, "not-found")
    except error:
        missing = String(error) == "session could not be resolved"
    assert_true(missing)
    var ambiguous = False
    try:
        _ = resolve_session_id(ids, "019a1234")
    except error:
        ambiguous = String(error) == "session selector is ambiguous"
    assert_true(ambiguous)
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
