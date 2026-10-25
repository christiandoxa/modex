from std.testing import assert_equal

from modex.provider_chat_metadata import merge_chat_metadata


def main() raises:
    assert_equal(merge_chat_metadata("null", "{\"request\":1}"), '{"request":1}')
    assert_equal(merge_chat_metadata("{\"provider\":1}", "null"), '{"provider":1}')
    assert_equal(merge_chat_metadata("{\"provider\":1}", "[]"), '{"provider":1}')
    assert_equal(merge_chat_metadata("null", "null"), "null")

    var provider = "{\"a\":1,\"b\":{\"x\":1,\"keep\":2},\"scalar\":4}"
    var request = "{\"a\":{\"z\":1},\"b\":{\"x\":{\"deep\":1},\"new\":3},\"scalar\":{\"s\":1},\"表\":\"🙂\"}"
    assert_equal(merge_chat_metadata(provider, request), '{"a":1,"b":{"keep":2,"new":3,"x":{"deep":1}},"scalar":4,"表":"🙂"}')

    assert_equal(merge_chat_metadata("{\"same\":1,\"same\":2}", "{\"same\":3,\"same\":4}"), '{"same":4}')
    print("Provider chat metadata checks: PASS")
