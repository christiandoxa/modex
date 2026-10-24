from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.json import quote_json
from modex.log_payload_render import payload_lines


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var data = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            data.append(buffer[index])
    var split = 0
    while split < len(data) and data[split] != 10:
        split += 1
    var width = Int(String(from_utf8=Span(data)[0:split]))
    var payload = String(from_utf8=Span(data)[split + 1:])
    for line in payload_lines(payload, width):
        print(quote_json(line))
