"""JSON-lines driver for the native buffered DeepSeek chat response mapper."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JSON_OBJECT, JSON_STRING, JsonDocument, serialize_json
from modex.provider_chat_buffered import deepseek_buffered_response
from modex.provider_chat_usage import json_unsigned


def required_string(doc: JsonDocument, name: StringSlice) raises -> String:
    var node = doc.get(doc.root, name)
    if node < 0 or doc.nodes[node].kind != JSON_STRING:
        raise Error("driver header requires string " + String(name))
    return doc.nodes[node].text


def required_unsigned(doc: JsonDocument, name: StringSlice) raises -> UInt64:
    var value = json_unsigned(doc, doc.get(doc.root, name))
    if not value:
        raise Error("driver header requires unsigned " + String(name))
    return value.value()


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var header_bytes = List[UInt8]()
    var response_bytes = List[UInt8]()
    var got_header = False
    var got_response = False
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if buffer[index] == 10:
                if not got_header:
                    got_header = True
                else:
                    got_response = True
                    break
            elif not got_header:
                header_bytes.append(buffer[index])
            elif not got_response:
                response_bytes.append(buffer[index])
        if got_response:
            break
    if not got_header:
        raise Error("missing driver header")
    if not got_response and not response_bytes:
        raise Error("missing buffered response JSON")

    var header = JsonDocument(String(from_utf8=Span(header_bytes)))
    if header.nodes[header.root].kind != JSON_OBJECT:
        raise Error("driver header must be a JSON object")
    var created_at = required_unsigned(header, "created_at")
    var response_id = required_string(header, "response_id")
    var metadata_node = header.get(header.root, "metadata")
    var metadata = serialize_json(header, metadata_node) if metadata_node >= 0 else String("null")
    var response = String(from_utf8=Span(response_bytes))
    print(deepseek_buffered_response(response, created_at, response_id, metadata))
