"""Test-only JSONL view of native chat-compatible chunk decoding."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JsonDocument, serialize_json
from modex.provider_chat_chunk import chat_first_choice, chat_choice_metadata, chat_choice_delta, chat_stream_error


def emit(bytes: List[UInt8]) raises:
    var doc = JsonDocument(String(from_utf8=Span(bytes)))
    var choice = chat_first_choice(doc)
    var raw = serialize_json(doc, choice) if choice >= 0 else String("null")
    print('{"choice":' + raw + ',"metadata":' + chat_choice_metadata(doc, choice)
          + ',"delta":' + chat_choice_delta(doc, choice) + ',"error":' + chat_stream_error(doc) + "}")


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var pending = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if buffer[index] == 10:
                emit(pending)
                pending.clear()
            else:
                pending.append(buffer[index])
    if pending:
        emit(pending)
