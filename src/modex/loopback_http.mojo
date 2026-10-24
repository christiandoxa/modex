"""Bounded loopback HTTP/1 GET through the pinned official POSIX wrappers."""

from std.bit import byte_swap
from std.collections import Array, List, Span
from std.net._sys.inet import in6_addr, in_addr
from std.memory import MaybeUninit
from std.net._sys.unix import (
    AF_INET, AF_INET6, F_GETFL, F_SETFL, MSG_DONTWAIT, MSG_NOSIGNAL,
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


def _request(path: String, header_name: String, header_value: String, host: String) raises -> List[UInt8]:
    if path.byte_length() == 0 or path.byte_length() > HTTP_HEADER_LIMIT or not path.startswith("/") or "\r" in path or "\n" in path or "#" in path:
        raise Error("invalid HTTP request target")
    for b in path.as_bytes():
        if b <= 32 or b == 127:
            raise Error("invalid HTTP request target")
    if header_name.byte_length() == 0:
        raise Error("invalid HTTP header name")
    for c in header_name:
        if not ((c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "-" or c == "_"):
            raise Error("invalid HTTP header name")
    if "\r" in header_value or "\n" in header_value:
        raise Error("invalid HTTP header value")
    if header_value.byte_length() + header_name.byte_length() + host.byte_length() > HTTP_HEADER_LIMIT:
        raise Error("HTTP request headers exceed limit")
    for b in header_value.as_bytes():
        if b < 32 or b == 127:
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


def _send_all(fd: Int32, bytes: List[UInt8], deadline: Float64) raises:
    var sent = 0
    while sent < len(bytes):
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
                if not ((b >= 65 and b <= 90) or (b >= 97 and b <= 122) or (b >= 48 and b <= 57) or b == 45 or b == 95):
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
    if status < 100 or status > 599:
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
            if not ((b >= 65 and b <= 90) or (b >= 97 and b <= 122) or (b >= 48 and b <= 57) or b == 45 or b == 95):
                raise Error("malformed HTTP response header")
        var name = raw_name.lower()
        var raw_value = line[byte=colon + 1:]
        for b in raw_value.as_bytes():
            if (b < 32 and b != 9) or b == 127:
                raise Error("malformed HTTP response header")
        var value = raw_value.strip(" \t")
        if name == "content-length":
            var parsed_length = _number(value)
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
                        if not ((b >= 65 and b <= 90) or (b >= 97 and b <= 122) or (b >= 48 and b <= 57) or b == 45 or b == 95):
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
        fd = socket(AF_INET6, SOCK_STREAM, 0)
        if fd < 0:
            raise Error("failed to create loopback socket")
        var addr_bytes = Array[UInt8, 16](fill=0)
        addr_bytes[15] = 1
        var addr6 = in6_addr(s6_addr=addr_bytes^)
        var peer6 = sockaddr_in6(port=_port_bytes(port), addr=addr6^, flowinfo=0, scope_id=0)
        if fcntl(fd, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
            _ = close(fd)
            raise Error("failed to set loopback socket close-on-exec")
        var flags = fcntl(fd, F_GETFL)
        if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
            _ = close(fd)
            raise Error("failed to set loopback socket nonblocking")
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
        fd = socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0:
            raise Error("failed to create loopback socket")
        var peer = sockaddr_in(port=_port_bytes(port), addr=in_addr(s_addr=_network32(ip)))
        if fcntl(fd, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
            _ = close(fd)
            raise Error("failed to set loopback socket close-on-exec")
        var flags = fcntl(fd, F_GETFL)
        if flags < 0 or fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0:
            _ = close(fd)
            raise Error("failed to set loopback socket nonblocking")
        started = perf_counter()
        result = connect(fd, Pointer(to=peer).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in]()))
    try:
        var read_deadline = started + Float64(read_timeout_ms) / 1000.0
        var connect_deadline = started + Float64(connect_timeout_ms) / 1000.0
        if read_deadline < connect_deadline:
            connect_deadline = read_deadline
        if result < 0:
            var e = get_errno()
            if e != ErrNo.EINPROGRESS and e != ErrNo.EINTR and e != ErrNo.EAGAIN:
                raise Error("loopback HTTP connect failed")
            while True:
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
                    break
                else:
                    var e = get_errno()
                    if e != ErrNo.ENOTCONN and e != ErrNo.EINVAL and e != ErrNo.EINPROGRESS:
                        raise Error("loopback HTTP connect failed")
                    _deadline_wait(connect_deadline)
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
