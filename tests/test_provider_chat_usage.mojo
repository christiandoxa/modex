from std.testing import assert_equal, assert_false, assert_true

from modex.json import JSON_NUMBER, JsonDocument
from modex.provider_chat_usage import chat_usage, json_unsigned


def main() raises:
    var missing = JsonDocument("{}")
    assert_equal(chat_usage(missing, -1, "deepseek"), "null")
    var null_usage = JsonDocument("{\"usage\":null}")
    assert_equal(chat_usage(null_usage, null_usage.get(null_usage.root, "usage"), "deepseek"), '{"input_tokens":0,"output_tokens":0,"total_tokens":0}')

    var usage_doc = JsonDocument("{\"usage\":{\"prompt_tokens\":18446744073709551615,\"completion_tokens\":1,\"prompt_cache_hit_tokens\":0,\"completion_tokens_details\":{\"reasoning_tokens\":3}}}")
    var usage = usage_doc.get(usage_doc.root, "usage")
    assert_equal(chat_usage(usage_doc, usage, "deepseek"), '{"input_tokens":18446744073709551615,"input_tokens_details":{"cached_tokens":0},"metadata":{"deepseek":{"prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":0}},"output_tokens":1,"output_tokens_details":{"reasoning_tokens":3},"total_tokens":18446744073709551615}')
    var escaped = JsonDocument('{"usage":{"prompt_tokens":1,"prompt\\u005ftokens":11,"completion_tokens":7,"completion_tokens_details":{"reasoning\\u005ftokens":4}}}')
    assert_equal(chat_usage(escaped, escaped.get(escaped.root, "usage"), "deepseek"), '{"input_tokens":11,"output_tokens":7,"output_tokens_details":{"reasoning_tokens":4},"total_tokens":18}')

    var nums = JsonDocument("[0,-0,1.0,1e0,18446744073709551615,18446744073709551616,-1,null]")
    assert_equal(json_unsigned(nums, nums.nodes[nums.root].children[0]).value(), UInt64(0))
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[1]))
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[2]))
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[3]))
    assert_equal(json_unsigned(nums, nums.nodes[nums.root].children[4]).value(), UInt64.MAX)
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[5]))
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[6]))
    assert_false(json_unsigned(nums, nums.nodes[nums.root].children[7]))
    assert_true(nums.nodes[nums.root].kind != JSON_NUMBER)
    print("Provider chat usage checks: PASS")
