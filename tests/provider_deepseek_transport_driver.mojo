"""Test-only file-config bridge to the native DeepSeek HTTP exchange."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv

from modex.json import JSON_ARRAY, JSON_BOOL, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from modex.provider_chat_usage import json_unsigned
from modex.provider_deepseek_transport import DeepSeekExchange, deepseek_event_stream


def _string(doc: JsonDocument, key: StringSlice, fallback: String = "", required: Bool = False) raises -> String:
    var node = doc.get(doc.root, key)
    if node < 0 and not required:
        return fallback
    if node < 0 or doc.nodes[node].kind != JSON_STRING:
        raise Error("driver config requires string " + String(key))
    return doc.nodes[node].text


def _unsigned(doc: JsonDocument, key: StringSlice, fallback: UInt64) raises -> UInt64:
    var node = doc.get(doc.root, key)
    if node < 0:
        return fallback
    var value = json_unsigned(doc, node)
    if not value:
        raise Error("driver config has invalid " + String(key))
    return value.value()


def _limit(doc: JsonDocument, key: StringSlice, fallback: Int) raises -> Int:
    var value = _unsigned(doc, key, UInt64(fallback))
    if value > UInt64(Int.MAX):
        raise Error("driver config has invalid " + String(key))
    return Int(value)


def _headers(doc: JsonDocument) raises -> List[Tuple[String, String]]:
    var output = List[Tuple[String, String]]()
    var node = doc.get(doc.root, "headers")
    if node < 0:
        return output^
    if doc.nodes[node].kind != JSON_ARRAY:
        raise Error("driver config headers must be pairs of strings")
    for pair in doc.nodes[node].children:
        if doc.nodes[pair].kind != JSON_ARRAY or len(doc.nodes[pair].children) != 2:
            raise Error("driver config headers must be pairs of strings")
        var name = doc.nodes[pair].children[0]
        var value = doc.nodes[pair].children[1]
        if doc.nodes[name].kind != JSON_STRING or doc.nodes[value].kind != JSON_STRING:
            raise Error("driver config headers must be pairs of strings")
        output.append((doc.nodes[name].text, doc.nodes[value].text))
    return output^


def _headers_json(headers: List[Tuple[String, String]]) -> String:
    var output = String("[")
    for index in range(len(headers)):
        if index:
            output += ","
        output += "[" + quote_json(headers[index][0]) + "," + quote_json(headers[index][1]) + "]"
    return output + "]"


def _hex(bytes: List[UInt8]) -> String:
    var output = String()
    var alphabet = String("0123456789abcdef")
    for byte in bytes:
        output += alphabet[byte=Int(byte) >> 4]
        output += alphabet[byte=Int(byte) & 15]
    return output


def _emit(mut output: RawFileDescriptor, line: String) raises:
    output.write_bytes((line + "\n").as_bytes())


def run(path: String, mut output: RawFileDescriptor) raises:
    var file = open(path, "r")
    var bytes = file.read_bytes()
    var doc = JsonDocument(String(from_utf8=Span(bytes)))
    if doc.nodes[doc.root].kind != JSON_OBJECT:
        raise Error("driver config must be a JSON object")
    var request = doc.get(doc.root, "request")
    if request < 0:
        raise Error("driver config requires request")
    var history = doc.get(doc.root, "history")
    var strict = doc.get(doc.root, "strict_tools")
    if strict >= 0 and doc.nodes[strict].kind != JSON_BOOL:
        raise Error("driver config strict_tools must be a boolean")
    var cancel_after = _unsigned(doc, "cancel_after_events", UInt64.MAX)
    var exchange = DeepSeekExchange(
        _string(doc, "address", required=True), _string(doc, "path", required=True), _string(doc, "api_key", required=True), serialize_json(doc, request),
        _unsigned(doc, "request_id", 1), _string(doc, "response_id", "resp_deepseek_1"), _unsigned(doc, "created_at", 1),
        _headers(doc), serialize_json(doc, history) if history >= 0 else String("[]"), strict >= 0 and doc.nodes[strict].text == "true", _string(doc, "web_search_mode", "auto"),
        _unsigned(doc, "connect_timeout_ms", 1000), _unsigned(doc, "request_timeout_ms", 1000), _unsigned(doc, "idle_timeout_ms", 1000),
        _limit(doc, "max_body_bytes", 4194304), _limit(doc, "line_max_bytes", 4194304), _limit(doc, "event_max_bytes", 4194304), _limit(doc, "accumulated_max_bytes", 4194304),
    )
    _emit(output, '{"type":"headers","status":' + String(exchange.status()) + ',"headers":' + _headers_json(exchange.headers()) + ',"body":' + exchange.body + ',"messages":' + exchange.messages + ',"response_metadata":' + exchange.response_metadata + "}")
    if not exchange.successful():
        _emit(output, '{"type":"http_error","status":' + String(exchange.status()) + ',"body_hex":' + quote_json(_hex(exchange.read_body())) + "}")
    elif not deepseek_event_stream(exchange.headers()):
        var body = exchange.read_buffered()
        _emit(output, '{"type":"buffered","status":' + String(exchange.status()) + ',"body":' + body + ',"conversation_messages":' + exchange.conversation_messages + "}")
    else:
        var emitted = UInt64(0)
        if cancel_after == 0:
            exchange.close()
        while not exchange.done:
            var events = exchange.read_events()
            for event in events:
                _emit(output, '{"type":"event","sse":' + quote_json(event) + "}")
                emitted += 1
                if emitted >= cancel_after:
                    exchange.close()
                    break
    _emit(output, '{"type":"done","cancelled":' + ("true" if exchange.cancelled else "false") + "}")


def main() raises:
    var output = RawFileDescriptor(1)
    try:
        var args = argv()
        if len(args) != 2:
            raise Error("usage: provider_deepseek_transport_driver CONFIG.json")
        run(args[1], output)
    except error:
        _emit(output, '{"type":"error","message":' + quote_json(String(error)) + "}")
