"""Responses input and history translation for the DeepSeek chat request."""

from std.collections import List

from .json import JSON_ARRAY, JSON_NULL, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .text import trim_text


def request_messages(doc: JsonDocument, history: String = "[]", thinking_enabled: Bool = False) raises -> String:
    var prior = JsonDocument(history)
    if prior.nodes[prior.root].kind != JSON_ARRAY:
        raise Error("DeepSeek history must be an array")
    var messages = List[String]()
    for item in prior.nodes[prior.root].children:
        messages.append(serialize_json(prior, item))
    var instructions = doc.get(doc.root, "instructions")
    if instructions >= 0 and doc.nodes[instructions].kind == JSON_STRING and trim_text(doc.nodes[instructions].text):
        var found = False
        for item in prior.nodes[prior.root].children:
            var role = prior.get(item, "role")
            var content = prior.get(item, "content")
            if prior.string(role) == "system" and prior.string(content) == doc.nodes[instructions].text:
                found = True
        if not found:
            messages.insert(0, '{"role":"system","content":' + quote_json(doc.nodes[instructions].text) + "}")
    var input = doc.get(doc.root, "input")
    if input >= 0:
        if doc.nodes[input].kind == JSON_STRING:
            messages.append(_simple_message("user", doc.nodes[input].text))
        elif doc.nodes[input].kind == JSON_ARRAY:
            for item in doc.nodes[input].children:
                if doc.nodes[item].kind != JSON_OBJECT:
                    raise Error("DeepSeek input items must be objects")
                _validate_item(doc, item)
                var kind = doc.string(doc.get(item, "type"))
                if kind == "mcp_call" and _history_has_call(prior, doc, item):
                    if _has_result(doc, item) and not _history_has_output(prior, doc, item):
                        _map_mcp_output(doc, item, messages)
                    continue
                if _replayed(prior, doc, item): continue
                _map_item(doc, item, messages)
        else:
            raise Error("DeepSeek input must be a string or array of input items")
    if len(messages) == 0:
        messages.append(_simple_message("user", ""))
    var output = _repair(messages)
    var repaired = JsonDocument(output)
    if len(repaired.nodes[repaired.root].children) == 0:
        output = '[{"role":"user","content":""}]'
    if thinking_enabled:
        output = _thinking(output)
    return output


def ensure_json_instruction(messages: String) raises -> String:
    var doc = JsonDocument(messages)
    if doc.nodes[doc.root].kind != JSON_ARRAY:
        raise Error("DeepSeek messages must be an array")
    for item in doc.nodes[doc.root].children:
        var role = doc.string(doc.get(item, "role"))
        var content = doc.string(doc.get(item, "content"))
        if (role == "system" or role == "user") and _contains_json(content):
            return serialize_json(doc, doc.root)
    return '[{"role":"system","content":"Respond with valid JSON only."},' + _join_serialized(doc, doc.root) + "]"


def _contains_json(value: String) -> Bool:
    for i in range(value.byte_length() - 3):
        var b = value.as_bytes()[i]
        if (b == 74 or b == 106) and (value.as_bytes()[i + 1] == 83 or value.as_bytes()[i + 1] == 115) and (value.as_bytes()[i + 2] == 79 or value.as_bytes()[i + 2] == 111) and (value.as_bytes()[i + 3] == 78 or value.as_bytes()[i + 3] == 110):
            return True
    return False


def _simple_message(role: String, content: String) -> String:
    return '{"role":' + quote_json(role) + ',"content":' + quote_json(content) + "}"


def _join_serialized(doc: JsonDocument, array: Int) -> String:
    var out = String()
    for i in range(len(doc.nodes[array].children)):
        if i > 0: out += ","
        out += serialize_json(doc, doc.nodes[array].children[i])
    return out


def _validate_item(doc: JsonDocument, item: Int) raises:
    if doc.get(item, "prefix") >= 0:
        raise Error("DeepSeek chat prefix completion requires the beta chat endpoint, which is outside this Responses adapter")
    var kind_node = doc.get(item, "type")
    if kind_node >= 0 and doc.nodes[kind_node].kind != JSON_STRING:
        raise Error("DeepSeek input item type must be a string")
    var kind = doc.string(kind_node)
    if kind == "message" or kind_node < 0:
        var role = doc.get(item, "role")
        if role >= 0 and doc.nodes[role].kind != JSON_STRING:
            raise Error("DeepSeek message role must be a string")
        if role >= 0:
            var r = doc.nodes[role].text
            if not (r == "system" or r == "developer" or r == "user" or r == "assistant" or (kind_node < 0 and r == "tool")):
                raise Error("DeepSeek message role `" + r + "` is not supported by this Responses adapter")
        _validate_content(doc, doc.get(item, "content"))
    elif kind == "function_call" or kind == "mcp_call" or kind == "custom_tool_call" or kind == "local_shell_call":
        var id = _first_string(doc, item, ["call_id", "tool_call_id", "id"])
        if not trim_text(id): raise Error("DeepSeek input tool items require a call_id")
        if kind == "local_shell_call":
            var action = doc.get(item, "action")
            var command = doc.get(action, "command") if action >= 0 and doc.nodes[action].kind == JSON_OBJECT else doc.get(item, "command")
            if action >= 0 and doc.nodes[action].kind == JSON_OBJECT:
                if command < 0 or doc.nodes[command].kind != JSON_ARRAY or len(doc.nodes[command].children) == 0:
                    raise Error("DeepSeek local_shell_call action.command must be an array of strings")
                for part in doc.nodes[command].children:
                    if doc.nodes[part].kind != JSON_STRING or not doc.nodes[part].text:
                        raise Error("DeepSeek local_shell_call action.command must be an array of strings")
            elif command < 0 or doc.nodes[command].kind != JSON_STRING or not trim_text(doc.nodes[command].text):
                raise Error("DeepSeek local_shell_call requires a command")
        else:
            var name = _first_string_node(doc, item, ["name", "tool_name"])
            if name < 0: name = _first_string_node(doc, doc.get(item, "function"), ["name"])
            if name < 0 or not trim_text(doc.nodes[name].text):
                raise Error("DeepSeek input tool call items require a function name")
    elif kind == "function_call_output" or kind == "custom_tool_call_output" or kind == "mcp_tool_result" or kind == "mcp_call_output":
        var id = _first_string(doc, item, ["call_id", "tool_call_id", "id"])
        if not trim_text(id): raise Error("DeepSeek input tool items require a call_id")
        var has = doc.get(item, "output") >= 0 or doc.get(item, "content") >= 0 or doc.get(item, "result") >= 0 or doc.get(item, "error") >= 0
        if not has: raise Error("DeepSeek input tool output items require output content")
    elif kind_node >= 0:
        raise Error("DeepSeek input item type `" + kind + "` is not supported by this Responses adapter")


def _validate_content(doc: JsonDocument, content: Int) raises:
    if content < 0: return
    var kind = doc.nodes[content].kind
    if kind == JSON_STRING: return
    if kind == JSON_ARRAY:
        for part in doc.nodes[content].children: _validate_part(doc, part)
    elif kind == JSON_OBJECT: _validate_part(doc, content)
    else: raise Error("DeepSeek message content must be a string, object, or array")


def _validate_part(doc: JsonDocument, part: Int) raises:
    if doc.nodes[part].kind != JSON_OBJECT: return
    if doc.get(part, "cache_control") >= 0: raise Error("DeepSeek per-message cache_control is not supported by this Responses adapter because DeepSeek context caching is automatic")
    for key in ["text", "input_text", "output_text"]:
        var value = doc.get(part, key)
        if value >= 0 and doc.nodes[value].kind == JSON_STRING: return
    var type = doc.string(doc.get(part, "type"))
    if not type: raise Error("DeepSeek text-only adapter does not support object message content parts without text or type")
    if type == "input_image" or type == "image_url" or type == "input_file" or type == "file" or type == "media" or type == "input_audio" or type == "input_video":
        raise Error("DeepSeek text-only adapter does not support message content part type `" + type + "`")
    if type == "input_text": raise Error("DeepSeek input_text content parts require a text field")
    if type == "output_text": raise Error("DeepSeek output_text content parts require a text field")
    if type == "text": raise Error("DeepSeek text content parts require a text field")
    raise Error("DeepSeek text-only adapter does not support message content part type `" + type + "`")


def _first_string(doc: JsonDocument, node: Int, names: List[String]) -> String:
    for name in names:
        var child = doc.get(node, name)
        if child >= 0 and doc.nodes[child].kind == JSON_STRING: return doc.nodes[child].text
    return ""


def _mapped_call_id(doc: JsonDocument, item: Int) -> String:
    # Mapping defaults a present non-string primary ID instead of trying the next field.
    for key in ["call_id", "tool_call_id", "id"]:
        var child = doc.get(item, key)
        if child >= 0:
            if doc.nodes[child].kind == JSON_STRING:
                return doc.nodes[child].text
            return "call_1"
    return "call_1"


def _first_string_node(doc: JsonDocument, node: Int, names: List[String]) -> Int:
    for name in names:
        var child = doc.get(node, name)
        if child >= 0 and doc.nodes[child].kind == JSON_STRING: return child
    return -1


def _thought_signature(doc: JsonDocument, item: Int) -> String:
    for key in ["gemini_thought_signature", "thought_signature", "thoughtSignature"]:
        var signature = doc.get(item, key)
        if signature >= 0 and doc.nodes[signature].kind == JSON_STRING and doc.nodes[signature].text: return doc.nodes[signature].text
    var signature = doc.get(doc.get(item, "provider_specific_fields"), "thought_signature")
    if signature >= 0 and doc.nodes[signature].kind == JSON_STRING and doc.nodes[signature].text: return doc.nodes[signature].text
    signature = doc.get(doc.get(doc.get(item, "extra_content"), "google"), "thought_signature")
    if signature >= 0 and doc.nodes[signature].kind == JSON_STRING: return doc.nodes[signature].text
    return ""


def _text(doc: JsonDocument, node: Int) -> String:
    if node < 0: return ""
    if doc.nodes[node].kind == JSON_STRING: return doc.nodes[node].text
    if doc.nodes[node].kind == JSON_ARRAY:
        var result = String()
        var emitted = False
        for child in doc.nodes[node].children:
            var part = _text_part(doc, child)
            if part:
                if emitted: result += "\n"
                emitted = True
                result += part.value()
        return result
    return serialize_json(doc, node)


def _text_part(doc: JsonDocument, node: Int) -> Optional[String]:
    if doc.nodes[node].kind == JSON_STRING: return Optional[String](doc.nodes[node].text)
    if doc.nodes[node].kind != JSON_OBJECT: return Optional[String]()
    for key in ["text", "input_text", "output_text"]:
        var value = doc.get(node, key)
        if value >= 0 and doc.nodes[value].kind == JSON_STRING: return Optional[String](doc.nodes[value].text)
    return Optional[String]()


def _map_item(doc: JsonDocument, item: Int, mut mapped: List[String]):
    var kind = doc.string(doc.get(item, "type"))
    if kind == "local_shell_call":
        var call_id = _mapped_call_id(doc, item)
        var action = doc.get(item, "action")
        var command = doc.get(item, "command")
        if command < 0: command = doc.get(action, "command")
        var command_text = String()
        if command >= 0 and doc.nodes[command].kind == JSON_STRING:
            command_text = doc.nodes[command].text
        elif command >= 0 and doc.nodes[command].kind == JSON_ARRAY:
            for part in doc.nodes[command].children:
                if doc.nodes[part].kind == JSON_STRING:
                    if command_text: command_text += " "
                    command_text += doc.nodes[part].text
        var args = '{"command":' + quote_json(command_text)
        for key in ["cwd", "timeout", "env"]:
            var value = doc.get(item, key)
            if value < 0: value = doc.get(action, key)
            if value >= 0: args += "," + quote_json(key) + ":" + serialize_json(doc, value)
        args += "}"
        mapped.append('{"role":"assistant","content":"","tool_calls":[{"id":' + quote_json(call_id) + ',"type":"function","function":{"name":"shell_command","arguments":' + quote_json(args) + "}}]}")
        return
    if kind == "function_call" or kind == "mcp_call" or kind == "custom_tool_call" or kind == "local_shell_call":
        var call_id = _mapped_call_id(doc, item)
        var name = _first_string(doc, item, ["name", "tool_name"])
        if not name: name = _first_string(doc, doc.get(item, "function"), ["name"])
        if kind == "custom_tool_call":
            var input = doc.get(item, "input")
            var raw = "" if input < 0 else serialize_json(doc, input)
            var call = '{"id":' + quote_json(call_id) + ',"type":"function","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json('{"input":' + raw + "}") + "}"
            var signature = _thought_signature(doc, item)
            if signature: call += ',"gemini_thought_signature":' + quote_json(signature)
            mapped.append('{"role":"assistant","content":"","tool_calls":[' + call + "}]}")
            return
        var args = doc.get(item, "arguments")
        if args < 0: args = doc.get(item, "input")
        if args < 0: args = doc.get(doc.get(item, "function"), "arguments")
        var argtext = "{}"
        if args >= 0:
            argtext = doc.nodes[args].text if doc.nodes[args].kind == JSON_STRING else serialize_json(doc, args)
        var call = '{"id":' + quote_json(call_id) + ',"type":"function","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json(argtext) + "}"
        var signature = _thought_signature(doc, item)
        if signature: call += ',"gemini_thought_signature":' + quote_json(signature)
        call += "}"
        mapped.append('{"role":"assistant","content":"","tool_calls":[' + call + "]}")
        if kind == "mcp_call" and _has_result(doc, item): _map_mcp_output(doc, item, mapped)
    elif kind == "function_call_output" or kind == "custom_tool_call_output" or kind == "mcp_tool_result" or kind == "mcp_call_output":
        var call_id = _mapped_call_id(doc, item)
        var value = -1
        for key in ["output", "content", "result", "error"]:
            value = doc.get(item, key)
            if value >= 0: break
        mapped.append('{"role":"tool","tool_call_id":' + quote_json(call_id) + ',"content":' + quote_json(_text(doc, value)) + "}")
    else:
        var role = doc.string(doc.get(item, "role"))
        if role == "developer": role = "system"
        if role != "system" and role != "assistant" and role != "tool": role = "user"
        var content = doc.get(item, "content")
        if content < 0: content = doc.get(item, "text")
        mapped.append(_simple_message(role, _text(doc, content)))


def _replayed(history: JsonDocument, doc: JsonDocument, item: Int) -> Bool:
    var kind = doc.string(doc.get(item, "type"))
    var call_id = _first_string(doc, item, ["call_id", "tool_call_id", "id"])
    if kind == "function_call_output" or kind == "custom_tool_call_output" or kind == "mcp_tool_result" or kind == "mcp_call_output":
        for message in history.nodes[history.root].children:
            var id = history.string(history.get(message, "tool_call_id"))
            if history.string(history.get(message, "role")) == "tool" and trim_text(id) and id == call_id: return True
        return False
    if kind == "function_call" or kind == "custom_tool_call" or kind == "local_shell_call" or kind == "mcp_call":
        return _history_has_call(history, doc, item)
    var role = doc.string(doc.get(item, "role"))
    if role == "developer": role = "system"
    if role != "system" and role != "assistant" and role != "tool": role = "user"
    var content = doc.get(item, "content")
    var text = _text(doc, content)
    if not trim_text(text): return True
    for message in history.nodes[history.root].children:
        var history_role = history.string(history.get(message, "role"))
        if history_role == "developer": history_role = "system"
        if history_role != "system" and history_role != "assistant" and history_role != "tool": history_role = "user"
        var history_content = history.get(message, "content")
        if history_role == role and history_content >= 0 and history.nodes[history_content].kind == JSON_STRING and trim_text(history.nodes[history_content].text) and history.nodes[history_content].text == text: return True
    return False


def _history_has_call(history: JsonDocument, doc: JsonDocument, item: Int) -> Bool:
    var call_id = _first_string(doc, item, ["call_id", "tool_call_id", "id"])
    for message in history.nodes[history.root].children:
        var calls = history.get(message, "tool_calls")
        if calls >= 0 and history.nodes[calls].kind == JSON_ARRAY:
            for call in history.nodes[calls].children:
                var id = history.string(history.get(call, "id"))
                if trim_text(id) and id == call_id: return True
    return False


def _history_has_output(history: JsonDocument, doc: JsonDocument, item: Int) -> Bool:
    var call_id = _first_string(doc, item, ["call_id", "tool_call_id", "id"])
    for message in history.nodes[history.root].children:
        var id = history.string(history.get(message, "tool_call_id"))
        if history.string(history.get(message, "role")) == "tool" and trim_text(id) and id == call_id: return True
    return False


def _has_result(doc: JsonDocument, item: Int) -> Bool:
    return doc.get(item, "output") >= 0 or doc.get(item, "content") >= 0 or doc.get(item, "result") >= 0 or doc.get(item, "error") >= 0


def _map_mcp_output(doc: JsonDocument, item: Int, mut mapped: List[String]):
    var call_id = _mapped_call_id(doc, item)
    var value = -1
    for key in ["output", "content", "result", "error"]:
        value = doc.get(item, key)
        if value >= 0: break
    mapped.append('{"role":"tool","tool_call_id":' + quote_json(call_id) + ',"content":' + serialize_json(doc, value) + "}")


def _repair(messages: List[String]) raises -> String:
    var output_ids = List[String]()
    for candidate in messages:
        var result = JsonDocument(candidate)
        if result.string(result.get(result.root, "role")) == "tool":
            var id = result.string(result.get(result.root, "tool_call_id"))
            if trim_text(id) and not _has_string(output_ids, id): output_ids.append(id)
    var used_calls = List[String]()
    var used_outputs = List[String]()
    var out = String("[")
    var first_message = True
    for candidate in messages:
        var msg = JsonDocument(candidate)
        var is_tool = msg.string(msg.get(msg.root, "role")) == "tool"
        if is_tool and len(output_ids) > 0: continue
        var calls = msg.get(msg.root, "tool_calls")
        if calls >= 0 and (msg.nodes[calls].kind != JSON_ARRAY or len(msg.nodes[calls].children) == 0): calls = -1
        var selected = List[Int]()
        if calls >= 0 and msg.nodes[calls].kind == JSON_ARRAY:
            for call in msg.nodes[calls].children:
                var id = msg.string(msg.get(call, "id"))
                if _has_string(output_ids, id) and not _has_string(used_calls, id):
                    selected.append(call)
                    used_calls.append(id)
        if calls >= 0 and msg.nodes[calls].kind == JSON_ARRAY and len(selected) == 0 and not _has_message_content(msg, msg.root):
            continue
        if not first_message: out += ","
        first_message = False
        if calls >= 0 and msg.nodes[calls].kind == JSON_ARRAY:
            if len(selected) > 0:
                out += _message_calls(msg, msg.root, calls, selected, False)
            else:
                out += _message_calls(msg, msg.root, calls, selected, True)
        else:
            out += candidate
        for call in selected:
            var id = msg.string(msg.get(call, "id"))
            for result_text in messages:
                var result = JsonDocument(result_text)
                if result.string(result.get(result.root, "role")) == "tool" and result.string(result.get(result.root, "tool_call_id")) == id and not _has_string(used_outputs, id):
                    out += "," + result_text
                    used_outputs.append(id)
                    break
    return out + "]"


def _has_string(values: List[String], wanted: String) -> Bool:
    for value in values:
        if value == wanted: return True
    return False


def _has_message_content(doc: JsonDocument, node: Int) -> Bool:
    for key in ["content", "reasoning_content"]:
        var value = doc.get(node, key)
        if value < 0 or doc.nodes[value].kind == JSON_NULL: continue
        var kind = doc.nodes[value].kind
        if kind == JSON_STRING and not trim_text(doc.nodes[value].text): continue
        if kind == JSON_ARRAY or kind == JSON_OBJECT:
            if len(doc.nodes[value].children) == 0: continue
        return True
    return False


def _message_calls(doc: JsonDocument, node: Int, calls: Int, selected: List[Int], drop: Bool) -> String:
    var output = String("{")
    var wrote = False
    var has_content = False
    for i in range(len(doc.nodes[node].children)):
        var child = doc.nodes[node].children[i]
        var key = doc.nodes[node].names[i]
        if child == calls and drop: continue
        if wrote: output += ","
        wrote = True
        output += quote_json(key) + ":"
        if child == calls:
            output += "["
            for j in range(len(selected)):
                if j > 0: output += ","
                output += serialize_json(doc, selected[j])
            output += "]"
        elif key == "content" and len(selected) > 0 and doc.nodes[child].kind == JSON_NULL:
            output += "\"\""
        else: output += serialize_json(doc, child)
        if key == "content": has_content = True
    if len(selected) > 0:
        if not has_content:
            if wrote: output += ","
            output += "\"content\":\"\""
    return output + "}"


def _thinking(messages: String) raises -> String:
    var doc = JsonDocument(messages)
    var out = String("[")
    for i in range(len(doc.nodes[doc.root].children)):
        if i > 0: out += ","
        var node = doc.nodes[doc.root].children[i]
        var role = doc.string(doc.get(node, "role"))
        var calls = doc.get(node, "tool_calls")
        if role == "assistant" and calls >= 0 and doc.nodes[calls].kind == JSON_ARRAY and len(doc.nodes[calls].children) > 0:
            var content = doc.get(node, "content")
            var reasoning = doc.get(node, "reasoning_content")
            if content < 0 or doc.nodes[content].kind == JSON_NULL or reasoning < 0 or doc.nodes[reasoning].kind != JSON_STRING:
                var object = serialize_json(doc, node)
                if content < 0: object = object.replace('"tool_calls":', '"content":"","tool_calls":')
                elif doc.nodes[content].kind == JSON_NULL: object = object.replace('"content":null', '"content":""')
                if reasoning < 0: object = object.replace('"tool_calls":', '"reasoning_content":"","tool_calls":')
                elif doc.nodes[reasoning].kind != JSON_STRING: object = object.replace('"reasoning_content":' + serialize_json(doc, reasoning), '"reasoning_content":""')
                out += object
            else: out += serialize_json(doc, node)
        else: out += serialize_json(doc, node)
    return out + "]"
