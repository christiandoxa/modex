from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.log_time import local_log_timestamp


def main() raises:
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var pending = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for i in range(size):
            if buffer[i] == 10:
                print(local_log_timestamp(String(from_utf8=Span(pending))))
                pending.clear()
            else:
                pending.append(buffer[i])
    if pending:
        print(local_log_timestamp(String(from_utf8=Span(pending))))
