from std.collections import List, Span
from std.io import RawFileDescriptor
from modex.json import JsonDocument, quote_json
from modex.log_transcript import transcript_event

def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var pending = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0: break
        for index in range(size):
            if buffer[index] == 10:
                emit(pending)
                pending.clear()
            else:
                pending.append(buffer[index])
    if pending: emit(pending)

def emit(bytes: List[UInt8]):
    try:
        var line = String(from_utf8=Span(bytes))
        var event = transcript_event(line)
        if event:
            var value = event.value()
            print("[" + quote_json(value[0]) + "," + quote_json(value[1]) + "," + quote_json(value[2]) + "]")
        else:
            print("null")
    except:
        print("ERROR")
