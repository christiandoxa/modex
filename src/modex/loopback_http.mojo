"""Bounded loopback HTTP/1 GET and streaming POST through official POSIX wrappers."""

from std.bit import byte_swap
from std.collections import Array, List, Span
from std.net._sys.inet import in6_addr, in_addr
from std.memory import MaybeUninit
from std.net._sys.unix import (
    AF_INET, AF_INET6, F_GETFL, F_SETFL, MSG_DONTWAIT, MSG_NOSIGNAL, MSG_PEEK,
    O_NONBLOCK, SO_ERROR, SOL_SOCKET, SOCK_STREAM, connect, getsockopt,
    getpeername, recv, send, sockaddr, sockaddr_in, sockaddr_in6, sockaddr_storage,
    socket,
)
from std.sys import Endian, size_of
from std.sys._libc import FcntlCommands, FcntlFDFlags, close, fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.time import perf_counter, sleep

comptime HTTP_HEADER_LIMIT = 65536


def _number(text: StringSlice) raises -> Int:
    if text.byte_length() == 0:
        raise Error("invalid loopback HTTP address")
    var n = 0
    for b in text.as_bytes():
        if b < 48 or b > 57:
            raise Error("invalid loopback HTTP address")
        var digit = Int(b - 48)
        if n > 214748364 or (n == 214748364 and digit > 7):
            raise Error("invalid loopback HTTP address")
        n = n * 10 + digit
    return n



def _hex(text: StringSlice) raises -> Int:
    if text.byte_length() == 0:
        raise Error("invalid chunk size")
    var n = 0
    for b in text.as_bytes():
        var digit: Int
        if b >= 48 and b <= 57:
            digit = Int(b - 48)
        elif b >= 65 and b <= 70:
            digit = Int(b - 55)
        elif b >= 97 and b <= 102:
            digit = Int(b - 87)
        else:
            raise Error("invalid chunk size")
        if n > 134217727 or (n == 134217727 and digit > 15):
            raise Error("invalid chunk size")
        n = n * 16 + digit
    return n


def _port_bytes(port: Int) -> UInt16:
    comptime if Endian.native() == Endian.little:
        return byte_swap(UInt16(port))
    else:
        return UInt16(port)


def _network32(value: UInt32) -> UInt32:
    comptime if Endian.native() == Endian.little:
        return byte_swap(value)
    else:
        return value


def _http_token_byte(b: UInt8) -> Bool:
    return (
        (b >= 48 and b <= 57)
        or (b >= 65 and b <= 90)
        or (b >= 97 and b <= 122)
        or b == 33 or b == 35 or b == 36 or b == 37 or b == 38 or b == 39
        or b == 42 or b == 43 or b == 45 or b == 46 or b == 94 or b == 95
        or b == 96 or b == 124 or b == 126
    )


def _request(path: String, header_name: String, header_value: String, host: String) raises -> List[UInt8]:
    if path.byte_length() == 0 or path.byte_length() > HTTP_HEADER_LIMIT or not path.startswith("/") or "\r" in path or "\n" in path or "#" in path:
        raise Error("invalid HTTP request target")
    for b in path.as_bytes():
        if b <= 32 or b == 127:
            raise Error("invalid HTTP request target")
    if header_name.byte_length() == 0:
        raise Error("invalid HTTP header name")
    for b in header_name.as_bytes():
        if not _http_token_byte(b):
            raise Error("invalid HTTP header name")
    if "\r" in header_value or "\n" in header_value:
        raise Error("invalid HTTP header value")
    if header_value.byte_length() + header_name.byte_length() + host.byte_length() > HTTP_HEADER_LIMIT:
        raise Error("HTTP request headers exceed limit")
    for b in header_value.as_bytes():
        if (b < 32 and b != 9) or b == 127:
            raise Error("invalid HTTP header value")
    var bytes = List[UInt8]()
    var head = "GET " + path + " HTTP/1.1\r\nHost: " + host + "\r\nConnection: close\r\n" + header_name + ": " + header_value + "\r\n\r\n"
    if head.byte_length() > HTTP_HEADER_LIMIT:
        raise Error("HTTP request headers exceed limit")
    for b in head.as_bytes():
        bytes.append(b)
    return bytes^


def _deadline_wait(deadline: Float64) raises:
    if perf_counter() >= deadline:
        raise Error("loopback HTTP request timed out")
    sleep(0.001)


def _check_downstream_peer(fd: Int32) raises:
    if fd < 0:
        return
    var byte: UInt8 = 0
    var result = recv(fd, Pointer(to=byte), 1, MSG_PEEK | MSG_DONTWAIT)
    # TCP EOF also represents a valid HTTP request half-close.
    if result >= 0:
        return
    var e = get_errno()
    if e != ErrNo.EAGAIN and e != ErrNo.EINTR:
        raise Error("downstream client disconnected")


def _send_all(fd: Int32, bytes: List[UInt8], deadline: Float64, downstream_fd: Int32 = -1) raises:
    var sent = 0
    while sent < len(bytes):
        _check_downstream_peer(downstream_fd)
        if perf_counter() >= deadline:
            raise Error("loopback HTTP request timed out")
        var n = send(fd, bytes.unsafe_ptr().unsafe_offset(sent), UInt(len(bytes) - sent), MSG_DONTWAIT | MSG_NOSIGNAL)
        if n > 0:
            sent += Int(n)
        else:
            var e = get_errno()
            if e != ErrNo.EAGAIN and e != ErrNo.EINTR:
                raise Error("loopback HTTP request write failed")
            _deadline_wait(deadline)


def _header_end_from(bytes: List[UInt8], start: Int) -> Int:
    if len(bytes) < 4:
        return -1
    var first = start if start > 0 else 0
    for i in range(first, len(bytes) - 3):
        if bytes[i] == 13 and bytes[i + 1] == 10 and bytes[i + 2] == 13 and bytes[i + 3] == 10:
            return i
    return -1


@fieldwise_init
struct ChunkProgress(Movable):
    var cursor: Int
    var decoded: Int
    var scan: Int
    var chunk_end: Int
    var trailer_bytes: Int
    var trailers: Bool
    var complete: Bool


def _advance_chunks(bytes: List[UInt8], mut progress: ChunkProgress, max_body_bytes: Int, deadline: Float64) raises:
    while not progress.complete:
        if perf_counter() >= deadline:
            raise Error("loopback HTTP request timed out")
        if progress.trailers:
            var trailer_end = progress.scan
            while trailer_end + 1 < len(bytes) and not (bytes[trailer_end] == 13 and bytes[trailer_end + 1] == 10):
                if trailer_end & 4095 == 0 and perf_counter() >= deadline:
                    raise Error("loopback HTTP request timed out")
                trailer_end += 1
            if trailer_end + 1 >= len(bytes):
                if progress.trailer_bytes + len(bytes) - progress.cursor > HTTP_HEADER_LIMIT:
                    raise Error("HTTP trailers exceed limit")
                progress.scan = max(progress.cursor, len(bytes) - 1)
                return
            if progress.trailer_bytes + trailer_end - progress.cursor + 2 > HTTP_HEADER_LIMIT:
                raise Error("HTTP trailers exceed limit")
            if trailer_end == progress.cursor:
                progress.trailer_bytes += 2
                progress.complete = True
                return
            var trailer = _ascii(bytes, progress.cursor, trailer_end)
            if trailer.byte_length() > HTTP_HEADER_LIMIT:
                raise Error("HTTP trailers exceed limit")
            var colon = trailer.find(":")
            if colon <= 0:
                raise Error("malformed HTTP trailer")
            for b in trailer[byte=0:colon].as_bytes():
                if not _http_token_byte(b):
                    raise Error("malformed HTTP trailer")
            for b in trailer[byte=colon + 1:].as_bytes():
                if (b < 32 and b != 9) or b == 127:
                    raise Error("malformed HTTP trailer")
            progress.trailer_bytes += trailer_end - progress.cursor + 2
            progress.cursor = trailer_end + 2
            progress.scan = progress.cursor
            continue
        if progress.chunk_end >= 0:
            if len(bytes) < progress.chunk_end + 2:
                return
            if bytes[progress.chunk_end] != 13 or bytes[progress.chunk_end + 1] != 10:
                raise Error("malformed chunk terminator")
            progress.cursor = progress.chunk_end + 2
            progress.scan = progress.cursor
            progress.chunk_end = -1
            continue
        var line_end = progress.scan
        while line_end + 1 < len(bytes) and not (bytes[line_end] == 13 and bytes[line_end + 1] == 10):
            if line_end & 4095 == 0 and perf_counter() >= deadline:
                raise Error("loopback HTTP request timed out")
            line_end += 1
        if line_end + 1 >= len(bytes):
            if len(bytes) - progress.cursor > HTTP_HEADER_LIMIT:
                raise Error("HTTP chunk-size line exceeds limit")
            progress.scan = max(progress.cursor, len(bytes) - 1)
            return
        if line_end - progress.cursor > HTTP_HEADER_LIMIT:
            raise Error("HTTP chunk-size line exceeds limit")
        var size_text = _ascii(bytes, progress.cursor, line_end).split(";")[0]
        var size = _hex(size_text)
        progress.cursor = line_end + 2
        progress.scan = progress.cursor
        if size == 0:
            progress.trailers = True
            continue
        if progress.decoded + size > max_body_bytes:
            raise Error("oversized chunked HTTP response")
        progress.decoded += size
        progress.chunk_end = progress.cursor + size

def _ascii(bytes: List[UInt8], start: Int, stop: Int) -> String:
    var out = List[UInt8]()
    for i in range(start, stop):
        out.append(bytes[i])
    return String(from_utf8_lossy=Span(out))


def _response_head(bytes: List[UInt8], end: Int) raises -> Tuple[Int, Int, Bool]:
    var lines = _ascii(bytes, 0, end).split("\r\n")
    if len(lines) == 0 or (not lines[0].startswith("HTTP/1.0 ") and not lines[0].startswith("HTTP/1.1 ")):
        raise Error("malformed HTTP response status")
    for b in lines[0].as_bytes():
        if (b < 32 and b != 9) or b == 127:
            raise Error("malformed HTTP response status")
    var status_parts = lines[0].split(" ")
    if len(status_parts) < 2 or status_parts[1].byte_length() != 3:
        raise Error("malformed HTTP response status")
    var status = _number(status_parts[1])
    if status < 100 or status > 999:
        raise Error("malformed HTTP response status")
    var length = -1
    var chunked = False
    for i in range(1, len(lines)):
        var line = lines[i]
        var colon = line.find(":")
        if colon <= 0 or line.byte_length() > HTTP_HEADER_LIMIT:
            raise Error("malformed HTTP response header")
        var raw_name = line[byte=0:colon]
        for b in raw_name.as_bytes():
            if not _http_token_byte(b):
                raise Error("malformed HTTP response header")
        var name = raw_name.lower()
        var raw_value = line[byte=colon + 1:]
        for b in raw_value.as_bytes():
            if (b < 32 and b != 9) or b == 127:
                raise Error("malformed HTTP response header")
        var value = raw_value.strip(" \t")
        if name == "content-length":
            for raw_length in value.split(","):
                var parsed_length = _number(raw_length.strip(" \t"))
                if length >= 0 and length != parsed_length:
                    raise Error("conflicting HTTP content lengths")
                length = parsed_length
        elif name == "transfer-encoding":
            if chunked or length >= 0 or value.lower() != "chunked":
                raise Error("unsupported or ambiguous HTTP transfer encoding")
            chunked = True
    if length >= 0 and chunked:
        raise Error("ambiguous HTTP response framing")
    return (status, length, chunked)


def _parse_body(bytes: List[UInt8], start: Int, status: Int, length: Int, chunked: Bool, max_body_bytes: Int, deadline: Float64) raises -> Tuple[Int, List[UInt8]]:
    var body = List[UInt8]()
    var body_start = start
    if status == 204 or status == 304:
        if perf_counter() >= deadline:
            raise Error("loopback HTTP request timed out")
        return (status, body^)
    if chunked:
        var cursor = body_start
        while True:
            if perf_counter() >= deadline:
                raise Error("loopback HTTP request timed out")
            var line_end = cursor
            while line_end + 1 < len(bytes) and not (bytes[line_end] == 13 and bytes[line_end + 1] == 10):
                if line_end & 4095 == 0 and perf_counter() >= deadline:
                    raise Error("loopback HTTP request timed out")
                line_end += 1
            if line_end + 1 >= len(bytes):
                raise Error("incomplete chunked HTTP response")
            if line_end - cursor > HTTP_HEADER_LIMIT:
                raise Error("HTTP chunk-size line exceeds limit")
            var size_text = _ascii(bytes, cursor, line_end).split(";")[0]
            var size = _hex(size_text)
            if size == 0:
                cursor = line_end + 2
                var trailer_bytes = 0
                while True:
                    var trailer_end = cursor
                    while trailer_end + 1 < len(bytes) and not (bytes[trailer_end] == 13 and bytes[trailer_end + 1] == 10):
                        if trailer_end & 4095 == 0 and perf_counter() >= deadline:
                            raise Error("loopback HTTP request timed out")
                        trailer_end += 1
                    if trailer_end + 1 >= len(bytes):
                        if trailer_bytes + len(bytes) - cursor > HTTP_HEADER_LIMIT:
                            raise Error("HTTP trailers exceed limit")
                        raise Error("incomplete chunked HTTP trailers")
                    if trailer_bytes + trailer_end - cursor + 2 > HTTP_HEADER_LIMIT:
                        raise Error("HTTP trailers exceed limit")
                    if trailer_end == cursor:
                        if perf_counter() >= deadline:
                            raise Error("loopback HTTP request timed out")
                        return (status, body^)
                    var trailer = _ascii(bytes, cursor, trailer_end)
                    if trailer.byte_length() > HTTP_HEADER_LIMIT:
                        raise Error("HTTP trailers exceed limit")
                    var trailer_colon = trailer.find(":")
                    if trailer_colon <= 0:
                        raise Error("malformed HTTP trailer")
                    for b in trailer[byte=0:trailer_colon].as_bytes():
                        if not _http_token_byte(b):
                            raise Error("malformed HTTP trailer")
                    for b in trailer[byte=trailer_colon + 1:].as_bytes():
                        if (b < 32 and b != 9) or b == 127:
                            raise Error("malformed HTTP trailer")
                    trailer_bytes += trailer_end - cursor + 2
                    cursor = trailer_end + 2
            if size < 0 or len(body) + size > max_body_bytes or line_end + 2 + size + 2 > len(bytes):
                raise Error("invalid or oversized chunked HTTP response")
            for i in range(line_end + 2, line_end + 2 + size):
                if i & 4095 == 0 and perf_counter() >= deadline:
                    raise Error("loopback HTTP request timed out")
                body.append(bytes[i])
            cursor = line_end + 2 + size
            if bytes[cursor] != 13 or bytes[cursor + 1] != 10:
                raise Error("malformed chunk terminator")
            cursor += 2
    else:
        var available = len(bytes) - body_start
        var take = available if length < 0 else length
        if take > max_body_bytes or take < 0 or available < take:
            raise Error("incomplete or oversized HTTP response body")
        for i in range(body_start, body_start + take):
            if i & 4095 == 0 and perf_counter() >= deadline:
                raise Error("loopback HTTP request timed out")
            body.append(bytes[i])
    if perf_counter() >= deadline:
        raise Error("loopback HTTP request timed out")
    return (status, body^)




def _open_loopback_socket(ipv6: Bool) raises -> Int32:
    var fd = socket(AF_INET6 if ipv6 else AF_INET, SOCK_STREAM, 0)
    if fd < 0:
        raise Error("failed to create loopback socket")
    if fcntl(fd, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
        _ = close(fd)
        raise Error("failed to set loopback socket close-on-exec")
    var flags = fcntl(fd, F_GETFL)
    if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
        _ = close(fd)
        raise Error("failed to set loopback socket nonblocking")
    return fd


def _finish_loopback_connect(fd: Int32, result: Int32, deadline: Float64, downstream_fd: Int32 = -1) raises:
    # Preserve connect's errno before the downstream socket probe changes it.
    var e = get_errno()
    _check_downstream_peer(downstream_fd)
    if result >= 0:
        return
    if e != ErrNo.EINPROGRESS and e != ErrNo.EINTR and e != ErrNo.EAGAIN:
        raise Error("loopback HTTP connect failed")
    while True:
        _check_downstream_peer(downstream_fd)
        var sock_error: Int32 = 0
        var opt_len = UInt32(size_of[Int32]())
        if getsockopt(fd, SOL_SOCKET, SO_ERROR, Pointer(to=sock_error).unsafe_bitcast[NoneType](), Pointer(to=opt_len)) < 0:
            raise Error("loopback HTTP connect check failed")
        if sock_error != 0:
            raise Error("loopback HTTP connect failed")
        var storage = MaybeUninit[sockaddr_storage]()
        var peer_len: UInt32 = UInt32(size_of[sockaddr_storage]())
        var peer_result = getpeername(fd, Pointer(to=storage).unsafe_bitcast[sockaddr](), Pointer(to=peer_len))
        _ = storage^.unsafe_forget()
        if peer_result == 0:
            return
        e = get_errno()
        if e != ErrNo.ENOTCONN and e != ErrNo.EINVAL and e != ErrNo.EINPROGRESS:
            raise Error("loopback HTTP connect failed")
        _deadline_wait(deadline)


def loopback_get(
    address: String,
    path: String,
    header_name: String,
    header_value: String,
    connect_timeout_ms: UInt64,
    read_timeout_ms: UInt64,
    max_body_bytes: Int,
) raises -> Tuple[Int, List[UInt8]]:
    if max_body_bytes < 0 or max_body_bytes > 4 * 1024 * 1024:
        raise Error("invalid or unsupported HTTP body limit")
    var fd: Int32
    var req: List[UInt8]
    var ipv6 = address.byte_length() > 0 and address.startswith("[")
    var started: Float64
    var result: Int32
    if ipv6:
        var close_bracket = address.find("]")
        if close_bracket < 0 or close_bracket + 1 >= address.byte_length() or not address[byte=close_bracket + 1:].startswith(":"):
            raise Error("invalid loopback HTTP address")
        if close_bracket != 4 or not address[byte=1:close_bracket].startswith("::1"):
            raise Error("HTTP address is not loopback")
        var port = _number(address[byte=close_bracket + 2:])
        if port == 0 or port > 65535:
            raise Error("invalid loopback HTTP port")
        req = _request(path, header_name, header_value, address)
        fd = _open_loopback_socket(True)
        var addr_bytes = Array[UInt8, 16](fill=0)
        addr_bytes[15] = 1
        var addr6 = in6_addr(s6_addr=addr_bytes^)
        var peer6 = sockaddr_in6(port=_port_bytes(port), addr=addr6^, flowinfo=0, scope_id=0)
        started = perf_counter()
        result = connect(fd, Pointer(to=peer6).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in6]()))
    else:
        var parts = address.split(":")
        if len(parts) != 2:
            raise Error("invalid loopback HTTP address")
        var octets = parts[0].split(".")
        if len(octets) != 4:
            raise Error("invalid loopback HTTP address")
        var ip = UInt32(0)
        for i in range(4):
            var octet = _number(octets[i])
            if octet > 255:
                raise Error("invalid loopback HTTP address")
            if i == 0 and octet != 127:
                raise Error("HTTP address is not loopback")
            ip = (ip << 8) | UInt32(octet)
        var port = _number(parts[1])
        if port == 0 or port > 65535:
            raise Error("invalid loopback HTTP port")
        req = _request(path, header_name, header_value, address)
        fd = _open_loopback_socket(False)
        var peer = sockaddr_in(port=_port_bytes(port), addr=in_addr(s_addr=_network32(ip)))
        started = perf_counter()
        result = connect(fd, Pointer(to=peer).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in]()))
    try:
        var read_deadline = started + Float64(read_timeout_ms) / 1000.0
        var connect_deadline = started + Float64(connect_timeout_ms) / 1000.0
        if read_deadline < connect_deadline:
            connect_deadline = read_deadline
        _finish_loopback_connect(fd, result, connect_deadline)
        _send_all(fd, req, read_deadline)
        var response = List[UInt8]()
        var max_wire_bytes = HTTP_HEADER_LIMIT + 65536 + max_body_bytes * 8
        var buffer = List[UInt8](length=8192, fill=0)
        var eof = False
        var interim_count = 0
        var interim_bytes = 0
        var response_status = -1
        var response_length = -1
        var response_chunked = False
        var final_end = -1
        var header_scan = 0
        var chunk_progress = ChunkProgress(cursor=0, decoded=0, scan=0, chunk_end=-1, trailer_bytes=0, trailers=False, complete=False)
        while not eof:
            if perf_counter() >= read_deadline:
                raise Error("loopback HTTP request timed out")
            var n = recv(fd, buffer.unsafe_ptr(), UInt(len(buffer)), MSG_DONTWAIT)
            if n > 0:
                for i in range(Int(n)):
                    response.append(buffer[i])
                if len(response) > max_wire_bytes:
                    raise Error("loopback HTTP response exceeds limit")
                var end = -1
                if final_end < 0:
                    end = _header_end_from(response, header_scan)
                while end >= 0:
                    if end > HTTP_HEADER_LIMIT:
                        raise Error("HTTP response headers exceed limit")
                    var head = _response_head(response, end)
                    if head[0] >= 100 and head[0] < 200:
                        if head[0] == 101:
                            raise Error("HTTP protocol upgrade is unsupported")
                        interim_count += 1
                        interim_bytes += end + 4
                        if interim_count > 8 or interim_bytes > HTTP_HEADER_LIMIT:
                            raise Error("too many or oversized informational responses")
                        var remainder = List[UInt8]()
                        for i in range(end + 4, len(response)):
                            remainder.append(response[i])
                        response = remainder^
                        header_scan = 0
                        end = _header_end_from(response, header_scan)
                        if end < 0:
                            header_scan = max(0, len(response) - 3)
                            break
                        continue
                    response_status = head[0]
                    response_length = head[1]
                    response_chunked = head[2]
                    final_end = end
                    if response_chunked:
                        chunk_progress = ChunkProgress(cursor=end + 4, decoded=0, scan=end + 4, chunk_end=-1, trailer_bytes=0, trailers=False, complete=False)
                    break
                if end < 0:
                    header_scan = max(0, len(response) - 3)
                if final_end < 0 and end < 0 and len(response) > HTTP_HEADER_LIMIT:
                    raise Error("HTTP response headers exceed limit")
                if final_end >= 0:
                    if response_status == 204 or response_status == 304:
                        break
                    if response_length >= 0:
                        if response_length > max_body_bytes:
                            raise Error("oversized HTTP response body")
                        if len(response) >= final_end + 4 + response_length:
                            break
                    elif response_chunked:
                        _advance_chunks(response, chunk_progress, max_body_bytes, read_deadline)
                        if chunk_progress.complete:
                            break
                    elif len(response) - final_end - 4 > max_body_bytes:
                        raise Error("oversized HTTP response body")
            elif n == 0:
                eof = True
            else:
                var e = get_errno()
                if e != ErrNo.EAGAIN and e != ErrNo.EINTR:
                    raise Error("loopback HTTP response read failed")
                _deadline_wait(read_deadline)
        if final_end < 0:
            raise Error("malformed HTTP response headers")
        if perf_counter() >= read_deadline:
            raise Error("loopback HTTP request timed out")
        var result = _parse_body(response, final_end + 4, response_status, response_length, response_chunked, max_body_bytes, read_deadline)
        _ = close(fd)
        return result^
    except:
        _ = close(fd)
        raise


def _drop_prefix(mut bytes: List[UInt8], count: Int):
    var rest = List[UInt8]()
    for i in range(count, len(bytes)):
        rest.append(bytes[i])
    bytes = rest^


def _line_end(bytes: List[UInt8], start: Int) -> Int:
    for i in range(max(0, start), len(bytes) - 1):
        if bytes[i] == 13 and bytes[i + 1] == 10:
            return i
    return -1


def _valid_request_field(name: String, value: String) raises:
    if name.byte_length() == 0:
        raise Error("invalid HTTP header name")
    for b in name.as_bytes():
        if not _http_token_byte(b):
            raise Error("invalid HTTP header name")
    for b in value.as_bytes():
        if (b < 32 and b != 9) or b == 127:
            raise Error("invalid HTTP header value")
    var lower_name = name.lower()
    if lower_name == "host" or lower_name == "content-length" or lower_name == "transfer-encoding" or lower_name == "connection":
        raise Error("caller-controlled HTTP framing header is forbidden")


def _stream_request(path: String, headers: List[Tuple[String, String]], host: String, body_length: Int) raises -> List[UInt8]:
    # Reuse GET's target validation without changing its established request bytes.
    _ = _request(path, "X", "", host)
    var head = "POST " + path + " HTTP/1.1\r\nHost: " + host + "\r\nConnection: close\r\nContent-Length: " + String(body_length) + "\r\n"
    var head_bytes = head.byte_length()
    if head_bytes > HTTP_HEADER_LIMIT - 2:
        raise Error("HTTP request headers exceed limit")
    for entry in headers:
        var name_bytes = entry[0].byte_length()
        var value_bytes = entry[1].byte_length()
        if name_bytes > HTTP_HEADER_LIMIT or value_bytes > HTTP_HEADER_LIMIT:
            raise Error("HTTP request headers exceed limit")
        var field_bytes = name_bytes + value_bytes + 4
        if field_bytes > HTTP_HEADER_LIMIT - 2 - head_bytes:
            raise Error("HTTP request headers exceed limit")
        _valid_request_field(entry[0], entry[1])
        head += entry[0] + ": " + entry[1] + "\r\n"
        head_bytes += field_bytes
    head += "\r\n"
    var request = List[UInt8]()
    for b in head.as_bytes():
        request.append(b)
    return request^


struct LoopbackHTTPStream(Movable):
    var fd: Int32
    var downstream_fd: Int32
    var status: Int
    var headers: List[Tuple[String, String]]
    var done: Bool
    var buffer: List[UInt8]
    var phase: Int
    var remaining: Int
    var body_bytes: Int
    var trailer_bytes: Int
    var header_scan: Int
    var interim_count: Int
    var interim_bytes: Int
    var wire_bytes: Int
    var max_wire_bytes: Int
    var max_body_bytes: Int
    var length: Int
    var request_deadline: Float64
    var idle_timeout_ms: UInt64

    def __init__(
        out self,
        address: String,
        path: String,
        headers: List[Tuple[String, String]],
        body: List[UInt8],
        connect_timeout_ms: UInt64,
        request_timeout_ms: UInt64,
        idle_timeout_ms: UInt64,
        max_body_bytes: Int,
        downstream_fd: Int32 = -1,
        allow_unbounded_body: Bool = False,
    ) raises:
        self.fd = -1
        self.downstream_fd = downstream_fd
        self.status = 0
        self.headers = List[Tuple[String, String]]()
        self.done = False
        self.buffer = List[UInt8]()
        self.phase = 0
        self.remaining = 0
        self.body_bytes = 0
        self.trailer_bytes = 0
        self.header_scan = 0
        self.interim_count = 0
        self.interim_bytes = 0
        self.wire_bytes = 0
        self.max_wire_bytes = 0
        self.max_body_bytes = -1 if allow_unbounded_body else max_body_bytes
        self.length = -1
        self.request_deadline = 0.0
        self.idle_timeout_ms = idle_timeout_ms
        if max_body_bytes < 0 or max_body_bytes > 4 * 1024 * 1024 or connect_timeout_ms == 0 or request_timeout_ms == 0 or idle_timeout_ms == 0:
            raise Error("invalid or unsupported HTTP stream limits")

        var ipv6 = address.byte_length() > 0 and address.startswith("[")
        var port: Int
        var ip: UInt32 = 0
        if ipv6:
            var close_bracket = address.find("]")
            if close_bracket != 4 or close_bracket + 1 >= address.byte_length() or not address[byte=close_bracket + 1:].startswith(":") or not address[byte=1:close_bracket].startswith("::1"):
                raise Error("HTTP address is not loopback")
            port = _number(address[byte=close_bracket + 2:])
        else:
            var parts = address.split(":")
            if len(parts) != 2:
                raise Error("invalid loopback HTTP address")
            var octets = parts[0].split(".")
            if len(octets) != 4:
                raise Error("invalid loopback HTTP address")
            for i in range(4):
                var octet = _number(octets[i])
                if octet > 255:
                    raise Error("invalid loopback HTTP address")
                if i == 0 and octet != 127:
                    raise Error("HTTP address is not loopback")
                ip = (ip << 8) | UInt32(octet)
            port = _number(parts[1])
        if port == 0 or port > 65535:
            raise Error("invalid loopback HTTP port")
        var request = _stream_request(path, headers, address, len(body))
        _check_downstream_peer(self.downstream_fd)
        var started = perf_counter()
        self.request_deadline = started + Float64(request_timeout_ms) / 1000.0
        var connect_deadline = started + Float64(connect_timeout_ms) / 1000.0
        if connect_deadline > self.request_deadline:
            connect_deadline = self.request_deadline
        self.max_wire_bytes = -1 if allow_unbounded_body else HTTP_HEADER_LIMIT * 2 + 65536 + max_body_bytes * 8
        self.fd = _open_loopback_socket(ipv6)
        try:
            var result: Int32
            if ipv6:
                var addr_bytes = Array[UInt8, 16](fill=0)
                addr_bytes[15] = 1
                var peer6 = sockaddr_in6(port=_port_bytes(port), addr=in6_addr(s6_addr=addr_bytes^), flowinfo=0, scope_id=0)
                result = connect(self.fd, Pointer(to=peer6).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in6]()))
            else:
                var peer = sockaddr_in(port=_port_bytes(port), addr=in_addr(s_addr=_network32(ip)))
                result = connect(self.fd, Pointer(to=peer).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in]()))
            _finish_loopback_connect(self.fd, result, connect_deadline, self.downstream_fd)
            _send_all(self.fd, request, self.request_deadline, self.downstream_fd)
            _send_all(self.fd, body, self.request_deadline, self.downstream_fd)
            while self.phase == 0:
                self._read_head()
        except:
            self.close()
            raise

    def close(mut self):
        if self.fd >= 0:
            _ = close(self.fd)
            self.fd = -1
        self.done = True

    def __deinit__(deinit self):
        self.close()

    def _receive(mut self) raises:
        var deadline = self.request_deadline if self.phase == 0 else perf_counter() + Float64(self.idle_timeout_ms) / 1000.0
        var chunk = List[UInt8](length=8192, fill=0)
        while True:
            _check_downstream_peer(self.downstream_fd)
            if perf_counter() >= deadline:
                raise Error("loopback HTTP stream timed out")
            var n = recv(self.fd, chunk.unsafe_ptr(), UInt(len(chunk)), MSG_DONTWAIT)
            if n > 0:
                var count = Int(n)
                if self.max_wire_bytes >= 0 and self.wire_bytes > self.max_wire_bytes - count:
                    raise Error("HTTP stream exceeds wire limit")
                if self.max_wire_bytes >= 0:
                    self.wire_bytes += count
                for i in range(count):
                    self.buffer.append(chunk[i])
                return
            if n == 0:
                self.phase = 6
                return
            var e = get_errno()
            if e != ErrNo.EAGAIN and e != ErrNo.EINTR:
                raise Error("loopback HTTP stream read failed")
            _deadline_wait(deadline)

    def _read_head(mut self) raises:
        var end = _header_end_from(self.buffer, self.header_scan)
        while end < 0:
            if len(self.buffer) > HTTP_HEADER_LIMIT:
                raise Error("HTTP response headers exceed limit")
            self.header_scan = max(0, len(self.buffer) - 3)
            if self.phase == 6:
                raise Error("truncated HTTP response headers")
            self._receive()
            end = _header_end_from(self.buffer, self.header_scan)
        if end > HTTP_HEADER_LIMIT:
            raise Error("HTTP response headers exceed limit")
        var parsed = _response_head(self.buffer, end)
        if parsed[0] >= 100 and parsed[0] < 200:
            if parsed[0] == 101:
                raise Error("HTTP protocol upgrade is unsupported")
            self.interim_count += 1
            self.interim_bytes += end + 4
            if self.interim_count > 8 or self.interim_bytes > HTTP_HEADER_LIMIT:
                raise Error("too many or oversized informational responses")
            _drop_prefix(self.buffer, end + 4)
            self.header_scan = 0
            return
        self.status = parsed[0]
        # A 304 length describes the representation; bodyless statuses consume no bytes.
        self.length = 0 if self.status == 204 or self.status == 304 else parsed[1]
        if self.max_body_bytes >= 0 and self.length > self.max_body_bytes:
            raise Error("oversized HTTP response body")
        var lines = _ascii(self.buffer, 0, end).split("\r\n")
        self.headers = List[Tuple[String, String]]()
        for i in range(1, len(lines)):
            var colon = lines[i].find(":")
            self.headers.append((String(lines[i][byte=0:colon]), String(lines[i][byte=colon + 1:].strip(" \t"))))
        _drop_prefix(self.buffer, end + 4)
        self.header_scan = 0
        if parsed[0] == 204 or parsed[0] == 304:
            self.phase = 6
        elif parsed[2]:
            self.phase = 2
        elif self.length >= 0:
            self.remaining = self.length
            self.phase = 1
        else:
            self.phase = 5

    def _read_trailers(mut self) raises:
        while True:
            var end = _line_end(self.buffer, self.header_scan)
            while end < 0:
                if self.trailer_bytes + len(self.buffer) > HTTP_HEADER_LIMIT:
                    raise Error("HTTP trailers exceed limit")
                if self.phase == 6:
                    raise Error("truncated HTTP chunk trailers")
                self.header_scan = max(0, len(self.buffer) - 1)
                self._receive()
                end = _line_end(self.buffer, self.header_scan)
            if self.trailer_bytes + end + 2 > HTTP_HEADER_LIMIT:
                raise Error("HTTP trailers exceed limit")
            if end == 0:
                _drop_prefix(self.buffer, 2)
                self.header_scan = 0
                self.phase = 6
                return
            var trailer = _ascii(self.buffer, 0, end)
            var colon = trailer.find(":")
            if colon <= 0:
                raise Error("malformed HTTP trailer")
            for b in trailer[byte=0:colon].as_bytes():
                if not _http_token_byte(b):
                    raise Error("malformed HTTP trailer")
            for b in trailer[byte=colon + 1:].as_bytes():
                if (b < 32 and b != 9) or b == 127:
                    raise Error("malformed HTTP trailer")
            self.trailer_bytes += end + 2
            _drop_prefix(self.buffer, end + 2)
            self.header_scan = 0

    def read_chunk(mut self) raises -> List[UInt8]:
        if self.done:
            return List[UInt8]()
        try:
            while True:
                if self.phase != 6:
                    _check_downstream_peer(self.downstream_fd)
                if self.phase == 0:
                    self._read_head()
                elif self.phase == 1:
                    if self.remaining == 0:
                        self.phase = 6
                        continue
                    if len(self.buffer) == 0:
                        self._receive()
                    if self.phase == 6:
                        raise Error("truncated HTTP response body")
                    var take = min(8192, min(len(self.buffer), self.remaining))
                    # Passthrough can set this cap after upstream header parsing.
                    if self.max_body_bytes >= 0 and take > self.max_body_bytes - self.body_bytes:
                        raise Error("oversized HTTP response body")
                    var out = List[UInt8]()
                    for i in range(take):
                        out.append(self.buffer[i])
                    _drop_prefix(self.buffer, take)
                    self.remaining -= take
                    if self.max_body_bytes >= 0:
                        self.body_bytes += take
                    return out^
                elif self.phase == 2:
                    var end = _line_end(self.buffer, self.header_scan)
                    while end < 0:
                        if len(self.buffer) > HTTP_HEADER_LIMIT:
                            raise Error("HTTP chunk-size line exceeds limit")
                        if self.phase == 6:
                            raise Error("truncated HTTP chunk size")
                        self.header_scan = max(0, len(self.buffer) - 1)
                        self._receive()
                        end = _line_end(self.buffer, self.header_scan)
                    if end > HTTP_HEADER_LIMIT:
                        raise Error("HTTP chunk-size line exceeds limit")
                    var size = _hex(_ascii(self.buffer, 0, end).split(";")[0])
                    _drop_prefix(self.buffer, end + 2)
                    self.header_scan = 0
                    if size == 0:
                        self.phase = 4
                    else:
                        if self.max_body_bytes >= 0 and size > self.max_body_bytes - self.body_bytes:
                            raise Error("oversized chunked HTTP response")
                        self.remaining = size
                        self.phase = 3
                elif self.phase == 3:
                    if len(self.buffer) == 0:
                        self._receive()
                    if self.phase == 6:
                        raise Error("truncated chunked HTTP response")
                    var take = min(8192, min(len(self.buffer), self.remaining))
                    var out = List[UInt8]()
                    for i in range(take):
                        out.append(self.buffer[i])
                    _drop_prefix(self.buffer, take)
                    self.remaining -= take
                    if self.max_body_bytes >= 0:
                        self.body_bytes += take
                    if self.remaining == 0:
                        self.phase = 7
                    return out^
                elif self.phase == 7:
                    while len(self.buffer) < 2:
                        if self.phase == 6:
                            raise Error("truncated chunk terminator")
                        self._receive()
                    if self.buffer[0] != 13 or self.buffer[1] != 10:
                        raise Error("malformed chunk terminator")
                    _drop_prefix(self.buffer, 2)
                    self.phase = 2
                elif self.phase == 4:
                    self.phase = 5
                    self._read_trailers()
                elif self.phase == 5:
                    if self.max_body_bytes >= 0 and len(self.buffer) > self.max_body_bytes - self.body_bytes:
                        raise Error("oversized HTTP response body")
                    if len(self.buffer) > 0:
                        var take = min(8192, len(self.buffer))
                        var out = List[UInt8]()
                        for i in range(take):
                            out.append(self.buffer[i])
                        _drop_prefix(self.buffer, take)
                        if self.max_body_bytes >= 0:
                            self.body_bytes += take
                        return out^
                    self._receive()
                elif self.phase == 6:
                    self.done = True
                    self.close()
                    return List[UInt8]()
        except:
            self.close()
            raise
