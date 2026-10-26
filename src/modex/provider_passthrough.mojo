"""Native DeepSeek Chat Completions passthrough transport."""

from std.collections import List

from .loopback_http import HTTP_HEADER_LIMIT, LoopbackHTTPStream
from .provider_deepseek_transport import deepseek_request_headers, deepseek_event_stream


comptime DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES = 4 * 1024 * 1024


def deepseek_chat_completions_path(base_path: String, target: String) -> String:
    var query = target.find("?")
    if query >= 0:
        return base_path + String(target[byte=query:])
    return base_path


def deepseek_chat_completions_stream(
    address: String,
    path: String,
    api_key: String,
    headers: List[Tuple[String, String]],
    body: List[UInt8],
    connect_timeout_ms: UInt64,
    request_timeout_ms: UInt64,
    idle_timeout_ms: UInt64,
    downstream_fd: Int32,
) raises -> LoopbackHTTPStream:
    var stream = LoopbackHTTPStream(
        address,
        path,
        deepseek_request_headers(headers, api_key, passthrough=True),
        body,
        connect_timeout_ms,
        request_timeout_ms,
        idle_timeout_ms,
        DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES,
        downstream_fd,
        True,
    )
    # Only successful SSE is streamed without an aggregate body limit.
    if stream.status < 200 or stream.status >= 300 or not deepseek_event_stream(stream.headers):
        stream.max_body_bytes = DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES
        stream.max_wire_bytes = HTTP_HEADER_LIMIT * 2 + 65536 + DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES * 8
        if stream.length > DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES:
            stream.close()
            raise Error("oversized HTTP response body")
    return stream^
