"""Native DeepSeek Responses request preparation and pending response context."""

from std.collections import List

from .json import JSON_BOOL, JsonDocument, quote_json, serialize_json
from .provider_request_messages import ensure_json_instruction, request_messages
from .provider_request_params import fields_object, optional_request_fields, request_format, request_metadata, request_reasoning, reasoning_fields, thinking_enabled, validate_request_shape
from .provider_request_prepare import prepare_request_body
from .provider_request_tools import request_tool_fields
from .text import trim_text


def translate_deepseek_request(source: String, history: String = "[]", strict_tools: Bool = False, web_search_mode: String = "auto", previous_response_found: Bool = False) raises -> String:
    var initial: JsonDocument
    try:
        initial = JsonDocument(source)
    except:
        raise Error("failed to parse Codex Responses request JSON")
    var doc = JsonDocument(serialize_json(initial, initial.root))
    validate_request_shape(doc)
    var effort = request_reasoning(doc)
    var thinking = thinking_enabled(effort)
    var model_node = doc.get(doc.root, "model")
    var model = canonical_deepseek_model(doc.string(model_node)) if model_node >= 0 else String("deepseek-v4-pro")
    var stream_node = doc.get(doc.root, "stream")
    var stream = stream_node >= 0 and doc.nodes[stream_node].kind == JSON_BOOL and doc.nodes[stream_node].text == "true"
    var messages = request_messages(doc, history, thinking)
    var format = request_format(doc)
    var metadata = request_metadata(doc, format, thinking)
    if format:
        messages = ensure_json_instruction(messages)
    var reasoning = reasoning_fields(effort)
    var tools = request_tool_fields(doc, thinking, strict_tools, web_search_mode)
    var options = optional_request_fields(doc, stream, format)
    var fields: List[String] = ['"model":' + quote_json(model), '"stream":' + ("true" if stream else "false"), '"messages":' + messages]
    for source_fields in [reasoning, tools, options]:
        var parsed = JsonDocument(source_fields)
        for index in range(len(parsed.nodes[parsed.root].children)):
            fields.append(quote_json(parsed.nodes[parsed.root].names[index]) + ":" + serialize_json(parsed, parsed.nodes[parsed.root].children[index]))
    var runtime_body = JsonDocument(fields_object(fields))
    var prepared = prepare_request_body(doc, serialize_json(runtime_body, runtime_body.root), history, previous_response_found, model)
    # The frozen simple-request pass replaces the body while keeping pending runtime messages.
    var result = JsonDocument('{"body":' + prepared + ',"messages":' + messages + ',"response_metadata":' + metadata + "}")
    return serialize_json(result, result.root)


def canonical_deepseek_model(model: String) -> String:
    var value = trim_text(model)
    if value.startswith("combo:"):
        var start = 6
        var has_component = False
        for index in range(6, value.byte_length() + 1):
            if index == value.byte_length() or value.as_bytes()[index] == 44 or value.as_bytes()[index] == 59 or value.as_bytes()[index] == 124 or value.as_bytes()[index] == 62:
                var component = String(value[byte=start:index])
                for byte in component.as_bytes():
                    has_component = has_component or (byte != 32 and byte != 9)
                var option = trim_text(component)
                if option:
                    return option
                start = index + 1
        if has_component:
            return model
    var alias = value.lower()
    if not value or alias == "auto" or alias == "pro":
        return "deepseek-v4-pro"
    if alias == "flash":
        return "deepseek-flash"
    return value
