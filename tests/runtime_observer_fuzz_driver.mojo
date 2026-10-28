"""Native differential driver for old and streaming runtime SSE ID selection."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import JSON_STRING, JsonDocument, quote_json
from modex.provider_sse_wire import ProviderSSEFramer
from modex.runtime_binding import RuntimeBindings
from modex.runtime_sse_binding_observer import RuntimeSSEBindingObserver
from modex.text import trim_text


def hex_digit(value: Int) -> Int:
    if 48 <= value <= 57:
        return value - 48
    if 65 <= value <= 70:
        return value - 55
    if 97 <= value <= 102:
        return value - 87
    return -1


def decode_hex(text: StringSlice) raises -> List[UInt8]:
    var encoded = String(text).as_bytes()
    if len(encoded) % 2 != 0:
        raise Error("odd hex input")
    var output = List[UInt8]()
    var index = 0
    while index < len(encoded):
        var high = hex_digit(Int(encoded[index]))
        var low = hex_digit(Int(encoded[index + 1]))
        if high < 0 or low < 0:
            raise Error("invalid hex input")
        output.append(UInt8(high * 16 + low))
        index += 2
    return output^


def old_id(body: String) -> String:
    try:
        var document = JsonDocument(body)
        var node = document.get(document.get(document.root, "response"), "id")
        if node < 0 or document.nodes[node].kind != JSON_STRING:
            node = document.get(document.root, "id")
        if node < 0 or document.nodes[node].kind != JSON_STRING:
            node = document.get(document.root, "response_id")
        if node >= 0 and document.nodes[node].kind == JSON_STRING:
            return trim_text(document.string(node))
        node = document.get(document.root, "responseId")
        if node >= 0 and document.nodes[node].kind == JSON_STRING:
            return trim_text(document.string(node))
        return trim_text(document.string(document.get(document.get(document.root, "message"), "id")))
    except:
        return ""


def append_old_frame(mut output: List[String], frame: Optional[List[String]]):
    if not frame:
        return
    var identifier = old_id(String("\n").join(frame.value()))
    if identifier:
        output.append(identifier^)


def old_observe(body: List[UInt8], schedule: List[Int]) raises -> Tuple[List[String], Bool]:
    var framer = ProviderSSEFramer()
    var output = List[String]()
    var failed = False
    var offset = 0
    for amount in schedule:
        var end = min(len(body), offset + amount)
        while offset < end and not failed:
            try:
                var frame = framer.consume(Span(body)[offset:end])
                offset += frame[0]
                append_old_frame(output, frame[1])
            except:
                failed = True
    if not failed:
        try:
            append_old_frame(output, framer.finish())
        except:
            failed = True
    return (output^, failed)


def new_observe(body: List[UInt8], schedule: List[Int]) raises -> Tuple[List[String], Bool]:
    var observer = RuntimeSSEBindingObserver()
    var output = List[String]()
    var failed = False
    var offset = 0
    for amount in schedule:
        var end = min(len(body), offset + amount)
        if offset < end:
            output.extend(observer.consume(Span(body)[offset:end]))
            if observer.is_failed():
                failed = True
                break
            offset = end
    if not failed:
        try:
            output.extend(observer.finish())
        except:
            failed = True
    return (output^, failed)


def remember_ids(values: List[String]) raises -> List[String]:
    var bindings = RuntimeBindings("synthetic-fuzz-key", "http://127.0.0.1:1/v1")
    for index in range(len(values)):
        var value = values[index]
        bindings.remember(0, value)
    var output = List[String]()
    for row in bindings.rows:
        output.append(row.key)
    return output^


def json_strings(values: List[String]) -> String:
    var result = String("[")
    for index in range(len(values)):
        if index > 0:
            result += ","
        result += quote_json(values[index])
    return result + "]"


def run_record(record: StringSlice) raises:
    var fields = String(record).split(":")
    if len(fields) != 2:
        raise Error("expected schedule:hex record")
    var schedule = List[Int]()
    for amount in fields[0].split(","):
        schedule.append(Int(amount))
    var body = decode_hex(fields[1])
    var old_result = old_observe(body, schedule)
    var new_result = new_observe(body, schedule)
    var old_bindings = remember_ids(old_result[0])
    var new_bindings = remember_ids(new_result[0])
    print(
        ("FAILED" if old_result[1] else "OK")
        + "\t"
        + json_strings(old_result[0])
        + "\t"
        + json_strings(old_bindings)
        + "\t"
        + ("FAILED" if new_result[1] else "OK")
        + "\t"
        + json_strings(new_result[0])
        + "\t"
        + json_strings(new_bindings)
    )


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var line = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if buffer[index] == 10:
                run_record(String(from_utf8=Span(line)))
                line.clear()
            else:
                line.append(buffer[index])
    if line:
        run_record(String(from_utf8=Span(line)))
