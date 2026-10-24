from std.collections import List
from std.testing import assert_equal, assert_true

from modex.provider_sse_wire import ProviderSSEFramer


def consume_error(line_max: Int, event_max: Int, bytes: ImmSpan[UInt8, _]) raises -> String:
    var framer = ProviderSSEFramer(line_max, event_max)
    try:
        _ = framer.consume(bytes)
    except e:
        return String(e)
    return "missing error"


def main() raises:
    var framer = ProviderSSEFramer(64, 16)
    var first = "data: hé\r\n".as_bytes()
    var first_result = framer.consume(Span(first)[:8])
    assert_equal(first_result[0], 8)
    assert_true(not first_result[1])
    var first_rest = framer.consume(Span(first)[8:])
    assert_equal(first_rest[0], len(first) - 8)
    assert_true(not first_rest[1])
    var second = "data:llo\n\n".as_bytes()
    var second_result = framer.consume(Span(second))
    assert_equal(second_result[0], len(second))
    assert_true(second_result[1])
    assert_equal(second_result[1].value(), ["hé", "llo"])
    assert_true(not framer.finish())
    assert_true(not framer.finish())

    var exact = ProviderSSEFramer(7, 3)
    var exact_bytes = "data:x\n".as_bytes()
    var exact_result = exact.consume(Span(exact_bytes))
    assert_equal(exact_result[0], len(exact_bytes))
    assert_true(not exact_result[1])
    var blank = "\n".as_bytes()
    var exact_done = exact.consume(Span(blank))
    assert_equal(exact_done[1].value(), ["x"])

    # Line limits count UTF-8 bytes, including when a scalar crosses chunks.
    var split_scalar = ProviderSSEFramer(7, 16)
    var scalar_prefix: List[UInt8] = [100, 97, 116, 97, 58, 32, 195]
    var scalar_suffix: List[UInt8] = [169, 10]
    _ = split_scalar.consume(Span(scalar_prefix))
    var scalar_error = ""
    try:
        _ = split_scalar.consume(Span(scalar_suffix))
    except e:
        scalar_error = String(e)
    assert_equal(scalar_error, "provider SSE line exceeded safe size limit (7)")

    var valid_overflow: List[UInt8] = [195, 169, 10]
    assert_equal(consume_error(2, 16, Span(valid_overflow)), "provider SSE line exceeded safe size limit (2)")
    var invalid_prefix: List[UInt8] = [195, 120]
    assert_equal(consume_error(1, 16, Span(invalid_prefix)), "stream did not contain valid UTF-8")

    # An event's byte budget restarts after its blank separator.
    var reset_budget = ProviderSSEFramer(64, 3)
    var separate_events = "data:x\n\ndata:y\n\n".as_bytes()
    var reset = reset_budget.consume(Span(separate_events))
    assert_equal(reset[0], len("data:x\n\n".as_bytes()))
    assert_equal(reset[1].value(), ["x"])
    var reset_tail = reset_budget.consume(Span(separate_events)[reset[0]:])
    assert_equal(reset_tail[1].value(), ["y"])

    var suffixes = ProviderSSEFramer(64, 16)
    var crlf_suffixes = "data:x\r\r\n\n".as_bytes()
    assert_equal(suffixes.consume(Span(crlf_suffixes))[1].value(), ["x"])

    var ignored = ProviderSSEFramer(64, 2)
    var ignored_bytes = ":comment\nevent: update\nid: 5\nretry: 2\ndata\n\ndata: \n\n".as_bytes()
    var offset = 0
    var frames = 0
    while offset < len(ignored_bytes):
        var next = ignored.consume(Span(ignored_bytes)[offset:])
        offset += next[0]
        if next[1]:
            assert_equal(len(next[1].value()), 1)
            assert_equal(next[1].value()[0], "")
            frames += 1
    assert_equal(frames, 2)

    var eof = ProviderSSEFramer(64, 16)
    var eof_bytes = "data:tail".as_bytes()
    var eof_result = eof.consume(Span(eof_bytes))
    assert_equal(eof_result[0], len(eof_bytes))
    assert_true(not eof_result[1])
    assert_equal(eof.finish().value(), ["tail"])

    var eof_separator = ProviderSSEFramer(64, 16)
    var eof_separator_bytes = "data:value\n\r".as_bytes()
    _ = eof_separator.consume(Span(eof_separator_bytes))
    assert_equal(eof_separator.finish().value(), ["value"])
    assert_true(not eof_separator.finish())

    var bad: List[UInt8] = [100, 97, 116, 97, 58, 32, 255, 10]
    assert_equal(consume_error(64, 16, Span(bad)), "stream did not contain valid UTF-8")
    var invalid_before_limit: List[UInt8] = [255, 49, 50, 51, 52]
    assert_equal(consume_error(4, 16, Span(invalid_before_limit)), "stream did not contain valid UTF-8")

    var failed = False
    try:
        var invalid_limits = ProviderSSEFramer(0, 1)
    except:
        failed = True
    assert_true(failed)

    var bad_comment_bytes: List[UInt8] = [58, 255, 10]
    assert_equal(consume_error(64, 16, Span(bad_comment_bytes)), "stream did not contain valid UTF-8")

    var preserve = ProviderSSEFramer(64, 16)
    var mixed: List[UInt8] = [100, 97, 116, 97, 58, 32, 111, 107, 10, 10, 255]
    var safe = preserve.consume(Span(mixed))
    assert_equal(safe[0], 10)
    assert_equal(safe[1].value(), ["ok"])
    failed = False
    try:
        _ = preserve.consume(Span(mixed)[safe[0]:])
        _ = preserve.finish()
    except:
        failed = True
    assert_true(failed)

    var too_long = "data:x\n".as_bytes()
    assert_equal(consume_error(6, 16, Span(too_long)), "provider SSE line exceeded safe size limit (6)")

    # Overflow stops at one byte beyond the configured line limit.
    var bounded = ProviderSSEFramer(3, 16)
    var overflow: List[UInt8] = [97, 98, 99, 100, 101, 102]
    var bounded_error = ""
    try:
        _ = bounded.consume(Span(overflow))
    except e:
        bounded_error = String(e)
    assert_equal(bounded_error, "provider SSE line exceeded safe size limit (3)")
    assert_equal(len(bounded.line), 4)

    var terminal = ProviderSSEFramer(64, 16)
    assert_true(not terminal.finish())
    failed = False
    try:
        _ = terminal.consume(Span(blank))
    except:
        failed = True
    assert_true(failed)
    assert_true(not terminal.finish())

    var sticky = ProviderSSEFramer(1, 16)
    var overflow_line = "ab".as_bytes()
    failed = False
    try:
        _ = sticky.consume(Span(overflow_line))
    except:
        failed = True
    assert_true(failed)
    failed = False
    try:
        _ = sticky.consume(Span(blank))
    except e:
        failed = String(e) == "provider SSE framer is failed"
    assert_true(failed)
    failed = False
    try:
        _ = sticky.finish()
    except e:
        failed = String(e) == "provider SSE framer is failed"
    assert_true(failed)

    var too_much = "data:xy\n\n".as_bytes()
    assert_equal(consume_error(64, 2, Span(too_much)), "provider SSE event exceeded safe size limit (2)")
    print("Provider SSE wire checks: PASS")
