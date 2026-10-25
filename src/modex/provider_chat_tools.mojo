"""Tool-call delta primitives for chat-compatible provider streams."""

from .json import JSON_OBJECT, JSON_STRING, JsonDocument, quote_json
from .provider_chat_usage import json_unsigned
from .text import trim_text


def chat_tool_delta(doc: JsonDocument, node: Int) raises -> String:
    var index = json_unsigned(doc, doc.get(node, "index"))
    var call_id = doc.get(node, "id")
    var function = doc.get(node, "function")
    var name = -1
    var arguments = -1
    if function >= 0 and doc.nodes[function].kind == JSON_OBJECT:
        name = doc.get(function, "name")
        arguments = doc.get(function, "arguments")
    var extra = doc.get(node, "extra_content")
    var google = doc.get(extra, "google") if extra >= 0 and doc.nodes[extra].kind == JSON_OBJECT else -1
    var signature = doc.get(google, "thought_signature") if google >= 0 and doc.nodes[google].kind == JSON_OBJECT else -1
    var result = "{\"index\":" + String(index.value() if index else UInt64(0))
    result += ",\"id\":" + _string_member(doc, call_id)
    result += ",\"name\":" + _string_member(doc, name)
    result += ",\"arguments\":" + _nonempty_member(doc, arguments)
    result += ",\"thought_signature\":" + _trimmed_member(doc, signature) + "}"
    return result


def incremental_arguments(current: String, incoming: String) -> Optional[String]:
    if not incoming:
        return Optional[String]()
    return Optional[String](incoming)


def fallback_tool_id(provider: String, request: UInt64, index: UInt64) -> String:
    return "call_" + provider + "_" + String(request) + "_" + String(index)


def _string_member(doc: JsonDocument, node: Int) -> String:
    if node >= 0 and doc.nodes[node].kind == JSON_STRING:
        return quote_json(doc.nodes[node].text)
    return "null"


def _nonempty_member(doc: JsonDocument, node: Int) -> String:
    if node >= 0 and doc.nodes[node].kind == JSON_STRING and doc.nodes[node].text:
        return quote_json(doc.nodes[node].text)
    return "null"


def _trimmed_member(doc: JsonDocument, node: Int) -> String:
    if node >= 0 and doc.nodes[node].kind == JSON_STRING and trim_text(doc.nodes[node].text):
        return quote_json(doc.nodes[node].text)
    return "null"
