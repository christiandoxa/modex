"""Native DeepSeek simple-request compatibility pass."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NULL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .text import trim_text


def prepare_request_body(doc: JsonDocument, runtime_body: String, history: String = "[]", previous_response_found: Bool = False) raises -> String:
    if doc.nodes[doc.root].kind != JSON_OBJECT: return runtime_body
    var prior = JsonDocument(history)
    if prior.nodes[prior.root].kind != JSON_ARRAY: return runtime_body
    if not _simple_request(doc, prior, previous_response_found) or not _core_conforms(doc): return runtime_body
    return _native_body(doc)


def _simple_request(doc: JsonDocument, history: JsonDocument, previous_response_found: Bool) -> Bool:
    var previous = doc.get(doc.root, "previous_response_id")
    if previous >= 0 and doc.nodes[previous].kind == JSON_STRING and trim_text(doc.nodes[previous].text) and (previous_response_found or len(history.nodes[history.root].children) > 0): return False
    for key in ["web_search_options", "safety_identifier"]:
        if doc.get(doc.root, key) >= 0: return False
    var format = doc.get(doc.root, "response_format")
    if format >= 0:
        if doc.nodes[format].kind != JSON_OBJECT: return False
        var kind = doc.string(doc.get(format, "type"))
        if kind != "text" and kind != "json_object" and kind != "json_schema" and kind != "json" and kind != "structured_output": return False
    var tools = doc.get(doc.root, "tools")
    if tools >= 0:
        if doc.nodes[tools].kind != JSON_ARRAY: return False
        for tool in doc.nodes[tools].children:
            if doc.nodes[tool].kind != JSON_OBJECT or doc.string(doc.get(tool, "type")) != "function": return False
            var function = doc.get(tool, "function")
            if function < 0 or doc.nodes[function].kind != JSON_OBJECT or not trim_text(doc.string(doc.get(function, "name"))): return False
    var choice = doc.get(doc.root, "tool_choice")
    if choice >= 0 and not _simple_tool_choice(doc, choice): return False
    var input = doc.get(doc.root, "input")
    if input < 0: return False
    if doc.nodes[input].kind == JSON_STRING: return True
    if doc.nodes[input].kind != JSON_ARRAY: return False
    for item in doc.nodes[input].children:
        if not _simple_item(doc, item): return False
    return True


def _core_conforms(doc: JsonDocument) -> Bool:
    for key in ["frequency_penalty", "presence_penalty", "n", "seed", "service_tier", "prediction", "logit_bias", "functions", "function_call", "max_tool_calls", "audio"]:
        if doc.get(doc.root, key) >= 0: return False
    var text = doc.get(doc.root, "text")
    if text >= 0:
        if doc.nodes[text].kind != JSON_OBJECT: return False
        for key in doc.nodes[text].names:
            if key != "format": return False
    var format = doc.get(doc.root, "response_format")
    if format < 0 and text >= 0: format = doc.get(text, "format")
    if format >= 0:
        if doc.nodes[format].kind != JSON_OBJECT: return False
        var format_type = doc.string(doc.get(format, "type"))
        if format_type != "text" and format_type != "json_object" and format_type != "json_schema" and format_type != "json" and format_type != "structured_output": return False
    for key in ["metadata", "client_metadata"]:
        var value = doc.get(doc.root, key)
        if value >= 0 and doc.nodes[value].kind != JSON_OBJECT: return False
    for key in ["prompt_cache_key", "prompt_cache_retention"]:
        var value = doc.get(doc.root, key)
        if value >= 0 and doc.nodes[value].kind != JSON_STRING: return False
    var user = doc.get(doc.root, "user_id")
    if user < 0: user = doc.get(doc.root, "user")
    if user < 0: user = doc.get(doc.root, "safety_identifier")
    if user >= 0 and (doc.nodes[user].kind != JSON_STRING or not _valid_user_id(doc.nodes[user].text)): return False
    for key in ["prefix", "suffix", "prompt"]:
        if doc.get(doc.root, key) >= 0: return False
    var reasoning = doc.get(doc.root, "reasoning")
    if reasoning >= 0:
        if doc.nodes[reasoning].kind != JSON_OBJECT: return False
        for key in doc.nodes[reasoning].names:
            if key != "effort": return False
        var effort = doc.get(reasoning, "effort")
        if effort >= 0 and doc.nodes[effort].kind != JSON_STRING: return False
    var effort = doc.get(doc.root, "reasoning_effort")
    if effort >= 0 and doc.nodes[effort].kind != JSON_STRING: return False
    if reasoning >= 0 and doc.get(reasoning, "effort") >= 0: effort = doc.get(reasoning, "effort")
    if effort >= 0:
        var value = trim_text(doc.nodes[effort].text).lower()
        if value != "max" and value != "xhigh" and value != "high" and value != "medium" and value != "low" and value != "minimal" and value != "none": return False
    var parallel = doc.get(doc.root, "parallel_tool_calls")
    if parallel >= 0 and not _is_true(doc, parallel): return False
    var stream_options = doc.get(doc.root, "stream_options")
    if stream_options >= 0:
        if doc.nodes[stream_options].kind != JSON_OBJECT or not _is_true(doc, doc.get(doc.root, "stream")): return False
        for key in doc.nodes[stream_options].names:
            if key != "include_usage": return False
        var include = doc.get(stream_options, "include_usage")
        if include >= 0 and not _is_true(doc, include): return False
    var include = doc.get(doc.root, "include")
    if include >= 0 and doc.nodes[include].kind != JSON_ARRAY: return False
    var store = doc.get(doc.root, "store")
    if store >= 0 and doc.nodes[store].kind != JSON_BOOL: return False
    var background = doc.get(doc.root, "background")
    if background >= 0 and doc.nodes[background].kind == JSON_BOOL and _is_true(doc, background): return False
    if background >= 0 and doc.nodes[background].kind != JSON_BOOL: return False
    var truncation = doc.get(doc.root, "truncation")
    if truncation >= 0 and (doc.nodes[truncation].kind != JSON_STRING or doc.string(truncation) != "disabled"): return False
    for key in ["temperature", "top_p"]:
        var value = doc.get(doc.root, key)
        if value >= 0 and doc.nodes[value].kind != JSON_NUMBER: return False
    for key in ["max_output_tokens", "max_tokens", "max_completion_tokens"]:
        var value = doc.get(doc.root, key)
        if value >= 0 and (doc.nodes[value].kind != JSON_NUMBER or not _positive_integer(doc.nodes[value].text)): return False
    var logprobs = doc.get(doc.root, "logprobs")
    if logprobs >= 0 and doc.nodes[logprobs].kind != JSON_BOOL: return False
    var top = doc.get(doc.root, "top_logprobs")
    if top >= 0 and (doc.nodes[top].kind != JSON_NUMBER or _small_uint(doc.nodes[top].text) < 0 or _small_uint(doc.nodes[top].text) > 20 or not _is_true(doc, logprobs)): return False
    var stop = doc.get(doc.root, "stop")
    if stop < 0: stop = doc.get(doc.root, "stop_sequences")
    if stop < 0: stop = doc.get(doc.root, "stopSequences")
    if stop >= 0 and doc.nodes[stop].kind != JSON_STRING and doc.nodes[stop].kind != JSON_ARRAY: return False
    if stop >= 0 and doc.nodes[stop].kind == JSON_ARRAY:
        if len(doc.nodes[stop].children) > 16: return False
        for item in doc.nodes[stop].children:
            if doc.nodes[item].kind != JSON_STRING: return False
    var modalities = doc.get(doc.root, "modalities")
    if modalities >= 0:
        if doc.nodes[modalities].kind != JSON_ARRAY: return False
        for item in doc.nodes[modalities].children:
            if doc.nodes[item].kind != JSON_STRING or doc.nodes[item].text != "text": return False
    return True


def _valid_user_id(value: String) -> Bool:
    var trimmed = trim_text(value)
    if trimmed.byte_length() > 512: return False
    for byte in trimmed.as_bytes():
        var code = Int(byte)
        if not ((48 <= code <= 57) or (65 <= code <= 90) or (97 <= code <= 122) or code == 45 or code == 95): return False
    return True


def _unsigned_integer(value: String) -> Bool:
    if not value: return False
    for byte in value.as_bytes():
        if byte < 48 or byte > 57: return False
    return True


def _positive_integer(value: String) -> Bool:
    if not _unsigned_integer(value): return False
    for byte in value.as_bytes():
        if byte != 48: return True
    return False


def _small_uint(value: String) -> Int:
    if not _unsigned_integer(value): return -1
    var result = 0
    for byte in value.as_bytes():
        result = result * 10 + Int(byte - 48)
        if result > 20: return 21
    return result


def _simple_tool_choice(doc: JsonDocument, choice: Int) -> Bool:
    if doc.nodes[choice].kind == JSON_NULL: return True
    if doc.nodes[choice].kind == JSON_STRING:
        var value = doc.nodes[choice].text
        return value == "auto" or value == "none" or value == "required"
    if doc.nodes[choice].kind != JSON_OBJECT or doc.string(doc.get(choice, "type")) != "function": return False
    var name = doc.get(choice, "name")
    return name >= 0 and doc.nodes[name].kind == JSON_STRING and doc.nodes[name].text


def _simple_item(doc: JsonDocument, item: Int) -> Bool:
    if doc.nodes[item].kind != JSON_OBJECT: return False
    var kind = doc.string(doc.get(item, "type"))
    if kind == "function_call" or kind == "mcp_call" or kind == "custom_tool_call" or kind == "local_shell_call":
        if not _id_shape(doc, item): return False
        if kind == "local_shell_call":
            var command = doc.get(item, "command")
            if command >= 0 and doc.nodes[command].kind == JSON_STRING: return True
            var action = doc.get(item, "action")
            if action < 0 or doc.nodes[action].kind != JSON_OBJECT: return False
            command = doc.get(action, "command")
            if command < 0 or doc.nodes[command].kind != JSON_ARRAY: return False
            for part in doc.nodes[command].children:
                if doc.nodes[part].kind != JSON_STRING: return False
            return True
        return _simple_name(doc, item, kind != "custom_tool_call")
    if kind == "function_call_output": return _is_string(doc, doc.get(item, "call_id")) and doc.get(item, "output") >= 0
    if kind == "custom_tool_call_output": return _is_string(doc, doc.get(item, "call_id")) and _has_result(doc, item)
    if kind == "mcp_tool_result" or kind == "mcp_call_output":
        return _has_string_id(doc, item) and _id_shape(doc, item) and _has_result(doc, item)
    var type = doc.get(item, "type")
    if type >= 0 and (doc.nodes[type].kind != JSON_STRING or kind != "message"): return False
    var role = doc.get(item, "role")
    if role >= 0 and (doc.nodes[role].kind != JSON_STRING or (doc.string(role) != "system" and doc.string(role) != "assistant" and doc.string(role) != "user" and doc.string(role) != "tool")): return False
    return _simple_content(doc, doc.get(item, "content"))


def _simple_content(doc: JsonDocument, content: Int) -> Bool:
    if content < 0 or doc.nodes[content].kind == JSON_STRING: return True
    if doc.nodes[content].kind != JSON_ARRAY: return False
    for part in doc.nodes[content].children:
        if not _simple_part(doc, part): return False
    return True


def _simple_part(doc: JsonDocument, part: Int) -> Bool:
    if doc.nodes[part].kind != JSON_OBJECT: return False
    var kind = doc.get(part, "type")
    if kind >= 0 and doc.string(kind) != "input_text" and doc.string(kind) != "output_text" and doc.string(kind) != "text": return False
    for key in ["text", "input_text", "output_text"]:
        var text = doc.get(part, key)
        if text >= 0: return doc.nodes[text].kind == JSON_STRING
    return False


def _simple_name(doc: JsonDocument, item: Int, include_function: Bool) -> Bool:
    for key in ["name", "tool_name"]:
        var value = doc.get(item, key)
        if value >= 0: return doc.nodes[value].kind == JSON_STRING
    if include_function:
        var function = doc.get(item, "function")
        if function >= 0 and doc.nodes[function].kind == JSON_OBJECT: return _is_string(doc, doc.get(function, "name"))
    return False


def _call_name_node(doc: JsonDocument, item: Int, include_function: Bool) -> Int:
    var name = doc.get(item, "name")
    if name < 0: name = doc.get(item, "tool_name")
    if name < 0 and include_function: name = doc.get(doc.get(item, "function"), "name")
    return name


def _id_shape(doc: JsonDocument, item: Int) -> Bool:
    for key in ["call_id", "tool_call_id", "id"]:
        var value = doc.get(item, key)
        if value >= 0: return doc.nodes[value].kind == JSON_STRING
    return True


def _has_string_id(doc: JsonDocument, item: Int) -> Bool:
    for key in ["call_id", "tool_call_id", "id"]:
        if _is_string(doc, doc.get(item, key)): return True
    return False


def _native_body(doc: JsonDocument) raises -> String:
    var model = doc.get(doc.root, "model")
    var model_text = "deepseek-chat" if model < 0 or doc.nodes[model].kind != JSON_STRING else _native_model(doc.nodes[model].text)
    var out = '{"model":' + quote_json(model_text) + ',"stream":' + ("true" if _is_true(doc, doc.get(doc.root, "stream")) else "false") + ',"messages":' + _native_messages(doc)
    var tools = doc.get(doc.root, "tools")
    if tools >= 0:
        var kept = List[String]()
        for tool in doc.nodes[tools].children:
            kept.append(serialize_json(doc, tool))
        if len(kept) > 0: out += ',"tools":[' + _join(kept) + "]"
    var reasoning = _reasoning(doc)
    var choice = _native_choice(doc, doc.get(doc.root, "tool_choice"))
    if choice and reasoning != 6 and reasoning != 7: out += ',"tool_choice":' + choice
    for key in ["temperature", "top_p"]:
        var value = doc.get(doc.root, key)
        if value >= 0: out += "," + quote_json(key) + ":" + serialize_json(doc, value)
    var tokens = doc.get(doc.root, "max_output_tokens")
    var alias = doc.get(doc.root, "max_tokens")
    if alias >= 0: tokens = alias
    alias = doc.get(doc.root, "max_completion_tokens")
    if alias >= 0: tokens = alias
    if tokens >= 0: out += ',"max_tokens":' + serialize_json(doc, tokens)
    for key in ["logprobs", "top_logprobs"]:
        var value = doc.get(doc.root, key)
        if value >= 0: out += "," + quote_json(key) + ":" + serialize_json(doc, value)
    var stop = doc.get(doc.root, "stop")
    if stop < 0: stop = doc.get(doc.root, "stop_sequences")
    if stop < 0: stop = doc.get(doc.root, "stopSequences")
    if stop >= 0: out += ',"stop":' + serialize_json(doc, stop)
    var user = doc.get(doc.root, "user_id")
    if user < 0: user = doc.get(doc.root, "user")
    if user < 0: user = doc.get(doc.root, "safety_identifier")
    if user >= 0 and doc.nodes[user].kind == JSON_STRING and trim_text(doc.nodes[user].text): out += ',"user_id":' + quote_json(trim_text(doc.nodes[user].text))
    if reasoning == 6: out += ',"thinking":{"type":"enabled"},"reasoning_effort":"max"'
    elif reasoning == 7: out += ',"thinking":{"type":"enabled"},"reasoning_effort":"high"'
    elif reasoning == 8: out += ',"thinking":{"type":"disabled"}'
    var format = doc.get(doc.root, "response_format")
    if format >= 0:
        var kind = doc.string(doc.get(format, "type"))
        if kind == "json_object" or kind == "json_schema" or kind == "json" or kind == "structured_output": out += ',"response_format":{"type":"json_object"}'
    return out + "}"


def _native_messages(doc: JsonDocument) raises -> String:
    var output = String("[")
    var first = True
    var instructions = doc.get(doc.root, "instructions")
    if _is_string(doc, instructions) and trim_text(doc.nodes[instructions].text):
        output += '{"role":"system","content":' + quote_json(doc.nodes[instructions].text) + "}"
        first = False
    var messages = doc.get(doc.root, "messages")
    if messages >= 0 and doc.nodes[messages].kind == JSON_ARRAY:
        for item in doc.nodes[messages].children:
            if not first: output += ","
            first = False
            output += serialize_json(doc, item)
        return output + "]"
    var input = doc.get(doc.root, "input")
    if input >= 0 and doc.nodes[input].kind == JSON_ARRAY:
        for item in doc.nodes[input].children:
            if not first: output += ","
            first = False
            output += _native_item(doc, item)
    elif input >= 0 and doc.nodes[input].kind == JSON_STRING:
        if not first: output += ","
        output += '{"role":"user","content":' + quote_json(doc.nodes[input].text) + "}"
    elif not first:
        output += ',{"role":"user","content":""}'
    else:
        output += '{"role":"user","content":""}'
    return output + "]"


def _native_item(doc: JsonDocument, item: Int) raises -> String:
    if doc.nodes[item].kind != JSON_OBJECT: return '{"role":"user","content":""}'
    var kind = doc.string(doc.get(item, "type"))
    if kind == "function_call" or kind == "mcp_call" or kind == "custom_tool_call":
        var id_node = _first_member(doc, item, ["call_id", "tool_call_id", "id"])
        var id = "call_1" if id_node < 0 else doc.nodes[id_node].text
        var name_node = _call_name_node(doc, item, kind != "custom_tool_call")
        var name = doc.string(name_node)
        if not name: return '{"role":"assistant","content":""}'
        var args = doc.get(item, "arguments")
        if args < 0: args = doc.get(item, "input")
        if args < 0: args = doc.get(doc.get(item, "function"), "arguments")
        var argument = "{}" if args < 0 else (doc.nodes[args].text if doc.nodes[args].kind == JSON_STRING else serialize_json(doc, args))
        var call = '{"id":' + quote_json(id) + ',"type":"function","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json(argument) + "}}"
        if kind == "custom_tool_call": call = '{"id":' + quote_json(id) + ',"type":"function","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json('{"input":' + ("" if args < 0 else serialize_json(doc, args)) + "}") + "}}"
        var signature = _signature(doc, item)
        if signature: call = String(call[byte=:call.byte_length() - 1]) + ',"gemini_thought_signature":' + quote_json(signature) + "}"
        var result = '{"role":"assistant","content":"","tool_calls":[' + call + "]}"
        if kind == "mcp_call" and _has_result(doc, item): result += "," + _native_output(doc, item, True)
        return result
    if kind == "local_shell_call":
        var id_node = _first_member(doc, item, ["call_id", "tool_call_id", "id"])
        var id = "call_1" if id_node < 0 else doc.nodes[id_node].text
        var action = doc.get(item, "action")
        var command = doc.get(item, "command")
        if command < 0: command = doc.get(action, "command")
        var cmd = String()
        if doc.nodes[command].kind == JSON_STRING: cmd = doc.nodes[command].text
        else:
            for part in doc.nodes[command].children:
                if cmd: cmd += " "
                cmd += doc.nodes[part].text
        var args = '{"command":' + quote_json(cmd)
        for key in ["cwd", "timeout", "env"]:
            var value = doc.get(item, key)
            if value < 0: value = doc.get(action, key)
            if value >= 0: args += "," + quote_json(key) + ":" + serialize_json(doc, value)
        return '{"role":"assistant","content":"","tool_calls":[{"id":' + quote_json(id) + ',"type":"function","function":{"name":"shell_command","arguments":' + quote_json(args + "}") + "}}]}"
    if kind == "function_call_output" or kind == "custom_tool_call_output" or kind == "mcp_tool_result" or kind == "mcp_call_output": return _native_output(doc, item, False)
    var role = doc.string(doc.get(item, "role"))
    if role == "developer": role = "system"
    if role != "assistant" and role != "system" and role != "tool": role = "user"
    var content = doc.get(item, "content")
    if content < 0: content = doc.get(item, "text")
    return '{"role":' + quote_json(role) + ',"content":' + quote_json(_content_text(doc, content)) + "}"


def _native_output(doc: JsonDocument, item: Int, raw: Bool) raises -> String:
    var id_node = _first_member(doc, item, ["call_id", "tool_call_id", "id"])
    var id = "call_1" if id_node < 0 else doc.nodes[id_node].text
    var value = -1
    for key in ["output", "content", "result", "error"]:
        value = doc.get(item, key)
        if value >= 0: break
    var content = serialize_json(doc, value) if raw and value >= 0 else quote_json(_content_text(doc, value))
    return '{"role":"tool","tool_call_id":' + quote_json(id) + ',"content":' + content + "}"


def _content_text(doc: JsonDocument, node: Int) -> String:
    if node < 0: return ""
    if doc.nodes[node].kind == JSON_STRING: return doc.nodes[node].text
    if doc.nodes[node].kind != JSON_ARRAY: return serialize_json(doc, node)
    var result = String()
    var first = True
    for item in doc.nodes[node].children:
        var text = _part_text(doc, item)
        if text:
            if not first: result += "\n"
            result += text.value()
            first = False
    return result


def _part_text(doc: JsonDocument, item: Int) -> Optional[String]:
    if doc.nodes[item].kind == JSON_STRING: return Optional[String](doc.nodes[item].text)
    if doc.nodes[item].kind != JSON_OBJECT: return Optional[String]()
    for key in ["text", "input_text", "output_text"]:
        var value = doc.get(item, key)
        if value >= 0 and doc.nodes[value].kind == JSON_STRING: return Optional[String](doc.nodes[value].text)
    return Optional[String]()


def _native_choice(doc: JsonDocument, choice: Int) raises -> String:
    if choice < 0: return ""
    if doc.nodes[choice].kind == JSON_STRING:
        var value = doc.nodes[choice].text
        return quote_json(value) if value == "auto" or value == "none" or value == "required" else ""
    var name = doc.get(choice, "name")
    if name < 0 or doc.nodes[name].kind != JSON_STRING:
        var function = doc.get(choice, "function")
        name = doc.get(function, "name")
    if name < 0 or doc.nodes[name].kind != JSON_STRING or not trim_text(doc.nodes[name].text): return ""
    return '{"type":"function","function":{"name":' + quote_json(doc.nodes[name].text) + "}}"


def _reasoning(doc: JsonDocument) -> Int:
    var effort = doc.get(doc.root, "reasoning_effort")
    var reasoning = doc.get(doc.root, "reasoning")
    if reasoning >= 0:
        var nested = doc.get(reasoning, "effort")
        if nested >= 0: effort = nested
    if effort < 0 or doc.nodes[effort].kind != JSON_STRING: return 0
    var value = trim_text(doc.nodes[effort].text).lower()
    if value == "max" or value == "xhigh": return 6
    if value == "high" or value == "medium" or value == "low": return 7
    if value == "minimal" or value == "none": return 8
    return 0


def _native_model(value: String) -> String:
    var model = trim_text(value)
    if model.startswith("combo:"):
        var start = 6
        for index in range(6, model.byte_length() + 1):
            if index == model.byte_length() or model.as_bytes()[index] == 44 or model.as_bytes()[index] == 59 or model.as_bytes()[index] == 124 or model.as_bytes()[index] == 62:
                var component = trim_text(String(model[byte=start:index]))
                if component:
                    model = component
                    break
                start = index + 1
    if model.lower() == "auto" or model.lower() == "pro": return "deepseek-v4-pro"
    if model.lower() == "flash": return "deepseek-v4-flash"
    return model


def _signature(doc: JsonDocument, item: Int) -> String:
    for key in ["gemini_thought_signature", "thought_signature", "thoughtSignature"]:
        var signature = doc.get(item, key)
        if signature >= 0 and doc.nodes[signature].kind == JSON_STRING and doc.nodes[signature].text: return doc.nodes[signature].text
    var signature = doc.get(doc.get(item, "provider_specific_fields"), "thought_signature")
    if signature >= 0 and doc.nodes[signature].kind == JSON_STRING and doc.nodes[signature].text: return doc.nodes[signature].text
    signature = doc.get(doc.get(doc.get(item, "extra_content"), "google"), "thought_signature")
    if signature >= 0 and doc.nodes[signature].kind == JSON_STRING and doc.nodes[signature].text: return doc.nodes[signature].text
    return ""


def _first_member(doc: JsonDocument, node: Int, names: List[String]) -> Int:
    for name in names:
        var value = doc.get(node, name)
        if value >= 0: return value
    return -1


def _has_result(doc: JsonDocument, item: Int) -> Bool:
    return doc.get(item, "output") >= 0 or doc.get(item, "content") >= 0 or doc.get(item, "result") >= 0 or doc.get(item, "error") >= 0


def _is_string(doc: JsonDocument, node: Int) -> Bool:
    return node >= 0 and doc.nodes[node].kind == JSON_STRING


def _is_true(doc: JsonDocument, node: Int) -> Bool:
    return node >= 0 and doc.nodes[node].kind == JSON_BOOL and doc.nodes[node].text == "true"


def _join(values: List[String]) -> String:
    var result = String()
    for i in range(len(values)):
        if i > 0: result += ","
        result += values[i]
    return result
