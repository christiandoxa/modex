"""Line-hex driver for the native chat stream reader."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JSON_OBJECT, JSON_STRING, JsonDocument, serialize_json
from modex.provider_chat_reader import DeepSeekChatReader
from modex.provider_chat_usage import json_unsigned


def decode_hex(line: List[UInt8]) raises -> List[UInt8]:
    var end = len(line)
    if end and line[end - 1] == 13:
        end -= 1
    if end % 2 != 0:
        raise Error("hex chunk has an odd number of digits")
    var out = List[UInt8]()
    for i in range(0, end, 2):
        var a = _hex_value(line[i])
        var b = _hex_value(line[i + 1])
        if a < 0 or b < 0:
            raise Error("invalid hex input")
        out.append(UInt8(a * 16 + b))
    return out^


def _hex_value(byte: UInt8) -> Int:
    var value = Int(byte)
    if 48 <= value <= 57:
        return value - 48
    if 65 <= value <= 70:
        return value - 55
    if 97 <= value <= 102:
        return value - 87
    return -1


def _required_unsigned(doc: JsonDocument, name: StringSlice) raises -> UInt64:
    var value = json_unsigned(doc, doc.get(doc.root, name))
    if not value:
        raise Error("driver header requires unsigned " + String(name))
    return value.value()


def _limit(doc: JsonDocument, name: StringSlice, fallback: Int) raises -> Int:
    var node = doc.get(doc.root, name)
    if node < 0:
        return fallback
    var value = json_unsigned(doc, node)
    if not value or value.value() > UInt64(Int.MAX):
        raise Error("driver header has invalid " + String(name))
    return Int(value.value())


def emit_events(mut output: RawFileDescriptor, events: List[String]) raises:
    for event in events:
        output.write_bytes(event.as_bytes())


def process_chunk(mut reader: DeepSeekChatReader, chunk: List[UInt8], mut output: RawFileDescriptor) raises:
    var offset = 0
    while offset < len(chunk) and not reader.done:
        var result = reader.consume(Span(chunk)[offset:])
        if result[0] <= 0:
            raise Error("chat stream reader made no progress")
        offset += result[0]
        emit_events(output, result[1])


def main() raises:
    var input = RawFileDescriptor(0)
    var output = RawFileDescriptor(1)
    var buffer = List[UInt8](length=8192, fill=0)
    var line = List[UInt8]()
    var got_header = False
    var reader = DeepSeekChatReader(0, "", 0)
    while not reader.done:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if buffer[index] != 10:
                line.append(buffer[index])
                continue
            if not got_header:
                var document = JsonDocument(String(from_utf8=Span(line)))
                if document.nodes[document.root].kind != JSON_OBJECT:
                    raise Error("driver header must be a JSON object")
                var request_id = _required_unsigned(document, "request_id")
                var created_at = _required_unsigned(document, "created_at")
                var response_node = document.get(document.root, "response_id")
                if response_node < 0 or document.nodes[response_node].kind != JSON_STRING:
                    raise Error("driver header requires string response_id")
                var metadata_node = document.get(document.root, "metadata")
                var metadata = serialize_json(document, metadata_node) if metadata_node >= 0 else String("null")
                var line_max = _limit(document, "line_max", 4194304)
                var event_max = _limit(document, "event_max", 4194304)
                var accumulated_max = _limit(document, "accumulated_max", 4194304)
                reader = DeepSeekChatReader(request_id, document.nodes[response_node].text, created_at, metadata, line_max, event_max, accumulated_max)
                got_header = True
            else:
                process_chunk(reader, decode_hex(line), output)
            line.clear()
            if reader.done:
                break
    if not got_header:
        raise Error("missing driver header")
    if not reader.done and line:
        process_chunk(reader, decode_hex(line), output)
    if not reader.done:
        emit_events(output, reader.finish())
