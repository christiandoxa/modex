from std.collections import List
from std.testing import assert_equal, assert_true

from modex.provider_sse_json import ProviderSSEJSONAssembler


def values(mut assembler: ProviderSSEJSONAssembler, lines: List[String]) raises -> String:
    var output = String()
    for value in assembler.push(lines):
        if output:
            output += "|"
        output += value
    return output^


def main() raises:
    var joined = ProviderSSEJSONAssembler(3)
    assert_equal(values(joined, [" {\"n\":", "1} "]), "{\"n\":\n1}")

    var separate = ProviderSSEJSONAssembler(3)
    assert_equal(values(separate, ["{\"n\":2}", " {\"n\":3} "]), "{\"n\":2}|{\"n\":3}")

    var fragments = ProviderSSEJSONAssembler(20)
    assert_equal(values(fragments, ["{\"n\":"]), "")
    assert_equal(values(fragments, ["1}"]), "{\"n\":1}")

    var precedence = ProviderSSEJSONAssembler(20)
    assert_equal(values(precedence, ["{"]), "")
    assert_equal(values(precedence, ["[1, true, null]"]), "[1, true, null]")
    assert_equal(values(precedence, ["2"]), "2")
    var pending_fragment_at_eof = False
    try:
        _ = precedence.finish()
    except:
        pending_fragment_at_eof = True
    assert_true(pending_fragment_at_eof)

    var unicode_done = ProviderSSEJSONAssembler()
    assert_equal(values(unicode_done, [" {\"ok\":true} "]), "{\"ok\":true}")
    var marker = List[String]()
    marker.append(" [DONE] ")
    marker.append("not JSON")
    assert_equal(values(unicode_done, marker), "")
    assert_true(unicode_done.done)
    assert_true(unicode_done.saw_done)
    assert_equal(len(unicode_done.finish()), 0)

    var pending_done = ProviderSSEJSONAssembler()
    assert_equal(values(pending_done, ["{\"n\":"]), "")
    var done_lines: List[String] = ["[DONE]"]
    var incomplete_done = False
    try:
        _ = values(pending_done, done_lines)
    except:
        incomplete_done = True
    assert_true(incomplete_done)
    assert_true(not pending_done.saw_done)
    var rejected_after_failure = False
    try:
        _ = values(pending_done, ["1}"])
    except:
        rejected_after_failure = True
    assert_true(rejected_after_failure)

    var eof = ProviderSSEJSONAssembler()
    assert_equal(values(eof, ["{\"x\":1}"]), "{\"x\":1}")
    assert_equal(len(eof.finish()), 0)
    assert_equal(len(eof.finish()), 0)

    var incomplete = ProviderSSEJSONAssembler()
    assert_equal(values(incomplete, ["{\"x\":"]), "")
    var incomplete_rejected = False
    try:
        _ = incomplete.finish()
    except:
        incomplete_rejected = True
    assert_true(incomplete_rejected)
    var sticky = False
    try:
        _ = incomplete.push(["1}"])
    except:
        sticky = True
    assert_true(sticky)

    var max_zero = ProviderSSEJSONAssembler(0)
    var zero_rejected = False
    try:
        _ = values(max_zero, ["{"])
    except error:
        zero_rejected = String(error) == "provider SSE accumulated JSON exceeded safe size limit (0)"
    assert_true(zero_rejected)

    var exact_limit = ProviderSSEJSONAssembler(1)
    assert_equal(values(exact_limit, ["["]), "")
    var over_limit = False
    try:
        _ = values(exact_limit, ["1,"])
    except error:
        over_limit = String(error) == "provider SSE accumulated JSON exceeded safe size limit (1)"
    assert_true(over_limit)

    var malformed = ProviderSSEJSONAssembler()
    var malformed_rejected = False
    try:
        _ = values(malformed, ["NaN"])
        _ = malformed.finish()
    except:
        malformed_rejected = True
    assert_true(malformed_rejected)
    print("Provider SSE JSON assembler checks: PASS")
