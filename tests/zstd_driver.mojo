from std.collections import Span
from std.sys import argv, exit, stderr

from modex.zstd import ZstdReader


def main():
    try:
        var args = argv()
        var reader = ZstdReader(open(args[1], "r"))
        var output = open(args[2], "w")
        while True:
            var block = reader.read_block()
            if not block:
                break
            output.write_all(Span(block))
    except error:
        print(error, file=stderr)
        var trace = error.get_stack_trace()
        if trace:
            print(trace.value(), file=stderr)
        exit(1)
