"""Internal loopback local-rewrite relay using native provider exchanges."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.net._sys.unix import F_GETFL, F_SETFL, O_NONBLOCK
from std.sys._libc import fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.os import getenv
from std.time import perf_counter
from std.time.time import _realtime_nanoseconds

from .json import JSON_ARRAY, JSON_STRING, JsonDocument
from .loopback_http import LoopbackHTTPStream, _number
from .loopback_server import LoopbackHTTPConnection, LoopbackHTTPListener, LoopbackHTTPRequest
from .provider_deepseek_transport import DeepSeekExchange, deepseek_event_stream, deepseek_request_headers
from .provider_conversations import ProviderConversationStore
from .provider_passthrough import deepseek_chat_completions_path, deepseek_chat_completions_stream
from .provider_rate_limits import deepseek_codex_rate_limit_headers
from .provider_request import translate_deepseek_request
from .text import trim_text, unsigned_value
from .uuid7 import new_uuid7


def local_rewrite_upstream(url: String) raises -> Tuple[String, String]:
    if not url.startswith("http://") or "@" in url or "?" in url or "#" in url:
        raise Error("this Modex gateway requires a credential-free numeric loopback HTTP upstream URL")
    for byte in url.as_bytes():
        if byte <= 32 or byte == 127:
            raise Error("invalid --base-url")
    var remaining = String(url[byte=7:])
    var slash = remaining.find("/")
    var address = String(remaining[byte=:slash]) if slash >= 0 else remaining
    var path = String(remaining[byte=slash:]) if slash >= 0 else String()
    if address.startswith("[::1]:"):
        var port = _number(address[byte=6:])
        if port < 1 or port > 65535: raise Error("invalid loopback HTTP port")
    else:
        var parts = address.split(":")
        if len(parts) != 2: raise Error("this Modex gateway requires a numeric loopback upstream with an explicit port")
        var octets = parts[0].split(".")
        if len(octets) != 4: raise Error("HTTP address is not loopback")
        for index in range(4):
            var octet = _number(octets[index])
            if octet > 255 or index == 0 and octet != 127: raise Error("HTTP address is not loopback")
        var port = _number(parts[1])
        if port < 1 or port > 65535: raise Error("invalid loopback HTTP port")
    while path.endswith("/"):
        var shorter = String(path[byte=:path.byte_length() - 1])
        path = shorter^
    if "/../" in path or "/./" in path or path.endswith("/..") or path.endswith("/."):
        raise Error("URL path normalization is not implemented by this Modex gateway")
    return address, path + "/chat/completions"


def _bytes(text: String) -> List[UInt8]:
    var output = List[UInt8]()
    for byte in text.as_bytes(): output.append(byte)
    return output^


def _timeout(name: String, fallback: UInt64) raises -> UInt64:
    var configured = getenv(name, "")
    if not configured: return fallback
    var value = unsigned_value(configured)
    if value == 0: raise Error(name + " must be greater than zero")
    return value


def _reply(mut connection: LoopbackHTTPConnection, status: Int, message: String) raises:
    connection.respond(status, [("content-type", "text/plain; charset=utf-8")], _bytes(message), 30000)


def _write_event(mut connection: LoopbackHTTPConnection, event: String) raises:
    var deadline = perf_counter() + 30.0
    var chunk = List[UInt8]()
    for byte in event.as_bytes():
        chunk.append(byte)
        if len(chunk) == 8192:
            var remaining = deadline - perf_counter()
            if remaining <= 0: raise Error("gateway response write timed out")
            connection.write_chunk(chunk, max(UInt64(1), UInt64(remaining * 1000.0)))
            chunk.clear()
    if chunk:
        var remaining = deadline - perf_counter()
        if remaining <= 0: raise Error("gateway response write timed out")
        connection.write_chunk(chunk, max(UInt64(1), UInt64(remaining * 1000.0)))


def _stream_history(exchange: DeepSeekExchange) -> String:
    var snapshot = exchange.reader.state.conversation_snapshot
    if not snapshot: return exchange.messages
    if exchange.messages == "[]": return "[" + snapshot.value() + "]"
    return String(exchange.messages[byte=:exchange.messages.byte_length() - 1]) + "," + snapshot.value() + "]"


def _route_error(mut connection: LoopbackHTTPConnection) raises:
    connection.respond(404, [("content-type", "application/json"), ("cache-control", "no-store"), ("x-content-type-options", "nosniff")], _bytes('{"error":{"code":"unsupported_provider_route","message":"provider route is not supported"}}'), 30000)


def _response_headers(headers: List[Tuple[String, String]]) -> List[Tuple[String, String]]:
    var tokens = List[String]()
    for name, value in headers:
        if name.lower() == "connection":
            for token in value.split(","): tokens.append(trim_text(String(token)).lower())
    var output = List[Tuple[String, String]]()
    for name, value in headers:
        var lower = name.lower()
        if lower in tokens or lower in ["connection", "content-length", "transfer-encoding", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "upgrade"]:
            continue
        output.append((name, value))
    return output^


def _session(doc: JsonDocument) -> String:
    var node = doc.get(doc.root, "session_id")
    if node < 0:
        node = doc.get(doc.get(doc.root, "client_metadata"), "session_id")
    return trim_text(doc.string(node))


def _namespace(headers: List[Tuple[String, String]], doc: JsonDocument) -> String:
    var found = False
    var explicit = String()
    for expected in ["session_id", "session-id", "x-session-id"]:
        for name, value in headers:
            if name.lower() == expected:
                found = True
                explicit = trim_text(value)
                break
        if found: break
    if explicit: return explicit
    for name, value in headers:
        if name.lower() == "x-codex-turn-metadata":
            try:
                var metadata = JsonDocument(value)
                var session = _session(metadata)
                if session: return session
            except:
                pass
            break
    var session = _session(doc)
    if session: return session
    for name, value in headers:
        if name.lower() == "x-prodex-internal-conversation-namespace": return value
    return "gateway"


def _history(doc: JsonDocument, store: ProviderConversationStore, namespace: String) raises -> String:
    var previous = doc.string(doc.get(doc.root, "previous_response_id"))
    var saved = store.history(previous, namespace)
    if saved: return saved.value()
    var input = doc.get(doc.root, "input")
    if input >= 0 and doc.nodes[input].kind == JSON_ARRAY:
        for item in doc.nodes[input].children:
            var kind = doc.string(doc.get(item, "type"))
            if kind == "function_call_output" or kind == "custom_tool_call_output" or kind == "mcp_tool_result" or kind == "mcp_call_output":
                for key in ["call_id", "tool_call_id", "id"]:
                    var value = doc.get(item, key)
                    if value >= 0 and doc.nodes[value].kind == JSON_STRING:
                        var id = doc.nodes[value].text
                        if not trim_text(id): return "[]"
                        var history = store.find_tool_history(id, namespace)
                        return history.value() if history else String("[]")
    return "[]"


def _serve(mut connection: LoopbackHTTPConnection, request: LoopbackHTTPRequest, address: String, path: String, key: String, request_id: UInt64, mut conversations: ProviderConversationStore, connect_ms: UInt64, idle_ms: UInt64) raises:
    var target = String(request.target.split("?", maxsplit=1)[0])
    if request.method == "POST" and target == "/v1/chat/completions":
        var stream: LoopbackHTTPStream
        try:
            stream = deepseek_chat_completions_stream(
                address,
                deepseek_chat_completions_path(path, request.target),
                key,
                request.headers.copy(),
                request.body.copy(),
                connect_ms,
                120000,
                idle_ms,
                connection.fd,
            )
        except:
            _reply(connection, 502, "upstream request failed")
            return
        var status = stream.status
        var response_headers = _response_headers(stream.headers.copy())
        if status >= 400 or status == 204 or status == 304 or not deepseek_event_stream(stream.headers):
            var body = List[UInt8]()
            try:
                while not stream.done:
                    var chunk = stream.read_chunk()
                    body.extend(chunk^)
            except:
                stream.close()
                _reply(connection, 502, "upstream request failed")
                return
            connection.respond(status, response_headers, body, 30000)
            return
        try:
            connection.start_stream(status, response_headers, 30000)
            while not stream.done:
                var chunk = stream.read_chunk()
                if chunk:
                    connection.write_chunk(chunk, 30000)
            connection.finish_stream(30000)
        except:
            stream.close()
            connection.close()
        return
    if request.method != "POST" or target != "/v1/responses":
        _route_error(connection)
        return
    var source: String
    var history: String
    var namespace: String
    var previous_found: Bool
    try:
        source = String(from_utf8=Span(request.body))
        var doc = JsonDocument(source)
        namespace = _namespace(request.headers, doc)
        previous_found = conversations.contains(doc.string(doc.get(doc.root, "previous_response_id")), namespace)
        history = _history(doc, conversations, namespace)
        var tools = doc.get(doc.root, "tools")
        var web = doc.get(doc.root, "web_search_options") >= 0
        if tools >= 0 and doc.nodes[tools].kind == JSON_ARRAY:
            for tool in doc.nodes[tools].children:
                web = web or doc.string(doc.get(tool, "type")).startswith("web_search")
        if web:
            _ = translate_deepseek_request(source, history)
            _reply(connection, 501, "DeepSeek native web-search routing is not implemented")
            return
    except:
        _reply(connection, 502, "upstream request failed")
        return
    var now = _realtime_nanoseconds()
    if now < 0: raise Error("system clock returned a negative timestamp")
    var exchange: DeepSeekExchange
    try:
        exchange = DeepSeekExchange(address, path, key, source, request_id, "resp_deepseek_" + new_uuid7(), UInt64(now // 1000000000), request.headers, history, connect_timeout_ms=connect_ms, request_timeout_ms=120000, idle_timeout_ms=idle_ms, downstream_fd=connection.fd, previous_response_found=previous_found)
    except:
        _reply(connection, 502, "upstream request failed")
        return
    if not exchange.successful():
        # Frozen dispatch keeps non-2xx quota headers raw, without Codex projection.
        try:
            var body = exchange.read_body()
            connection.respond(exchange.status(), _response_headers(exchange.headers()), body, 30000)
        except:
            _reply(connection, 502, "upstream request failed")
        return
    if not deepseek_event_stream(exchange.headers()):
        var body: String
        try:
            body = exchange.read_buffered()
        except:
            _reply(connection, 502, "provider response could not be processed")
            return
        var response = JsonDocument(body)
        if response.string(response.get(response.root, "status")) != "failed" and trim_text(response.string(response.get(response.root, "id"))):
            conversations.insert(response.string(response.get(response.root, "id")), exchange.conversation_messages, namespace)
        var response_headers = List[Tuple[String, String]]()
        response_headers.append(("content-type", "application/json; charset=utf-8"))
        response_headers.extend(deepseek_codex_rate_limit_headers(exchange.headers()))
        connection.respond(exchange.status(), response_headers, _bytes(body), 30000)
        return
    try:
        var response_headers = List[Tuple[String, String]]()
        response_headers.append(("content-type", "text/event-stream; charset=utf-8"))
        response_headers.extend(deepseek_codex_rate_limit_headers(exchange.headers()))
        connection.start_stream(exchange.status(), response_headers, 30000)
        while not exchange.done:
            var events = exchange.read_events()
            for event in events:
                if event.startswith("event: response.completed\r\n") and trim_text(exchange.reader.state.response_id):
                    conversations.insert(exchange.reader.state.response_id, _stream_history(exchange), namespace)
                _write_event(connection, event)
        connection.finish_stream(30000)
    except:
        exchange.close()
        connection.close()


def serve_local_rewrite(mut listener: LoopbackHTTPListener, upstream_url: String, key: String, parent_fd: Int32 = -1) raises:
    var upstream = local_rewrite_upstream(upstream_url)
    _ = deepseek_request_headers([], key)
    var connect_ms = _timeout("PRODEX_RUNTIME_PROXY_HTTP_CONNECT_TIMEOUT_MS", 5000)
    var idle_ms = _timeout("PRODEX_RUNTIME_PROXY_STREAM_IDLE_TIMEOUT_MS", 300000)
    var request_id = UInt64(0)
    var conversations = ProviderConversationStore()
    var parent_bytes = List[UInt8](length=1, fill=0)
    if parent_fd >= 0:
        var flags = fcntl(parent_fd, F_GETFL, 0)
        if flags < 0 or fcntl(parent_fd, F_SETFL, flags | O_NONBLOCK) < 0:
            raise Error("could not configure local provider parent channel")
    # shortcut: requests run serially; add workers together with baseline admission controls.
    while True:
        if parent_fd >= 0:
            var parent = RawFileDescriptor(parent_fd)
            try:
                _ = parent.read_bytes(Span(parent_bytes))
                return
            except:
                var error = get_errno()
                if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
                    raise Error("local provider parent channel failed")
        var accepted = listener.accept(UInt64(100 if parent_fd >= 0 else 1000))
        if not accepted: continue
        var connection = accepted.take()
        request_id = request_id + 1 if request_id < UInt64.MAX else request_id
        try:
            var request = connection.read_request(120000)
            _serve(connection, request, upstream[0], upstream[1], key, request_id, conversations, connect_ms, idle_ms)
        except error:
            var message = String(error)
            var too_large = "oversized" in message or "exceeds wire limit" in message
            try:
                _reply(connection, 413 if too_large else 502, "proxied request body is too large" if too_large else "gateway request capture failed")
            except:
                pass
        connection.close()
