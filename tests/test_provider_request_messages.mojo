from std.testing import assert_equal, assert_true

from modex.json import JsonDocument
from modex.provider_request_messages import ensure_json_instruction, request_messages


def main() raises:
    var simple = JsonDocument('{"instructions":"  rules  ","input":"hello"}')
    assert_equal(request_messages(simple), '[{"role":"system","content":"  rules  "},{"role":"user","content":"hello"}]')
    var duplicate_system = JsonDocument('{"instructions":"rules","input":[]}')
    assert_equal(request_messages(duplicate_system, '[{"role":"system","content":"rules"}]'), '[{"content":"rules","role":"system"}]')
    var replay = JsonDocument('{"input":[{"type":"message","role":"user","content":"prior"},{"type":"function_call","call_id":"old","name":"lookup"},{"type":"function_call_output","call_id":"done","output":"skip"}]}')
    assert_equal(request_messages(replay, '[{"role":"user","content":"prior"},{"role":"assistant","tool_calls":[{"id":"old"}]},{"role":"tool","tool_call_id":"old","content":"old result"}]'), '[{"content":"prior","role":"user"},{"role":"assistant","tool_calls":[{"id":"old"}],"content":""},{"content":"old result","role":"tool","tool_call_id":"old"}]')
    var calls = JsonDocument('{"input":[{"type":"function_call","call_id":"c","name":"lookup","arguments":"{\\"q\\":1}"},{"type":"function_call_output","call_id":"c","output":"ok"}]}')
    assert_equal(request_messages(calls), '[{"role":"assistant","content":"","tool_calls":[{"function":{"arguments":"{\\"q\\":1}","name":"lookup"},"id":"c","type":"function"}]},{"role":"tool","tool_call_id":"c","content":"ok"}]')
    var fallback_call_ids = JsonDocument('{"input":[{"type":"function_call","call_id":null,"tool_call_id":"call_alias","name":"lookup"},{"type":"function_call_output","call_id":null,"tool_call_id":"call_alias","output":"ok"}]}')
    assert_equal(request_messages(fallback_call_ids), '[{"role":"assistant","content":"","tool_calls":[{"function":{"arguments":"{}","name":"lookup"},"id":"call_1","type":"function"}]},{"role":"tool","tool_call_id":"call_1","content":"ok"}]')
    var continuation_output = JsonDocument('{"input":[{"type":"function_call_output","call_id":null,"tool_call_id":"call_alias","output":"ok"}]}')
    assert_equal(request_messages(continuation_output, '[{"role":"assistant","content":"","tool_calls":[{"id":"call_1","type":"function","function":{"name":"lookup","arguments":"{}"}}]}]'), '[{"content":"","role":"assistant","tool_calls":[{"function":{"arguments":"{}","name":"lookup"},"id":"call_1","type":"function"}]},{"role":"tool","tool_call_id":"call_1","content":"ok"}]')

    var malformed_id = JsonDocument('{"input":[{"type":"function_call","call_id":" ","id":"valid","name":"lookup"}]}')
    var raised = False
    try: _ = request_messages(malformed_id)
    except: raised = True
    assert_true(raised)
    var missing_output_id = JsonDocument('{"input":[{"type":"function_call_output","output":"orphan"}]}')
    raised = False
    try: _ = request_messages(missing_output_id)
    except: raised = True
    assert_true(raised)
    var malformed_type = JsonDocument('{"input":[{"type":null,"role":"user","content":"x"}]}')
    raised = False
    try: _ = request_messages(malformed_type)
    except: raised = True
    assert_true(raised)
    var empty_type = JsonDocument('{"input":[{"type":"","role":"user","content":"x"}]}')
    raised = False
    try: _ = request_messages(empty_type)
    except: raised = True
    assert_true(raised)
    var action_without_command = JsonDocument('{"input":[{"type":"local_shell_call","id":"s","command":"pwd","action":{}}]}')
    raised = False
    try: _ = request_messages(action_without_command)
    except: raised = True
    assert_true(raised)
    var action_with_invalid_command = JsonDocument('{"input":[{"type":"local_shell_call","id":"s","action":{"command":[]}}]}')
    raised = False
    try: _ = request_messages(action_with_invalid_command)
    except: raised = True
    assert_true(raised)
    var cached_text = JsonDocument('{"input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"x","cache_control":{}}]}]}')
    raised = False
    try: _ = request_messages(cached_text)
    except: raised = True
    assert_true(raised)
    var text_parts = JsonDocument('{"input":[{"type":"message","role":"user","content":["α",{"input_text":"β"},{"output_text":"🔥"}]}]}')
    assert_equal(request_messages(text_parts), '[{"role":"user","content":"α\\nβ\\n🔥"}]')
    var mcp = JsonDocument('{"input":[{"type":"mcp_call","call_id":"mcp","name":"lookup","arguments":"{}","output":{"ok":true}}]}')
    assert_equal(request_messages(mcp), '[{"role":"assistant","content":"","tool_calls":[{"function":{"arguments":"{}","name":"lookup"},"id":"mcp","type":"function"}]},{"role":"tool","tool_call_id":"mcp","content":{"ok":true}}]')
    var unmatched = JsonDocument('{"input":[{"type":"function_call","call_id":"missing","name":"lookup"}]}')
    assert_equal(request_messages(unmatched), '[{"role":"user","content":""}]')
    assert_equal(ensure_json_instruction('[{"role":"user","content":"hi"}]'), '[{"role":"system","content":"Respond with valid JSON only."},{"content":"hi","role":"user"}]')
    assert_equal(ensure_json_instruction('[{"role":"system","content":"Respond with valid JSON only."}]'), '[{"content":"Respond with valid JSON only.","role":"system"}]')
    assert_equal(ensure_json_instruction('[{"role":"user","content":"Please output JSON now."}]'), '[{"content":"Please output JSON now.","role":"user"}]')
    var invalid_role = JsonDocument('{"input":[{"type":"message","role":"critic","content":"no"}]}')
    raised = False
    try: _ = request_messages(invalid_role)
    except: raised = True
    assert_true(raised)
    var invalid_item = JsonDocument('{"input":[false]}')
    raised = False
    try: _ = request_messages(invalid_item)
    except: raised = True
    assert_true(raised)
    var thinking = JsonDocument('{"input":[{"type":"function_call","call_id":"c","name":"lookup"},{"type":"function_call_output","call_id":"c","output":"ok"}]}')
    assert_equal(request_messages(thinking, "[]", True), '[{"content":"","role":"assistant","reasoning_content":"","tool_calls":[{"function":{"arguments":"{}","name":"lookup"},"id":"c","type":"function"}]},{"content":"ok","role":"tool","tool_call_id":"c"}]')
    assert_equal(request_messages(JsonDocument('{"input":[],"reasoning_effort":"high"}'), '[{"role":"assistant","tool_calls":[{"id":"a"}],"reasoning_content":false},{"role":"tool","tool_call_id":"a","content":"ok"}]', True), '[{"content":"","reasoning_content":"","role":"assistant","tool_calls":[{"id":"a"}]},{"content":"ok","role":"tool","tool_call_id":"a"}]')
    assert_equal(request_messages(JsonDocument('{"input":[]}'), '[{"role":"assistant","content":null,"reasoning_content":"think","tool_calls":[{"id":"missing"}]},{"role":"tool","tool_call_id":"done","content":"ok"}]'), '[{"content":null,"reasoning_content":"think","role":"assistant"}]')
    var signature = JsonDocument('{"input":[{"type":"function_call","call_id":"c","name":"lookup","gemini_thought_signature":"","thought_signature":"sig"},{"type":"function_call_output","call_id":"c","output":"ok"}]}')
    assert_equal(request_messages(signature), '[{"role":"assistant","content":"","tool_calls":[{"function":{"arguments":"{}","name":"lookup"},"gemini_thought_signature":"sig","id":"c","type":"function"}]},{"role":"tool","tool_call_id":"c","content":"ok"}]')
    print("Provider request message checks: PASS")
