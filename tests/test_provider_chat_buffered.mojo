from std.testing import assert_equal, assert_true

from modex.json import JSON_BOOL, JsonDocument, quote_json
from modex.provider_chat_buffered import deepseek_buffered_assistant_messages, deepseek_buffered_response


def tool_error(arguments: String, expected: String, name: String = "lookup") raises:
    var source = '{"choices":[{"message":{"tool_calls":[{"id":"synthetic-call","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json(arguments) + "}}]}}]}"
    var response = JsonDocument(deepseek_buffered_response(source, 1, "resp_test"))
    var error = response.get(response.root, "error")
    assert_equal(response.string(response.get(error, "message")), "DeepSeek returned malformed JSON arguments for tool call `" + name + "`: " + expected)


def main() raises:
    var translated = deepseek_buffered_response(
        '{"id":"chatcmpl_buffered_1","model":"deepseek-chat","created":1700000000,"choices":[{"message":{"content":"こんにちは 🌋","reasoning_content":"考えています","refusal":"拒否","annotations":[{"type":"citation","url":"https://example.invalid/source"}],"tool_calls":[{"id":"call_東京","function":{"name":"functions.検索","arguments":"{\\"query\\":\\"café 🍜\\"}"}}]},"finish_reason":"tool_calls","logprobs":{"tokens":["ok"]}}],"system_fingerprint":"fp_buffered_1","usage":{"prompt_tokens":11,"completion_tokens":7,"total_tokens":18,"prompt_cache_hit_tokens":5,"prompt_cache_miss_tokens":6,"completion_tokens_details":{"reasoning_tokens":2}}}',
        99,
        "resp_fallback",
        '{"trace":"synthetic"}',
    )
    assert_equal(
        translated,
        '{"created_at":1700000000,"id":"chatcmpl_buffered_1","metadata":{"deepseek":{"annotations":[{"type":"citation","url":"https://example.invalid/source"}],"finish_reason":"tool_calls","logprobs":{"tokens":["ok"]},"reasoning_content":"考えています","refusal":"拒否","system_fingerprint":"fp_buffered_1"},"trace":"synthetic"},"model":"deepseek-chat","object":"response","output":[{"content":[{"text":"こんにちは 🌋","type":"output_text"}],"role":"assistant","type":"message"},{"arguments":"{\\"query\\":\\"café 🍜\\"}","call_id":"call_東京","name":"検索","namespace":"functions","type":"function_call"}],"usage":{"input_tokens":11,"input_tokens_details":{"cached_tokens":5},"metadata":{"deepseek":{"prompt_cache_hit_tokens":5,"prompt_cache_miss_tokens":6}},"output_tokens":7,"output_tokens_details":{"reasoning_tokens":2},"total_tokens":18}}',
    )

    var malformed = deepseek_buffered_response(
        '{"created":42,"choices":[{"message":{"content":"before error","tool_calls":[{"function":{"name":"lookup","arguments":"{bad"}}]}}]}',
        99,
        "resp_fallback",
    )
    assert_equal(
        malformed,
        '{"created_at":42,"error":{"code":"invalid_tool_call_arguments","message":"DeepSeek returned malformed JSON arguments for tool call `lookup`: key must be a string at line 1 column 2"},"id":"resp_fallback","model":"deepseek-chat","object":"response","output":[{"content":[{"text":"before error","type":"output_text"}],"role":"assistant","type":"message"}],"status":"failed"}',
    )

    var defaults = JsonDocument(deepseek_buffered_response("{\"choices\":[]}", 23, "resp_test", "{\"request\":true}"))
    assert_equal(defaults.string(defaults.get(defaults.root, "id")), "resp_test")
    assert_equal(defaults.nodes[defaults.get(defaults.root, "created_at")].text, "23")
    assert_equal(defaults.string(defaults.get(defaults.root, "model")), "deepseek-chat")
    assert_equal(len(defaults.nodes[defaults.get(defaults.root, "output")].children), 0)
    var merged_request_metadata = defaults.get(defaults.get(defaults.root, "metadata"), "request")
    assert_equal(defaults.nodes[merged_request_metadata].kind, JSON_BOOL)

    var special = JsonDocument(deepseek_buffered_response(
        '{"choices":[{"message":{"tool_calls":[{"function":{"name":"functions.exec_command","arguments":"{\\"cmd\\":\\"cargo test\\"}"}},{"function":{"name":"apply_patch","arguments":"{\\"patch\\":\\"*** Begin Patch\\\\n*** End Patch\\"}"}},{"function":{"name":"tool_search","arguments":"{\\"query\\":\\"東京\\"}"}}]}}]}',
        1,
        "resp_special",
        "null",
    ))
    var output = special.get(special.root, "output")
    var generated_id = special.string(special.get(special.nodes[output].children[0], "call_id"))
    assert_true(generated_id.startswith("call_deepseek_"))
    assert_equal(generated_id.byte_length(), 50)
    assert_equal(generated_id[byte=28], "7")
    assert_equal(special.string(special.get(special.nodes[output].children[0], "name")), "exec_command")
    assert_true(special.string(special.get(special.nodes[output].children[0], "arguments")).find("rtk cargo test") >= 0)
    assert_equal(special.string(special.get(special.nodes[output].children[1], "input")), "{\"patch\":\"*** Begin Patch\\n*** End Patch\"}")
    assert_equal(special.nodes[special.get(special.nodes[output].children[2], "arguments")].kind, 5)
    var next_id = special.string(special.get(special.nodes[output].children[1], "call_id"))
    assert_true(next_id.startswith("call_deepseek_"))
    assert_true(next_id != generated_id)

    var empty_metadata = JsonDocument(deepseek_buffered_response('{"choices":[{"message":{"reasoning_content":"","refusal":"","annotations":[]}}],"system_fingerprint":""}', 1, "resp_empty"))
    assert_equal(empty_metadata.get(empty_metadata.root, "metadata"), -1)
    var blank_metadata = JsonDocument(deepseek_buffered_response('{"choices":[{"message":{"reasoning_content":" ","refusal":"\\t","annotations":[]}}],"system_fingerprint":"　"}', 1, "resp_empty"))
    assert_equal(blank_metadata.get(blank_metadata.root, "metadata"), -1)
    var wrong_types = JsonDocument(deepseek_buffered_response('{"id":false,"created":-1,"model":7,"usage":null,"choices":[{"message":{"content":[],"tool_calls":[{"id":"call-wrong","function":{"name":"  lookup  ","arguments":{"ignored":true}}}]}}]}', 2, "resp_types"))
    assert_equal(wrong_types.string(wrong_types.get(wrong_types.root, "id")), "resp_types")
    assert_equal(wrong_types.nodes[wrong_types.get(wrong_types.root, "created_at")].text, "2")
    var wrong_output = wrong_types.get(wrong_types.root, "output")
    var wrong_call = wrong_types.nodes[wrong_output].children[0]
    assert_equal(wrong_types.string(wrong_types.get(wrong_call, "name")), "lookup")
    assert_equal(wrong_types.string(wrong_types.get(wrong_call, "arguments")), "{}")
    var usage = wrong_types.get(wrong_types.root, "usage")
    assert_equal(wrong_types.nodes[wrong_types.get(usage, "total_tokens")].text, "0")

    var command_only = '{"command":"cargo test"}'
    var shell = JsonDocument(deepseek_buffered_response('{"choices":[{"message":{"tool_calls":[{"id":"call-shell","function":{"name":"shell","arguments":' + quote_json(command_only) + "}}]}}]}", 1, "resp_shell"))
    var shell_call = shell.nodes[shell.get(shell.root, "output")].children[0]
    assert_equal(shell.string(shell.get(shell_call, "arguments")), command_only)

    tool_error('{"x":[1,]}', "trailing comma at line 1 column 9")
    tool_error('{"x":', "EOF while parsing a value at line 1 column 5")
    tool_error('{"x" 1}', "expected `:` at line 1 column 6")
    tool_error('[1 2]', "expected `,` or `]` at line 1 column 4")
    tool_error('{"x":1 "y":2}', "expected `,` or `}` at line 1 column 8")
    tool_error('true false', "trailing characters at line 1 column 6")
    tool_error('[truX,]', "expected ident at line 1 column 5")
    tool_error('[01,]', "invalid number at line 1 column 3")
    tool_error('[1e999,]', "number out of range at line 1 column 6")
    tool_error('"unterminated', "EOF while parsing a string at line 1 column 13")
    tool_error('{"x":"\\q"', "invalid escape at line 1 column 8")
    tool_error('{"x":"\\uD800"', "unexpected end of hex escape at line 1 column 13")
    tool_error(" \n", "EOF while parsing a value at line 2 column 0", "tool_search")
    for arguments in ['truX', '01', '1e999', '"\\q"', '"\\uD800"', '{\n"é": 1,\n"x":truX}']:
        var accepted = JsonDocument(deepseek_buffered_response('{"choices":[{"message":{"tool_calls":[{"id":"synthetic-call","function":{"name":"lookup","arguments":' + quote_json(arguments) + "}}]}}]}", 1, "resp_fragments"))
        assert_equal(accepted.get(accepted.root, "error"), -1)
        var accepted_call = accepted.nodes[accepted.get(accepted.root, "output")].children[0]
        assert_equal(accepted.string(accepted.get(accepted_call, "arguments")), arguments)
    var rejected = False
    try:
        _ = deepseek_buffered_response("{bad", 1, "resp_bad")
    except error:
        rejected = String(error) == "failed to parse DeepSeek chat response JSON"
    assert_true(rejected)
    var prefix = String('{"id":"at-cap","ignored":"')
    var suffix = String('"}')
    var at_cap = prefix + String("x") * (4194304 - prefix.byte_length() - suffix.byte_length()) + suffix
    var cap_response = JsonDocument(deepseek_buffered_response(at_cap, 1, "resp_cap"))
    assert_equal(cap_response.string(cap_response.get(cap_response.root, "id")), "at-cap")
    rejected = False
    try:
        _ = deepseek_buffered_response(at_cap + " ", 1, "resp_cap")
    except error:
        rejected = String(error) == "buffered response exceeded safe size limit (4194304)"
    assert_true(rejected)
    assert_equal(deepseek_buffered_assistant_messages("{}"), "[]")
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":"","refusal":"ignored"}}]}'), "[]")
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":null,"reasoning_content":" ","tool_calls":null}}]}'), '[{"content":"","reasoning_content":" ","role":"assistant","tool_calls":null}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":false,"reasoning_content":"think"}}]}'), '[{"content":null,"reasoning_content":"think","role":"assistant"}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":null,"tool_calls":[{"id":"original-call","function":{"name":"shell","arguments":"{\\"cmd\\":\\"cargo test\\"}"},"extra_content":{"google":{"thought_signature":"original-signature"}}}]}}]}'), '[{"content":"","role":"assistant","tool_calls":[{"extra_content":{"google":{"thought_signature":"original-signature"}},"function":{"arguments":"{\\"cmd\\":\\"rtk cargo test\\"}","name":"shell"},"id":"original-call"}]}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":"first"}},{"message":{"content":"ignored"}}]}'), '[{"content":"first","role":"assistant"}]')
    print("Provider buffered chat checks: PASS")
