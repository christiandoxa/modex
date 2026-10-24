from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv, exit, stderr

from modex.sha256 import SHA256, hash_file

def digit(value: UInt8) -> Int:
    var byte = Int(value)
    if 48 <= byte <= 57: return byte - 48
    if 97 <= byte <= 102: return byte - 87
    if 65 <= byte <= 70: return byte - 55
    return -1

def update_hex(mut hash: SHA256, line: List[UInt8]) raises:
    if len(line) % 2: raise Error("odd-length hex input")
    var bytes = List[UInt8](capacity=len(line) // 2)
    for index in range(0, len(line), 2):
        var high = digit(line[index])
        var low = digit(line[index + 1])
        if high < 0 or low < 0: raise Error("invalid hex input")
        bytes.append(UInt8((high << 4) | low))
    hash.update(bytes)

def main():
    try:
        var args = argv()
        if args[1] == "file":
            print(hash_file(args[2], Int(args[3])))
            return
        if args[1] != "stdin": raise Error("expected stdin or file mode")
        var input = RawFileDescriptor(0)
        var buffer = List[UInt8](length=8192, fill=0)
        var line = List[UInt8]()
        var hash = SHA256()
        while True:
            var count = input.read_bytes(Span(buffer))
            if count == 0: break
            for index in range(count):
                if buffer[index] == 10:
                    update_hex(hash, line)
                    line.clear()
                else:
                    line.append(buffer[index])
        if line: update_hex(hash, line)
        print(hash.hex_digest())
    except error:
        print(error, file=stderr)
        exit(1)
