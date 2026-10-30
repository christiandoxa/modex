"""Test-only raw passthrough consumer; never buffers the response body."""
from std.collections import List
from std.io import RawFileDescriptor
from std.sys import argv
from modex.loopback_http import HTTP_HEADER_LIMIT
from modex.provider_passthrough import deepseek_chat_completions_path, deepseek_chat_completions_stream


def main() raises:
    var args = argv()
    if len(args) < 3 or len(args) > 4:
        raise Error("usage: provider_passthrough_driver ADDRESS API_KEY [CANCEL_FD]")
    var body: List[UInt8] = [0, 255, 10, 123, 125]
    var cancel_fd = Int32(Int(args[3])) if len(args) == 4 else Int32(-1)
    var stream = deepseek_chat_completions_stream(args[1], deepseek_chat_completions_path("/chat/completions", "/v1/chat/completions?raw=%2B&raw=2"), args[2], [("Content-Type", "application/custom+json"), ("Authorization", "Bearer inbound-fake"), ("Connection", "X-Private"), ("X-Private", "hidden"), ("Accept-Encoding", "gzip")], body^, 1000, 5000, 1000, -1, "POST", HTTP_HEADER_LIMIT, HTTP_HEADER_LIMIT, cancel_fd)
    var output = RawFileDescriptor(1)
    output.write_bytes(("status " + String(stream.status) + "\n").as_bytes())
    var count = 0
    var checksum = UInt64(0)
    try:
        while not stream.done:
            var chunk = stream.read_chunk()
            if len(chunk) > 8192:
                raise Error("unbounded response chunk")
            count += len(chunk)
            for byte in chunk:
                checksum += UInt64(byte)
    except error:
        if String(error) != "loopback HTTP request cancelled":
            raise
        stream.close()
        output.write_bytes(("CANCELLED " + String(error) + "\n").as_bytes())
        return
    print("body", count, checksum)
