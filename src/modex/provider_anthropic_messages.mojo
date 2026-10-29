"""DeepSeek chat requests and Anthropic Messages function and search tools."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .provider_chat_items import tool_output_item
from .provider_chat_buffered import deepseek_buffered_assistant_messages
from .provider_chat_metadata import merge_chat_metadata
from .provider_chat_usage import json_unsigned
from .text import trim_text, unsigned_value

comptime ANTHROPIC_BUFFERED_MAX_CONTENT_BLOCKS = 65_536


def validate_deepseek_anthropic_request(source: String) raises:
    var doc = JsonDocument(source)
    _only_fields(doc, doc.root, ["model", "input", "stream", "tools", "tool_choice"], "request")
    var model = doc.get(doc.root, "model")
    if model >= 0 and doc.nodes[model].kind != JSON_STRING:
        raise Error("Anthropic Messages slice requires a string model")
    var input = doc.get(doc.root, "input")
    if input < 0:
        raise Error("Anthropic Messages slice requires input")
    if doc.nodes[input].kind == JSON_STRING:
        pass
    elif doc.nodes[input].kind == JSON_ARRAY and len(doc.nodes[input].children) > 0:
        var has_conversation_message = False
        for item in doc.nodes[input].children:
            var type = doc.string(doc.get(item, "type"))
            if type == "function_call_output":
                _only_fields(doc, item, ["type", "call_id", "output"], "function call output")
                var call_id = doc.get(item, "call_id")
                var output = doc.get(item, "output")
                if call_id < 0 or doc.nodes[call_id].kind != JSON_STRING or not doc.nodes[call_id].text or output < 0:
                    raise Error("Anthropic function call output requires a call_id and output")
                continue
            _only_fields(doc, item, ["type", "role", "content"], "input message")
            var type_node = doc.get(item, "type")
            if type_node >= 0 and (doc.nodes[type_node].kind != JSON_STRING or doc.nodes[type_node].text != "message"):
                raise Error("Anthropic Messages slice supports only message input items")
            var role = doc.get(item, "role")
            if role >= 0 and (doc.nodes[role].kind != JSON_STRING or (doc.nodes[role].text != "user" and doc.nodes[role].text != "assistant" and doc.nodes[role].text != "system" and doc.nodes[role].text != "developer")):
                raise Error("Anthropic Messages slice supports only user, assistant, system, and developer message roles")
            var content = doc.get(item, "content")
            if content < 0 or doc.nodes[content].kind != JSON_STRING or not trim_text(doc.nodes[content].text):
                raise Error("Anthropic Messages slice supports only non-whitespace string message content")
            if role < 0 or (doc.nodes[role].text != "system" and doc.nodes[role].text != "developer"):
                has_conversation_message = True
        if not has_conversation_message:
            raise Error("Anthropic Messages slice requires a user or assistant message")
    else:
        raise Error("Anthropic Messages slice supports only string input or simple message arrays")
    var stream = doc.get(doc.root, "stream")
    if stream >= 0 and doc.nodes[stream].kind != JSON_BOOL:
        raise Error("Anthropic Messages stream must be a boolean")
    var tools = doc.get(doc.root, "tools")
    if tools < 0 or doc.nodes[tools].kind != JSON_ARRAY:
        raise Error("Anthropic Messages slice requires a web_search_preview tool")
    var web_count = 0
    for tool in doc.nodes[tools].children:
        if doc.nodes[tool].kind != JSON_OBJECT:
            raise Error("Anthropic Messages tool must be an object")
        var kind = doc.string(doc.get(tool, "type"))
        if kind == "function":
            # The shared Responses tool mapper validates names, schemas, and strict mode.
            continue
        if kind != "web_search_preview":
            raise Error("Anthropic Messages slice supports function and web_search_preview tools")
        _only_fields(doc, tool, ["type", "allowed_domains"], "web search tool")
        web_count += 1
        var domains = doc.get(tool, "allowed_domains")
        if domains >= 0:
            if doc.nodes[domains].kind != JSON_ARRAY:
                raise Error("Anthropic web_search allowed_domains must be an array")
            for domain in doc.nodes[domains].children:
                if doc.nodes[domain].kind != JSON_STRING or not doc.nodes[domain].text:
                    raise Error("Anthropic web_search allowed_domains entries must be non-empty strings")
    if web_count != 1:
        raise Error("Anthropic Messages slice requires exactly one web_search_preview tool")


def deepseek_anthropic_messages_body(source: String) raises -> String:
    var prepared = JsonDocument(source)
    var body = JsonDocument(serialize_json(prepared, prepared.get(prepared.root, "body")))
    _only_fields(body, body.root, ["max_tokens", "messages", "model", "stream", "stream_options", "tool_choice", "tools", "web_search_options"], "translated request")
    var max_tokens = body.get(body.root, "max_tokens")
    if max_tokens >= 0 and (body.nodes[max_tokens].kind != JSON_NUMBER or body.nodes[max_tokens].text != "4096"):
        raise Error("Anthropic Messages slice supports the default max_tokens value only")
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
            if call_id < 0 or doc.nodes[call_id].kind != JSON_STRING or not doc.nodes[call_id].text:
                raise Error("Anthropic tool result requires a tool_call_id")
            if content < 0 or doc.nodes[content].kind != JSON_STRING:
                raise Error("Anthropic tool result content must be a string")
            role = "user"
            if has_message and role != current_role:
                messages.append('{"content":[' + ",".join(content_parts) + '],"role":' + quote_json(current_role) + "}")
                content_parts = List[String]()
            current_role = role
            has_message = True
            content_parts.append('{"type":"tool_result","tool_use_id":' + serialize_json(doc, call_id) + ',"content":' + serialize_json(doc, content) + "}")
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
        if has_message and role != current_role:
            messages.append('{"content":[' + ",".join(content_parts) + '],"role":' + quote_json(current_role) + "}")
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
                var parsed_arguments = JsonDocument(doc.nodes[arguments].text)
                content_parts.append('{"type":"tool_use","id":' + serialize_json(doc, call_id) + ',"name":' + serialize_json(doc, name) + ',"input":' + serialize_json(parsed_arguments, parsed_arguments.root) + "}")
    if not has_message:
        raise Error("Anthropic Messages slice requires a user or assistant message")
    messages.append('{"content":[' + ",".join(content_parts) + '],"role":' + quote_json(current_role) + "}")
    var system = String()
    if len(system_parts) > 0: system = quote_json("\n\n".join(system_parts))
    return (system, "[" + ",".join(messages) + "]")


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
        _only_fields(doc, web, ["allowed_domains"], "web_search_options")
        var item = '{"name":"web_search","type":"web_search_20250305"'
        var domains = doc.get(web, "allowed_domains")
        if domains >= 0: item += ',"allowed_domains":' + serialize_json(doc, domains)
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
    var id = doc.string(doc.get(doc.root, "id"))
    var model = doc.string(doc.get(doc.root, "model"))
    var output = List[String]()
    var text_runs = List[String]()
    var searches = List[AnthropicWebSearch]()
    var tool_calls = List[String]()
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
                searches.append(AnthropicWebSearch(UInt64(len(output)), search_id, input_json, "[]", False))
                output.append("$search$" + String(len(searches) - 1))
            elif kind == "tool_use":
                var id = doc.string(doc.get(block, "id"))
                var name = doc.string(doc.get(block, "name"))
                var input = doc.get(block, "input")
                var arguments = "{}" if input < 0 else serialize_json(doc, input)
                tool_calls.append(tool_output_item(id, name, arguments, Optional[String]()))
                output.append("$tool$" + String(len(tool_calls) - 1))
            elif kind == "web_search_tool_result":
                var search_id = doc.string(doc.get(block, "tool_use_id"))
                var index = 0
                var found = False
                while index < len(searches):
                    if searches[index].id == search_id and not searches[index].done:
                        searches[index].sources = _search_sources(doc, block)
                        searches[index].done = True
                        found = True
                        break
                    index += 1
                if not found: raise Error("Anthropic web-search result does not match a tool use")
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
        elif value == "$break$":
            output_index += 1
        else:
            raise Error("Anthropic buffered response output plan is invalid")
    var result = '{"id":' + quote_json(id) + ',"object":"response","created_at":' + String(created_at) + ',"model":' + quote_json(model) + ',"output":[' + ",".join(items) + ']'
    var usage = doc.get(doc.root, "usage")
    if usage >= 0:
        var input_tokens = json_unsigned(doc, doc.get(usage, "input_tokens"))
        var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
        var input_count = input_tokens.value() if input_tokens else UInt64(0)
        var output_count = output_tokens.value() if output_tokens else UInt64(0)
        var total_count = UInt64.MAX if output_count > UInt64.MAX - input_count else input_count + output_count
        result += ',"usage":{"input_tokens":' + String(input_count) + ',"output_tokens":' + String(output_count) + ',"total_tokens":' + String(total_count) + "}"
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
    if content < 0 or doc.nodes[content].kind != JSON_ARRAY:
        raise Error("Anthropic web-search result content must be an array")
    var output = List[String]()
    for item in doc.nodes[content].children:
        if doc.nodes[item].kind != JSON_OBJECT:
            raise Error("Anthropic web-search results must be objects")
        _only_fields(doc, item, ["type", "url", "title"], "web-search result")
        if doc.string(doc.get(item, "type")) != "web_search_result":
            raise Error("Anthropic web-search result type is not supported")
        var url = doc.get(item, "url")
        if url < 0 or doc.nodes[url].kind != JSON_STRING:
            raise Error("Anthropic web-search result requires a URL")
        var value = '{"type":"url","url":' + serialize_json(doc, url)
        var title = doc.get(item, "title")
        if title >= 0:
            if doc.nodes[title].kind != JSON_STRING: raise Error("Anthropic web-search result title must be a string")
            value += ',"title":' + serialize_json(doc, title)
        output.append(value + "}")
    return "[" + ",".join(output) + "]"


def _web_search_item(search: AnthropicWebSearch, in_progress: Bool) raises -> String:
    var queries: String
    if in_progress and (not search.input_json or search.input_json == "{}"):
        queries = "[]"
    else:
        var input = JsonDocument(search.input_json)
        _only_fields(input, input.root, ["query"], "web-search input")
        var query = input.get(input.root, "query")
        if query < 0 or input.nodes[query].kind != JSON_STRING or not input.nodes[query].text:
            raise Error("Anthropic web-search input requires a non-empty query")
        queries = "[" + serialize_json(input, query) + "]"
    return '{"type":"web_search_call","id":' + quote_json(search.id) + ',"status":' + quote_json("in_progress" if in_progress else "completed") + ',"action":{"type":"search","queries":' + queries + ',"sources":' + search.sources + "}}"


def _validate_anthropic_buffered_response(doc: JsonDocument) raises:
    if doc.nodes[doc.root].kind != JSON_OBJECT:
        raise Error("Anthropic Messages response must be an object")
    _only_fields(doc, doc.root, ["id", "type", "role", "model", "content", "stop_reason", "usage"], "response")
    if doc.string(doc.get(doc.root, "type")) != "message" or doc.string(doc.get(doc.root, "role")) != "assistant":
        raise Error("Anthropic Messages response must be an assistant message")
    var id = doc.get(doc.root, "id")
    var model = doc.get(doc.root, "model")
    if id < 0 or doc.nodes[id].kind != JSON_STRING or model < 0 or doc.nodes[model].kind != JSON_STRING:
        raise Error("Anthropic Messages response requires string id and model")
    var usage = doc.get(doc.root, "usage")
    if usage < 0 or doc.nodes[usage].kind != JSON_OBJECT:
        raise Error("Anthropic Messages response usage is missing")
    _only_fields(doc, usage, ["input_tokens", "output_tokens"], "usage")
    var input_tokens = json_unsigned(doc, doc.get(usage, "input_tokens"))
    var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
    if not input_tokens or not output_tokens:
        raise Error("Anthropic Messages token usage is invalid")
    var content = doc.get(doc.root, "content")
    if content < 0 or doc.nodes[content].kind != JSON_ARRAY:
        raise Error("Anthropic Messages content must be an array")
    if len(doc.nodes[content].children) > ANTHROPIC_BUFFERED_MAX_CONTENT_BLOCKS:
        raise Error("Anthropic Messages content has too many blocks")
    var has_tool_use = False
    for block in doc.nodes[content].children:
        if doc.string(doc.get(block, "type")) == "tool_use":
            has_tool_use = True
            break
    if has_tool_use:
        if len(doc.nodes[content].children) == 0:
            raise Error("Anthropic Messages tool-use content is missing")
        var tool_count = 0
        var search_ids = List[String]()
        var result_ids = List[String]()
        for block in doc.nodes[content].children:
            var kind = doc.string(doc.get(block, "type"))
            if kind == "text":
                _only_fields(doc, block, ["type", "text"], "text block")
                var text = doc.get(block, "text")
                if text < 0 or doc.nodes[text].kind != JSON_STRING:
                    raise Error("Anthropic Messages text block is invalid")
            elif kind == "tool_use":
                _only_fields(doc, block, ["type", "id", "name", "input"], "tool-use block")
                var id = doc.get(block, "id")
                var name = doc.get(block, "name")
                if id < 0 or doc.nodes[id].kind != JSON_STRING or not doc.nodes[id].text:
                    raise Error("Anthropic tool_use block requires an id")
                if name < 0 or doc.nodes[name].kind != JSON_STRING or not doc.nodes[name].text:
                    raise Error("Anthropic tool_use block requires a name")
                tool_count += 1
            elif kind == "server_tool_use":
                _only_fields(doc, block, ["type", "id", "name", "input"], "web-search tool use")
                var id = doc.get(block, "id")
                var name = doc.get(block, "name")
                var input = doc.get(block, "input")
                if doc.string(doc.get(block, "type")) != "server_tool_use" or doc.string(name) != "web_search" or id < 0 or doc.nodes[id].kind != JSON_STRING or not doc.nodes[id].text or input < 0 or doc.nodes[input].kind != JSON_OBJECT:
                    raise Error("Anthropic web-search tool use is invalid")
                _only_fields(doc, input, ["query"], "web-search input")
                var query = doc.get(input, "query")
                if query < 0 or doc.nodes[query].kind != JSON_STRING or not doc.nodes[query].text:
                    raise Error("Anthropic web-search input requires a non-empty query")
                # shortcut: two mixed search pairs, expand after broader multi-search replies are qualified.
                if len(search_ids) >= 2: raise Error("Mixed Anthropic replies support at most two web-search tool uses")
                search_ids.append(doc.nodes[id].text)
            elif kind == "web_search_tool_result":
                _only_fields(doc, block, ["type", "tool_use_id", "content"], "web-search result block")
                var id = doc.get(block, "tool_use_id")
                var available = False
                if id >= 0 and doc.nodes[id].kind == JSON_STRING:
                    var search_count = 0
                    var result_count = 0
                    for prior in search_ids:
                        if prior == doc.nodes[id].text: search_count += 1
                    for prior in result_ids:
                        if prior == doc.nodes[id].text: result_count += 1
                    available = result_count < search_count
                if not available:
                    raise Error("Anthropic web-search result does not match a preceding tool use")
                var result_content = doc.get(block, "content")
                if result_content < 0 or doc.nodes[result_content].kind != JSON_ARRAY or len(doc.nodes[result_content].children) == 0:
                    raise Error("Anthropic web-search result must contain at least one source")
                _ = _search_sources(doc, block)
                result_ids.append(doc.nodes[id].text)
            else:
                raise Error("Anthropic Messages tool-use content has an unsupported block")
        if tool_count == 0:
            raise Error("Anthropic Messages tool-use content requires a tool_use block")
        if len(search_ids) != len(result_ids):
            raise Error("Anthropic web-search tool uses and results must be paired")
        return
    if doc.string(doc.get(doc.root, "stop_reason")) != "end_turn":
        raise Error("Anthropic Messages stop reason is not supported")
    if len(doc.nodes[content].children) != 3:
        raise Error("Anthropic Messages content is outside the supported web-search shape")
    var search = doc.nodes[content].children[0]
    _only_fields(doc, search, ["type", "id", "name", "input"], "web-search tool use")
    if doc.string(doc.get(search, "type")) != "server_tool_use" or doc.string(doc.get(search, "name")) != "web_search":
        raise Error("Anthropic Messages content starts with an unsupported block")
    var search_id = doc.get(search, "id")
    if search_id < 0 or doc.nodes[search_id].kind != JSON_STRING or not doc.nodes[search_id].text:
        raise Error("Anthropic web-search tool use requires an id")
    var input = doc.get(search, "input")
    if input < 0 or doc.nodes[input].kind != JSON_OBJECT:
        raise Error("Anthropic web-search tool input must be an object")
    _only_fields(doc, input, ["query"], "web-search input")
    var query = doc.get(input, "query")
    if query < 0 or doc.nodes[query].kind != JSON_STRING or not doc.nodes[query].text:
        raise Error("Anthropic web-search input requires a non-empty query")
    var result = doc.nodes[content].children[1]
    _only_fields(doc, result, ["type", "tool_use_id", "content"], "web-search result block")
    if doc.string(doc.get(result, "type")) != "web_search_tool_result" or doc.string(doc.get(result, "tool_use_id")) != doc.nodes[search_id].text:
        raise Error("Anthropic web-search result does not match its tool use")
    var result_content = doc.get(result, "content")
    if result_content < 0 or doc.nodes[result_content].kind != JSON_ARRAY or len(doc.nodes[result_content].children) == 0:
        raise Error("Anthropic web-search result must contain at least one source")
    _ = _search_sources(doc, result)
    var text = doc.nodes[content].children[2]
    _only_fields(doc, text, ["type", "text"], "text block")
    var text_value = doc.get(text, "text")
    if doc.string(doc.get(text, "type")) != "text" or text_value < 0 or doc.nodes[text_value].kind != JSON_STRING:
        raise Error("Anthropic Messages text block is invalid")


def _only_fields(doc: JsonDocument, node: Int, allowed: List[String], context: String) raises:
    if node < 0 or doc.nodes[node].kind != JSON_OBJECT:
        raise Error("Anthropic " + context + " must be an object")
    for index in range(len(doc.nodes[node].names)):
        var name = doc.nodes[node].names[index]
        if name not in allowed:
            raise Error("Anthropic " + context + " field " + name + " is not supported")


@fieldwise_init
struct AnthropicWebSearch(Copyable):
    var output_index: UInt64
    var id: String
    var input_json: String
    var sources: String
    var done: Bool
