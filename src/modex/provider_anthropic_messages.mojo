"""DeepSeek chat requests and Anthropic Messages responses for web search."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .provider_chat_buffered import deepseek_buffered_assistant_messages
from .provider_chat_metadata import merge_chat_metadata
from .provider_chat_usage import json_unsigned
from .text import unsigned_value


def validate_deepseek_anthropic_request(source: String) raises:
    var doc = JsonDocument(source)
    _only_fields(doc, doc.root, ["model", "input", "stream", "tools"], "request")
    var model = doc.get(doc.root, "model")
    if model >= 0 and doc.nodes[model].kind != JSON_STRING:
        raise Error("Anthropic Messages slice requires a string model")
    var input = doc.get(doc.root, "input")
    if input < 0 or doc.nodes[input].kind != JSON_STRING:
        raise Error("Anthropic Messages slice supports only string input")
    var stream = doc.get(doc.root, "stream")
    if stream >= 0 and doc.nodes[stream].kind != JSON_BOOL:
        raise Error("Anthropic Messages stream must be a boolean")
    var tools = doc.get(doc.root, "tools")
    if tools < 0 or doc.nodes[tools].kind != JSON_ARRAY or len(doc.nodes[tools].children) != 1:
        raise Error("Anthropic Messages slice requires exactly one web_search_preview tool")
    var tool = doc.nodes[tools].children[0]
    _only_fields(doc, tool, ["type", "allowed_domains"], "web search tool")
    if doc.nodes[tool].kind != JSON_OBJECT or doc.string(doc.get(tool, "type")) != "web_search_preview":
        raise Error("Anthropic Messages slice supports only web_search_preview")
    var domains = doc.get(tool, "allowed_domains")
    if domains >= 0:
        if doc.nodes[domains].kind != JSON_ARRAY:
            raise Error("Anthropic web_search allowed_domains must be an array")
        for domain in doc.nodes[domains].children:
            if doc.nodes[domain].kind != JSON_STRING or not doc.nodes[domain].text:
                raise Error("Anthropic web_search allowed_domains entries must be non-empty strings")


def deepseek_anthropic_messages_body(source: String) raises -> String:
    var prepared = JsonDocument(source)
    var body = JsonDocument(serialize_json(prepared, prepared.get(prepared.root, "body")))
    _only_fields(body, body.root, ["max_tokens", "messages", "model", "stream", "stream_options", "web_search_options"], "translated request")
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
    var messages = _messages(body)
    fields.append('"messages":' + messages)
    fields.append('"model":' + _field(body, "model", '"auto"'))
    fields.append('"stream":' + _field(body, "stream", "false"))
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


def _messages(doc: JsonDocument) raises -> String:
    var source = doc.get(doc.root, "messages")
    if source < 0 or doc.nodes[source].kind != JSON_ARRAY:
        raise Error("Anthropic Messages requires a messages array")
    if len(doc.nodes[source].children) != 1:
        raise Error("Anthropic Messages slice supports one simple user message")
    var messages = List[String]()
    for item in doc.nodes[source].children:
        if doc.nodes[item].kind != JSON_OBJECT:
            raise Error("Anthropic Messages entries must be objects")
        _only_fields(doc, item, ["role", "content"], "message")
        var role = doc.string(doc.get(item, "role"))
        var content = doc.get(item, "content")
        if role != "user" or content < 0 or doc.nodes[content].kind != JSON_STRING:
            raise Error("Anthropic Messages slice supports one simple user text message")
        messages.append('{"content":[{"text":' + serialize_json(doc, content) + ',"type":"text"}],"role":"user"}')
    return "[" + ",".join(messages) + "]"


def _tools(doc: JsonDocument) raises -> String:
    var output = List[String]()
    var tools = doc.get(doc.root, "tools")
    if tools >= 0:
        if doc.nodes[tools].kind != JSON_ARRAY:
            raise Error("Anthropic Messages tools must be an array")
        if len(doc.nodes[tools].children) != 0:
            raise Error("Anthropic Messages slice does not translate function tools")
    var web = doc.get(doc.root, "web_search_options")
    if web >= 0:
        if doc.nodes[web].kind != JSON_OBJECT:
            raise Error("Anthropic Messages web_search_options must be an object")
        _only_fields(doc, web, ["allowed_domains"], "web_search_options")
        var item = '{"name":"web_search","type":"web_search_20250305"'
        var domains = doc.get(web, "allowed_domains")
        if domains >= 0: item += ',"allowed_domains":' + serialize_json(doc, domains)
        output.append(item + "}")
    if len(output) != 1:
        raise Error("Anthropic Messages slice requires one web-search tool")
    return "[" + ",".join(output) + "]" if output else String()


def _choice(doc: JsonDocument) raises -> String:
    var choice = doc.get(doc.root, "tool_choice")
    if choice >= 0: raise Error("Anthropic Messages slice does not translate tool_choice")
    return String()


def anthropic_buffered_response(source: String, created_at: UInt64, request_metadata: String = "null") raises -> String:
    var doc = JsonDocument(source)
    _validate_anthropic_buffered_response(doc)
    var id = doc.string(doc.get(doc.root, "id"))
    var model = doc.string(doc.get(doc.root, "model"))
    var output = List[String]()
    var text = String()
    var text_marker_added = False
    var searches = List[AnthropicWebSearch]()
    var content = doc.get(doc.root, "content")
    if content >= 0:
        for block in doc.nodes[content].children:
            var kind = doc.string(doc.get(block, "type"))
            if kind == "text":
                var value = doc.string(doc.get(block, "text"))
                text += value
                if not text_marker_added:
                    output.append("$text$")
                    text_marker_added = True
            elif kind == "server_tool_use" and doc.string(doc.get(block, "name")) == "web_search":
                var search_id = doc.string(doc.get(block, "id"))
                if not search_id: search_id = "web_search_" + String(len(searches))
                var input = doc.get(block, "input")
                var input_json = serialize_json(doc, input) if input >= 0 else "{}"
                searches.append(AnthropicWebSearch(UInt64(len(output)), search_id, input_json, "[]", False))
                output.append("$search$" + String(len(searches) - 1))
            elif kind == "web_search_tool_result":
                var search_id = doc.string(doc.get(block, "tool_use_id"))
                var index = 0
                var found = False
                while index < len(searches):
                    if searches[index].id == search_id:
                        searches[index].sources = _search_sources(doc, block)
                        found = True
                    index += 1
                if not found: raise Error("Anthropic web-search result does not match a tool use")
    var items = List[String]()
    for value in output:
        if value == "$text$":
            items.append('{"type":"message","role":"assistant","content":[{"type":"output_text","text":' + quote_json(text) + "}]}")
        elif value.startswith("$search$"):
            var search = searches[unsigned_value(String(value[byte=8:]) )].copy()
            items.append(_web_search_item(search, False))
    var result = '{"id":' + quote_json(id) + ',"object":"response","created_at":' + String(created_at) + ',"model":' + quote_json(model) + ',"output":[' + ",".join(items) + ']'
    var usage = doc.get(doc.root, "usage")
    if usage >= 0:
        var input_tokens = json_unsigned(doc, doc.get(usage, "input_tokens"))
        var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
        var input_count = input_tokens.value() if input_tokens else UInt64(0)
        var output_count = output_tokens.value() if output_tokens else UInt64(0)
        var total_count = UInt64.MAX if output_count > UInt64.MAX - input_count else input_count + output_count
        result += ',"usage":{"input_tokens":' + String(input_count) + ',"output_tokens":' + String(output_count) + ',"total_tokens":' + String(total_count) + "}"
    var provider_metadata = '{"anthropic":{"stop_reason":"end_turn"}}'
    result += ',"metadata":' + merge_chat_metadata(provider_metadata, request_metadata)
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
    if doc.string(doc.get(doc.root, "stop_reason")) != "end_turn":
        raise Error("Anthropic Messages stop reason is not supported")
    var usage = doc.get(doc.root, "usage")
    if usage < 0 or doc.nodes[usage].kind != JSON_OBJECT:
        raise Error("Anthropic Messages response usage is missing")
    _only_fields(doc, usage, ["input_tokens", "output_tokens"], "usage")
    var input_tokens = json_unsigned(doc, doc.get(usage, "input_tokens"))
    var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
    if not input_tokens or not output_tokens:
        raise Error("Anthropic Messages token usage is invalid")
    var content = doc.get(doc.root, "content")
    if content < 0 or doc.nodes[content].kind != JSON_ARRAY or len(doc.nodes[content].children) != 3:
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
