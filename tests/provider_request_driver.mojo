"""Test-only JSONL bridge to the DeepSeek request translator."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JsonDocument, quote_json, serialize_json
from modex.provider_request import translate_deepseek_request


def emit(line: List[UInt8]):
    try:
        var doc = JsonDocument(String(from_utf8=Span(line)))
        var request = doc.get(doc.root, "request")
        var history = doc.get(doc.root, "history")
        var strict = doc.get(doc.root, "strict_tools")
        var web = doc.get(doc.root, "web_search_mode")
        var strict_tools = strict >= 0 and doc.nodes[strict].text == "true"
        var history_json = serialize_json(doc, history) if history >= 0 else "[]"
        var web_mode = doc.string(web) if web >= 0 else "auto"
        var output = translate_deepseek_request(
            serialize_json(doc, request), history_json, strict_tools, web_mode
        )
        print("{\"ok\":" + output + "}")
    except e:
        print("{\"error\":" + quote_json(String(e)) + "}")


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
