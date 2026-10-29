"""Test-only process driver for the internal local-rewrite relay."""

from std.io import RawFileDescriptor
from std.sys import argv

from modex.loopback_http import _number
from modex.loopback_server import LoopbackHTTPListener
from modex.provider_deepseek_transport import deepseek_request_headers
from modex.runtime_local_rewrite import deepseek_runtime_route, local_rewrite_upstream, local_rewrite_worker_count, serve_local_rewrite


def main() raises:
    var arguments = argv()
    if len(arguments) != 4 and len(arguments) != 5:
        raise Error("expected LISTEN_ADDRESS UPSTREAM_URL API_KEY [PARENT_FD]")
    var upstream = String(arguments[2])
    var key = String(arguments[3])
    var parent_fd = Int32(_number(arguments[4])) if len(arguments) == 5 else Int32(-1)
    _ = local_rewrite_upstream(upstream)
    _ = deepseek_request_headers([], key)
    var route = deepseek_runtime_route()
    var listener = LoopbackHTTPListener(String(arguments[1]))
    var output = RawFileDescriptor(1)
    var startup = "READY http://" + listener.address + "/v1"
    if parent_fd >= 0:
        startup += " WORKERS=" + String(local_rewrite_worker_count())
    output.write_bytes((startup + "\n").as_bytes())
    serve_local_rewrite(listener, upstream, [key], route[0], route[1], route[2], parent_fd=parent_fd, web_search_mode=route[3])
