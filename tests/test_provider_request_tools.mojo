from std.testing import assert_equal, assert_true

from modex.json import JsonDocument, serialize_json
from modex.provider_request_tools import request_tool_fields


def check(source: String, expected: String, strict_tools: Bool = False, web_search_mode: String = "auto") raises:
    var doc = JsonDocument(source)
    var actual = JsonDocument(request_tool_fields(doc, strict_tools=strict_tools, web_search_mode=web_search_mode))
    var wanted = JsonDocument(expected)
    assert_equal(serialize_json(actual, actual.root), serialize_json(wanted, wanted.root))


def reject(source: String, expected: String, strict_tools: Bool = False, web_search_mode: String = "auto") raises:
    var doc = JsonDocument(source)
    var actual = String()
    try:
        _ = request_tool_fields(doc, strict_tools=strict_tools, web_search_mode=web_search_mode)
    except error:
        actual = String(error)
    assert_equal(actual, expected)


def main() raises:
    var empty = JsonDocument("{}")
    assert_equal(request_tool_fields(empty), "{}")

    var basic = JsonDocument('{"tools":[{"type":"function","name":"lookup","description":"find","parameters":{"type":"object","properties":{}}}],"tool_choice":"required"}')
    assert_equal(request_tool_fields(basic), '{"tool_choice":"required","tools":[{"type":"function","function":{"name":"lookup","description":"find","parameters":{"properties":{},"type":"object"}}}]}')

    var duplicate = JsonDocument('{"tools":[{"type":"function","name":"same"},{"type":"function","name":"same"}]}')
    assert_equal(request_tool_fields(duplicate), '{"tools":[{"type":"function","function":{"name":"same"}}]}')

    var patch = JsonDocument('{"tools":[{"type":"custom","name":"apply_patch","description":"edit"}]}')
    assert_true(request_tool_fields(patch).find("Original custom tool format JSON") < 0)
    assert_true(request_tool_fields(patch).find("Exact raw apply_patch input") >= 0)

    var namespace = JsonDocument('{"tools":[{"type":"namespace","name":"agents","tools":[{"type":"function","name":"run"}]}],"tool_choice":{"type":"function","namespace":"agents","name":"run"}}')
    assert_equal(request_tool_fields(namespace), '{"tool_choice":{"type":"function","function":{"name":"agents--run"}},"tools":[{"type":"function","function":{"name":"agents--run"}}]}')

    var web = JsonDocument('{"web_search_options":{"search_context_size":"high"}}')
    assert_equal(request_tool_fields(web), '{"web_search_options":{"search_context_size":"high"}}')

    var strict = JsonDocument('{"tools":[{"type":"function","name":"lookup","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer"}}}}]}')
    assert_equal(request_tool_fields(strict, strict_tools=True), '{"tools":[{"type":"function","function":{"name":"lookup","parameters":{"type":"object","properties":{"limit":{"type":"integer"},"query":{"type":"string"}},"required":["limit","query"],"additionalProperties":false},"strict":true}}]}')

    var upgraded = JsonDocument('{"tools":[{"type":"function","name":"lookup","parameters":{"type":"object","additionalProperties":true}},{"type":"function","name":"lookup","parameters":{"type":"object","properties":{"q":{"type":"string"}}}}]}')
    assert_true(request_tool_fields(upgraded).find("\"q\"") >= 0)
    assert_true(request_tool_fields(upgraded).find("additionalProperties\":true") < 0)

    var signed_zero = JsonDocument('{"tools":[{"type":"function","name":"zero","parameters":{"type":"number","enum":[-0.0]}},{"type":"function","name":"zero","parameters":{"type":"number","enum":[0.0]}}]}')
    assert_equal(request_tool_fields(signed_zero).find("\"type\":\"function\""), request_tool_fields(signed_zero).rfind("\"type\":\"function\""))

    var conflicting = JsonDocument('{"tools":[{"type":"function","name":"lookup","parameters":{"type":"object","properties":{"q":{"type":"string"}}}},{"type":"function","name":"lookup","parameters":{"type":"object","properties":{"q":{"type":"integer"}}}}]}')
    var conflict_rejected = False
    try:
        _ = request_tool_fields(conflicting)
    except error:
        conflict_rejected = String(error) == "DeepSeek function tool name `lookup` is duplicated after translation"
    assert_true(conflict_rejected)

    var strict_true = JsonDocument('{"tools":[{"type":"function","name":"lookup","strict":true}]}')
    var strict_true_rejected = False
    try:
        _ = request_tool_fields(strict_true)
    except error:
        strict_true_rejected = String(error) == "DeepSeek strict function tool `lookup` requires deepseek.strict_tools=true"
    assert_true(strict_true_rejected)

    var unsupported_schema = JsonDocument('{"tools":[{"type":"function","name":"lookup","parameters":{"type":"object","properties":{"q":{"type":"string","pattern":"x"}}}}]}')
    var schema_rejected = False
    try:
        _ = request_tool_fields(unsupported_schema, strict_tools=True)
    except error:
        schema_rejected = String(error) == "DeepSeek strict tool schema `lookup` could not be normalized"
    assert_true(schema_rejected)

    var invalid_shape = JsonDocument('{"tools":[{"type":"file_search"}]}')
    var shape_rejected = False
    try:
        _ = request_tool_fields(invalid_shape)
    except error:
        shape_rejected = String(error) == "DeepSeek tool type `file_search` is not supported"
    assert_true(shape_rejected)

    var bad_domains = JsonDocument('{"web_search_options":{"allowed_domains":[""]}}')
    var domains_rejected = False
    try:
        _ = request_tool_fields(bad_domains)
    except error:
        domains_rejected = String(error) == "DeepSeek web_search allowed_domains entries must be non-empty strings"
    assert_true(domains_rejected)

    var wrong_target = JsonDocument('{"tools":[{"type":"function","name":"lookup"}],"tool_choice":{"type":"function","name":"missing"}}')
    var target_rejected = False
    try:
        _ = request_tool_fields(wrong_target)
    except error:
        target_rejected = String(error) == "DeepSeek named tool_choice `missing` does not match any translated function tool"
    assert_true(target_rejected)

    var mcp = JsonDocument('{"tools":[{"type":"mcp_toolset","server_label":"git tools","allowed_tools":["status","push"]}]}')
    var mcp_result = request_tool_fields(mcp)
    assert_true(mcp_result.find("mcp__git_tools__status") >= 0)
    assert_true(mcp_result.find("mcp__git_tools__push") >= 0)

    var mcp_invalid = JsonDocument('{"tools":[{"type":"mcp_toolset","server_name":"server","allowed_tools":["　"]}]}')
    var mcp_rejected = False
    try:
        _ = request_tool_fields(mcp_invalid)
    except error:
        mcp_rejected = String(error) == "DeepSeek MCP toolset `server` requires allowed_tools or enabled configs"
    assert_true(mcp_rejected)

    var web_context = JsonDocument('{"tools":[{"type":"web_search_preview","context_size":"wide"}]}')
    var context_rejected = False
    try:
        _ = request_tool_fields(web_context)
    except error:
        context_rejected = String(error) == "DeepSeek web_search context_size must be low, medium, or high"
    assert_true(context_rejected)

    var ignored_choice = JsonDocument('{"tool_choice":{"type":"function"}}')
    assert_equal(request_tool_fields(ignored_choice, thinking_enabled=True), "{}")

    var bad_choice = JsonDocument('{"tool_choice":"always"}')
    var choice_rejected = False
    try:
        _ = request_tool_fields(bad_choice)
    except error:
        choice_rejected = String(error) == "DeepSeek tool_choice string `always` is not supported"
    assert_true(choice_rejected)

    var name_64 = String("a") * 64
    var name_ok_json = '{"tools":[{"type":"function","name":"' + name_64 + '"}]}'
    var name_ok = JsonDocument(name_ok_json)
    assert_true(request_tool_fields(name_ok).find(name_64) >= 0)

    var name_65 = String("a") * 65
    var name_over_json = '{"tools":[{"type":"function","name":"' + name_65 + '"}]}'
    var name_over = JsonDocument(name_over_json)
    var name_rejected = False
    try:
        _ = request_tool_fields(name_over)
    except error:
        name_rejected = String(error) == "DeepSeek function tool names must use only letters, numbers, underscores, or dashes and be at most 64 bytes"
    assert_true(name_rejected)

    var many = '{"tools":['
    var many_at_limit = '{"tools":['
    for i in range(129):
        if i: many += ","
        many += '{"type":"function","name":"tool_' + String(i) + '"}'
        if i < 128:
            if i: many_at_limit += ","
            many_at_limit += '{"type":"function","name":"tool_' + String(i) + '"}'
    many += ']}'
    many_at_limit += ']}'
    var at_limit = JsonDocument(many_at_limit)
    assert_true(request_tool_fields(at_limit).find("tool_127") >= 0)
    var too_many = JsonDocument(many)
    var count_rejected = False
    try:
        _ = request_tool_fields(too_many)
    except error:
        count_rejected = String(error) == "DeepSeek supports at most 128 function tools"
    assert_true(count_rejected)

    check('{"tools":[]}', "{}")
    check('{"tools":[{}, {"type":7}]}', "{}")
    check('{"tools":[{"type":"function","name":"top","function":{}}]}', "{}")
    check('{"tools":[{"type":7,"name":"mcp__s__implicit","schema":{}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__implicit","parameters":{}}}]}')
    check('{"tools":[{"type":"mcp_function","name":"lookup","input_schema":{"type":"object"}}]}', '{"tools":[{"type":"function","function":{"name":"lookup","parameters":{"type":"object"}}}]}')
    reject('{"tools":[{"type":"mcp_function","function":{"name":"lookup"},"schema":{}}]}', "DeepSeek MCP function tools require a name")
    reject('{"tools":[{"type":"function","name":" ","function":{"name":"lookup"}}]}', "DeepSeek function tools require a name")

    check('{"tools":[{"type":"mcp","server_label":"git tools","configs":{"status":{"enabled":true},"push":{"enabled":false}}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__git_tools__status","description":"MCP tool status from git tools.","parameters":{"type":"object","additionalProperties":true}}}]}')
    check('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["base"],"default_config":{"enabled":false},"configs":{"force":{"enabled":true},"text":{"enabled":"yes"},"missing":{},"false":{"enabled":false}}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__base","description":"MCP tool base from s.","parameters":{"type":"object","additionalProperties":true}}},{"type":"function","function":{"name":"mcp__s__force","description":"MCP tool force from s.","parameters":{"type":"object","additionalProperties":true}}}]}')
    reject('{"tools":[{"type":"mcp","server_label":"s","default_config":{"enabled":false},"configs":{"text":{"enabled":"yes"},"missing":{}}}]}', "DeepSeek MCP toolset `s` requires allowed_tools or enabled configs")
    check('{"tools":[{"type":"mcp","mcp_server_name":" ","server_label":"fallback","allowed_tools":["status"]}]}', "{}")
    check('{"tools":[{"type":"mcp","mcp_server_name":7,"server_label":"s","configs":{"  mcp__external__run  ":{}}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__external__run","description":"MCP tool   mcp__external__run   from s.","parameters":{"type":"object","additionalProperties":true}}}]}')

    check('{"tools":[{"type":"mcp_toolset","name":"mcp__s__direct","server_label":"s","schema":{},"allowed_tools":["run"]}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__direct","parameters":{}}},{"type":"function","function":{"name":"mcp__s__run","description":"MCP tool run from s.","parameters":{"type":"object","additionalProperties":true}}}]}')
    check('{"tools":[{"type":"namespace","name":"mcp__side","schema":{},"tools":[{"type":"function","name":"run"}]}]}', '{"tools":[{"type":"function","function":{"name":"mcp__side","parameters":{}}},{"type":"function","function":{"name":"mcp__side__run"}}]}')
    check('{"tools":[{"type":"tool_search","name":"mcp__s__search","parametersJsonSchema":{}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__search","parameters":{}}},{"type":"function","function":{"name":"tool_search"}}]}')
    check('{"tools":[{"type":"tool_search","strict":true,"parametersJsonSchema":false}]}', '{"tools":[{"type":"function","function":{"name":"tool_search"}}]}')
    check('{"tools":[{"type":"namespace","name":" agents ","strict":true,"tools":[{"type":"function","name":" run ","function":{"name":"ignored","parameters":null},"parameters":{}}]}]}', '{"tools":[{"type":"function","function":{"name":"agents--run","parameters":{}}}]}')

    check('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["run"]}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__run","description":"MCP tool run from s.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":false},"strict":true}}]}', True)
    check('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["run"]},{"type":"function","name":"mcp__s__run","parameters":{"type":"object","properties":{"q":{"type":"string"}}}}]}', '{"tools":[{"type":"function","function":{"name":"mcp__s__run","parameters":{"type":"object","properties":{"q":{"type":"string"}}}}}]}')
    reject('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["run"]},{"type":"function","name":"mcp__s__run","parameters":{"type":"object","properties":{"q":{"type":"string"}}}}]}', "DeepSeek function tool name `mcp__s__run` is duplicated after translation", True)
    reject('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["a-b","a b"]}]}', "DeepSeek function tool name `mcp__s__a_b` is duplicated after translation", True)
    check('{"tools":[{"type":"function","name":"shape","parameters":{"properties":{"optional":{"type":"string"}},"required":false,"additionalProperties":7}}]}', '{"tools":[{"type":"function","function":{"name":"shape","parameters":{"type":"object","properties":{"optional":{"type":"string"}},"required":["optional"],"additionalProperties":false},"strict":true}}]}', True)
    check('{"tools":[{"type":"function","name":"shape","parameters":{"type":"string","properties":false,"required":42,"items":null,"additionalProperties":"ignored","description":false}}]}', '{"tools":[{"type":"function","function":{"name":"shape","parameters":{"type":"string","properties":false,"required":42,"items":null,"additionalProperties":"ignored","description":false},"strict":true}}]}', True)
    check('{"tools":[{"type":"function","name":"shape","parameters":{"type":7,"enum":null,"properties":null,"anyOf":[]}}]}', '{"tools":[{"type":"function","function":{"name":"shape","parameters":{"type":7,"enum":null,"properties":null,"anyOf":[]},"strict":true}}]}', True)

    check('{"tools":[{"type":"namespace","name":" mcp__srv_ ","tools":[{"type":"function","name":" _run "}]}],"tool_choice":{"type":"function","namespace":" mcp__srv_ ","name":" _run "}}', '{"tool_choice":{"type":"function","function":{"name":"mcp__srv_--_run"}},"tools":[{"type":"function","function":{"name":"mcp__srv_--_run"}}]}')
    check('{"tools":[{"type":"namespace","name":"mcp__srv","tools":[{"type":"function","name":"mcp__other__run"}]}]}', '{"tools":[{"type":"function","function":{"name":"mcp__srv--mcp__other__run"}}]}')
    check('{"tools":[{"type":"namespace","name":"ns","tools":[{"type":"function","name":"run"}]}],"tool_choice":{"type":"function","server_label":"ns","name":"run"}}', '{"tool_choice":{"type":"function","function":{"name":"ns--run"}},"tools":[{"type":"function","function":{"name":"ns--run"}}]}')
    check('{"tools":[{"type":"mcp","server_label":"s","allowed_tools":["run"]}],"tool_choice":{"type":"mcp_function","server_label":"s","name":" run "}}', '{"tool_choice":{"type":"function","function":{"name":"mcp__s__run"}},"tools":[{"type":"function","function":{"name":"mcp__s__run","description":"MCP tool run from s.","parameters":{"type":"object","additionalProperties":true}}}]}')
    check('{"tools":[{"type":"function","name":"run"}],"tool_choice":{"type":"function","namespace":"","server_label":"ignored","name":"run"}}', '{"tool_choice":{"type":"function","function":{"name":"run"}},"tools":[{"type":"function","function":{"name":"run"}}]}')
    reject('{"tool_choice":{"type":"function","name":"","function":{"name":"run"}}}', "DeepSeek named tool_choice requires a function name")
    reject('{"tool_choice":{"type":"mcp_tool","server_label":" s ","name":"run"}}', "DeepSeek function tool names must use only letters, numbers, underscores, or dashes and be at most 64 bytes")

    check('{"tools":[{"type":"web_search","context_size":"wide","allowed_domains":false}],"web_search_options":{"type":"web_search","context_size":"wide","location":null}}', '{"web_search_options":{"type":"web_search","context_size":"wide","location":null}}')
    check('{"tools":[{"type":"web_search","context_size":"high","location":{"city":"Tokyo"},"ignored":true}]}', '{"web_search_options":{"search_context_size":"high","user_location":{"city":"Tokyo"}}}')
    reject('{"tools":[{"type":"web_search","context_size":"high"},{"type":"web_search_preview","context_size":"wide"}]}', "DeepSeek web_search context_size must be low, medium, or high")
    check('{"tools":[{"type":"web_search","context_size":"high"},{"type":"web_search_preview","context_size":"wide"}],"web_search_options":{}}', '{"web_search_options":{}}')
    reject('{"tools":[{"type":"web_search","context_size":"wide"}]}', "DeepSeek web_search context_size must be low, medium, or high", web_search_mode="off")
    reject('{"web_search_options":null}', "DeepSeek web search mode is off; remove web_search tools or set deepseek.web_search_mode", web_search_mode="off")
    reject('{"web_search_options":{"max_uses":18446744073709551616}}', "DeepSeek web_search max_uses must be a positive integer")
    print("Provider request tool checks: PASS")
