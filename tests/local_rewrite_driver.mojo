"""Test-only process driver for the internal local-rewrite relay."""

from std.io import RawFileDescriptor
from std.sys import argv

from modex.loopback_server import LoopbackHTTPListener
from modex.provider_deepseek_transport import deepseek_request_headers
from modex.runtime_local_rewrite import local_rewrite_upstream, serve_local_rewrite


def main() raises:
    var arguments = argv()
    if len(arguments) != 4:
        raise Error("expected LISTEN_ADDRESS UPSTREAM_URL API_KEY")
    var upstream = String(arguments[2])
    var key = String(arguments[3])
    _ = local_rewrite_upstream(upstream)
    _ = deepseek_request_headers([], key)
    var listener = LoopbackHTTPListener(String(arguments[1]))
    var output = RawFileDescriptor(1)
    output.write_bytes(("READY http://" + listener.address + "/v1\n").as_bytes())
    serve_local_rewrite(listener, upstream, key)
