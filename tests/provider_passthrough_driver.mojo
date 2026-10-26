"""Test-only raw passthrough consumer; never buffers the response body."""
from std.collections import List
from std.sys import argv
from modex.provider_passthrough import deepseek_chat_completions_path, deepseek_chat_completions_stream


def main() raises:
    var args = argv()
    var body: List[UInt8] = [0, 255, 10, 123, 125]
    var stream = deepseek_chat_completions_stream(args[1], deepseek_chat_completions_path("/chat/completions", "/v1/chat/completions?raw=%2B&raw=2"), args[2], [("Content-Type", "application/custom+json"), ("Authorization", "Bearer inbound-fake"), ("Connection", "X-Private"), ("X-Private", "hidden"), ("Accept-Encoding", "gzip")], body, 1000, 5000, 1000, -1)
    print("status", stream.status)
    var count = 0
    var checksum = UInt64(0)
    while not stream.done:
        var chunk = stream.read_chunk()
        if len(chunk) > 8192:
            raise Error("unbounded response chunk")
        count += len(chunk)
        for byte in chunk:
            checksum += UInt64(byte)
    print("body", count, checksum)
