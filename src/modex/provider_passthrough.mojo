"""Native DeepSeek API passthrough transport."""

from std.collections import List

from .loopback_http import HTTP_HEADER_LIMIT, LoopbackHTTPStream
from .provider_deepseek_transport import deepseek_event_stream, deepseek_open_redirectable_stream, deepseek_request_headers


comptime DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES = 4 * 1024 * 1024


def deepseek_chat_completions_path(base_path: String, target: String) -> String:
    var query = target.find("?")
    if query >= 0:
        return base_path + String(target[byte=query:])
    return base_path


def deepseek_passthrough_stream(
    address: String,
    path: String,
    api_key: String,
    headers: List[Tuple[String, String]],
    var body: List[UInt8],
    connect_timeout_ms: UInt64,
    request_timeout_ms: UInt64,
    idle_timeout_ms: UInt64,
    downstream_fd: Int32,
    request_method: String = "POST",
    request_header_limit: Int = HTTP_HEADER_LIMIT,
    request_field_limit: Int = HTTP_HEADER_LIMIT,
    cancel_fd: Int32 = -1,
    anthropic_messages: Bool = False,
) raises -> LoopbackHTTPStream:
    var include_content_length = not anthropic_messages or len(body) > 0 or (request_method != "GET" and request_method != "HEAD")
    var stream = deepseek_open_redirectable_stream(
        address,
        path,
        deepseek_request_headers(headers, api_key, passthrough=not anthropic_messages, anthropic_messages=anthropic_messages),
        body^,
        connect_timeout_ms,
        request_timeout_ms,
        idle_timeout_ms,
        DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES,
        downstream_fd,
        True,
        request_method,
        request_header_limit,
        request_field_limit,
        cancel_fd,
        False,
        include_content_length,
    )
    # The frozen passthrough streams SSE on 2xx/3xx, and buffers non-SSE.
    # Keep >=400 rejection in the send path, before response dispatch; a
    # successful or redirect buffered response fails in its reader instead.
    var streaming = 200 <= stream.status < 400 and stream.status != 204 and stream.status != 304 and deepseek_event_stream(stream.headers)
    if not streaming:
        stream.max_body_bytes = DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES
        stream.max_wire_bytes = HTTP_HEADER_LIMIT * 2 + 65536 + DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES * 8
        if stream.status >= 400 and stream.length > DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES:
            stream.close()
            raise Error("oversized HTTP response body")
    return stream^
