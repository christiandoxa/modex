from std.testing import assert_equal

from modex.json import JsonDocument
from modex.provider_request_prepare import prepare_request_body


def main() raises:
    var basic = JsonDocument('{"model":"flash","input":"hello","stream":true,"stream_options":{"include_usage":true},"text":{"format":{"type":"json_object"}}}')
    assert_equal(prepare_request_body(basic, '{"runtime":true}'), '{"model":"deepseek-v4-flash","stream":true,"messages":[{"role":"user","content":"hello"}]}')
    var combo_model = JsonDocument('{"model":"combo:flash,auto","input":"x"}')
    assert_equal(prepare_request_body(combo_model, '{"runtime":true}'), '{"model":"deepseek-v4-flash","stream":false,"messages":[{"role":"user","content":"x"}]}')
    var combo_pro = JsonDocument('{"model":"combo:pro,flash","input":"x"}')
    assert_equal(prepare_request_body(combo_pro, '{"runtime":true}'), '{"model":"deepseek-v4-pro","stream":false,"messages":[{"role":"user","content":"x"}]}')
    var combo_model_with_empty_first = JsonDocument('{"model":"combo: , custom-model","input":"x"}')
    assert_equal(prepare_request_body(combo_model_with_empty_first, '{"runtime":true}'), '{"model":"custom-model","stream":false,"messages":[{"role":"user","content":"x"}]}')

    var missing = JsonDocument('{"model":"deepseek-chat"}')
    var known_empty = JsonDocument('{"input":"next","previous_response_id":"saved"}')
    assert_equal(prepare_request_body(known_empty, '{"runtime":true}', previous_response_found=True), '{"runtime":true}')
    assert_equal(prepare_request_body(missing, '{"runtime":true}'), '{"runtime":true}')
    var empty = JsonDocument('{"input":""}')
    assert_equal(prepare_request_body(empty, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":""}]}')
    var empty_array = JsonDocument('{"input":[]}')
    assert_equal(prepare_request_body(empty_array, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[]}')

    var messages_win = JsonDocument('{"input":"ignored","messages":[{"role":"developer","content":"raw"}]}')
    assert_equal(prepare_request_body(messages_win, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"content":"raw","role":"developer"}]}')

    var calls = JsonDocument('{"input":[{"type":"function_call","call_id":"c","name":"lookup","arguments":{"q":1}},{"type":"function_call_output","call_id":"c","output":"ok"}]}')
    assert_equal(prepare_request_body(calls, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"assistant","content":"","tool_calls":[{"id":"c","type":"function","function":{"name":"lookup","arguments":"{\\\"q\\\":1}"}}]},{"role":"tool","tool_call_id":"c","content":"ok"}]}')

    var mcp = JsonDocument('{"input":[{"type":"mcp_call","id":"m","name":"mcp__server__lookup","arguments":"{}","output":{"ok":true}}]}')
    assert_equal(prepare_request_body(mcp, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"assistant","content":"","tool_calls":[{"id":"m","type":"function","function":{"name":"mcp__server__lookup","arguments":"{}"}}]},{"role":"tool","tool_call_id":"m","content":{"ok":true}}]}')

    var empty_tool_name_and_id = JsonDocument('{"input":[{"type":"function_call","name":"","call_id":"missing-name"},{"type":"function_call","name":"lookup","call_id":"","arguments":{}},{"type":"function_call_output","call_id":"","output":"ok"}]}')
    assert_equal(prepare_request_body(empty_tool_name_and_id, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"assistant","content":""},{"role":"assistant","content":"","tool_calls":[{"id":"","type":"function","function":{"name":"lookup","arguments":"{}"}}]},{"role":"tool","tool_call_id":"","content":"ok"}]}')

    var shell = JsonDocument('{"input":[{"type":"local_shell_call","id":"s","command":"pwd","action":{}}]}')
    assert_equal(prepare_request_body(shell, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"assistant","content":"","tool_calls":[{"id":"s","type":"function","function":{"name":"shell_command","arguments":"{\\\"command\\\":\\\"pwd\\\"}"}}]}]}')

    var schema = JsonDocument('{"input":"hello","response_format":{"type":"json_schema","json_schema":{"name":"answer"}}}')
    assert_equal(prepare_request_body(schema, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"hello"}],"response_format":{"type":"json_object"}}')

    var optional = JsonDocument('{"model":"flash","input":"x","temperature":0.2,"top_p":0.9,"max_output_tokens":11,"max_tokens":22,"max_completion_tokens":33,"logprobs":true,"top_logprobs":5,"stop":["a"],"stop_sequences":["b"],"stopSequences":["c"],"user_id":" user_1 ","reasoning_effort":"high","response_format":{"type":"json_schema"}}')
    assert_equal(prepare_request_body(optional, '{"runtime":true}'), '{"model":"deepseek-v4-flash","stream":false,"messages":[{"role":"user","content":"x"}],"temperature":0.2,"top_p":0.9,"max_tokens":33,"logprobs":true,"top_logprobs":5,"stop":["a"],"user_id":"user_1","thinking":{"type":"enabled"},"reasoning_effort":"high","response_format":{"type":"json_object"}}')
    var choice_with_max_reasoning = JsonDocument('{"input":"x","tool_choice":"required","reasoning_effort":"max"}')
    assert_equal(prepare_request_body(choice_with_max_reasoning, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}],"thinking":{"type":"enabled"},"reasoning_effort":"max"}')
    var choice_with_high_reasoning = JsonDocument('{"input":"x","tool_choice":"required","reasoning_effort":"high"}')
    assert_equal(prepare_request_body(choice_with_high_reasoning, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}],"thinking":{"type":"enabled"},"reasoning_effort":"high"}')

    var null_choice = JsonDocument('{"input":"x","tool_choice":null}')
    assert_equal(prepare_request_body(null_choice, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}]}')
    var nested_choice = JsonDocument('{"input":"x","tool_choice":{"type":"function","function":{"name":"lookup"}}}')
    assert_equal(prepare_request_body(nested_choice, '{"runtime":true}'), '{"runtime":true}')
    var text_format = JsonDocument('{"input":"x","text":{"format":{"type":"json_object"}}}')
    assert_equal(prepare_request_body(text_format, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}]}')
    var text_modality = JsonDocument('{"input":"x","modalities":["text"]}')
    assert_equal(prepare_request_body(text_modality, '{"runtime":true}'), '{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}]}')

    var incompatible = JsonDocument('{"input":[{"type":"message","role":"user","content":[{"type":"input_image","image_url":"x"}]}]}')
    assert_equal(prepare_request_body(incompatible, '{"runtime":true}'), '{"runtime":true}')

    var rejected_format = JsonDocument('{"input":"hello","text":{"format":{"type":"json_object"},"verbosity":"high"}}')
    assert_equal(prepare_request_body(rejected_format, '{"runtime":true}'), '{"runtime":true}')
    var rejected_parameter = JsonDocument('{"input":"hello","temperature":"hot"}')
    assert_equal(prepare_request_body(rejected_parameter, '{"runtime":true}'), '{"runtime":true}')
    var rejected_user = JsonDocument('{"input":"hello","user_id":"not allowed"}')
    assert_equal(prepare_request_body(rejected_user, '{"runtime":true}'), '{"runtime":true}')

    var continuation = JsonDocument('{"previous_response_id":"resp_1","input":"next"}')
    assert_equal(prepare_request_body(continuation, '{"runtime":true}', '[{"role":"user","content":"old"}]'), '{"runtime":true}')
    print("Provider request preparation checks: PASS")
