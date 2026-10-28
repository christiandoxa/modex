"""Focused timeout checks for the app-server JSON-RPC reader."""

from modex.app_server_rpc import _RpcReader
from modex.super_hooks import HookTrustSession
from std.testing import assert_equal
from std.time import perf_counter


def main() raises:
    var reader = _RpcReader()
    reader.bytes[0] = 10
    reader.count = 1
    var message = String()
    try:
        _ = reader.next_line(0, -1.0, "initialize")
    except error:
        message = String(error)
    if message != "Codex hook-trust preflight timed out waiting for initialize":
        raise Error("expired deadline did not reject an already-buffered RPC line")
    assert_equal(reader.offset, 0)
    assert_equal(reader.next_line(0, perf_counter() + 1.0, "initialize"), "")

    var truncated = _RpcReader()
    for byte in '{"id":1,"result":'.as_bytes():
        truncated.line.append(byte)
    truncated.eof = True
    var partial = truncated.next_line(0, perf_counter() + 1.0, "initialize")
    assert_equal(partial, "{\"id\":1,\"result\":")
    var session = HookTrustSession("/synthetic")
    assert_equal(session.accept(partial), False)
    message = String()
    try:
        _ = truncated.next_line(0, perf_counter() + 1.0, "initialize")
    except error:
        message = String(error)
    if message != "Codex hook-trust preflight initialize failed: channel is empty and sending half is closed":
        raise Error("empty EOF after a truncated RPC line did not report closed channel")
    print("App-server RPC reader checks: PASS")
