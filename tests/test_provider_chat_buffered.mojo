from std.testing import assert_equal, assert_true
from std.time.time import _realtime_nanoseconds

from modex.json import JSON_BOOL, JSON_NULL, JsonDocument, quote_json
from modex.provider_anthropic_messages import anthropic_buffered_assistant_messages, anthropic_buffered_response
from modex.provider_chat_buffered import deepseek_buffered_assistant_messages, deepseek_buffered_response
from modex.provider_chat_usage import json_unsigned


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

    var defaults_before = UInt64(max(0, _realtime_nanoseconds() // 1000000000))
    var defaults = JsonDocument(deepseek_buffered_response("{\"choices\":[]}", 23, "resp_test", "{\"request\":true}"))
    var defaults_after = UInt64(max(0, _realtime_nanoseconds() // 1000000000))
    assert_equal(defaults.string(defaults.get(defaults.root, "id")), "resp_test")
    var default_created_at = json_unsigned(defaults, defaults.get(defaults.root, "created_at"))
    assert_true(default_created_at)
    assert_true(default_created_at.value() >= defaults_before)
    assert_true(default_created_at.value() <= defaults_after)
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
    var wrong_created_at = json_unsigned(wrong_types, wrong_types.get(wrong_types.root, "created_at"))
    assert_true(wrong_created_at)
    assert_true(wrong_created_at.value() > 2)
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
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[]}'), "[]")
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":"","refusal":"ignored"}}]}'), "[]")
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":"first"}},null]}'), '[{"content":"first","role":"assistant"}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":null,"reasoning_content":" ","tool_calls":null}}]}'), '[{"content":"","reasoning_content":" ","role":"assistant","tool_calls":null}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":false,"reasoning_content":"think"}}]}'), '[{"content":null,"reasoning_content":"think","role":"assistant"}]')
    for source in ['{"choices":[null,{"message":{"content":"ignored"}}]}', '{"choices":[7]}']:
        rejected = False
        try:
            _ = deepseek_buffered_assistant_messages(source)
        except error:
            rejected = String(error) == "DeepSeek chat response choice is not an object"
        assert_true(rejected)
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":null,"tool_calls":[{"id":"original-call","function":{"name":"shell","arguments":"{\\"cmd\\":\\"cargo test\\"}"},"extra_content":{"google":{"thought_signature":"original-signature"}}}]}}]}'), '[{"content":"","role":"assistant","tool_calls":[{"extra_content":{"google":{"thought_signature":"original-signature"}},"function":{"arguments":"{\\"cmd\\":\\"rtk cargo test\\"}","name":"shell"},"id":"original-call"}]}]')
    assert_equal(deepseek_buffered_assistant_messages('{"choices":[{"message":{"content":"first"}},{"message":{"content":"ignored"}}]}'), '[{"content":"first","role":"assistant"}]')

    var anthropic_tool = '{"id":"msg_tool_use","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"text","text":"Found it."},{"type":"tool_use","id":"call_tool_use","name":"functions--lookup","input":{"query":"release"}}],"stop_reason":"tool_use","usage":{"input_tokens":3,"output_tokens":5}}'
    var anthropic_tool_response = JsonDocument(anthropic_buffered_response(anthropic_tool, 7))
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_response.root, "id")), "msg_tool_use")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_response.root, "object")), "response")
    var anthropic_metadata = anthropic_tool_response.get(anthropic_tool_response.root, "metadata")
    var anthropic_metadata_provider = anthropic_tool_response.get(anthropic_metadata, "anthropic")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_metadata_provider, "stop_reason")), "tool_use")
    var anthropic_output = anthropic_tool_response.get(anthropic_tool_response.root, "output")
    assert_equal(len(anthropic_tool_response.nodes[anthropic_output].children), 2)
    var anthropic_message = anthropic_tool_response.nodes[anthropic_output].children[0]
    var anthropic_tool_call = anthropic_tool_response.nodes[anthropic_output].children[1]
    var anthropic_message_content = anthropic_tool_response.get(anthropic_message, "content")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_response.nodes[anthropic_message_content].children[0], "text")), "Found it.")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_call, "type")), "function_call")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_call, "call_id")), "call_tool_use")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_call, "namespace")), "functions")
    assert_equal(anthropic_tool_response.string(anthropic_tool_response.get(anthropic_tool_call, "arguments")), "{\"query\":\"release\"}")
    var anthropic_history = JsonDocument(anthropic_buffered_assistant_messages(anthropic_tool))
    var history_message = anthropic_history.nodes[anthropic_history.root].children[0]
    assert_equal(anthropic_history.string(anthropic_history.get(history_message, "content")), "Found it.")
    var history_tool_calls = anthropic_history.get(history_message, "tool_calls")
    var history_tool_call = anthropic_history.nodes[history_tool_calls].children[0]
    var history_function = anthropic_history.get(history_tool_call, "function")
    assert_equal(anthropic_history.string(anthropic_history.get(history_function, "name")), "functions--lookup")
    var anthropic_text_only_source = '{"id":"msg_text_only","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"text","text":"previous reply"}],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
    var anthropic_text_only = JsonDocument(anthropic_buffered_response(anthropic_text_only_source, 7))
    var anthropic_text_output = anthropic_text_only.get(anthropic_text_only.root, "output")
    assert_equal(len(anthropic_text_only.nodes[anthropic_text_output].children), 1)
    var anthropic_empty_source = '{"id":"msg_empty","type":"message","role":"assistant","model":"deepseek-chat","content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
    var anthropic_empty = JsonDocument(anthropic_buffered_response(anthropic_empty_source, 7))
    assert_equal(len(anthropic_empty.nodes[anthropic_empty.get(anthropic_empty.root, "output")].children), 0)
    assert_equal(anthropic_buffered_assistant_messages(anthropic_empty_source), "[]")
    assert_equal(anthropic_buffered_assistant_messages(
        '{"id":"msg_empty_text","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"text","text":""}],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}',
    ), "[]")
    var rejected_anthropic_text = False
    try:
        _ = anthropic_buffered_response(
            '{"id":"msg_invalid_text","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"text"}],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}',
            7,
        )
    except error:
        rejected_anthropic_text = String(error) == "Anthropic Messages text block is invalid"
    assert_true(rejected_anthropic_text)
    var anthropic_missing_input = JsonDocument(anthropic_buffered_response(
        '{"id":"msg_tool_default","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"tool_use","id":"call_default","name":"lookup"}],"stop_reason":"tool_use","usage":{"input_tokens":1,"output_tokens":1}}',
        7,
    ))
    var default_tool = anthropic_missing_input.nodes[anthropic_missing_input.get(anthropic_missing_input.root, "output")].children[0]
    assert_equal(anthropic_missing_input.string(anthropic_missing_input.get(default_tool, "arguments")), "{}")
    var anthropic_mixed = JsonDocument(anthropic_buffered_response(
        '{"id":"msg_mixed","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"text","text":"Found "},{"type":"text","text":"it."},{"type":"tool_use","id":"call_one","name":"one","input":7},{"type":"text","text":"Next"},{"type":"tool_use","id":"call_two","name":"two","input":[1,"two"]}],"stop_reason":"tool_use","usage":{"input_tokens":1,"output_tokens":1}}',
        7,
    ))
    var mixed_output = anthropic_mixed.get(anthropic_mixed.root, "output")
    assert_equal(len(anthropic_mixed.nodes[mixed_output].children), 4)
    var first_text = anthropic_mixed.nodes[mixed_output].children[0]
    var first_text_content = anthropic_mixed.get(first_text, "content")
    assert_equal(len(anthropic_mixed.nodes[first_text_content].children), 2)
    assert_equal(anthropic_mixed.string(anthropic_mixed.get(anthropic_mixed.nodes[first_text_content].children[0], "text")), "Found ")
    assert_equal(anthropic_mixed.string(anthropic_mixed.get(anthropic_mixed.nodes[first_text_content].children[1], "text")), "it.")
    assert_equal(anthropic_mixed.string(anthropic_mixed.get(anthropic_mixed.nodes[mixed_output].children[1], "arguments")), "7")
    assert_equal(anthropic_mixed.string(anthropic_mixed.get(anthropic_mixed.nodes[mixed_output].children[3], "arguments")), '[1,"two"]')
    var anthropic_missing_stop = JsonDocument(anthropic_buffered_response(
        '{"id":"msg_stop","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"tool_use","id":"call_stop","name":"lookup","input":{}}],"usage":{"input_tokens":1,"output_tokens":1}}',
        7,
    ))
    assert_true(anthropic_missing_stop.get(anthropic_missing_stop.root, "metadata") < 0)
    var anthropic_null_stop = JsonDocument(anthropic_buffered_response(
        '{"id":"msg_stop","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"tool_use","id":"call_stop","name":"lookup","input":{}}],"stop_reason":null,"usage":{"input_tokens":1,"output_tokens":1}}',
        7,
    ))
    var null_stop_metadata = anthropic_null_stop.get(anthropic_null_stop.root, "metadata")
    var null_stop_provider = anthropic_null_stop.get(null_stop_metadata, "anthropic")
    assert_equal(anthropic_null_stop.nodes[anthropic_null_stop.get(null_stop_provider, "stop_reason")].kind, JSON_NULL)
    var rejected_anthropic_tool = False
    try:
        _ = anthropic_buffered_response(
            '{"id":"msg_invalid_tool","type":"message","role":"assistant","model":"deepseek-chat","content":[{"type":"tool_use","name":"lookup","input":{}}],"stop_reason":"tool_use","usage":{"input_tokens":1,"output_tokens":1}}',
            7,
        )
    except error:
        rejected_anthropic_tool = String(error) == "Anthropic tool_use block requires an id"
    assert_true(rejected_anthropic_tool)
    print("Provider buffered chat checks: PASS")
