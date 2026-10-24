from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.log_payload import readable_upstream_payload


def main() raises:
    var input = RawFileDescriptor(0)
    var output = RawFileDescriptor(1)
    var buffer = List[UInt8](length=8192, fill=0)
    var header = List[UInt8]()
    var paths = List[String](length=7, fill="")
    var present = List[Bool](length=7, fill=False)
    var field = 0
    var payload = List[UInt8]()
    var headers_done = False
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if headers_done:
                payload.append(buffer[index])
            elif buffer[index] == 10:
                if len(header) > 0 and header[0] == 49:
                    present[field] = True
                    paths[field] = String(from_utf8=Span(header)[1:])
                header.clear()
                field += 1
                if field == 7:
                    headers_done = True
            else:
                header.append(buffer[index])
    var text = readable_upstream_payload(payload, paths, present)
    output.write_bytes(text.as_bytes())
    output.write_bytes([10])
