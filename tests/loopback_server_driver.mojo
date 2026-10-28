"""Small process driver for exercising the owned loopback HTTP server."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv
from std.time import sleep

from modex.json import quote_json
from modex.loopback_server import LoopbackHTTPListener, LoopbackHTTPRequest


def emit(mut output: RawFileDescriptor, line: String) raises:
    output.write_bytes((line + "\n").as_bytes())


def hex(bytes: List[UInt8]) -> String:
    var alphabet = "0123456789abcdef"
    var result = String()
    for byte in bytes:
        result += alphabet[byte=Int(byte) >> 4]
        result += alphabet[byte=Int(byte) & 15]
    return result


def request_line(request: LoopbackHTTPRequest) -> String:
    var header_json = "["
    for index in range(len(request.headers)):
        if index:
            header_json += ","
        header_json += "[" + quote_json(request.headers[index][0]) + "," + quote_json(request.headers[index][1]) + "]"
    header_json += "]"
    return '{"method":' + quote_json(request.method) + ',"target":' + quote_json(request.target) + ',"headers":' + header_json + ',"body_hex":' + quote_json(hex(request.body)) + "}"


def bytes_of(text: String) -> List[UInt8]:
    var output = List[UInt8]()
    for byte in text.as_bytes():
        output.append(byte)
    return output^


def run(mode: String, mut output: RawFileDescriptor) raises:
    var listener = LoopbackHTTPListener("[::1]:0" if mode == "ipv6" else "127.0.0.1:0")
    emit(output, "READY " + listener.address)
    if mode == "idle":
        var idle = listener.accept(150)
        emit(output, "IDLE " + ("true" if not idle else "false"))
        return
    var accepted = listener.accept(3000)
    if not accepted:
        emit(output, "ACCEPT_TIMEOUT")
        return
    var connection = accepted.take()
    if mode == "close":
        connection.close()
        emit(output, "CLOSED")
        return

    var request: LoopbackHTTPRequest
    try:
        var request_timeout = UInt64(150 if mode == "timeout" else 2000)
        if mode == "small-limit":
            request = connection.read_request(request_timeout, 3)
        else:
            request = connection.read_request(request_timeout)
    except error:
        var message = String(error)
        var status = 413 if message.find("oversized") >= 0 or message.find("exceeds wire limit") >= 0 else 400
        connection.respond(status, List[Tuple[String, String]](), bytes_of(message), 500)
        emit(output, "REJECT " + quote_json(message))
        return
    emit(output, "REQUEST " + request_line(request))

    if mode == "status-206" or mode == "status-418" or mode == "status-422":
        var status = 206 if mode == "status-206" else 418 if mode == "status-418" else 422
        connection.respond(status, List[Tuple[String, String]](), List[UInt8](), 1000)
        emit(output, "STATUS_SENT")
    elif mode == "bodyless-sse-204" or mode == "bodyless-sse-304":
        var headers = List[Tuple[String, String]]()
        headers.append(("Content-Type", "text/event-stream"))
        connection.respond(204 if mode == "bodyless-sse-204" else 304, headers, List[UInt8](), 1000, False, True)
        emit(output, "BODYLESS_SENT")
    elif mode == "head-buffered":
        var headers = List[Tuple[String, String]]()
        headers.append(("Content-Type", "application/octet-stream"))
        connection.respond(200, headers, bytes_of("representation"), 1000)
        emit(output, "HEAD_BUFFERED_SENT")
    elif mode == "head-stream" or mode == "head-stream-cancel":
        var headers = List[Tuple[String, String]]()
        headers.append(("Content-Type", "text/event-stream"))
        connection.start_stream(200, headers, 1000)
        if mode == "head-stream-cancel":
            var detected = False
            for _ in range(500):
                if connection.client_disconnected():
                    detected = True
                    break
                sleep(0.002)
            emit(output, "DISCONNECTED " + ("true" if detected else "false"))
            if detected:
                try:
                    connection.write_chunk(bytes_of("after-cancel"), 1000)
                    emit(output, "WRITE_SURVIVED")
                except error:
                    emit(output, "WRITE_FAILED")
            connection.close()
        else:
            connection.write_chunk(bytes_of("first\n"), 1000)
            sleep(0.35)
            connection.write_chunk(bytes_of("second\n"), 1000)
            connection.finish_stream(1000)
            emit(output, "HEAD_STREAM_DONE")
    elif mode == "stream":
        var headers = List[Tuple[String, String]]()
        headers.append(("Content-Type", "text/event-stream"))
        connection.start_stream(200, headers, 1000)
        connection.write_chunk(bytes_of("first\n"), 1000)
        sleep(0.35)
        connection.write_chunk(bytes_of("second\n"), 1000)
        connection.finish_stream(1000)
        emit(output, "STREAM_DONE")
    elif mode == "cancel":
        var headers = List[Tuple[String, String]]()
        headers.append(("Content-Type", "text/event-stream"))
        connection.start_stream(200, headers, 1000)
        connection.write_chunk(bytes_of("first\n"), 1000)
        var detected = False
        for _ in range(500):
            if connection.client_disconnected():
                detected = True
                break
            sleep(0.002)
        emit(output, "DISCONNECTED " + ("true" if detected else "false"))
        if detected:
            try:
                connection.write_chunk(bytes_of("after-cancel"), 1000)
                emit(output, "WRITE_SURVIVED")
            except error:
                emit(output, "WRITE_FAILED")
        connection.close()
    elif mode == "bad-response" or mode == "framing-response":
        var headers = List[Tuple[String, String]]()
        if mode == "bad-response":
            headers.append(("X-Test", "ok\r\nInjected: yes"))
        else:
            headers.append(("Content-Length", "0"))
        try:
            connection.respond(200, headers, List[UInt8](), 1000)
        except error:
            emit(output, "RESPONSE_REJECTED " + quote_json(String(error)))
    else:
        if mode == "move":
            var moved = connection^
            moved.respond(202, List[Tuple[String, String]](), request.body, 1000)
        else:
            var headers = List[Tuple[String, String]]()
            headers.append(("Content-Type", "application/octet-stream"))
            connection.respond(200, headers, request.body, 1000)
        emit(output, "RESPONDED")


def main() raises:
    var output = RawFileDescriptor(1)
    var args = argv()
    if len(args) != 2:
        raise Error("usage: loopback_server_driver MODE")
    run(args[1], output)
