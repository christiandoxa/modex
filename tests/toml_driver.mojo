from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import quote_json
from modex.toml import (
    TOML_ARRAY,
    TOML_BOOLEAN,
    TOML_DATETIME,
    TOML_FLOAT,
    TOML_INTEGER,
    TOML_LOCAL_DATE,
    TOML_LOCAL_DATETIME,
    TOML_LOCAL_TIME,
    TOML_STRING,
    TOML_TABLE,
    TOMLDocument,
)


def value(document: TOMLDocument, node: Int) -> String:
    var kind = document.nodes[node].kind
    if kind == TOML_TABLE:
        var output = String("{")
        for i in range(len(document.nodes[node].children)):
            if i: output += ","
            output += quote_json(document.nodes[node].names[i]) + ":" + value(document, document.nodes[node].children[i])
        output += "}"
        return output^
    if kind == TOML_ARRAY:
        var output = String("[")
        for i in range(len(document.nodes[node].children)):
            if i: output += ","
            output += value(document, document.nodes[node].children[i])
        output += "]"
        return output^
    var type = String("integer")
    if kind == TOML_STRING: type = "string"
    elif kind == TOML_FLOAT: type = "float"
    elif kind == TOML_BOOLEAN: type = "bool"
    elif kind == TOML_DATETIME: type = "datetime"
    elif kind == TOML_LOCAL_DATETIME: type = "datetime-local"
    elif kind == TOML_LOCAL_DATE: type = "date-local"
    elif kind == TOML_LOCAL_TIME: type = "time-local"
    return "{\"type\":" + quote_json(type) + ",\"value\":" + quote_json(document.nodes[node].text) + "}"


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var source = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for i in range(size):
            source.append(buffer[i])
    try:
        var document = TOMLDocument(String(from_utf8=Span(source)))
        print(value(document, document.root))
    except:
        print("ERROR")
