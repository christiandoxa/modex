from std.testing import assert_equal, assert_false, assert_true

from modex.json import JsonDocument
from modex.provider_chat_tools import chat_tool_delta, fallback_tool_id, incremental_arguments


def main() raises:
    var doc = JsonDocument('{"index":7,"id":"call_1","function":{"name":"lookup","arguments":"{\\"q\\":1}"},"extra_content":{"google":{"thought_signature":" sig "}}}')
    assert_equal(chat_tool_delta(doc, doc.root), '{"index":7,"id":"call_1","name":"lookup","arguments":"{\\"q\\":1}","thought_signature":" sig "}')

    var missing = JsonDocument('{"index":-0,"id":false,"function":{"name":4,"arguments":""},"extra_content":{"google":{"thought_signature":" 　"}}}')
    assert_equal(chat_tool_delta(missing, missing.root), '{"index":0,"id":null,"name":null,"arguments":null,"thought_signature":null}')
    var out_of_range = JsonDocument('{"index":18446744073709551616}')
    assert_equal(chat_tool_delta(out_of_range, out_of_range.root), '{"index":0,"id":null,"name":null,"arguments":null,"thought_signature":null}')

    assert_true(incremental_arguments("{\"x\":", "1}"))
    assert_equal(incremental_arguments("previous", "1}").value(), "1}")
    assert_false(incremental_arguments("previous", ""))
    assert_equal(fallback_tool_id("provider-東京", UInt64.MAX, UInt64.MAX), "call_provider-東京_18446744073709551615_18446744073709551615")
    print("Provider chat tools checks: PASS")
