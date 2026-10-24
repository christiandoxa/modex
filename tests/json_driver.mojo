"""Test-only tree serialization for independent parser differential tests."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JSON_ARRAY, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json


def serialize(document: JsonDocument, index: Int) -> String:
    ref node = document.nodes[index]
    if node.kind == JSON_STRING:
        return quote_json(node.text)
    if node.kind == JSON_ARRAY or node.kind == JSON_OBJECT:
        var output = String("{" if node.kind == JSON_OBJECT else "[")
        for offset in range(len(node.children)):
            if offset:
                output += ","
            if node.kind == JSON_OBJECT:
                output += quote_json(node.names[offset]) + ":"
            output += serialize(document, node.children[offset])
        output += "}" if node.kind == JSON_OBJECT else "]"
        return output^
    return node.text


def emit(bytes: List[UInt8]):
    try:
        var document = JsonDocument(String(from_utf8=Span(bytes)))
        print(serialize(document, document.root))
    except:
        print("ERROR")


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
