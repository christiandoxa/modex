"""Bounded native loopback HTTP/1 listener, parser, and response writer."""

from std.bit import byte_swap
from std.collections import Array, List, Span
from std.memory import MaybeUninit
from std.net._sys.inet import in6_addr, in_addr
from std.net._sys.unix import (
    AF_INET, AF_INET6, F_GETFL, F_SETFL, MSG_DONTWAIT, MSG_NOSIGNAL, MSG_PEEK,
    O_NONBLOCK, SO_REUSEADDR, SOL_SOCKET, SOCK_STREAM, bind, listen, accept, getsockname,
    recv, send, setsockopt, sockaddr, sockaddr_in, sockaddr_in6, sockaddr_storage, socket,
)
from std.sys import Endian, size_of
from std.sys._libc import FcntlCommands, FcntlFDFlags, close, fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.time import perf_counter, sleep
from std.time.time import _realtime_nanoseconds

from .local_time import format_http_date

comptime HTTP_HEADER_LIMIT = 65536
# shortcut: cap unbounded baseline heads at 2 MiB, below the outbound cap; raise with larger oracle evidence.
comptime HTTP_MAX_REQUEST_HEADER_LIMIT = 2 * 1024 * 1024
comptime HTTP_DEFAULT_BODY_LIMIT = 64 * 1024 * 1024
comptime HTTP_MAX_BODY_LIMIT = 64 * 1024 * 1024
comptime HTTP_DEFERRED_BODY_THRESHOLD = 1024
comptime HTTP_MAX_RESPONSE_BODY_BYTES = 16777216


@fieldwise_init
struct LoopbackHTTPRequest(Movable):
    var method: String
    var target: String
    var headers: List[Tuple[String, String]]
    var body: List[UInt8]


struct LoopbackHTTPListener(Movable):
    var fd: Int32
    var address: String

    def __init__(out self, address: String, backlog: Int = 128) raises:
        self.fd = -1
        self.address = ""
        if backlog < 1 or backlog > 4096:
            raise Error("invalid loopback HTTP listen backlog")
        var ipv6 = address.startswith("[")
        var host: String
        var port: Int
        var ip: UInt32 = 0
        if ipv6:
            var bracket = address.find("]")
            if bracket != 4 or not address.startswith("[::1]:"):
                raise Error("HTTP listen address must be numeric loopback")
            host = "[::1]"
            port = _number(address[byte=6:])
        else:
            var parts = address.split(":")
            if len(parts) != 2:
                raise Error("invalid loopback HTTP listen address")
            host = String(parts[0])
            var octets = host.split(".")
            if len(octets) != 4:
                raise Error("HTTP listen address must be numeric loopback")
            for index in range(4):
                var octet = _number(octets[index])
                if octet > 255 or (index == 0 and octet != 127):
                    raise Error("HTTP listen address must be numeric loopback")
                ip = (ip << 8) | UInt32(octet)
            port = _number(parts[1])
        if port > 65535:
            raise Error("invalid loopback HTTP port")

        self.fd = socket(AF_INET6 if ipv6 else AF_INET, SOCK_STREAM, 0)
        if self.fd < 0:
            raise Error("failed to create loopback HTTP listener")
        try:
            _configure_fd(self.fd)
            var reuse: Int32 = 1
            if setsockopt(self.fd, SOL_SOCKET, SO_REUSEADDR, Pointer(to=reuse).unsafe_bitcast[NoneType](), UInt32(size_of[Int32]())) < 0:
                raise Error("failed to set loopback HTTP listener reuse option")
            if ipv6:
                var bytes = Array[UInt8, 16](fill=0)
                bytes[15] = 1
                var addr = sockaddr_in6(port=_port_bytes(port), addr=in6_addr(s6_addr=bytes^), flowinfo=0, scope_id=0)
                if bind(self.fd, Pointer(to=addr).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in6]())) < 0:
                    raise Error("failed to bind loopback HTTP listener")
                var actual_bytes = Array[UInt8, 16](fill=0)
                actual_bytes[15] = 1
                var actual = sockaddr_in6(port=UInt16(0), addr=in6_addr(s6_addr=actual_bytes^), flowinfo=0, scope_id=0)
                var actual_len = UInt32(size_of[sockaddr_in6]())
                if getsockname(self.fd, Pointer(to=actual).unsafe_bitcast[sockaddr](), Pointer(to=actual_len)) < 0:
                    raise Error("failed to inspect loopback HTTP listener address")
                self.address = host + ":" + String(_host_port(actual.port()))
            else:
                var addr = sockaddr_in(port=_port_bytes(port), addr=in_addr(s_addr=_network32(ip)))
                if bind(self.fd, Pointer(to=addr).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in]())) < 0:
                    raise Error("failed to bind loopback HTTP listener")
                var actual = sockaddr_in(port=UInt16(0), addr=in_addr(s_addr=0))
                var actual_len = UInt32(size_of[sockaddr_in]())
                if getsockname(self.fd, Pointer(to=actual).unsafe_bitcast[sockaddr](), Pointer(to=actual_len)) < 0:
                    raise Error("failed to inspect loopback HTTP listener address")
                self.address = host + ":" + String(_host_port(actual.port()))
            if listen(self.fd, Int32(backlog)) < 0:
                raise Error("failed to listen on loopback HTTP socket")
        except:
            self.close()
            raise

    def close(mut self):
        if self.fd >= 0:
            _ = close(self.fd)
            self.fd = -1

    def __deinit__(deinit self):
        self.close()

    def accept(mut self, timeout_ms: UInt64) raises -> Optional[LoopbackHTTPConnection]:
        if self.fd < 0:
            raise Error("loopback HTTP listener is closed")
        var deadline = _deadline(timeout_ms)
        while True:
            var peer = MaybeUninit[sockaddr_storage]()
            var peer_length = UInt32(size_of[sockaddr_storage]())
            var client = accept(self.fd, Pointer(to=peer).unsafe_bitcast[sockaddr](), Pointer(to=peer_length))
            _ = peer^.unsafe_forget()
            if client >= 0:
                try:
                    _configure_fd(client)
                except:
                    _ = close(client)
                    raise
                return Optional[LoopbackHTTPConnection](LoopbackHTTPConnection(client))
            var error = get_errno()
            if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                raise Error("loopback HTTP accept failed")
            if perf_counter() >= deadline:
                return Optional[LoopbackHTTPConnection]()
            sleep(0.001)


struct LoopbackHTTPConnection(Movable):
    var fd: Int32
    var input: List[UInt8]
    var wire_bytes: Int
    var streaming: Bool
    var request_read: Bool
    var head_request: Bool
    var expect_continue_sent: Bool
    var keep_alive_enabled: Bool
    var include_default_response_headers: Bool
    var keep_alive: Bool
    var waiting_for_request: Bool
    var worker_tracked: Bool
    var request_header_scan: Int
    var request_header_deadline: Float64
    var request_capture_error: String
    var request_capture_progress: Bool
    var request_head_parsed: Bool
    var request_body_deferred: Bool
    var response_version: String
    var done: Bool

    def __init__(out self, fd: Int32):
        self.fd = fd
        self.input = List[UInt8]()
        self.wire_bytes = 0
        self.streaming = False
        self.request_read = False
        self.head_request = False
        self.expect_continue_sent = False
        self.keep_alive_enabled = False
        self.include_default_response_headers = False
        self.keep_alive = False
        self.waiting_for_request = False
        self.worker_tracked = False
        self.request_header_scan = 0
        self.request_header_deadline = 0.0
        self.request_capture_error = ""
        self.request_capture_progress = False
        self.request_head_parsed = False
        self.request_body_deferred = False
        self.response_version = "HTTP/1.1"
        self.done = False

    def close(mut self):
        if self.fd >= 0 and not self.worker_tracked:
            _ = close(self.fd)
            self.fd = -1
        self.done = True

    def __deinit__(deinit self):
        self.close()

    def client_disconnected(mut self) raises -> Bool:
        if self.fd < 0:
            return True
        var byte: UInt8 = 0
        var result = recv(self.fd, Pointer(to=byte), 1, MSG_PEEK | MSG_DONTWAIT)
        if result == 0:
            return True
        if result > 0:
            return False
        var error = get_errno()
        if error == ErrNo.EAGAIN or error == ErrNo.EINTR:
            return False
        if error == ErrNo.ECONNRESET:
            return True
        raise Error("loopback HTTP peer check failed")

    def discard_incoming_or_disconnected(mut self, mut buffer: List[UInt8]) raises -> Bool:
        if self.fd < 0:
            return True
        if not buffer:
            raise Error("loopback HTTP discard buffer is empty")
        var result = recv(self.fd, buffer.unsafe_ptr(), UInt(len(buffer)), MSG_DONTWAIT)
        if result == 0:
            return True
        if result > 0:
            return False
        var error = get_errno()
        if error == ErrNo.EAGAIN or error == ErrNo.EINTR:
            return False
        if error == ErrNo.ECONNRESET:
            return True
        raise Error("loopback HTTP peer check failed")

    def expect_continue_was_sent(self) -> Bool:
        return self.expect_continue_sent

    def request_head_was_parsed(self) -> Bool:
        return self.request_head_parsed

    def request_body_was_deferred(self) -> Bool:
        return self.request_body_deferred

    def capture_request_headers(mut self, timeout_ms: UInt64, header_limit: Int, byte_limit: Int) -> Bool:
        self.request_capture_progress = False
        if self.fd < 0 or self.done:
            return False
        if self.request_capture_error or self.request_header_scan < 0:
            return True
        if self.request_header_deadline == 0.0:
            self.request_header_deadline = perf_counter() + Float64(timeout_ms) / 1000.0
        if perf_counter() >= self.request_header_deadline:
            self.request_capture_error = "loopback HTTP request timed out"
            self.request_header_scan = -1
            self.request_header_deadline = 0.0
            return True

        var scan_start = self.request_header_scan
        var scan_end = min(len(self.input), scan_start + byte_limit + 3)
        var header_end = _header_end(self.input, self.request_header_scan, scan_end)
        if header_end >= 0:
            self.request_header_scan = -1
            self.request_header_deadline = 0.0
            return True
        self.request_header_scan = max(self.request_header_scan, scan_end - 3)
        self.request_capture_progress = self.request_header_scan > scan_start
        if self.request_header_scan > header_limit:
            self.request_header_scan = -1
            self.request_header_deadline = 0.0
            return True
        if self.request_header_scan < len(self.input) - 3:
            return False
        if len(self.input) > header_limit:
            self.request_header_scan = -1
            self.request_header_deadline = 0.0
            return True

        var capacity = min(byte_limit, header_limit + 4 - len(self.input))
        if capacity <= 0:
            return False
        var buffer = List[UInt8](length=capacity, fill=0)
        var size = recv(self.fd, buffer.unsafe_ptr(), UInt(capacity), MSG_DONTWAIT)
        if size > 0:
            var count = Int(size)
            self.wire_bytes += count
            for index in range(count):
                self.input.append(buffer[index])
            self.request_capture_progress = True
            scan_start = self.request_header_scan
            scan_end = min(len(self.input), scan_start + byte_limit + 3)
            header_end = _header_end(self.input, self.request_header_scan, scan_end)
            if header_end >= 0:
                self.request_header_scan = -1
                self.request_header_deadline = 0.0
                return True
            self.request_header_scan = max(self.request_header_scan, scan_end - 3)
            self.request_capture_progress = self.request_capture_progress or self.request_header_scan > scan_start
            if self.request_header_scan > header_limit or len(self.input) > header_limit:
                self.request_header_scan = -1
                self.request_header_deadline = 0.0
                return True
            return False
        if size == 0:
            self.request_capture_error = "truncated HTTP request"
        else:
            var error = get_errno()
            if error == ErrNo.EAGAIN or error == ErrNo.EINTR:
                return False
            self.request_capture_error = "loopback HTTP request read failed"
        self.request_header_scan = -1
        self.request_header_deadline = 0.0
        return True

    def request_ready(mut self) raises -> Bool:
        if self.fd < 0 or self.done:
            return False
        if len(self.input) > 0:
            return True
        var byte: UInt8 = 0
        var result = recv(self.fd, Pointer(to=byte), 1, MSG_PEEK | MSG_DONTWAIT)
        if result > 0:
            return True
        if result == 0:
            return False
        var error = get_errno()
        if error == ErrNo.EAGAIN or error == ErrNo.EINTR or error == ErrNo.ECONNRESET:
            return False
        raise Error("loopback HTTP peer check failed")

    def read_request(mut self, timeout_ms: UInt64, max_body_bytes: Int = HTTP_DEFAULT_BODY_LIMIT, allow_upgrade_headers: Bool = False, validate_request_target: Bool = False, reject_chunked_trailers: Bool = False, defer_expectation_errors: Bool = False, preflight_body_limit_before_continue: Bool = False, use_request_version_for_continue: Bool = False, use_request_version_for_response: Bool = False, request_header_limit: Int = HTTP_HEADER_LIMIT) raises -> LoopbackHTTPRequest:
        if self.fd < 0 or self.done or self.request_read:
            raise Error("loopback HTTP connection is closed")
        self.request_head_parsed = False
        self.request_body_deferred = False
        if self.request_capture_error:
            raise Error(self.request_capture_error)
        self.request_header_scan = 0
        self.keep_alive = False
        self.waiting_for_request = False
        if max_body_bytes < 0 or max_body_bytes > HTTP_MAX_BODY_LIMIT:
            raise Error("invalid or unsupported HTTP request body limit")
        if request_header_limit < 0 or request_header_limit > HTTP_MAX_REQUEST_HEADER_LIMIT:
            raise Error("invalid or unsupported HTTP request header limit")
        var deadline = _deadline(timeout_ms)
        var wire_limit = request_header_limit * 2 + max_body_bytes * 8
        var header_scan = 0
        var header_end = _header_end(self.input, header_scan)
        while header_end < 0:
            if len(self.input) > request_header_limit:
                raise Error("HTTP request headers exceed limit")
            header_scan = max(0, len(self.input) - 3)
            self._receive(deadline, wire_limit)
            header_end = _header_end(self.input, header_scan)
        if header_end > request_header_limit:
            raise Error("HTTP request headers exceed limit")
        # The relay caps target bytes, so its request line also includes method and version bytes.
        var max_request_line_bytes = HTTP_HEADER_LIMIT if validate_request_target else 8192
        if use_request_version_for_response:
            self.response_version = _request_line_version(self.input, max_request_line_bytes)
        var head = _parse_request_head(self.input, header_end, allow_upgrade_headers, max_request_line_bytes, defer_expectation_errors)
        self.request_head_parsed = True
        self.request_body_deferred = defer_expectation_errors and (head.expect_continue or head.chunked or head.length > HTTP_DEFERRED_BODY_THRESHOLD)
        self.head_request = head.method == "HEAD"
        if head.unsupported_expectation:
            raise Error("unsupported HTTP expectation")
        var upgrade_body = False
        var saw_connection = False
        var websocket_upgrade = False
        if allow_upgrade_headers and defer_expectation_errors:
            for header in head.headers:
                var name = String(header[0]).lower()
                var value = String(header[1]).lower()
                if name == "connection" and not saw_connection:
                    saw_connection = True
                    upgrade_body = "upgrade" in value
                elif name == "upgrade" and value == "websocket":
                    websocket_upgrade = True
            upgrade_body = upgrade_body and not websocket_upgrade
        if validate_request_target and not request_target_valid(head.target) and (head.expect_continue or head.length > max_body_bytes or (defer_expectation_errors and head.length > HTTP_DEFERRED_BODY_THRESHOLD)):
            raise Error("invalid HTTP request target")
        if defer_expectation_errors and (head.expect_continue or head.chunked or head.length > HTTP_DEFERRED_BODY_THRESHOLD):
            for header in head.headers:
                if String(header[0]).lower() == "upgrade" and String(header[1]).lower() == "websocket":
                    raise Error("websocket upgrade fallback")
        if preflight_body_limit_before_continue and head.length > max_body_bytes:
            raise Error("oversized HTTP request body")
        var body_start = header_end + 4
        var request_end = body_start
        var body = List[UInt8]()
        if upgrade_body and validate_request_target and not request_target_valid(head.target):
            self.request_read = True
            return LoopbackHTTPRequest(head.method, head.target, head.headers.copy(), body^)
        if validate_request_target and reject_chunked_trailers and head.chunked and not request_target_valid(head.target):
            self.request_read = True
            return LoopbackHTTPRequest(head.method, head.target, head.headers.copy(), body^)
        if head.expect_continue:
            var continue_version = "HTTP/1.1"
            if use_request_version_for_continue:
                continue_version = head.version
            _send_all(self.fd, _bytes(continue_version + " 100 Continue\r\n\r\n"), deadline)
            self.expect_continue_sent = True
        if upgrade_body:
            while True:
                if len(self.input) - body_start > max_body_bytes:
                    raise Error("oversized HTTP request body")
                try:
                    self._receive(deadline, wire_limit)
                except error:
                    if String(error) == "truncated HTTP request":
                        break
                    raise
            request_end = len(self.input)
            for index in range(body_start, request_end):
                body.append(self.input[index])
        elif head.chunked:
            body = self._read_chunked(body_start, max_body_bytes, deadline, wire_limit, request_end, validate_request_target and not request_target_valid(head.target), reject_chunked_trailers, self.keep_alive_enabled)
        elif head.length >= 0:
            if head.length > max_body_bytes:
                raise Error("oversized HTTP request body")
            var body_end = body_start + head.length
            while len(self.input) < body_end:
                self._receive(deadline, wire_limit)
            if len(self.input) != body_end and not self.keep_alive_enabled:
                raise Error("pipelined HTTP requests are unsupported")
            request_end = body_end
            for index in range(body_start, body_end):
                body.append(self.input[index])
        elif len(self.input) != body_start and not self.keep_alive_enabled:
            raise Error("request body requires Content-Length or chunked framing")
        if self.keep_alive_enabled:
            self.input = self.input[request_end:len(self.input):1]
            self.wire_bytes = len(self.input)
        self.request_read = True
        if self.keep_alive_enabled and not upgrade_body:
            self.keep_alive = _request_keep_alive(head.version, head.headers)
        self.request_header_scan = 0
        return LoopbackHTTPRequest(head.method, head.target, head.headers.copy(), body^)

    def respond(mut self, status: Int, headers: List[Tuple[String, String]], body: List[UInt8], timeout_ms: UInt64, include_bodyless_length: Bool = False, bodyless_chunked: Bool = False) raises:
        try:
            # The 0.439.2 SSE passthrough writes a chunked header with no body.
            if bodyless_chunked and ((status != 204 and status != 304) or include_bodyless_length):
                raise Error("chunked bodyless framing requires an empty 204/304 response")
            if len(body) > HTTP_MAX_RESPONSE_BODY_BYTES:
                raise Error("oversized HTTP response body")
            if (status == 204 or status == 304) and len(body) != 0:
                raise Error("HTTP response status forbids a body")
            var response_version = self.response_version
            if bodyless_chunked:
                response_version = "HTTP/1.1"
            var response = _response_head(
                status, headers, len(body), False, include_bodyless_length,
                bodyless_chunked, response_version, not self.keep_alive_enabled,
                self.include_default_response_headers,
            )
            var deadline = _deadline(timeout_ms)
            _send_all(self.fd, response, deadline)
            if not self.head_request:
                _send_all(self.fd, body, deadline)
            if bodyless_chunked:
                _send_all(self.fd, _bytes("0\r\n\r\n"), deadline)
            self._finish_response()
        except:
            self.close()
            raise

    def start_stream(mut self, status: Int, headers: List[Tuple[String, String]], timeout_ms: UInt64) raises:
        try:
            if self.streaming or self.done:
                raise Error("loopback HTTP response stream already started")
            if status == 204 or status == 304:
                raise Error("HTTP response status forbids a stream body")
            var response = _response_head(
                status, headers, 0, True, False, False, "HTTP/1.1",
                not self.keep_alive_enabled,
            )
            _send_all(self.fd, response, _deadline(timeout_ms))
            self.streaming = True
        except:
            self.close()
            raise

    def write_chunk(mut self, bytes: List[UInt8], timeout_ms: UInt64) raises:
        try:
            if not self.streaming or self.done:
                raise Error("loopback HTTP response stream is not active")
            if len(bytes) == 0:
                return
            if len(bytes) > HTTP_MAX_BODY_LIMIT:
                raise Error("oversized HTTP response stream chunk")
            if self.head_request:
                if self.client_disconnected():
                    raise Error("loopback HTTP response write failed")
                return
            var framed = _chunk_frame(bytes)
            _send_all(self.fd, framed, _deadline(timeout_ms))
        except:
            self.close()
            raise

    def finish_stream(mut self, timeout_ms: UInt64, include_head_terminal_chunk: Bool = False) raises:
        try:
            if not self.streaming or self.done:
                raise Error("loopback HTTP response stream is not active")
            var final = List[UInt8]()
            if not self.head_request or include_head_terminal_chunk:
                for byte in "0\r\n\r\n".as_bytes():
                    final.append(byte)
                _send_all(self.fd, final, _deadline(timeout_ms))
            self._finish_response()
        except:
            self.close()
            raise

    def _receive(mut self, deadline: Float64, wire_limit: Int) raises:
        var buffer = List[UInt8](length=8192, fill=0)
        while True:
            if perf_counter() >= deadline:
                raise Error("loopback HTTP request timed out")
            var size = recv(self.fd, buffer.unsafe_ptr(), UInt(len(buffer)), MSG_DONTWAIT)
            if size > 0:
                var count = Int(size)
                if self.wire_bytes > wire_limit - count:
                    raise Error("HTTP request exceeds wire limit")
                self.wire_bytes += count
                for index in range(count):
                    self.input.append(buffer[index])
                return
            if size == 0:
                raise Error("truncated HTTP request")
            var error = get_errno()
            if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                raise Error("loopback HTTP request read failed")
            sleep(0.001)

    def _finish_response(mut self):
        if not self.keep_alive:
            self.close()
            return
        self.streaming = False
        self.request_read = False
        self.head_request = False
        self.expect_continue_sent = False
        self.response_version = "HTTP/1.1"
        self.waiting_for_request = True
        self.request_header_scan = 0
        self.request_header_deadline = 0.0
        self.request_capture_error = ""
        self.request_capture_progress = False
        self.request_head_parsed = False
        self.request_body_deferred = False

    def _read_chunked(mut self, start: Int, max_body_bytes: Int, deadline: Float64, wire_limit: Int, mut request_end: Int, invalid_target_before_body_limit: Bool = False, reject_trailers: Bool = False, allow_pipelining: Bool = False) raises -> List[UInt8]:
        var output = List[UInt8]()
        var cursor = start
        var trailer_start: Int
        while True:
            var line_scan = cursor
            var line_end = _line_end(self.input, line_scan)
            while line_end < 0:
                if len(self.input) - cursor > HTTP_HEADER_LIMIT:
                    raise Error("HTTP chunk-size line exceeds limit")
                line_scan = max(cursor, len(self.input) - 1)
                self._receive(deadline, wire_limit)
                line_end = _line_end(self.input, line_scan)
            if line_end - cursor > HTTP_HEADER_LIMIT:
                raise Error("HTTP chunk-size line exceeds limit")
            var size_line = _ascii(self.input, cursor, line_end)
            for byte in size_line.as_bytes():
                if byte < 32 or byte == 127:
                    raise Error("malformed HTTP chunk-size line")
            var semicolon = size_line.find(";")
            var size_text = String(size_line[byte=:semicolon]) if semicolon >= 0 else size_line
            var size = _hex(size_text)
            cursor = line_end + 2
            if size == 0:
                trailer_start = cursor
                break
            if size > max_body_bytes - len(output):
                if invalid_target_before_body_limit:
                    raise Error("invalid HTTP request target")
                raise Error("oversized HTTP request body")
            var chunk_end = cursor + size
            while len(self.input) < chunk_end + 2:
                self._receive(deadline, wire_limit)
            for index in range(cursor, chunk_end):
                output.append(self.input[index])
            if self.input[chunk_end] != 13 or self.input[chunk_end + 1] != 10:
                raise Error("malformed HTTP chunk terminator")
            cursor = chunk_end + 2
        var trailer_bytes = 0
        cursor = trailer_start
        if reject_trailers:
            while len(self.input) < cursor + 1:
                try:
                    self._receive(deadline, wire_limit)
                except:
                    raise Error("truncated HTTP chunk trailer terminator")
            if self.input[cursor] != 13:
                raise Error("HTTP request trailers are unsupported")
            while len(self.input) < cursor + 2:
                try:
                    self._receive(deadline, wire_limit)
                except:
                    raise Error("truncated HTTP chunk trailer terminator")
            if self.input[cursor + 1] != 10:
                raise Error("malformed HTTP chunk trailer terminator")
            cursor += 2
            if len(self.input) != cursor and not allow_pipelining:
                raise Error("pipelined HTTP requests are unsupported")
            request_end = cursor
            return output^
        while True:
            var trailer_scan = cursor
            var end = _line_end(self.input, trailer_scan)
            while end < 0:
                if trailer_bytes + len(self.input) - cursor > HTTP_HEADER_LIMIT:
                    raise Error("HTTP trailers exceed limit")
                trailer_scan = max(cursor, len(self.input) - 1)
                self._receive(deadline, wire_limit)
                end = _line_end(self.input, trailer_scan)
            if trailer_bytes + end - cursor + 2 > HTTP_HEADER_LIMIT:
                raise Error("HTTP trailers exceed limit")
            if end == cursor:
                cursor += 2
                break
            _validate_header_line(self.input, cursor, end)
            var trailer = _ascii(self.input, cursor, end)
            var colon = trailer.find(":")
            var name = String(trailer[byte=:colon]).lower()
            if name == "content-length" or name == "transfer-encoding" or name == "host" or name == "connection":
                raise Error("forbidden HTTP trailer field")
            trailer_bytes += end - cursor + 2
            cursor = end + 2
        if len(self.input) != cursor and not allow_pipelining:
            raise Error("pipelined HTTP requests are unsupported")
        request_end = cursor
        return output^


@fieldwise_init
struct ParsedRequestHead(Movable):
    var method: String
    var target: String
    var version: String
    var headers: List[Tuple[String, String]]
    var length: Int
    var chunked: Bool
    var expect_continue: Bool
    var unsupported_expectation: Bool


def _parse_request_head(bytes: List[UInt8], end: Int, allow_upgrade_headers: Bool, max_request_line_bytes: Int, defer_expectation_errors: Bool = False) raises -> ParsedRequestHead:
    var head = _ascii(bytes, 0, end)
    var lines = head.split("\r\n")
    if not lines or lines[0].byte_length() > max_request_line_bytes:
        raise Error("malformed HTTP request line")
    var request_line = lines[0].split(" ")
    var malformed_suffix = False
    if len(request_line) > 3:
        var last = String(request_line[len(request_line) - 1])
        if last == "HTTP/1.0" or last == "HTTP/1.1":
            raise Error("malformed HTTP request target spacing")
        if defer_expectation_errors:
            malformed_suffix = True
        else:
            raise Error("malformed HTTP request line suffix")
    if (len(request_line) != 3 and not malformed_suffix) or request_line[0].byte_length() == 0 or request_line[1].byte_length() == 0:
        raise Error("malformed HTTP request line")
    var version = String(request_line[2])
    if version != "HTTP/1.0" and version != "HTTP/1.1":
        raise Error("unsupported HTTP request version")
    for byte in request_line[0].as_bytes():
        if not _http_token_byte(byte):
            raise Error("malformed HTTP method")
    var malformed_target = False
    for byte in request_line[1].as_bytes():
        if byte <= 32 or byte == 127 or byte == 35:
            if defer_expectation_errors:
                malformed_target = True
            else:
                raise Error("malformed HTTP request target")
    var headers = List[Tuple[String, String]]()
    var content_length = -1
    var has_content_length = False
    var has_transfer_encoding = False
    var chunked = False
    var has_host = False
    var expect_continue = False
    var unsupported_expectation = False
    var has_connection_upgrade = False
    var has_non_websocket_upgrade = False
    var offset = lines[0].byte_length() + 2
    for index in range(1, len(lines)):
        var line = lines[index]
        if line.byte_length() == 0:
            continue
        var colon = line.find(":")
        if colon <= 0:
            raise Error("malformed HTTP request header")
        _validate_header_line(bytes, offset, offset + line.byte_length())
        offset += line.byte_length() + 2
        var name = String(line[byte=:colon])
        var lower = name.lower()
        var value = String(line[byte=colon + 1:].strip(" \t"))
        if lower == "content-length":
            if has_content_length:
                raise Error("duplicate HTTP content length")
            has_content_length = True
            content_length = _number(value)
        elif lower == "transfer-encoding":
            if has_transfer_encoding:
                raise Error("duplicate HTTP transfer encoding")
            has_transfer_encoding = True
            if value.lower() != "chunked":
                raise Error("unsupported HTTP transfer encoding")
            chunked = True
        elif lower == "host":
            if has_host or not value:
                raise Error("invalid HTTP host header")
            has_host = True
        elif lower == "expect":
            if expect_continue or value.lower() != "100-continue":
                if defer_expectation_errors:
                    unsupported_expectation = True
                else:
                    raise Error("unsupported HTTP expectation")
            else:
                expect_continue = True
        elif lower == "connection":
            for token in value.split(","):
                if String(token).strip(" \t").lower() == "upgrade":
                    has_connection_upgrade = True
        elif lower == "upgrade":
            if not allow_upgrade_headers:
                raise Error("HTTP protocol upgrades are unsupported")
            if value.lower() != "websocket":
                has_non_websocket_upgrade = True
        headers.append((name, value))
    if has_content_length and has_transfer_encoding:
        raise Error("ambiguous HTTP request framing")
    if defer_expectation_errors:
        if unsupported_expectation:
            return ParsedRequestHead(String(request_line[0]), String(request_line[1]), version, headers^, content_length, chunked, expect_continue, True)
        if malformed_suffix:
            raise Error("malformed HTTP request line suffix")
        if malformed_target:
            raise Error("malformed HTTP request target")
    if has_connection_upgrade and has_non_websocket_upgrade and not defer_expectation_errors:
        raise Error("HTTP protocol upgrades are unsupported")
    if version == "HTTP/1.1" and not has_host:
        raise Error("HTTP/1.1 request requires Host")
    return ParsedRequestHead(String(request_line[0]), String(request_line[1]), version, headers^, content_length, chunked, expect_continue, False)


def _request_target_hex(value: UInt8) -> Int:
    var byte = Int(value)
    if 48 <= byte <= 57: return byte - 48
    if 65 <= byte <= 70: return byte - 55
    if 97 <= byte <= 102: return byte - 87
    return -1


def request_target_valid(target: String) -> Bool:
    var length = target.byte_length()
    if length == 0 or length > 8192:
        return False
    var bytes = target.as_bytes()
    if bytes[0] != 47 or (length > 1 and bytes[1] == 47):
        return False

    var path_length = length
    var index = 0
    while index < length:
        var byte = Int(bytes[index])
        if byte > 127 or byte <= 32 or byte == 127 or byte == 35 or byte == 92:
            return False
        if byte == 63:
            path_length = index
            break
        index += 1

    index = path_length
    while index < length:
        var byte = Int(bytes[index])
        if byte > 127 or byte <= 32 or byte == 127 or byte == 35:
            return False
        index += 1

    var segment_start = 0
    index = 0
    while index <= path_length:
        if index == path_length or bytes[index] == 47:
            var segment_length = index - segment_start
            if (
                segment_length == 1 and bytes[segment_start] == 46
            ) or (
                segment_length == 2 and bytes[segment_start] == 46
                and bytes[segment_start + 1] == 46
            ):
                return False
            if index < path_length and index > 0 and bytes[index - 1] == 47:
                return False
            segment_start = index + 1
        index += 1

    index = 0
    while index < length:
        if bytes[index] != 37:
            index += 1
            continue
        if index + 2 >= length:
            return False
        var high = _request_target_hex(bytes[index + 1])
        var low = _request_target_hex(bytes[index + 2])
        if high < 0 or low < 0:
            return False
        var decoded = (high << 4) | low
        if index < path_length and (
            decoded >= 128 or decoded <= 32 or decoded == 127
            or decoded == 47 or decoded == 92 or decoded == 37
            or decoded == 63 or decoded == 35 or decoded == 46
        ):
            return False
        index += 3
    return True


def _validate_header_line(bytes: List[UInt8], start: Int, end: Int) raises:
    var colon = -1
    for index in range(start, end):
        if bytes[index] == 58 and colon < 0:
            colon = index
        if bytes[index] == 9:
            continue
        if bytes[index] < 32 or bytes[index] == 127:
            raise Error("malformed HTTP header value")
    if colon <= start:
        raise Error("malformed HTTP header name")
    for index in range(start, colon):
        if not _http_token_byte(bytes[index]):
            raise Error("malformed HTTP header name")


def _header_end(bytes: List[UInt8], start: Int = 0, end: Int = -1) -> Int:
    var limit = len(bytes) if end < 0 else min(len(bytes), end)
    if limit < 4:
        return -1
    for index in range(max(0, start), limit - 3):
        if bytes[index] == 13 and bytes[index + 1] == 10 and bytes[index + 2] == 13 and bytes[index + 3] == 10:
            return index
    return -1


def _line_end(bytes: List[UInt8], start: Int) -> Int:
    for index in range(max(0, start), len(bytes) - 1):
        if bytes[index] == 13 and bytes[index + 1] == 10:
            return index
    return -1


def _request_line_version(bytes: List[UInt8], max_request_line_bytes: Int) -> String:
    var line_end = _line_end(bytes, 0)
    if line_end <= 0 or line_end > max_request_line_bytes:
        return "HTTP/1.1"
    var line: String
    try:
        line = _ascii(bytes, 0, line_end)
    except:
        return "HTTP/1.1"
    var parts = line.split(" ")
    if len(parts) < 3 or parts[0].byte_length() == 0 or parts[1].byte_length() == 0:
        return "HTTP/1.1"
    for byte in parts[0].as_bytes():
        if not _http_token_byte(byte):
            return "HTTP/1.1"
    var version = String(parts[2])
    if version == "HTTP/1.0" or version == "HTTP/1.1":
        return version
    return "HTTP/1.1"


def _request_keep_alive(version: String, headers: List[Tuple[String, String]]) -> Bool:
    var connection = String()
    for name, value in headers:
        if name.lower() == "connection":
            connection = value.lower()
            break
    if "close" in connection or "upgrade" in connection:
        return False
    if version == "HTTP/1.0":
        return "keep-alive" in connection
    return True


def _ascii(bytes: List[UInt8], start: Int, end: Int) raises -> String:
    var value = List[UInt8]()
    for index in range(start, end):
        if bytes[index] > 127:
            raise Error("non-ASCII byte in HTTP header")
        value.append(bytes[index])
    return String(from_utf8=Span(value))


def _response_head(status: Int, headers: List[Tuple[String, String]], body_length: Int, chunked: Bool, include_bodyless_length: Bool = False, bodyless_chunked: Bool = False, version: String = "HTTP/1.1", include_connection_close: Bool = True, include_default_headers: Bool = False) raises -> List[UInt8]:
    if status < 200 or status > 599:
        raise Error("invalid final HTTP response status")
    var output = List[UInt8]()
    var text = version + " " + String(status) + " " + _reason(status) + "\r\n"
    for byte in text.as_bytes():
        output.append(byte)

    var has_date = False
    var has_server = False
    for name, value in headers:
        _validate_response_header(name, value)
        var lower = name.lower()
        if lower == "date": has_date = True
        elif lower == "server": has_server = True
        if lower == "content-length" or lower == "transfer-encoding" or lower == "connection" or lower == "trailer" or lower == "upgrade" or lower == "keep-alive" or lower == "proxy-connection":
            raise Error("caller-controlled HTTP response framing header is forbidden")

    var header_bytes = len(output)
    if include_default_headers and not has_server:
        text = "Server: tiny-http (Rust)\r\n"
        if header_bytes + text.byte_length() + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        header_bytes += text.byte_length()
        for byte in text.as_bytes(): output.append(byte)
    if include_default_headers and not has_date:
        var nanoseconds = _realtime_nanoseconds()
        text = "Date: " + format_http_date(nanoseconds // 1_000_000_000) + "\r\n"
        if header_bytes + text.byte_length() + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        header_bytes += text.byte_length()
        for byte in text.as_bytes(): output.append(byte)

    if include_default_headers:
        for name, value in headers:
            var line = name + ": " + value + "\r\n"
            header_bytes += line.byte_length()
            if header_bytes + 2 > HTTP_HEADER_LIMIT:
                raise Error("HTTP response headers exceed limit")
            for byte in line.as_bytes(): output.append(byte)

    if not chunked and not bodyless_chunked and (status != 204 and status != 304 or include_bodyless_length):
        text = "Content-Length: " + String(body_length) + "\r\n"
        if header_bytes + text.byte_length() + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        header_bytes += text.byte_length()
        for byte in text.as_bytes(): output.append(byte)
    if chunked or bodyless_chunked:
        text = "Transfer-Encoding: chunked\r\n"
        if header_bytes + text.byte_length() + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        header_bytes += text.byte_length()
        for byte in text.as_bytes(): output.append(byte)
    if include_connection_close:
        text = "Connection: close\r\n"
        if header_bytes + text.byte_length() + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        header_bytes += text.byte_length()
        for byte in text.as_bytes(): output.append(byte)

    if not include_default_headers:
        for name, value in headers:
            var line = name + ": " + value + "\r\n"
            header_bytes += line.byte_length()
            if header_bytes + 2 > HTTP_HEADER_LIMIT:
                raise Error("HTTP response headers exceed limit")
            for byte in line.as_bytes(): output.append(byte)
    for byte in "\r\n".as_bytes():
        output.append(byte)
    return output^


def _bytes(text: String) -> List[UInt8]:
    var output = List[UInt8]()
    for byte in text.as_bytes():
        output.append(byte)
    return output^


def _validate_response_header(name: String, value: String) raises:
    if name.byte_length() == 0:
        raise Error("invalid HTTP response header name")
    for byte in name.as_bytes():
        if not _http_token_byte(byte):
            raise Error("invalid HTTP response header name")
    for byte in value.as_bytes():
        if (byte < 32 and byte != 9) or byte == 127:
            raise Error("invalid HTTP response header value")


def _chunk_frame(bytes: List[UInt8]) -> List[UInt8]:
    var alphabet = String("0123456789ABCDEF")
    var digits = List[UInt8]()
    var size = len(bytes)
    while size > 0:
        digits.append(alphabet.as_bytes()[size & 15])
        size = size >> 4
    var output = List[UInt8]()
    for index in range(len(digits) - 1, -1, -1):
        output.append(digits[index])
    output.append(13)
    output.append(10)
    output.extend(bytes.copy())
    output.append(13)
    output.append(10)
    return output^


def _send_all(fd: Int32, bytes: List[UInt8], deadline: Float64) raises:
    var sent = 0
    while sent < len(bytes):
        if perf_counter() >= deadline:
            raise Error("loopback HTTP response write timed out")
        var count = send(fd, bytes.unsafe_ptr().unsafe_offset(sent), UInt(len(bytes) - sent), MSG_DONTWAIT | MSG_NOSIGNAL)
        if count > 0:
            sent += Int(count)
        else:
            var error = get_errno()
            if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                raise Error("loopback HTTP response write failed")
            sleep(0.001)


def _configure_fd(fd: Int32) raises:
    if fcntl(fd, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
        raise Error("failed to set loopback socket close-on-exec")
    var flags = fcntl(fd, F_GETFL)
    if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
        raise Error("failed to set loopback socket nonblocking")


def _deadline(timeout_ms: UInt64) -> Float64:
    return perf_counter() + Float64(timeout_ms) / 1000.0


def _number(text: StringSlice) raises -> Int:
    if text.byte_length() == 0:
        raise Error("invalid HTTP decimal number")
    var value = 0
    for byte in text.as_bytes():
        if byte < 48 or byte > 57:
            raise Error("invalid HTTP decimal number")
        var digit = Int(byte - 48)
        if value > 214748364 or (value == 214748364 and digit > 7):
            raise Error("HTTP decimal number exceeds limit")
        value = value * 10 + digit
    return value


def _hex(text: StringSlice) raises -> Int:
    if text.byte_length() == 0:
        raise Error("invalid HTTP chunk size")
    var value = 0
    for byte in text.as_bytes():
        var digit = -1
        if byte >= 48 and byte <= 57:
            digit = Int(byte - 48)
        elif byte >= 65 and byte <= 70:
            digit = Int(byte - 55)
        elif byte >= 97 and byte <= 102:
            digit = Int(byte - 87)
        if digit < 0 or value > 134217727 or (value == 134217727 and digit > 15):
            raise Error("invalid or oversized HTTP chunk size")
        value = value * 16 + digit
    return value


def _http_token_byte(byte: UInt8) -> Bool:
    return (
        (byte >= 48 and byte <= 57) or (byte >= 65 and byte <= 90) or
        (byte >= 97 and byte <= 122) or byte == 33 or byte == 35 or
        byte == 36 or byte == 37 or byte == 38 or byte == 39 or byte == 42 or
        byte == 43 or byte == 45 or byte == 46 or byte == 94 or byte == 95 or
        byte == 96 or byte == 124 or byte == 126
    )


def _port_bytes(port: Int) -> UInt16:
    comptime if Endian.native() == Endian.little:
        return byte_swap(UInt16(port))
    else:
        return UInt16(port)


def _host_port(port: UInt16) -> UInt16:
    comptime if Endian.native() == Endian.little:
        return byte_swap(port)
    else:
        return port


def _network32(value: UInt32) -> UInt32:
    comptime if Endian.native() == Endian.little:
        return byte_swap(value)
    else:
        return value


def _reason(status: Int) -> String:
    if status == 200:
        return "OK"
    if status == 201:
        return "Created"
    if status == 202:
        return "Accepted"
    if status == 203:
        return "Non-Authoritative Information"
    if status == 204:
        return "No Content"
    if status == 205:
        return "Reset Content"
    if status == 206:
        return "Partial Content"
    if status == 207:
        return "Multi-Status"
    if status == 208:
        return "Already Reported"
    if status == 226:
        return "IM Used"
    if status == 300:
        return "Multiple Choices"
    if status == 301:
        return "Moved Permanently"
    if status == 302:
        return "Found"
    if status == 303:
        return "See Other"
    if status == 304:
        return "Not Modified"
    if status == 305:
        return "Use Proxy"
    if status == 307:
        return "Temporary Redirect"
    if status == 308:
        return "Permanent Redirect"
    if status == 400:
        return "Bad Request"
    if status == 401:
        return "Unauthorized"
    if status == 402:
        return "Payment Required"
    if status == 403:
        return "Forbidden"
    if status == 404:
        return "Not Found"
    if status == 405:
        return "Method Not Allowed"
    if status == 406:
        return "Not Acceptable"
    if status == 407:
        return "Proxy Authentication Required"
    if status == 408:
        return "Request Timeout"
    if status == 409:
        return "Conflict"
    if status == 410:
        return "Gone"
    if status == 411:
        return "Length Required"
    if status == 412:
        return "Precondition Failed"
    if status == 413:
        return "Payload Too Large"
    if status == 414:
        return "URI Too Long"
    if status == 415:
        return "Unsupported Media Type"
    if status == 416:
        return "Range Not Satisfiable"
    if status == 417:
        return "Expectation Failed"
    if status == 421:
        return "Misdirected Request"
    if status == 422:
        return "Unprocessable Entity"
    if status == 423:
        return "Locked"
    if status == 424:
        return "Failed Dependency"
    if status == 426:
        return "Upgrade Required"
    if status == 428:
        return "Precondition Required"
    if status == 429:
        return "Too Many Requests"
    if status == 431:
        return "Request Header Fields Too Large"
    if status == 451:
        return "Unavailable For Legal Reasons"
    if status == 500:
        return "Internal Server Error"
    if status == 501:
        return "Not Implemented"
    if status == 502:
        return "Bad Gateway"
    if status == 503:
        return "Service Unavailable"
    if status == 504:
        return "Gateway Timeout"
    if status == 505:
        return "HTTP Version Not Supported"
    if status == 506:
        return "Variant Also Negotiates"
    if status == 507:
        return "Insufficient Storage"
    if status == 508:
        return "Loop Detected"
    if status == 510:
        return "Not Extended"
    if status == 511:
        return "Network Authentication Required"
    return "Unknown"
