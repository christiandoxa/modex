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

comptime HTTP_HEADER_LIMIT = 65536
comptime HTTP_DEFAULT_BODY_LIMIT = 64 * 1024 * 1024
comptime HTTP_MAX_BODY_LIMIT = 64 * 1024 * 1024
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
    var done: Bool

    def __init__(out self, fd: Int32):
        self.fd = fd
        self.input = List[UInt8]()
        self.wire_bytes = 0
        self.streaming = False
        self.request_read = False
        self.done = False

    def close(mut self):
        if self.fd >= 0:
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

    def read_request(mut self, timeout_ms: UInt64, max_body_bytes: Int = HTTP_DEFAULT_BODY_LIMIT) raises -> LoopbackHTTPRequest:
        if self.fd < 0 or self.done or self.request_read:
            raise Error("loopback HTTP connection is closed")
        if max_body_bytes < 0 or max_body_bytes > HTTP_MAX_BODY_LIMIT:
            raise Error("invalid or unsupported HTTP request body limit")
        var deadline = _deadline(timeout_ms)
        var wire_limit = HTTP_HEADER_LIMIT * 2 + max_body_bytes * 8
        var header_scan = 0
        var header_end = _header_end(self.input, header_scan)
        while header_end < 0:
            if len(self.input) > HTTP_HEADER_LIMIT:
                raise Error("HTTP request headers exceed limit")
            header_scan = max(0, len(self.input) - 3)
            self._receive(deadline, wire_limit)
            header_end = _header_end(self.input, header_scan)
        if header_end > HTTP_HEADER_LIMIT:
            raise Error("HTTP request headers exceed limit")
        var head = _parse_request_head(self.input, header_end)
        var body_start = header_end + 4
        var body = List[UInt8]()
        if head.expect_continue:
            _send_all(self.fd, _bytes("HTTP/1.1 100 Continue\r\n\r\n"), deadline)
        if head.chunked:
            body = self._read_chunked(body_start, max_body_bytes, deadline, wire_limit)
        elif head.length >= 0:
            if head.length > max_body_bytes:
                raise Error("oversized HTTP request body")
            var body_end = body_start + head.length
            while len(self.input) < body_end:
                self._receive(deadline, wire_limit)
            if len(self.input) != body_end:
                raise Error("pipelined HTTP requests are unsupported")
            for index in range(body_start, body_end):
                body.append(self.input[index])
        elif len(self.input) != body_start:
            raise Error("request body requires Content-Length or chunked framing")
        self.request_read = True
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
            var response = _response_head(status, headers, len(body), False, include_bodyless_length, bodyless_chunked)
            var deadline = _deadline(timeout_ms)
            _send_all(self.fd, response, deadline)
            _send_all(self.fd, body, deadline)
            if bodyless_chunked:
                _send_all(self.fd, _bytes("0\r\n\r\n"), deadline)
            self.close()
        except:
            self.close()
            raise

    def start_stream(mut self, status: Int, headers: List[Tuple[String, String]], timeout_ms: UInt64) raises:
        try:
            if self.streaming or self.done:
                raise Error("loopback HTTP response stream already started")
            if status == 204 or status == 304:
                raise Error("HTTP response status forbids a stream body")
            var response = _response_head(status, headers, 0, True)
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
            var framed = _chunk_frame(bytes)
            _send_all(self.fd, framed, _deadline(timeout_ms))
        except:
            self.close()
            raise

    def finish_stream(mut self, timeout_ms: UInt64) raises:
        try:
            if not self.streaming or self.done:
                raise Error("loopback HTTP response stream is not active")
            var final = List[UInt8]()
            for byte in "0\r\n\r\n".as_bytes():
                final.append(byte)
            _send_all(self.fd, final, _deadline(timeout_ms))
            self.close()
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

    def _read_chunked(mut self, start: Int, max_body_bytes: Int, deadline: Float64, wire_limit: Int) raises -> List[UInt8]:
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
        if len(self.input) != cursor:
            raise Error("pipelined HTTP requests are unsupported")
        return output^


@fieldwise_init
struct ParsedRequestHead(Movable):
    var method: String
    var target: String
    var headers: List[Tuple[String, String]]
    var length: Int
    var chunked: Bool
    var expect_continue: Bool


def _parse_request_head(bytes: List[UInt8], end: Int) raises -> ParsedRequestHead:
    var head = _ascii(bytes, 0, end)
    var lines = head.split("\r\n")
    if not lines or lines[0].byte_length() > 8192:
        raise Error("malformed HTTP request line")
    var request_line = lines[0].split(" ")
    if len(request_line) != 3 or request_line[0].byte_length() == 0 or request_line[1].byte_length() == 0:
        raise Error("malformed HTTP request line")
    var version = String(request_line[2])
    if version != "HTTP/1.0" and version != "HTTP/1.1":
        raise Error("unsupported HTTP request version")
    for byte in request_line[0].as_bytes():
        if not _http_token_byte(byte):
            raise Error("malformed HTTP method")
    for byte in request_line[1].as_bytes():
        if byte <= 32 or byte == 127 or byte == 35:
            raise Error("malformed HTTP request target")
    var headers = List[Tuple[String, String]]()
    var content_length = -1
    var has_content_length = False
    var has_transfer_encoding = False
    var chunked = False
    var has_host = False
    var expect_continue = False
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
                raise Error("unsupported HTTP expectation")
            expect_continue = True
        elif lower == "upgrade":
            raise Error("HTTP protocol upgrades are unsupported")
        headers.append((name, value))
    if has_content_length and has_transfer_encoding:
        raise Error("ambiguous HTTP request framing")
    if version == "HTTP/1.1" and not has_host:
        raise Error("HTTP/1.1 request requires Host")
    return ParsedRequestHead(String(request_line[0]), String(request_line[1]), headers^, content_length, chunked, expect_continue)


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


def _header_end(bytes: List[UInt8], start: Int = 0) -> Int:
    if len(bytes) < 4:
        return -1
    for index in range(max(0, start), len(bytes) - 3):
        if bytes[index] == 13 and bytes[index + 1] == 10 and bytes[index + 2] == 13 and bytes[index + 3] == 10:
            return index
    return -1


def _line_end(bytes: List[UInt8], start: Int) -> Int:
    for index in range(max(0, start), len(bytes) - 1):
        if bytes[index] == 13 and bytes[index + 1] == 10:
            return index
    return -1


def _ascii(bytes: List[UInt8], start: Int, end: Int) raises -> String:
    var value = List[UInt8]()
    for index in range(start, end):
        if bytes[index] > 127:
            raise Error("non-ASCII byte in HTTP header")
        value.append(bytes[index])
    return String(from_utf8=Span(value))


def _response_head(status: Int, headers: List[Tuple[String, String]], body_length: Int, chunked: Bool, include_bodyless_length: Bool = False, bodyless_chunked: Bool = False) raises -> List[UInt8]:
    if status < 200 or status > 599:
        raise Error("invalid final HTTP response status")
    var output = List[UInt8]()
    var text = "HTTP/1.1 " + String(status) + " " + _reason(status) + "\r\n"
    for byte in text.as_bytes():
        output.append(byte)
    if not chunked and not bodyless_chunked and (status != 204 and status != 304 or include_bodyless_length):
        text = "Content-Length: " + String(body_length) + "\r\n"
        for byte in text.as_bytes():
            output.append(byte)
    if chunked or bodyless_chunked:
        for byte in "Transfer-Encoding: chunked\r\n".as_bytes():
            output.append(byte)
    for byte in "Connection: close\r\n".as_bytes():
        output.append(byte)
    var header_bytes = len(output)
    for name, value in headers:
        _validate_response_header(name, value)
        var lower = name.lower()
        if lower == "content-length" or lower == "transfer-encoding" or lower == "connection" or lower == "trailer" or lower == "upgrade" or lower == "keep-alive" or lower == "proxy-connection":
            raise Error("caller-controlled HTTP response framing header is forbidden")
        var line = name + ": " + value + "\r\n"
        header_bytes += line.byte_length()
        if header_bytes + 2 > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        for byte in line.as_bytes():
            output.append(byte)
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
    var alphabet = String("0123456789abcdef")
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
    if status == 204:
        return "No Content"
    if status == 301:
        return "Moved Permanently"
    if status == 302:
        return "Found"
    if status == 304:
        return "Not Modified"
    if status == 400:
        return "Bad Request"
    if status == 401:
        return "Unauthorized"
    if status == 403:
        return "Forbidden"
    if status == 404:
        return "Not Found"
    if status == 405:
        return "Method Not Allowed"
    if status == 408:
        return "Request Timeout"
    if status == 413:
        return "Content Too Large"
    if status == 415:
        return "Unsupported Media Type"
    if status == 417:
        return "Expectation Failed"
    if status == 422:
        return "Unprocessable Content"
    if status == 429:
        return "Too Many Requests"
    if status == 500:
        return "Internal Server Error"
    if status == 502:
        return "Bad Gateway"
    if status == 503:
        return "Service Unavailable"
    if status == 504:
        return "Gateway Timeout"
    return "Response"
