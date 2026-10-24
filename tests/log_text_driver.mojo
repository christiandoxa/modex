"""Test-only JSON-lines driver for transcript text projections."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JsonDocument, quote_json
from modex.log_text import operation_value, safe_text, tool_name, visible_message, visible_tool_output


def emit(bytes: List[UInt8]):
    try:
        var doc = JsonDocument(String(from_utf8=Span(bytes)))
        var method = doc.string(doc.get(doc.root, "method"))
        var text = doc.string(doc.get(doc.root, "text"))
        var output = String()
        if method == "safe":
            output = safe_text(text)
        elif method == "message":
            output = visible_message(text)
        elif method == "tool":
            output = visible_tool_output(text)
        elif method == "tool_name":
            output = tool_name(text)
        elif method == "operation":
            output = operation_value(text)
        else:
            raise Error("unknown transcript text projection")
        print(quote_json(output))
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
