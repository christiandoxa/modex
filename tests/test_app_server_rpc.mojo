"""Focused timeout checks for the app-server JSON-RPC reader."""

from modex.app_server_rpc import _RpcReader
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
    print("App-server RPC reader checks: PASS")
