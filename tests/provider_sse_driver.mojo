"""Hex-line driver for the native provider SSE components."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import quote_json
from modex.provider_sse_json import ProviderSSEJSONAssembler
from modex.provider_sse_wire import ProviderSSEFramer


def emit_frames(ref frames: Optional[List[String]], mut assembler: ProviderSSEJSONAssembler, mode: String) raises:
    if not frames:
        return
    if mode == "frames":
        for frame in frames.value():
            print("FRAME\t" + quote_json(frame))
    else:
        var values = assembler.push(frames.value())
        for value in values:
            print("VALUE\t" + quote_json(value))


def decode_hex(line: List[UInt8]) raises -> List[UInt8]:
    var out = List[UInt8]()
    var i = 0
    while i + 1 < len(line):
        var a = Int(line[i])
        var b = Int(line[i + 1])
        if a == 10 or a == 13:
            break
        a = a - 48 if a <= 57 else a - 87
        b = b - 48 if b <= 57 else b - 87
        if a < 0 or a > 15 or b < 0 or b > 15:
            raise Error("invalid hex input")
        out.append(UInt8(a * 16 + b))
        i += 2
    return out^


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var line = List[UInt8]()
    var header = True
    var mode = String("frames")
    var line_max = 4194304
    var event_max = 4194304
    var accumulated_max = 4194304
    var framer = ProviderSSEFramer()
    var assembler = ProviderSSEJSONAssembler()
    try:
        while True:
            var size = input.read_bytes(Span(buffer))
            if size == 0:
                break
            for index in range(size):
                if buffer[index] != 10:
                    line.append(buffer[index])
                    continue
                if header:
                    var text = String(from_utf8=Span(line))
                    var fields = text.split(" ")
                    mode = String(fields[0])
                    if len(fields) > 1:
                        line_max = Int(fields[1])
                    if len(fields) > 2:
                        event_max = Int(fields[2])
                    if len(fields) > 3:
                        accumulated_max = Int(fields[3])
                    framer = ProviderSSEFramer(line_max, event_max)
                    assembler = ProviderSSEJSONAssembler(accumulated_max)
                    header = False
                else:
                    var chunk = decode_hex(line)
                    var offset = 0
                    while offset < len(chunk):
                        var result = framer.consume(Span(chunk)[offset:])
                        var used = result[0]
                        offset += used
                        emit_frames(result[1], assembler, mode)
                        if mode == "json" and assembler.done:
                            print("EOF")
                            return
                line.clear()
        if header:
            raise Error("missing driver header")
        var final_frame = framer.finish()
        emit_frames(final_frame, assembler, mode)
        if mode == "json":
            var values = assembler.finish()
            for value in values:
                print("VALUE\t" + quote_json(value))
        print("EOF")
    except e:
        print("ERROR\t" + String(e))
