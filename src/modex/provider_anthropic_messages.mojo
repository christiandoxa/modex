"""DeepSeek chat requests and Anthropic Messages function and search tools."""

from std.collections import Dict, List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .provider_chat_items import tool_output_item
from .provider_chat_buffered import deepseek_buffered_assistant_messages
from .provider_chat_metadata import merge_chat_metadata
from .provider_chat_usage import json_unsigned
from .text import unsigned_value

comptime ANTHROPIC_BUFFERED_MAX_CONTENT_BLOCKS = 65_536


def validate_deepseek_anthropic_request(source: String) raises:
    var doc = JsonDocument(source)
    _only_fields(doc, doc.root, ["model", "input", "instructions", "stream", "tools", "web_search_options", "parallel_tool_calls", "tool_choice", "max_output_tokens", "max_tokens", "max_completion_tokens", "temperature", "top_p", "stop", "stop_sequences", "stopSequences", "metadata", "include", "store"], "request")
    var metadata = doc.get(doc.root, "metadata")
    if metadata >= 0 and doc.nodes[metadata].kind != JSON_OBJECT:
        raise Error("Anthropic Responses metadata must be an object")
    var include = doc.get(doc.root, "include")
    if include >= 0 and doc.nodes[include].kind != JSON_ARRAY:
        raise Error("Anthropic Responses include must be an array")
    var model = doc.get(doc.root, "model")
    if model >= 0 and doc.nodes[model].kind != JSON_STRING:
        raise Error("Anthropic Messages slice requires a string model")
    var instructions = doc.get(doc.root, "instructions")
    if instructions >= 0 and doc.nodes[instructions].kind != JSON_STRING:
        raise Error("Anthropic Messages instructions must be a string")
    var input = doc.get(doc.root, "input")
    if input < 0:
        raise Error("Anthropic Messages slice requires input")
    if doc.nodes[input].kind == JSON_STRING:
        pass
    elif doc.nodes[input].kind == JSON_ARRAY:
        for item in doc.nodes[input].children:
            var type = doc.string(doc.get(item, "type"))
            if type == "function_call":
                continue
            if type == "function_call_output":
                # The shared request mapper validates ID aliases and output fields.
                continue
            var type_node = doc.get(item, "type")
            if type_node >= 0 and (doc.nodes[type_node].kind != JSON_STRING or doc.nodes[type_node].text != "message"):
                raise Error("Anthropic Messages slice supports only message input items")
            var role = doc.get(item, "role")
            if type_node >= 0 and role >= 0 and (doc.nodes[role].kind != JSON_STRING or (doc.nodes[role].text != "user" and doc.nodes[role].text != "assistant" and doc.nodes[role].text != "system" and doc.nodes[role].text != "developer")):
                raise Error("Anthropic Messages slice supports only user, assistant, system, and developer message roles")
            var content = doc.get(item, "content")
            if content < 0 or (doc.nodes[content].kind != JSON_STRING and doc.nodes[content].kind != JSON_ARRAY and doc.nodes[content].kind != JSON_OBJECT):
                raise Error("Anthropic Messages slice supports only text message content")
    else:
        raise Error("Anthropic Messages slice supports only string input or simple message arrays")
    var stream = doc.get(doc.root, "stream")
    if stream >= 0 and doc.nodes[stream].kind != JSON_BOOL:
        raise Error("Anthropic Messages stream must be a boolean")
    var parallel = doc.get(doc.root, "parallel_tool_calls")
    if parallel >= 0 and (doc.nodes[parallel].kind != JSON_BOOL or doc.nodes[parallel].text != "true"):
        raise Error("Anthropic Messages only accepts `parallel_tool_calls=true`")
    var tools = doc.get(doc.root, "tools")
    var web_search_options = doc.get(doc.root, "web_search_options")
    if tools < 0 and web_search_options < 0:
        raise Error("Anthropic Messages slice requires a web_search_preview tool")
    if tools >= 0 and doc.nodes[tools].kind != JSON_ARRAY:
        raise Error("Anthropic Messages slice requires a web_search_preview tool")
    var web_count = 0
    if tools >= 0:
        for tool in doc.nodes[tools].children:
            if doc.nodes[tool].kind != JSON_OBJECT:
                raise Error("Anthropic Messages tool must be an object")
            var kind = doc.string(doc.get(tool, "type"))
            if kind == "function":
                # The shared Responses tool mapper validates names, schemas, and strict mode.
                continue
            if kind != "web_search_preview":
                raise Error("Anthropic Messages slice supports function and web_search_preview tools")
            _only_fields(doc, tool, ["type", "allowed_domains", "blocked_domains", "user_location", "max_uses", "search_context_size"], "web search tool")
            web_count += 1
            var allowed_domains = doc.get(tool, "allowed_domains")
            var blocked_domains = doc.get(tool, "blocked_domains")
            if allowed_domains >= 0 and blocked_domains >= 0:
                raise Error("Anthropic web search cannot combine allowed_domains and blocked_domains")
            for key in [String("allowed_domains"), "blocked_domains"]:
                var domains = doc.get(tool, key)
                if domains >= 0:
                    if doc.nodes[domains].kind != JSON_ARRAY:
                        raise Error("Anthropic web_search " + key + " must be an array")
                    for domain in doc.nodes[domains].children:
                        if doc.nodes[domain].kind != JSON_STRING or not doc.nodes[domain].text:
                            raise Error("Anthropic web_search " + key + " entries must be non-empty strings")
            var max_uses = doc.get(tool, "max_uses")
            if max_uses >= 0:
                var count = json_unsigned(doc, max_uses)
                if not count or count.value() == 0:
                    raise Error("Anthropic web search max_uses must be a positive integer")
            var location = doc.get(tool, "user_location")
            if location >= 0 and doc.nodes[location].kind != JSON_OBJECT:
                raise Error("Anthropic web search user_location must be an object")
            var search_context = doc.get(tool, "search_context_size")
            if search_context >= 0 and (
                doc.nodes[search_context].kind != JSON_STRING
                or (doc.nodes[search_context].text != "low" and doc.nodes[search_context].text != "medium" and doc.nodes[search_context].text != "high")
            ):
                raise Error("Anthropic web search search_context_size must be low, medium, or high")
    if web_count != 1 and not (web_count == 0 and web_search_options >= 0):
        raise Error("Anthropic Messages slice requires exactly one web_search_preview tool")


def anthropic_search_filters_conflict(source: String) raises -> Bool:
    var doc = JsonDocument(source)
    var options = doc.get(doc.root, "web_search_options")
    if _has_both_domain_filters(doc, options):
        return True
    var tools = doc.get(doc.root, "tools")
    if tools >= 0 and doc.nodes[tools].kind == JSON_ARRAY:
        for tool in doc.nodes[tools].children:
            if doc.string(doc.get(tool, "type")) == "web_search_preview" and _has_both_domain_filters(doc, tool):
                return True
    return False


def anthropic_auto_chat_fallback_safe(reason: String) -> Bool:
    return (
        reason.startswith("Anthropic Messages does not translate chat field ")
        or reason.startswith("Anthropic Messages does not translate web_search_options field ")
        or reason.startswith("Anthropic web_search_options field ")
        or reason.startswith("Anthropic web search ")
    )


def _has_both_domain_filters(doc: JsonDocument, node: Int) -> Bool:
    return node >= 0 and doc.nodes[node].kind == JSON_OBJECT and doc.get(node, "allowed_domains") >= 0 and doc.get(node, "blocked_domains") >= 0


def deepseek_anthropic_messages_body(source: String) raises -> String:
    var prepared = JsonDocument(source)
    var body = JsonDocument(serialize_json(prepared, prepared.get(prepared.root, "body")))
    _only_fields(body, body.root, ["max_tokens", "messages", "model", "stream", "stream_options", "tool_choice", "tools", "web_search_options", "temperature", "top_p", "stop"], "translated request")
    var model = body.get(body.root, "model")
    if model < 0 or body.nodes[model].kind != JSON_STRING:
        raise Error("Anthropic Messages model must be a string")
    var stream = body.get(body.root, "stream")
    if stream < 0 or body.nodes[stream].kind != JSON_BOOL:
        raise Error("Anthropic Messages stream must be a boolean")
    var stream_options = body.get(body.root, "stream_options")
    if stream_options >= 0:
        _only_fields(body, stream_options, ["include_usage"], "stream_options")
        var include_usage = body.get(stream_options, "include_usage")
        if include_usage < 0 or body.nodes[include_usage].kind != JSON_BOOL or body.nodes[include_usage].text != "true":
            raise Error("Anthropic Messages does not translate stream_options")
    var fields = List[String]()
    fields.append('"max_tokens":' + _field(body, "max_tokens", "4096"))
    var translated_messages = _messages(body)
    fields.append('"messages":' + translated_messages[1])
    fields.append('"model":' + _field(body, "model", '"auto"'))
    fields.append('"stream":' + _field(body, "stream", "false"))
    if translated_messages[0]: fields.append('"system":' + translated_messages[0])
    var stop = body.get(body.root, "stop")
    if stop >= 0:
        fields.append('"stop_sequences":' + ("[" + serialize_json(body, stop) + "]" if body.nodes[stop].kind == JSON_STRING else serialize_json(body, stop)))
    if body.get(body.root, "temperature") >= 0:
        fields.append('"temperature":' + serialize_json(body, body.get(body.root, "temperature")))
    var tools = _tools(body)
    if tools: fields.append('"tools":' + tools)
    var choice = _choice(body)
    if choice: fields.append('"tool_choice":' + choice)
    if body.get(body.root, "top_p") >= 0:
        fields.append('"top_p":' + serialize_json(body, body.get(body.root, "top_p")))
    return "{" + ",".join(fields) + "}"


def _field(doc: JsonDocument, key: String, fallback: String) raises -> String:
    var value = doc.get(doc.root, key)
    return serialize_json(doc, value) if value >= 0 else fallback


def _messages(doc: JsonDocument) raises -> Tuple[String, String]:
    var source = doc.get(doc.root, "messages")
    if source < 0 or doc.nodes[source].kind != JSON_ARRAY or len(doc.nodes[source].children) == 0:
        raise Error("Anthropic Messages requires a messages array")
    var messages = List[String]()
    var tool_results = List[String]()
    var content_parts = List[String]()
    var system_parts = List[String]()
    var current_role = String()
    var has_message = False
    for item in doc.nodes[source].children:
        var role = doc.string(doc.get(item, "role"))
        var content = doc.get(item, "content")
        if role == "tool":
            _only_fields(doc, item, ["role", "tool_call_id", "content"], "tool message")
            var call_id = doc.get(item, "tool_call_id")
            if content < 0 or doc.nodes[content].kind != JSON_STRING:
                raise Error("Anthropic tool result content must be a string")
            var tool_use_id = quote_json("call_prodex")
            if call_id >= 0 and doc.nodes[call_id].kind == JSON_STRING:
                tool_use_id = serialize_json(doc, call_id)
            role = "user"
            if has_message and role != current_role:
                messages.append(_message(current_role, tool_results, content_parts))
                tool_results = List[String]()
                content_parts = List[String]()
            current_role = role
            has_message = True
            tool_results.append('{"type":"tool_result","tool_use_id":' + tool_use_id + ',"content":' + serialize_json(doc, content) + "}")
            continue
        _only_fields(doc, item, ["role", "content", "tool_calls"], "message")
        if role == "developer": role = "system"
        var tool_calls = doc.get(item, "tool_calls")
        if (role != "user" and role != "assistant" and role != "system") or content < 0 or doc.nodes[content].kind != JSON_STRING:
            raise Error("Anthropic Messages slice requires string text messages")
        if role == "system":
            if tool_calls >= 0:
                raise Error("Anthropic Messages system messages cannot contain tool calls")
            system_parts.append(doc.nodes[content].text)
            continue
        if not doc.nodes[content].text and tool_calls < 0:
            continue
        if has_message and role != current_role:
            messages.append(_message(current_role, tool_results, content_parts))
            tool_results = List[String]()
            content_parts = List[String]()
        current_role = role
        has_message = True
        if doc.nodes[content].text or tool_calls < 0:
            content_parts.append('{"text":' + serialize_json(doc, content) + ',"type":"text"}')
        if tool_calls >= 0:
            if role != "assistant" or doc.nodes[tool_calls].kind != JSON_ARRAY:
                raise Error("Anthropic tool_calls must be an assistant array")
            for call in doc.nodes[tool_calls].children:
                _only_fields(doc, call, ["id", "type", "function"], "tool call")
                var call_id = doc.get(call, "id")
                var function = doc.get(call, "function")
                if call_id < 0 or doc.nodes[call_id].kind != JSON_STRING or not doc.nodes[call_id].text or function < 0 or doc.nodes[function].kind != JSON_OBJECT:
                    raise Error("Anthropic tool call requires an id and function")
                _only_fields(doc, function, ["name", "arguments"], "tool function")
                var name = doc.get(function, "name")
                var arguments = doc.get(function, "arguments")
                if name < 0 or doc.nodes[name].kind != JSON_STRING or not doc.nodes[name].text or arguments < 0 or doc.nodes[arguments].kind != JSON_STRING:
                    raise Error("Anthropic tool function requires a name and JSON arguments")
                var parsed_arguments_json: String
                try:
                    var parsed_arguments = JsonDocument(doc.nodes[arguments].text)
                    parsed_arguments_json = serialize_json(parsed_arguments, parsed_arguments.root)
                except:
                    raise Error("Anthropic tool function arguments must be valid JSON")
                content_parts.append('{"type":"tool_use","id":' + serialize_json(doc, call_id) + ',"name":' + serialize_json(doc, name) + ',"input":' + parsed_arguments_json + "}")
    if not has_message:
        raise Error("Anthropic Messages slice requires a user or assistant message")
    messages.append(_message(current_role, tool_results, content_parts))
    var system = String()
    if len(system_parts) > 0: system = quote_json("\n\n".join(system_parts))
    return (system, "[" + ",".join(messages) + "]")


def _message(role: String, tool_results: List[String], content_parts: List[String]) -> String:
    var content = List[String]()
    for block in tool_results: content.append(block)
    for block in content_parts: content.append(block)
    return '{"content":[' + ",".join(content) + '],"role":' + quote_json(role) + "}"


def _tools(doc: JsonDocument) raises -> String:
    var output = List[String]()
    var choice = doc.get(doc.root, "tool_choice")
    if choice >= 0 and doc.nodes[choice].kind == JSON_STRING and doc.nodes[choice].text == "none":
        return String()
    var tools = doc.get(doc.root, "tools")
    if tools >= 0:
        if doc.nodes[tools].kind != JSON_ARRAY:
            raise Error("Anthropic Messages tools must be an array")
        for tool in doc.nodes[tools].children:
            _only_fields(doc, tool, ["type", "function"], "function tool")
            if doc.string(doc.get(tool, "type")) != "function":
                raise Error("Anthropic Messages slice supports only function tools")
            var function = doc.get(tool, "function")
            _only_fields(doc, function, ["name", "description", "parameters", "strict"], "function tool")
            var name = doc.get(function, "name")
            if name < 0 or doc.nodes[name].kind != JSON_STRING or not doc.nodes[name].text:
                raise Error("Anthropic function tool requires a name")
            var parameters = doc.get(function, "parameters")
            if parameters >= 0 and doc.nodes[parameters].kind != JSON_OBJECT:
                raise Error("Anthropic function tool parameters must be an object")
            var item = '{"name":' + serialize_json(doc, name) + ',"input_schema":' + (serialize_json(doc, parameters) if parameters >= 0 else '{"type":"object","properties":{}}')
            var description = doc.get(function, "description")
            if description >= 0: item += ',"description":' + serialize_json(doc, description)
            output.append(item + "}")
    var web = doc.get(doc.root, "web_search_options")
    if web >= 0:
        if doc.nodes[web].kind != JSON_OBJECT:
            raise Error("Anthropic Messages web_search_options must be an object")
        _only_fields(doc, web, ["allowed_domains", "blocked_domains", "user_location", "max_uses", "search_context_size"], "web_search_options")
        var item = '{"name":"web_search","type":"web_search_20250305"'
        for key in [String("allowed_domains"), "blocked_domains", "user_location", "max_uses"]:
            var value = doc.get(web, key)
            if value >= 0: item += "," + quote_json(key) + ":" + serialize_json(doc, value)
        output.append(item + "}")
    if not output:
        raise Error("Anthropic Messages slice requires a tool")
    return "[" + ",".join(output) + "]" if output else String()


def _choice(doc: JsonDocument) raises -> String:
    var choice = doc.get(doc.root, "tool_choice")
    if choice < 0: return String()
    if doc.nodes[choice].kind == JSON_STRING:
        var kind = doc.nodes[choice].text
        if kind == "none": return String()
        if kind == "auto": return '{"type":"auto"}'
        if kind == "required": return '{"type":"any"}'
        raise Error("Anthropic Messages tool_choice is not supported")
    if doc.nodes[choice].kind != JSON_OBJECT or doc.string(doc.get(choice, "type")) != "function":
        raise Error("Anthropic Messages tool_choice is not supported")
    var function = doc.get(choice, "function")
    _only_fields(doc, choice, ["type", "function"], "tool_choice")
    _only_fields(doc, function, ["name"], "tool_choice function")
    var name = doc.get(function, "name")
    if name < 0 or doc.nodes[name].kind != JSON_STRING or not doc.nodes[name].text:
        raise Error("Anthropic named tool_choice requires a function name")
    return '{"type":"tool","name":' + serialize_json(doc, name) + "}"


def anthropic_buffered_response(source: String, created_at: UInt64, request_metadata: String = "null") raises -> String:
    var doc = JsonDocument(source)
    _validate_anthropic_buffered_response(doc)
    var id_node = doc.get(doc.root, "id")
    var id = doc.string(id_node) if id_node >= 0 and doc.nodes[id_node].kind == JSON_STRING else "resp_anthropic"
    var model_node = doc.get(doc.root, "model")
    var model = doc.string(model_node) if model_node >= 0 and doc.nodes[model_node].kind == JSON_STRING else "unknown"
    var output = List[String]()
    var text_runs = List[String]()
    var searches = List[AnthropicWebSearch]()
    var latest_search_by_id = Dict[String, Int]()
    var tool_calls = List[String]()
    var reasoning_items = List[String]()
    var content = doc.get(doc.root, "content")
    if content >= 0:
        for block in doc.nodes[content].children:
            var kind = doc.string(doc.get(block, "type"))
            if kind == "text":
                var value = doc.string(doc.get(block, "text"))
                text_runs.append('{"type":"output_text","text":' + quote_json(value) + "}")
                output.append("$text$" + String(len(text_runs) - 1))
            elif kind == "server_tool_use" and doc.string(doc.get(block, "name")) == "web_search":
                var search_id = doc.string(doc.get(block, "id"))
                if not search_id: search_id = "web_search_" + String(len(searches))
                var input = doc.get(block, "input")
                var input_json = serialize_json(doc, input) if input >= 0 else "{}"
                var search_position = len(searches)
                searches.append(AnthropicWebSearch(UInt64(len(output)), search_id, input_json, "[]", False))
                latest_search_by_id[search_id] = search_position
                output.append("$search$" + String(search_position))
            elif kind == "tool_use":
                var id = doc.string(doc.get(block, "id"))
                var name = doc.string(doc.get(block, "name"))
                var input = doc.get(block, "input")
                var arguments = "{}" if input < 0 else serialize_json(doc, input)
                tool_calls.append(tool_output_item(id, name, arguments, Optional[String]()))
                output.append("$tool$" + String(len(tool_calls) - 1))
            elif kind == "thinking":
                var thinking = doc.get(block, "thinking")
                if thinking >= 0 and doc.nodes[thinking].kind == JSON_STRING:
                    reasoning_items.append('{"type":"reasoning","summary":[{"type":"summary_text","text":' + serialize_json(doc, thinking) + "}]}")
                    output.append("$reasoning$" + String(len(reasoning_items) - 1))
                else:
                    output.append("$break$")
            elif kind == "web_search_tool_result":
                var search_id = doc.string(doc.get(block, "tool_use_id"))
                var search_position = latest_search_by_id.get(search_id)
                if search_position:
                    searches[search_position.value()].sources = _search_sources(doc, block)
                output.append("$break$")
    var items = List[String]()
    var output_index = 0
    while output_index < len(output):
        var value = output[output_index]
        if value.startswith("$text$"):
            var parts = List[String]()
            while output_index < len(output) and output[output_index].startswith("$text$"):
                var text_index = unsigned_value(String(output[output_index][byte=6:]))
                parts.append(text_runs[text_index])
                output_index += 1
            items.append('{"type":"message","role":"assistant","content":[' + ",".join(parts) + "]}")
        elif value.startswith("$search$"):
            var search = searches[unsigned_value(String(value[byte=8:]) )].copy()
            items.append(_web_search_item(search, False))
            output_index += 1
        elif value.startswith("$tool$"):
            items.append(tool_calls[unsigned_value(String(value[byte=6:]))])
            output_index += 1
        elif value.startswith("$reasoning$"):
            items.append(reasoning_items[unsigned_value(String(value[byte=11:]))])
            output_index += 1
        elif value == "$break$":
            output_index += 1
        else:
            raise Error("Anthropic buffered response output plan is invalid")
    var result = '{"id":' + quote_json(id) + ',"object":"response","created_at":' + String(created_at) + ',"model":' + quote_json(model) + ',"output":[' + ",".join(items) + ']'
    var usage = doc.get(doc.root, "usage")
    if usage >= 0 and doc.nodes[usage].kind == JSON_OBJECT:
        var input_tokens = json_unsigned(doc, doc.get(usage, "input_tokens"))
        var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
        var input_count = input_tokens.value() if input_tokens else UInt64(0)
        var output_count = output_tokens.value() if output_tokens else UInt64(0)
        var total_count = UInt64.MAX if output_count > UInt64.MAX - input_count else input_count + output_count
        result += ',"usage":{"input_tokens":' + String(input_count) + ',"output_tokens":' + String(output_count) + ',"total_tokens":' + String(total_count) + "}"
        var server_tool_use = doc.get(usage, "server_tool_use")
        if server_tool_use >= 0 and doc.nodes[server_tool_use].kind == JSON_OBJECT:
            var web_search_requests = json_unsigned(doc, doc.get(server_tool_use, "web_search_requests"))
            if web_search_requests:
                result += ',"tool_usage":{"web_search":{"num_requests":' + String(web_search_requests.value()) + "}}"
    var stop_reason = doc.get(doc.root, "stop_reason")
    var provider_metadata = "{}"
    if stop_reason >= 0:
        provider_metadata = '{"anthropic":{"stop_reason":' + serialize_json(doc, stop_reason) + "}}"
    var metadata = merge_chat_metadata(provider_metadata, request_metadata)
    if metadata != "null" and metadata != "{}": result += ',"metadata":' + metadata
    return result + "}"


def anthropic_buffered_assistant_messages(source: String) raises -> String:
    var doc = JsonDocument(source)
    _validate_anthropic_buffered_response(doc)
    var text = String()
    var calls = List[String]()
    var content = doc.get(doc.root, "content")
    if content >= 0:
        for block in doc.nodes[content].children:
            var kind = doc.string(doc.get(block, "type"))
            if kind == "text":
                text += doc.string(doc.get(block, "text"))
            elif kind == "tool_use":
                var input = doc.get(block, "input")
                var arguments = "{}" if input < 0 else serialize_json(doc, input)
                calls.append('{"id":' + quote_json(doc.string(doc.get(block, "id"))) + ',"type":"function","function":{"name":' + quote_json(doc.string(doc.get(block, "name"))) + ',"arguments":' + quote_json(arguments) + "}}")
    var message = '{"role":"assistant","content":' + quote_json(text)
    if calls: message += ',"tool_calls":[' + ",".join(calls) + "]"
    return deepseek_buffered_assistant_messages('{"choices":[{"message":' + message + "}}]}")


def _search_sources(doc: JsonDocument, block: Int) raises -> String:
    var content = doc.get(block, "content")
    var output = List[String]()
    if content < 0 or doc.nodes[content].kind != JSON_ARRAY:
        return "[]"
    for item in doc.nodes[content].children:
        var url = doc.get(item, "url")
        if url < 0 or doc.nodes[url].kind != JSON_STRING:
            continue
        var value = '{"type":"url","url":' + serialize_json(doc, url)
        var title = doc.get(item, "title")
        if title >= 0 and doc.nodes[title].kind == JSON_STRING:
            value += ',"title":' + serialize_json(doc, title)
        output.append(value + "}")
    return "[" + ",".join(output) + "]"


def _search_queries(input_json: String, preserve_non_string_values: Bool) raises -> String:
    if not input_json:
        return "[]"
    var input = JsonDocument(input_json)
    if input.nodes[input.root].kind != JSON_OBJECT:
        return "[]"
    var query = input.get(input.root, "query")
    if query >= 0 and input.nodes[query].kind == JSON_STRING:
        return "[" + serialize_json(input, query) + "]"
    var values = input.get(input.root, "queries")
    if values < 0 or input.nodes[values].kind != JSON_ARRAY:
        return "[]"
    var output = List[String]()
    for value in input.nodes[values].children:
        if preserve_non_string_values or input.nodes[value].kind == JSON_STRING:
            output.append(serialize_json(input, value))
    return "[" + ",".join(output) + "]"


def _web_search_item(search: AnthropicWebSearch, in_progress: Bool) raises -> String:
    var queries = _search_queries(search.input_json, False)
    return '{"type":"web_search_call","id":' + quote_json(search.id) + ',"status":' + quote_json("in_progress" if in_progress else "completed") + ',"action":{"type":"search","queries":' + queries + ',"sources":' + search.sources + "}}"


def _validate_anthropic_buffered_response(doc: JsonDocument) raises:
    if doc.nodes[doc.root].kind != JSON_OBJECT:
        raise Error("Anthropic Messages response must be an object")
    var content = doc.get(doc.root, "content")
    if content < 0 or doc.nodes[content].kind != JSON_ARRAY:
        raise Error("Anthropic Messages content must be an array")
    if len(doc.nodes[content].children) > ANTHROPIC_BUFFERED_MAX_CONTENT_BLOCKS:
        raise Error("Anthropic Messages content has too many blocks")
    # Both pinned releases project text blocks from text and ignore other fields.
    var has_tool_use = False
    for block in doc.nodes[content].children:
        if doc.string(doc.get(block, "type")) == "tool_use":
            has_tool_use = True
            break
    if has_tool_use:
        if len(doc.nodes[content].children) == 0:
            raise Error("Anthropic Messages tool-use content is missing")
        var tool_count = 0
        for block in doc.nodes[content].children:
            var kind = doc.string(doc.get(block, "type"))
            if kind == "text":
                var text = doc.get(block, "text")
                if text < 0 or doc.nodes[text].kind != JSON_STRING:
                    raise Error("Anthropic Messages text block is invalid")
            elif kind == "tool_use":
                var id = doc.get(block, "id")
                var name = doc.get(block, "name")
                if id < 0 or doc.nodes[id].kind != JSON_STRING or not doc.nodes[id].text:
                    raise Error("Anthropic tool_use block requires an id")
                if name < 0 or doc.nodes[name].kind != JSON_STRING or not doc.nodes[name].text:
                    raise Error("Anthropic tool_use block requires a name")
                tool_count += 1
            elif kind == "server_tool_use":
                var id = doc.get(block, "id")
                var name = doc.get(block, "name")
                if doc.string(doc.get(block, "type")) != "server_tool_use" or doc.string(name) != "web_search" or id < 0 or doc.nodes[id].kind != JSON_STRING or not doc.nodes[id].text:
                    raise Error("Anthropic web-search tool use is invalid")
            elif kind == "web_search_tool_result":
                var id = doc.get(block, "tool_use_id")
                if id < 0 or doc.nodes[id].kind != JSON_STRING or not doc.nodes[id].text:
                    raise Error("Anthropic web-search result requires a tool_use_id")
                _ = _search_sources(doc, block)
            elif kind == "thinking":
                pass
            else:
                raise Error("Anthropic Messages tool-use content has an unsupported block")
        if tool_count == 0:
            raise Error("Anthropic Messages tool-use content requires a tool_use block")
        return
    var text_and_orphan_results = True
    for block in doc.nodes[content].children:
        var kind = doc.string(doc.get(block, "type"))
        if kind == "thinking":
            continue
        if kind == "web_search_tool_result":
            var result_id = doc.get(block, "tool_use_id")
            if result_id < 0 or doc.nodes[result_id].kind != JSON_STRING or not doc.nodes[result_id].text:
                raise Error("Anthropic web-search result requires a tool_use_id")
            _ = _search_sources(doc, block)
            continue
        if kind != "text":
            text_and_orphan_results = False
            continue
        var text = doc.get(block, "text")
        if text < 0 or doc.nodes[text].kind != JSON_STRING:
            raise Error("Anthropic Messages text block is invalid")
    if text_and_orphan_results:
        return
    var search_index = Int(-1)
    var result_index = Int(-1)
    var text_index = Int(-1)
    var shape_index = 0
    for block in doc.nodes[content].children:
        if doc.string(doc.get(block, "type")) == "thinking":
            continue
        if shape_index == 0:
            search_index = block
        elif shape_index == 1:
            result_index = block
        elif shape_index == 2:
            text_index = block
        else:
            raise Error("Anthropic Messages content is outside the supported web-search shape")
        shape_index += 1
    if shape_index != 3:
        raise Error("Anthropic Messages content is outside the supported web-search shape")
    var search = search_index
    if doc.string(doc.get(search, "type")) != "server_tool_use" or doc.string(doc.get(search, "name")) != "web_search":
        raise Error("Anthropic Messages content starts with an unsupported block")
    var search_id = doc.get(search, "id")
    if search_id < 0 or doc.nodes[search_id].kind != JSON_STRING or not doc.nodes[search_id].text:
        raise Error("Anthropic web-search tool use requires an id")
    var result = result_index
    if doc.string(doc.get(result, "type")) != "web_search_tool_result" or doc.string(doc.get(result, "tool_use_id")) != doc.nodes[search_id].text:
        raise Error("Anthropic web-search result does not match its tool use")
    _ = _search_sources(doc, result)
    var text = text_index
    var text_value = doc.get(text, "text")
    if doc.string(doc.get(text, "type")) != "text" or text_value < 0 or doc.nodes[text_value].kind != JSON_STRING:
        raise Error("Anthropic Messages text block is invalid")


def _only_fields(doc: JsonDocument, node: Int, allowed: List[String], context: String) raises:
    if node < 0 or doc.nodes[node].kind != JSON_OBJECT:
        raise Error("Anthropic " + context + " must be an object")
    for index in range(len(doc.nodes[node].names)):
        var name = doc.nodes[node].names[index]
        if name not in allowed:
            if context == "translated request":
                raise Error("Anthropic Messages does not translate chat field `" + name + "`")
            raise Error("Anthropic " + context + " field " + name + " is not supported")


@fieldwise_init
struct AnthropicWebSearch(Copyable):
    var output_index: UInt64
    var id: String
    var input_json: String
    var sources: String
    var done: Bool
