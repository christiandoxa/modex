from std.collections import List
from std.testing import assert_equal, assert_true

from modex.json import JSON_ARRAY, JSON_NUMBER, JsonDocument, quote_json, serialize_json, serialize_number


def main() raises:
    var document = JsonDocument("{\"text\":\"hello\\n\\uD83D\\uDD25\",\"numbers\":[-0,1.2e+3],\"duplicate\":1,\"duplicate\":2}")
    assert_equal(document.string(document.get(document.root, "text")), "hello\n🔥")
    var numbers = document.get(document.root, "numbers")
    assert_equal(document.nodes[numbers].kind, JSON_ARRAY)
    var number = document.nodes[numbers].children[1]
    assert_equal(document.nodes[number].kind, JSON_NUMBER)
    assert_equal(document.nodes[number].text, "1.2e+3")
    assert_equal(document.nodes[document.get(document.root, "duplicate")].text, "2")
    assert_equal(document.get(document.root, "missing"), -1)
    assert_equal(quote_json("text\n\t\"\\\x00🔥"), "\"text\\n\\t\\\"\\\\\\u0000🔥\"")
    var valid: List[String] = ["null", "true", "false", "[]", "{}", "123", "-2.5e-2", "1e-999", "\"\\/\\b\\f\\r\\t\"", " [ 1, { \"a\": [] } ] "]
    for source in valid:
        var parsed = JsonDocument(source)
        assert_true(parsed.root >= 0)
    var invalid: List[String] = ["", "NaN", "01", "-", "1.", "1e", "1e+", "1e999", "[1,]", "{\"x\":1,}", "{x:1}", "true false", "\"\\uD800\"", "\"\\uDC00\"", "\"\\uD800\\u0041\"", "\"\\x00\"", "\"\n\"", "\"unterminated"]
    for source in invalid:
        var failed = False
        try:
            var parsed = JsonDocument(source)
        except:
            failed = True
        assert_true(failed, source)
    var nested = String()
    for _ in range(127):
        nested += "["
    nested += "0"
    for _ in range(127):
        nested += "]"
    var boundary = JsonDocument(nested)
    var over = "[" + nested + "]"
    var rejected = False
    try:
        var parsed = JsonDocument(over)
    except:
        rejected = True
    assert_true(rejected)
    var ordered = JsonDocument("{\"z\":0,\"a\":[true,null,{\"second\":2,\"first\":1}],\"z\":9}")
    assert_equal(serialize_json(ordered, ordered.root), "{\"a\":[true,null,{\"first\":1,\"second\":2}],\"z\":9}")
    var compact = JsonDocument("{\"z\":1e0,\"a\":-0,\"max\":18446744073709551615}")
    assert_equal(serialize_json(compact, compact.root), "{\"a\":-0.0,\"max\":18446744073709551615,\"z\":1.0}")
    for source, expected in [
        ("1e-7", "1e-7"), ("-1e-6", "-1e-6"), ("1e-5", "0.00001"),
        ("-1.234e-5", "-0.00001234"), ("1e2", "100.0"), ("-0", "-0.0"),
    ]:
        assert_equal(serialize_number(source), expected)
    var pretty = JsonDocument("{\"z\":[],\"a\":{\"x\":\"表🙂\"}}")
    assert_equal(serialize_json(pretty, pretty.root, 2), "{\n  \"a\": {\n    \"x\": \"表🙂\"\n  },\n  \"z\": []\n}")
    print("JSON unit checks: PASS")
