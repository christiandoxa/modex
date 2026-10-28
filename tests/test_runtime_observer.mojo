from std.collections import List, Span
from std.testing import assert_equal, assert_true

from modex.json import JSON_STRING, JsonDocument
from modex.provider_sse_wire import ProviderSSEFramer
from modex.runtime_sse_binding_observer import RuntimeSSEBindingObserver
from modex.text import trim_text


def observe(body: List[UInt8], chunk_size: Int = 997) raises -> List[String]:
    var observer = RuntimeSSEBindingObserver()
    var output = List[String]()
    var offset = 0
    while offset < len(body):
        var end = min(len(body), offset + chunk_size)
        output.extend(observer.consume(Span(body)[offset:end]))
        if observer.is_failed():
            raise Error("runtime SSE binding observer rejected invalid UTF-8")
        offset = end
    output.extend(observer.finish())
    return output^


def bytes(text: String) -> List[UInt8]:
    var result = List[UInt8]()
    result.extend(text.as_bytes())
    return result^


def old_id(body: String) -> String:
    try:
        var doc = JsonDocument(body)
        var node = doc.get(doc.get(doc.root, "response"), "id")
        if node < 0 or doc.nodes[node].kind != JSON_STRING:
            node = doc.get(doc.root, "id")
        if node < 0 or doc.nodes[node].kind != JSON_STRING:
            node = doc.get(doc.root, "response_id")
        if node >= 0 and doc.nodes[node].kind == JSON_STRING:
            return trim_text(doc.string(node))
        node = doc.get(doc.root, "responseId")
        if node >= 0 and doc.nodes[node].kind == JSON_STRING:
            return trim_text(doc.string(node))
        return trim_text(doc.string(doc.get(doc.get(doc.root, "message"), "id")))
    except:
        return ""


def old_observe(body: List[UInt8], chunk_size: Int) raises -> List[String]:
    var framer = ProviderSSEFramer()
    var result = List[String]()
    var offset = 0
    while offset < len(body):
        var end = min(len(body), offset + chunk_size)
        var chunk_offset = offset
        while chunk_offset < end:
            var frame = framer.consume(Span(body)[chunk_offset:end])
            chunk_offset += frame[0]
            if frame[1]:
                var value = old_id(String("\n").join(frame[1].value()))
                if value:
                    result.append(value^)
        offset = end
    var final_frame = framer.finish()
    if final_frame:
        var value = old_id(String("\n").join(final_frame.value()))
        if value:
            result.append(value^)
    return result^


def compare_old(body: List[UInt8], chunk_size: Int) raises:
    var old_failed = False
    var old_values = List[String]()
    try:
        old_values = old_observe(body, chunk_size)
    except:
        old_failed = True
    var new_failed = False
    var new_values = List[String]()
    try:
        new_values = observe(body, chunk_size)
    except:
        new_failed = True
    assert_equal(new_failed, old_failed)
    if not old_failed:
        assert_equal(new_values, old_values)


def depth_json(arrays: Int) -> String:
    var output = String("{\"response\":{\"id\":\"resp_depth\"},\"deep\":")
    output += String("[") * arrays + "0" + String("]") * arrays + "}"
    return output^


def main() raises:
    var valid = observe(bytes("event: response.completed\ndata: {\"response\":{\"id\":\"resp_valid\"},\"ok\":true}\n\n"))
    assert_equal(valid, ["resp_valid"])

    var escaped = observe(bytes("data: {\"res\\u0070onse\":{\"id\":\"resp_escaped\"}}\n\n"))
    assert_equal(escaped, ["resp_escaped"])

    var duplicate_parent = observe(bytes("data: {\"response\":{\"id\":\"resp_stale\"},\"response\":{},\"id\":\"resp_root\"}\n\n"))
    assert_equal(duplicate_parent, ["resp_root"])

    var wrong_type = observe(bytes("data: {\"response\":{\"id\":12},\"id\":\"resp_fallback\"}\n\n"))
    assert_equal(wrong_type, ["resp_fallback"])

    var message_fallback = observe(bytes("data: {\"message\":{\"id\":\"resp_message\"}}\n\n"))
    assert_equal(message_fallback, ["resp_message"])

    var malformed = observe(bytes("data: {\"response\":{\"id\":\"resp_uncommitted\"},\"tail\":true}x\n\n"))
    assert_equal(len(malformed), 0)

    var invalid_number = observe(bytes("data: {\"response\":{\"id\":\"resp_uncommitted\"},\"n\":1e9999}\n\n"))
    assert_equal(len(invalid_number), 0)

    var recovery = observe(bytes("data: {bad}\n\ndata: {\"response\":{\"id\":\"resp_after_bad\"}}\n\n"))
    assert_equal(recovery, ["resp_after_bad"])

    var large = List[UInt8]()
    large.extend("data: {\"response\":{\"id\":\"resp_large\"},\"filler\":\"".as_bytes())
    for _ in range(4 * 1024 * 1024 + 32):
        large.append(120)
    large.extend("\"}\n\n".as_bytes())
    var large_observed = observe(large, 8191)
    assert_equal(large_observed, ["resp_large"])

    var no_midstream_commit = RuntimeSSEBindingObserver()
    var prefix = bytes("data: {\"response\":{\"id\":\"resp_wait\"},\"tail\":true}x")
    assert_equal(len(no_midstream_commit.consume(Span(prefix))), 0)
    assert_equal(len(no_midstream_commit.finish()), 0)

    var split_data = observe(bytes("data: {\"response\":\ndata:  {\"id\":\"resp_lines\"}}\n\n"))
    assert_equal(split_data, ["resp_lines"])

    var duplicate_id = observe(bytes("data: {\"response\":{\"id\":\"old\",\"id\":null},\"id\":\"resp_last\"}\n\n"))
    assert_equal(duplicate_id, ["resp_last"])

    var unicode_field_whitespace = observe(bytes("data:\u00a0{\"response\":{\"id\":\"resp_unicode_prefix\"}}\n\n"))
    assert_equal(unicode_field_whitespace, ["resp_unicode_prefix"])

    var exact_id_limit = observe(bytes("data: {\"response\":{\"id\":\"" + String("x") * 1024 + "\"}}\n\n"))
    assert_equal(exact_id_limit, [String("x") * 1024])
    var over_id_limit = observe(bytes("data: {\"response\":{\"id\":\"" + String("x") * 1025 + "\"}}\n\n"))
    assert_equal(len(over_id_limit), 0)

    var invalid_utf8: List[UInt8] = [100, 97, 116, 97, 58, 32, 123, 34, 105, 100, 34, 58, 34, 255, 34, 125, 10, 10]
    var failed = False
    try:
        _ = observe(invalid_utf8)
    except:
        failed = True
    assert_true(failed)

    # For inputs within the old observer limits, the streaming validator and
    # previous framer plus complete JsonDocument parse must select identical IDs.
    var cases = List[String]()
    cases.append("{\"response\":{\"id\":\"resp_basic\"}}")
    cases.append(" { \"response\" : { \"id\" : \" resp_space \" }, \"n\":-0 }")
    cases.append("{\"res\\u0070onse\":{\"id\":\"resp_key_escape\"}}")
    cases.append("{\"response\":{\"id\":\"resp\\u002fescape\\\\quote\\\"\"}}")
    cases.append("{\"response\":{\"id\":\"resp_é_東京_🔥\"}}")
    cases.append("{\"response\":{\"id\":\"old\",\"id\":\"resp_duplicate\"}}")
    cases.append("{\"response\":{\"id\":12},\"id\":\"resp_root_fallback\"}")
    cases.append("{\"response\":null,\"response_id\":\"resp_snake_fallback\"}")
    cases.append("{\"response\":[],\"responseId\":\"resp_camel_fallback\"}")
    cases.append("{\"message\":{\"id\":\"resp_message_fallback\"}}")
    cases.append("{\"other\":{\"id\":\"resp_nested_decoy\"}}")
    cases.append("{\"response\":{\"meta\":{\"id\":\"resp_decoy\"}}}")
    cases.append("{\"response\":{\"id\":\"resp_null_tail\"},\"tail\":null}")
    cases.append("{\"response\":{\"id\":\"resp_bools\"},\"v\":[true,false,null]}")
    cases.append("{\"response\":{\"id\":\"resp_numbers\"},\"v\":[0,-0,1.2e+3,-2.5E-2]}")
    cases.append("{\"response\":{\"id\":\"resp_max_finite\"},\"v\":1.7976931348623157e308}")
    cases.append("{\"response\":{\"id\":\"resp_long_fraction\"},\"v\":0." + String("0") * 300 + "1}")
    cases.append("{\"response\":{\"id\":\"resp_long_exponent\"},\"v\":1" + String("0") * 300 + "e-300}")
    cases.append("{\"response\":{\"id\":\"resp_long_overflow\"},\"v\":1" + String("0") * 300 + "e9999}")
    cases.append("{\"response\":{\"id\":\"resp_incomplete_escape\"},\"v\":\"\\u12\"}")
    cases.append("{\"response\":{\"id\":\"resp_unpaired_surrogate\"},\"v\":\"\\uD800\"}")
    cases.append("{\"response\":{\"id\":\"resp_bad_leading_zero\"},\"v\":01}")
    cases.append("{\"response\":{\"id\":\"resp_bad_fraction\"},\"v\":1.}")
    cases.append("{\"response\":{\"id\":\"resp_bad_exponent\"},\"v\":1e+}")
    cases.append("{\"response\":{\"id\":\"resp_overflow\"},\"v\":1e9999}")
    cases.append("{\"response\":{\"id\":\"resp_trailing\"}}x")
    cases.append("{\"response\":{\"id\":\"resp_missing_comma\"} \"x\":1}")
    cases.append("{\"response\":{\"id\":\"resp_trailing_comma\",}}")
    cases.append("{\"response\":{\"id\":\"resp_incomplete\"}")
    cases.append("[ {\"response\":{\"id\":\"resp_array_root_decoy\"}} ]")
    cases.append(depth_json(125))
    cases.append(depth_json(126))
    cases.append(depth_json(127))

    for index in range(len(cases)):
        var framed = bytes("event: response.completed\r\ndata: " + cases[index] + "\r\n\r\n")
        for chunk_size in [1, 2, 3, 7, 31, 997]:
            compare_old(framed, chunk_size)

    # SSE joins multiple data lines with LF; these remain equivalent across
    # byte splits, including splits through a UTF-8 scalar and JSON escape.
    for text in [
        String("data: {\"response\":\ndata: {\"id\":\"resp_multiline\"}}\n\n"),
        String("data: {\"response\":{\"id\":\"resp_東京\"}}\n\n"),
        String("data: {\"response\":{\"id\":\"resp_eof\"}}"),
        String("data: {\"res\\u0070onse\":{\"id\":\"resp_escape_boundary\"}}\n\n"),
        String(": comment\nevent: response.completed\nid: ignored\ndata\n\n"),
        String("data: {\"response\":{\"id\":\"first\"}}\n\ndata: {\"id\":\"second\"}\n\n"),
    ]:
        var framed = bytes(text)
        for chunk_size in [1, 2, 3, 5, 13, 997]:
            compare_old(framed, chunk_size)

    var invalid_utf8_overlong: List[UInt8] = [100, 97, 116, 97, 58, 32, 123, 34, 105, 100, 34, 58, 34, 240, 128, 128, 128, 34, 125, 10, 10]
    for chunk_size in [1, 2, 3, 4, 19]:
        compare_old(invalid_utf8_overlong, chunk_size)

    var completed_before_invalid = bytes("data: {\"response\":{\"id\":\"resp_before_invalid\"}}\n\n")
    completed_before_invalid.extend(invalid_utf8_overlong.copy())
    var partial_observer = RuntimeSSEBindingObserver()
    var partial_values = partial_observer.consume(Span(completed_before_invalid))
    assert_equal(partial_values, ["resp_before_invalid"])
    assert_true(partial_observer.is_failed())
