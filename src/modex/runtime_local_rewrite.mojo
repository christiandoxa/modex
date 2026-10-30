"""Internal loopback local-rewrite relay using native provider exchanges."""

from std.collections import Array, List, Optional, Span
from std.io import RawFileDescriptor
from std.memory import OwnedPointer
from std.net._sys.unix import AF_UNIX, F_GETFL, F_SETFL, O_NONBLOCK, SHUT_RDWR, SOCK_STREAM, shutdown, socketpair
from std.atomic import Atomic
from std.runtime import parallelism_level
from std.runtime._asyncrt import TaskGroup
from std.sys._libc import FcntlCommands, FcntlFDFlags, close, fcntl
from std.sys._libc_errno import ErrNo, get_errno
from std.os import getenv
from std.time import perf_counter, sleep
from std.time.time import _realtime_nanoseconds
from std.utils.lock import BlockingScopedLock, BlockingSpinLock

from .json import JSON_ARRAY, JSON_STRING, JsonDocument
from .loopback_http import HTTP_HEADER_LIMIT, HTTP_OUTBOUND_REQUEST_HEADER_LIMIT, HTTP_REQUEST_FIELD_LIMIT, LoopbackHTTPStream, _number
from .loopback_server import HTTP_MAX_REQUEST_HEADER_LIMIT, LoopbackHTTPConnection, LoopbackHTTPListener, LoopbackHTTPRequest, request_target_valid
from .log_operational import valid_url_authority
from .provider_deepseek_transport import DeepSeekExchange, deepseek_event_stream, deepseek_model_retry_available, deepseek_request_headers, deepseek_request_model_attempts, deepseek_retryable_api_key_response, deepseek_retryable_model_response
from .provider_conversations import ProviderConversationStore
from .provider_anthropic_messages import anthropic_auto_chat_fallback_safe, anthropic_search_filters_conflict, deepseek_anthropic_messages_body
from .provider_passthrough import DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES, deepseek_chat_completions_path, deepseek_chat_completions_stream
from .provider_rate_limits import deepseek_codex_rate_limit_headers
from .provider_request import translate_deepseek_request
from .provider_request_params import request_format
from .runtime_binding import RuntimeBindings
from .runtime_sse_binding_observer import RuntimeSSEBindingObserver

comptime HTTP_KEEP_ALIVE_MAX_PARKED = 128
# Each parked socket gets bounded read/scan work per event-loop pass.
comptime LOCAL_REWRITE_HEADER_CAPTURE_BYTES_PER_CONNECTION = 512
from .text import is_whitespace, trim_text, unsigned_value
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
    # Frozen URL assembly trims literal trailing slashes before parsing separators.
    path = path.replace("\\", "/")
    return address, _normalize_upstream_path(path + "/chat/completions")


def local_rewrite_anthropic_messages_upstream(url: String) raises -> Tuple[String, String]:
    var route = local_rewrite_upstream(url)
    var address = route[0]
    var remaining = String(url[byte=7:])
    var slash = remaining.find("/")
    var path = String(remaining[byte=slash:]) if slash >= 0 else String()
    while path.endswith("/"):
        var shorter = String(path[byte=:path.byte_length() - 1])
        path = shorter^
    if path.endswith("/anthropic/v1"):
        path += "/messages"
    elif path.endswith("/anthropic"):
        path += "/v1/messages"
    elif path.endswith("/v1") or path.endswith("/beta"):
        path = String(path[byte=:path.byte_length() - (3 if path.endswith("/v1") else 5)]) + "/anthropic/v1/messages"
    else:
        path += "/anthropic/v1/messages"
    path = path.replace("\\", "/")
    return address, _normalize_upstream_path(path)


def _normalize_upstream_path(target: String) -> String:
    var segments = List[String]()
    # Normalize the assembled path, preserving empty segments and the authority root.
    for segment in target.split("/"):
        var value = String(segment)
        var lower = value.lower()
        if lower == "." or lower == "%2e":
            continue
        if lower in ["..", ".%2e", "%2e.", "%2e%2e"]:
            if len(segments) > 1:
                _ = segments.pop()
            continue
        segments.append(value^)
    var path = String("/").join(segments)
    var encoded = String()
    comptime HEX = StaticString("0123456789ABCDEF")
    for byte in path.as_bytes():
        # Frozen URL path encoding also escapes "<>`{}; existing escapes stay intact.
        if byte >= 128 or Int(byte) in [34, 60, 62, 96, 123, 125]:
            encoded += "%" + HEX[byte=Int(byte) // 16] + HEX[byte=Int(byte) % 16]
        else:
            encoded += chr(Int(byte))
    return encoded


def _strict_tools_value(name: String, value: String) raises -> Bool:
    if not value:
        raise Error(name + " cannot be empty")
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            raise Error(name + " must not contain whitespace")
    var token = value.lower()
    if token in ["true", "1", "yes", "on"]:
        return True
    if token in ["false", "0", "no", "off"]:
        return False
    raise Error(name + " must be true or false")


def _validate_deepseek_beta_url(value: String, name: String = "PRODEX_DEEPSEEK_BETA_BASE_URL") raises:
    var invalid = name + " must be an http(s) URL with host and no credentials, query, or fragment"
    if not value:
        raise Error(name + " cannot be empty")
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            raise Error(name + " must not contain whitespace")
    var scheme_end = value.find("://")
    if scheme_end < 0 or value.find("?") >= 0 or value.find("#") >= 0:
        raise Error(invalid)
    var scheme = String(value[byte=:scheme_end]).lower()
    if scheme != "http" and scheme != "https":
        raise Error(invalid)
    var authority_start = scheme_end + 3
    var authority_end = value.byte_length()
    for delimiter in ["/", "\\"]:
        var found = value.find(delimiter, authority_start)
        if found >= 0 and found < authority_end:
            authority_end = found
    var authority = String(value[byte=authority_start:authority_end])
    if authority.find("@") >= 0 or not valid_url_authority(authority) or not _valid_deepseek_beta_host(authority):
        raise Error(invalid)


# shortcut: reject fullwidth mappings to forbidden host characters; add UTS #46 for full IDN parity.
def _valid_deepseek_beta_host(authority: String) -> Bool:
    if authority.startswith("["):
        return True
    var end = authority.find(":")
    var host = String(authority[byte=:end]) if end >= 0 else authority
    var decoded_host = List[UInt8]()
    var index = 0
    while index < host.byte_length():
        var byte = Int(host.as_bytes()[index])
        if byte == 60 or byte == 62 or byte == 91 or byte == 93 or byte == 94 or byte == 124:
            return False
        if byte == 37:
            if index + 2 >= host.byte_length():
                return False
            var high = _url_host_hex_value(Int(host.as_bytes()[index + 1]))
            var low = _url_host_hex_value(Int(host.as_bytes()[index + 2]))
            if high < 0 or low < 0:
                return False
            var decoded = high * 16 + low
            if decoded <= 32 or decoded == 127 or decoded in [
                35, 37, 47, 58, 60, 62, 63, 64, 91, 92, 93, 94, 124,
            ]:
                return False
            decoded_host.append(UInt8(decoded))
            index += 2
        else:
            decoded_host.append(UInt8(byte))
        index += 1
    var decoded_text: String
    try:
        decoded_text = String(from_utf8=Span(decoded_host))
    except:
        return False
    if decoded_text.byte_length() != len(decoded_host):
        return False
    for character in decoded_text.codepoints():
        var codepoint = Int(character)
        if 0xFF01 <= codepoint <= 0xFF5E:
            var mapped = codepoint - 0xFEE0
            if mapped in [35, 37, 47, 58, 60, 62, 63, 64, 91, 92, 93, 94, 124]:
                return False
    return valid_url_authority(decoded_text)


def _url_host_hex_value(byte: Int) -> Int:
    if 48 <= byte <= 57:
        return byte - 48
    if 65 <= byte <= 70:
        return byte - 55
    if 97 <= byte <= 102:
        return byte - 87
    return -1


def _web_search_mode(configured: Optional[String] = None) raises -> String:
    var name = String("deepseek.web_search_mode" if configured else "PRODEX_DEEPSEEK_WEB_SEARCH_MODE")
    var value = configured.value() if configured else getenv(name, "\x00")
    if not configured and value == "\x00": return "auto"
    if not value: raise Error(name + " cannot be empty")
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            raise Error(name + " must not contain whitespace")
    var token = value.lower()
    if token == "auto" or token == "anthropic": return token
    if token in ["off", "disabled", "disable"]: return "off"
    if token in ["openai_chat", "openai-chat", "chat"]: return "openai_chat"
    raise Error(name + " must be auto, off, openai_chat, or anthropic")


def deepseek_runtime_route(configured_mode: Optional[String] = None, configured_strict: Optional[String] = None, configured_beta: Optional[String] = None) raises -> Tuple[Bool, String, String, String]:
    var strict_name = String("deepseek.strict_tools" if configured_strict else "PRODEX_DEEPSEEK_STRICT_TOOLS")
    var strict_value = configured_strict.value() if configured_strict else getenv(strict_name, "\x00")
    var strict_tools = False
    if configured_strict or strict_value != "\x00":
        strict_tools = _strict_tools_value(strict_name, strict_value)
    var beta_name = String("deepseek.beta_base_url" if configured_beta else "PRODEX_DEEPSEEK_BETA_BASE_URL")
    var beta_value = configured_beta.value() if configured_beta else getenv(beta_name, "\x00")
    if not strict_tools:
        if configured_beta or beta_value != "\x00":
            _validate_deepseek_beta_url(beta_value, beta_name)
        return False, String(), String(), _web_search_mode(configured_mode)
    if not configured_beta and beta_value == "\x00":
        raise Error("strict tools require PRODEX_DEEPSEEK_BETA_BASE_URL to be a numeric loopback HTTP URL")
    if configured_beta:
        _validate_deepseek_beta_url(beta_value, beta_name)
    var route = (String(), String())
    try:
        route = local_rewrite_upstream(beta_value)
    except:
        raise Error(beta_name + " must be a credential-free numeric loopback HTTP URL")
    return True, route[0], route[1], _web_search_mode(configured_mode)


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


def _invalid_request_target(mut connection: LoopbackHTTPConnection) raises:
    connection.respond(400, [
        ("content-type", "application/json"), ("cache-control", "no-store"),
        ("x-content-type-options", "nosniff"),
    ], _bytes('{"error":{"code":"invalid_request_target","message":"request target is invalid"}}'), 30000)


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
        var valid = True
        for byte in value.as_bytes():
            if byte > 126 or byte < 32 and byte != 9:
                valid = False
                break
        if not valid:
            continue
        output.append((name, value))
    return output^


def _binding_response_id(body: String) -> String:
    try:
        var doc = JsonDocument(body)
        var node = doc.get(doc.get(doc.root, "response"), "id")
        if node < 0 or doc.nodes[node].kind != JSON_STRING:
            node = doc.get(doc.root, "id")
        if node < 0 or doc.nodes[node].kind != JSON_STRING:
            node = doc.get(doc.root, "response_id")
        if node >= 0 and doc.nodes[node].kind == JSON_STRING:
            return trim_text(doc.string(node))
        node = doc.get(doc.root, "responseId")
        if node >= 0 and doc.nodes[node].kind == JSON_STRING:
            return trim_text(doc.string(node))
        return trim_text(doc.string(doc.get(doc.get(doc.root, "message"), "id")))
    except:
        return ""


def _passthrough_response(mut connection: LoopbackHTTPConnection, mut stream: LoopbackHTTPStream, state_ptr: Pointer[LocalRewriteSharedState, MutUntrackedOrigin], api_key_index: Int, prebuffered_body: List[UInt8]) raises:
    var streaming = 200 <= stream.status < 400 and stream.status != 204 and stream.status != 304 and deepseek_event_stream(stream.headers)
    if not streaming and (stream.status < 200 or stream.status >= 300):
        stream.max_body_bytes = DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES
        stream.max_wire_bytes = HTTP_HEADER_LIMIT * 2 + 65536 + DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES * 8
        if stream.length > DEEPSEEK_PASSTHROUGH_MAX_BODY_BYTES:
            stream.close()
            # The frozen >=400 send fails before dispatch; 3xx buffering fails
            # after its response is accepted, as a provider processing error.
            _reply(connection, 502, "provider response could not be processed" if 300 <= stream.status < 400 else "upstream request failed")
            return
    var response_headers = _response_headers(stream.headers.copy())
    if not streaming:
        var body = prebuffered_body.copy()
        try:
            while not stream.done:
                var chunk = stream.read_chunk()
                body.extend(chunk^)
        except:
            stream.close()
            # A buffered <400 response reached downstream response processing;
            # >=400 was already an upstream send-path failure in the release.
            _reply(connection, 502, "provider response could not be processed" if 200 <= stream.status < 400 else "upstream request failed")
            return
        if 200 <= stream.status < 400:
            try:
                state_ptr[].remember_binding(0, _binding_response_id(String(from_utf8=Span(body))), api_key_index)
            except:
                pass
        # TinyHTTP's buffered path retains Content-Length: 0 for bodyless replies.
        var sse = deepseek_event_stream(stream.headers)
        connection.respond(stream.status, response_headers, body, 30000, not sse, sse and (stream.status == 204 or stream.status == 304))
        return
    try:
        connection.start_stream(stream.status, response_headers, 30000)
        var observer = RuntimeSSEBindingObserver()
        var observing = True
        while not stream.done:
            var chunk = stream.read_chunk()
            if chunk:
                if observing:
                    try:
                        var observed = observer.consume(Span(chunk))
                        for response_id in observed:
                            state_ptr[].remember_binding(0, response_id, api_key_index)
                        if observer.is_failed():
                            observing = False
                    except:
                        observing = False
                connection.write_chunk(chunk, 30000)
        if observing:
            try:
                var final_ids = observer.finish()
                for response_id in final_ids:
                    state_ptr[].remember_binding(0, response_id, api_key_index)
            except:
                pass
        connection.finish_stream(30000, include_head_terminal_chunk=True)
    except:
        stream.close()
        connection.close()


def _session(doc: JsonDocument) -> String:
    var node = doc.get(doc.root, "session_id")
    if node < 0:
        node = doc.get(doc.get(doc.root, "client_metadata"), "session_id")
    return trim_text(doc.string(node))


def _request_session(headers: List[Tuple[String, String]], doc: JsonDocument) -> String:
    var explicit = String()
    for expected in ["session_id", "session-id", "x-session-id"]:
        for name, value in headers:
            if name.lower() == expected:
                explicit = trim_text(value)
                break
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
    return _session(doc)


def _request_turn_state(headers: List[Tuple[String, String]]) -> String:
    for name, value in headers:
        if name.lower() == "x-codex-turn-state":
            return trim_text(value)
    return ""


def _binding_error(mut connection: LoopbackHTTPConnection) raises:
    connection.respond(503, [("content-type", "application/json"), ("cache-control", "no-store"), ("x-content-type-options", "nosniff")], _bytes('{"error":{"code":"bound_continuation_unavailable","message":"bound continuation provider is unavailable"}}'), 30000)


def _namespace(headers: List[Tuple[String, String]], doc: JsonDocument) -> String:
    var session = _request_session(headers, doc)
    if session: return session
    for name, value in headers:
        if name.lower() == "x-prodex-internal-conversation-namespace": return value
    return "gateway"


def _continuation_identity_valid(headers: List[Tuple[String, String]], doc: JsonDocument) -> Bool:
    var parts: List[String] = [trim_text(doc.string(doc.get(doc.root, "previous_response_id"))), _request_session(headers, doc)]
    for name, value in headers:
        if name.lower() == "x-codex-turn-state":
            parts.append(trim_text(value))
            break
    for part in parts:
        if part.byte_length() > 1024: return False
        for character in part.codepoints():
            var codepoint = Int(character)
            if codepoint <= 31 or 127 <= codepoint <= 159: return False
    return True


def _parent_channel_closed(parent_fd: Int32, mut parent_bytes: List[UInt8]) raises -> Bool:
    if parent_fd < 0:
        return False
    var parent = RawFileDescriptor(parent_fd)
    try:
        _ = parent.read_bytes(Span(parent_bytes))
        return True
    except:
        var error = get_errno()
        if error != ErrNo.EAGAIN and error != ErrNo.EINTR:
            raise Error("local provider parent channel failed")
    return False


def _evict_oldest_idle_connection(mut parked: List[LoopbackHTTPConnection]) raises -> Bool:
    var evicted = False
    var parked_count = len(parked)
    for _ in range(parked_count):
        var idle = parked.pop()
        if not evicted and not idle.request_ready():
            idle.close()
            evicted = True
        else:
            parked.insert(0, idle^)
    return evicted


def _history(doc: JsonDocument, store: ProviderConversationStore, namespace: Optional[String]) raises -> String:
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


struct LocalRewriteSharedState(Movable):
    var lock: BlockingSpinLock
    var conversations: ProviderConversationStore
    var bindings: RuntimeBindings
    var sequence: UInt64
    var stopping: Atomic[Int]
    var active: Int
    var active_fds: List[Int32]
    var queued: List[LoopbackHTTPConnection]
    var completed: List[LoopbackHTTPConnection]
    var cancel_read_fd: Int32
    var cancel_write_fd: Int32
    var address: String
    var path: String
    var messages_address: String
    var messages_path: String
    var api_keys: List[String]
    var api_key_cursor: Int
    var connect_ms: UInt64
    var idle_ms: UInt64
    var lookahead_ms: UInt64
    var allow_local_file_access: Bool
    var strict_tools: Bool
    var beta_address: String
    var beta_path: String
    var web_search_mode: String

    def __init__(out self, api_keys: List[String], endpoint: String, address: String, path: String, messages_address: String, messages_path: String, connect_ms: UInt64, idle_ms: UInt64, lookahead_ms: UInt64, allow_local_file_access: Bool, strict_tools: Bool, beta_address: String, beta_path: String, web_search_mode: String) raises:
        self.lock = BlockingSpinLock()
        self.conversations = ProviderConversationStore()
        self.bindings = RuntimeBindings(api_keys[0], endpoint)
        self.sequence = 0
        self.api_keys = api_keys.copy()
        self.api_key_cursor = 0
        self.stopping = Atomic[Int](0)
        self.active = 0
        self.active_fds = List[Int32]()
        self.queued = List[LoopbackHTTPConnection]()
        self.completed = List[LoopbackHTTPConnection]()
        self.cancel_read_fd = -1
        self.cancel_write_fd = -1
        self.address = address
        self.path = path
        self.messages_address = messages_address
        self.messages_path = messages_path
        self.connect_ms = connect_ms
        self.idle_ms = idle_ms
        self.lookahead_ms = lookahead_ms
        self.allow_local_file_access = allow_local_file_access
        self.strict_tools = strict_tools
        self.beta_address = beta_address
        self.beta_path = beta_path
        self.web_search_mode = web_search_mode
        var descriptors = Array[Int32, 2](fill=-1)
        if socketpair(AF_UNIX, SOCK_STREAM, 0, Pointer(to=descriptors)) != 0:
            raise Error("could not create local provider cancellation channel")
        self.cancel_read_fd = descriptors[0]
        self.cancel_write_fd = descriptors[1]
        for descriptor in descriptors:
            if fcntl(descriptor, FcntlCommands.F_SETFD, FcntlFDFlags.FD_CLOEXEC) < 0:
                _ = close(self.cancel_read_fd)
                _ = close(self.cancel_write_fd)
                self.cancel_read_fd = -1
                self.cancel_write_fd = -1
                raise Error("could not protect local provider cancellation channel")

    def next_api_key_start(mut self) -> Int:
        var selected: Int
        with BlockingScopedLock(self.lock):
            selected = self.api_key_cursor
            self.api_key_cursor += 1
            if self.api_key_cursor >= len(self.api_keys): self.api_key_cursor = 0
        return selected

    def api_key_count(self) -> Int:
        return len(self.api_keys)

    def api_key_at(self, index: Int) -> String:
        return self.api_keys[index]

    def __deinit__(deinit self):
        if self.cancel_read_fd >= 0: _ = close(self.cancel_read_fd)
        if self.cancel_write_fd >= 0: _ = close(self.cancel_write_fd)

    def next_request_id(mut self) -> UInt64:
        var request_id: UInt64
        with BlockingScopedLock(self.lock):
            if self.sequence < UInt64.MAX:
                self.sequence += 1
            request_id = self.sequence
        return request_id

    def permits(mut self, previous: String, turn: String, session: String) -> Bool:
        var allowed: Bool
        with BlockingScopedLock(self.lock):
            allowed = self.bindings.permits(previous, turn, session)
        return allowed

    def remember_request(mut self, previous: String, turn: String, session: String, api_key_index: Int) raises:
        with BlockingScopedLock(self.lock):
            self.bindings.remember_request(previous, turn, session, self.api_keys[api_key_index])

    def remember_binding(mut self, kind: Int, key: String, api_key_index: Int) raises:
        with BlockingScopedLock(self.lock):
            self.bindings.remember(kind, key, self.api_keys[api_key_index])

    def history(mut self, doc: JsonDocument, namespace: Optional[String]) raises -> Tuple[Bool, String]:
        var found: Bool
        var messages: String
        with BlockingScopedLock(self.lock):
            var previous = doc.string(doc.get(doc.root, "previous_response_id"))
            found = self.conversations.contains(previous, namespace)
            messages = _history(doc, self.conversations, namespace)
        return (found, messages)

    def insert_conversation(mut self, response_id: String, messages: String, namespace: Optional[String]) raises:
        with BlockingScopedLock(self.lock):
            self.conversations.insert(response_id, messages, namespace)

    def has_capacity(mut self, worker_count: Int) -> Bool:
        var available: Bool
        with BlockingScopedLock(self.lock):
            available = self.stopping.load() == 0 and self.active + len(self.queued) < worker_count
        return available

    def enqueue(mut self, var connection: LoopbackHTTPConnection):
        with BlockingScopedLock(self.lock):
            self.queued.append(connection^)

    def take_work(mut self) -> Optional[LoopbackHTTPConnection]:
        var selected = Optional[LoopbackHTTPConnection]()
        with BlockingScopedLock(self.lock):
            if self.stopping.load() == 0 and self.queued:
                self.active += 1
                var connection = self.queued.pop(0)
                connection.worker_tracked = True
                self.active_fds.append(connection.fd)
                selected = Optional[LoopbackHTTPConnection](connection^)
        return selected^

    def finish_request(mut self, var connection: LoopbackHTTPConnection):
        var close_connection = Optional[LoopbackHTTPConnection]()
        with BlockingScopedLock(self.lock):
            self.active -= 1
            connection.worker_tracked = False
            var remaining_fds = List[Int32]()
            for fd in self.active_fds:
                if fd != connection.fd:
                    remaining_fds.append(fd)
            self.active_fds = remaining_fds^
            if self.stopping.load() != 0 or not connection.waiting_for_request:
                close_connection = Optional[LoopbackHTTPConnection](connection^)
            else:
                self.completed.append(connection^)
        if close_connection:
            var to_close = close_connection.take()
            to_close.close()

    def take_completed(mut self) -> List[LoopbackHTTPConnection]:
        var ready: List[LoopbackHTTPConnection]
        with BlockingScopedLock(self.lock):
            ready = self.completed^
            self.completed = List[LoopbackHTTPConnection]()
        return ready^

    def has_pending_work(mut self) -> Bool:
        var pending: Bool
        with BlockingScopedLock(self.lock):
            pending = self.active > 0 or len(self.queued) > 0 or len(self.completed) > 0
        return pending

    def is_stopping(self) -> Bool:
        return self.stopping.load() != 0

    def stop(mut self):
        var queued: List[LoopbackHTTPConnection]
        var completed: List[LoopbackHTTPConnection]
        with BlockingScopedLock(self.lock):
            self.stopping.store(1)
            _ = shutdown(self.cancel_write_fd, SHUT_RDWR)
            for fd in self.active_fds:
                _ = shutdown(fd, SHUT_RDWR)
            queued = self.queued^
            self.queued = List[LoopbackHTTPConnection]()
            completed = self.completed^
            self.completed = List[LoopbackHTTPConnection]()
        while queued:
            var connection = queued.pop()
            connection.close()
        while completed:
            var connection = completed.pop()
            connection.close()


def _serve(mut connection: LoopbackHTTPConnection, request: LoopbackHTTPRequest, address: String, path: String, messages_address: String, messages_path: String, request_id: UInt64, state_ptr: Pointer[LocalRewriteSharedState, MutUntrackedOrigin], connect_ms: UInt64, idle_ms: UInt64, lookahead_ms: UInt64, allow_local_file_access: Bool, strict_tools: Bool, beta_address: String, beta_path: String, web_search_mode: String) raises:
    var target = String(request.target.split("?", maxsplit=1)[0])
    if target != "/v1/chat/completions" and target != "/v1/responses":
        _route_error(connection)
        return
    var source = String()
    var doc = JsonDocument("{}")
    try:
        source = String(from_utf8=Span(request.body))
        doc = JsonDocument(source)
    except:
        if target == "/v1/responses":
            _ = state_ptr[].next_api_key_start()
            _reply(connection, 502, "upstream request failed")
            return
    var previous = trim_text(doc.string(doc.get(doc.root, "previous_response_id")))
    var turn = _request_turn_state(request.headers)
    var session = _request_session(request.headers, doc)
    if not _continuation_identity_valid(request.headers, doc) or not state_ptr[].permits(previous, turn, session):
        _binding_error(connection)
        return
    var key_count = state_ptr[].api_key_count()
    var attempt_count = key_count
    var key_start = state_ptr[].next_api_key_start()
    var key_index = key_start
    if target == "/v1/chat/completions":
        var stream: LoopbackHTTPStream
        var prebuffered_error = List[UInt8]()
        try:
            stream = deepseek_chat_completions_stream(
                address,
                deepseek_chat_completions_path(path, request.target),
                state_ptr[].api_key_at(key_index),
                request.headers.copy(),
                request.body.copy(),
                connect_ms,
                120000,
                idle_ms,
                connection.fd,
                request.method,
                request_header_limit=HTTP_OUTBOUND_REQUEST_HEADER_LIMIT,
                request_field_limit=HTTP_REQUEST_FIELD_LIMIT,
                cancel_fd=state_ptr[].cancel_read_fd,
            )
        except:
            _reply(connection, 502, "upstream request failed")
            return
        for attempt_index in range(attempt_count):
            prebuffered_error = List[UInt8]()
            if attempt_index > 0:
                key_index = (key_start + attempt_index) % key_count
                try:
                    stream = deepseek_chat_completions_stream(
                        address,
                        deepseek_chat_completions_path(path, request.target),
                        state_ptr[].api_key_at(key_index),
                        request.headers.copy(),
                        request.body.copy(),
                        connect_ms,
                        120000,
                        idle_ms,
                        connection.fd,
                        request.method,
                        request_header_limit=HTTP_OUTBOUND_REQUEST_HEADER_LIMIT,
                        request_field_limit=HTTP_REQUEST_FIELD_LIMIT,
                        cancel_fd=state_ptr[].cancel_read_fd,
                    )
                except:
                    _reply(connection, 502, "upstream request failed")
                    return
            if stream.status >= 400 and attempt_index + 1 < attempt_count:
                try:
                    prebuffered_error = stream.read_buffered()
                except:
                    _reply(connection, 502, "upstream request failed")
                    return
                if deepseek_retryable_api_key_response(stream.status, prebuffered_error, attempt_index, attempt_count):
                    stream.close()
                    continue
            break
        if 200 <= stream.status < 400:
            state_ptr[].remember_request(previous, turn, session, key_index)
        _passthrough_response(connection, stream, state_ptr, key_index, prebuffered_error)
        return
    var history: String
    var namespace = Optional[String]()
    var previous_found: Bool
    var web = False
    var fallback_web_search = False
    try:
        if not allow_local_file_access:
            namespace = Optional[String](_namespace(request.headers, doc))
        var context = state_ptr[].history(doc, namespace)
        previous_found = context[0]
        history = context[1]
        var tools = doc.get(doc.root, "tools")
        web = doc.get(doc.root, "web_search_options") >= 0
        if tools >= 0 and doc.nodes[tools].kind == JSON_ARRAY:
            for tool in doc.nodes[tools].children:
                web = web or doc.string(doc.get(tool, "type")).startswith("web_search")
        var has_json_format = False
        if web and request_format(doc): has_json_format = True
        if web and (anthropic_search_filters_conflict(source) or has_json_format):
            _ = translate_deepseek_request(source, history, strict_tools, web_search_mode)
            var input = doc.get(doc.root, "input")
            if input >= 0 and doc.nodes[input].kind == JSON_STRING and not doc.nodes[input].text:
                connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                return
            if web_search_mode == "auto":
                web = False
                fallback_web_search = True
            elif web_search_mode == "anthropic":
                connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                return
        if web and web_search_mode == "off":
            _ = translate_deepseek_request(source, history, strict_tools, web_search_mode)
        if web_search_mode == "openai_chat":
            web = False
        if web:
            var input = doc.get(doc.root, "input")
            if input >= 0 and doc.nodes[input].kind == JSON_STRING and not doc.nodes[input].text:
                connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                return
            var translated = translate_deepseek_request(source, history, strict_tools, web_search_mode, ignore_web_search=fallback_web_search)
            try:
                _ = deepseek_anthropic_messages_body(translated)
            except error:
                var reason = String(error)
                if reason == "Anthropic Messages slice requires a user or assistant message" or reason == "Anthropic tool function arguments must be valid JSON":
                    connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                    return
                elif anthropic_auto_chat_fallback_safe(reason):
                    if web_search_mode == "auto":
                        web = False
                        fallback_web_search = True
                    elif web_search_mode == "anthropic":
                        connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                        return
                    else:
                        raise
                else:
                    raise
    except:
        _reply(connection, 502, "upstream request failed")
        return
    var now = _realtime_nanoseconds()
    if now < 0: raise Error("system clock returned a negative timestamp")
    var model_attempts: List[String]
    try:
        model_attempts = deepseek_request_model_attempts(doc)
    except:
        connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"DeepSeek model fallback could not be parsed","type":"invalid_request_error"}}'), 30000)
        return
    var exchange: DeepSeekExchange
    var prebuffered_error = List[UInt8]()
    var native_first_event_retries = 0
    var terminal_attempt = False
    var exit_credentials = False
    try:
        var exchange_address = messages_address if web else (beta_address if strict_tools else address)
        var exchange_path = messages_path if web else (beta_path if strict_tools else path)
        exchange = DeepSeekExchange(exchange_address, exchange_path, state_ptr[].api_key_at(key_index), source, request_id, "resp_deepseek_" + new_uuid7(), UInt64(now // 1000000000), request.headers, history, strict_tools=strict_tools, web_search_mode=web_search_mode, connect_timeout_ms=connect_ms, request_timeout_ms=120000, idle_timeout_ms=idle_ms, downstream_fd=connection.fd, previous_response_found=previous_found, native_messages=web, request_method=request.method, request_header_limit=HTTP_OUTBOUND_REQUEST_HEADER_LIMIT, request_field_limit=HTTP_REQUEST_FIELD_LIMIT, ignore_web_search=fallback_web_search, cancel_fd=state_ptr[].cancel_read_fd, model_override=model_attempts[0])
    except error:
        if web and (String(error) == "Anthropic Messages slice requires a user or assistant message" or String(error) == "Anthropic tool function arguments must be valid JSON"):
            connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
        else:
            _reply(connection, 502, "upstream request failed")
        return
    for attempt_index in range(attempt_count):
        if attempt_index > 0:
            key_index = (key_start + attempt_index) % key_count
        for model_index in range(len(model_attempts)):
            prebuffered_error = List[UInt8]()
            if attempt_index > 0 or model_index > 0:
                try:
                    var exchange_address = messages_address if web else (beta_address if strict_tools else address)
                    var exchange_path = messages_path if web else (beta_path if strict_tools else path)
                    exchange = DeepSeekExchange(exchange_address, exchange_path, state_ptr[].api_key_at(key_index), source, request_id, "resp_deepseek_" + new_uuid7(), UInt64(now // 1000000000), request.headers, history, strict_tools=strict_tools, web_search_mode=web_search_mode, connect_timeout_ms=connect_ms, request_timeout_ms=120000, idle_timeout_ms=idle_ms, downstream_fd=connection.fd, previous_response_found=previous_found, native_messages=web, request_method=request.method, request_header_limit=HTTP_OUTBOUND_REQUEST_HEADER_LIMIT, request_field_limit=HTTP_REQUEST_FIELD_LIMIT, ignore_web_search=fallback_web_search, cancel_fd=state_ptr[].cancel_read_fd, model_override=model_attempts[model_index])
                except error:
                    if web and (String(error) == "Anthropic Messages slice requires a user or assistant message" or String(error) == "Anthropic tool function arguments must be valid JSON"):
                        connection.respond(400, [("content-type", "application/json; charset=utf-8")], _bytes('{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'), 30000)
                    else:
                        _reply(connection, 502, "upstream request failed")
                    return
            if exchange.status() >= 400:
                var has_next_model = model_index + 1 < len(model_attempts)
                var has_next_key = attempt_index + 1 < attempt_count
                if has_next_model or has_next_key:
                    try:
                        prebuffered_error = exchange.read_error_body()
                    except:
                        _reply(connection, 502, "upstream request failed")
                        return
                    if deepseek_retryable_model_response(exchange.status(), prebuffered_error, model_index, len(model_attempts)):
                        exchange.close()
                        continue
                    if deepseek_retryable_api_key_response(exchange.status(), prebuffered_error, attempt_index, attempt_count):
                        exchange.close()
                        exit_credentials = True
                        break
                terminal_attempt = True
                break
            if exchange.successful() and deepseek_event_stream(exchange.headers()):
                var first_event_class: Int
                try:
                    first_event_class = exchange.prefetch(lookahead_ms)
                except:
                    _reply(connection, 502, "upstream request failed")
                    return
                if web and first_event_class >= 0 and native_first_event_retries == 0:
                    var can_retry_model = first_event_class >= 1 and first_event_class <= 4 and deepseek_model_retry_available(model_index, len(model_attempts))
                    var can_retry_key = first_event_class <= 3 and attempt_index + 1 < attempt_count
                    if can_retry_model:
                        native_first_event_retries += 1
                        exchange.close()
                        continue
                    if can_retry_key:
                        native_first_event_retries += 1
                        exchange.close()
                        exit_credentials = True
                        break
            terminal_attempt = True
            break
        if terminal_attempt:
            break
        if exit_credentials:
            exit_credentials = False
            continue
    if 200 <= exchange.status() < 400 and (not exchange.successful() or not deepseek_event_stream(exchange.headers())):
        state_ptr[].remember_request(previous, turn, session, key_index)
    if not exchange.successful():
        # Frozen dispatch keeps non-2xx quota headers raw, without Codex projection.
        _passthrough_response(connection, exchange.http, state_ptr, key_index, prebuffered_error)
        return
    if not deepseek_event_stream(exchange.headers()):
        var body: String
        try:
            body = exchange.read_buffered()
        except error:
            # Match the releases' internal failure for a non-object first choice.
            if String(error) == "DeepSeek chat response choice is not an object":
                connection.respond(500, [], List[UInt8](), 30000)
            else:
                _reply(connection, 502, "provider response could not be processed")
            return
        var response = JsonDocument(body)
        state_ptr[].remember_binding(0, _binding_response_id(body), key_index)
        if response.string(response.get(response.root, "status")) != "failed" and trim_text(response.string(response.get(response.root, "id"))):
            state_ptr[].insert_conversation(response.string(response.get(response.root, "id")), exchange.conversation_messages, namespace)
        var response_headers = List[Tuple[String, String]]()
        response_headers.append(("content-type", "application/json; charset=utf-8"))
        response_headers.extend(deepseek_codex_rate_limit_headers(exchange.headers()))
        connection.respond(exchange.status(), response_headers, _bytes(body), 30000)
        return
    state_ptr[].remember_request(previous, turn, session, key_index)
    try:
        var response_headers = List[Tuple[String, String]]()
        response_headers.append(("content-type", "text/event-stream; charset=utf-8"))
        response_headers.extend(deepseek_codex_rate_limit_headers(exchange.headers()))
        connection.start_stream(exchange.status(), response_headers, 30000)
        while not exchange.done:
            var events = exchange.read_events()
            state_ptr[].remember_binding(0, exchange.reader.state.response_id, key_index)
            for event in events:
                if event.startswith("event: response.completed\r\n") and trim_text(exchange.reader.state.response_id):
                    state_ptr[].insert_conversation(exchange.reader.state.response_id, _stream_history(exchange), namespace)
                _write_event(connection, event)
        if exchange.downstream_body_incomplete:
            # Both releases answer queued requests after leaving this response chunk open.
            connection.continue_after_incomplete_stream()
        else:
            connection.finish_stream(30000, include_head_terminal_chunk=True)
    except:
        exchange.close()
        connection.close()


def _serve_connection(mut connection: LoopbackHTTPConnection, address: String, path: String, messages_address: String, messages_path: String, state_ptr: Pointer[LocalRewriteSharedState, MutUntrackedOrigin], connect_ms: UInt64, idle_ms: UInt64, lookahead_ms: UInt64, allow_local_file_access: Bool, strict_tools: Bool, beta_address: String, beta_path: String, web_search_mode: String) raises:
    var request_id = state_ptr[].next_request_id()
    var request = LoopbackHTTPRequest("", "", List[Tuple[String, String]](), List[UInt8]())
    var captured = False
    try:
        request = connection.read_request(120000, allow_upgrade_headers=True, validate_request_target=True, reject_chunked_trailers=True, defer_expectation_errors=True, preflight_body_limit_before_continue=True, use_request_version_for_continue=True, use_request_version_for_response=True, request_header_limit=HTTP_MAX_REQUEST_HEADER_LIMIT, tiny_http_request_line_compat=True)
        captured = True
    except error:
        var message = String(error)
        var malformed_syntax = message == "malformed HTTP request line" or message == "unsupported HTTP request version" or message == "malformed HTTP request target spacing" or message == "malformed HTTP method" or message == "malformed HTTP request header" or message == "malformed HTTP header name" or message == "malformed HTTP header value"
        if message == "invalid HTTP request target" or message == "malformed HTTP request target":
            try:
                _invalid_request_target(connection)
            except:
                pass
        elif message == "unsupported HTTP expectation":
            try:
                connection.respond(417, [], List[UInt8](), 30000)
            except:
                pass
        elif message == "websocket upgrade fallback":
            try:
                _reply(connection, 426, "provider adapter requires HTTPS Responses transport fallback")
            except:
                pass
        elif message == "truncated HTTP request":
            if connection.request_head_was_parsed() and connection.request_body_was_deferred():
                try:
                    _reply(connection, 502, "upstream request failed")
                except:
                    pass
        elif message == "non-ASCII byte in HTTP header":
            connection.close()
        else:
            if malformed_syntax:
                try:
                    connection.respond(400, [], List[UInt8](), 30000)
                except:
                    pass
            elif message == "malformed HTTP request line suffix":
                try:
                    _reply(connection, 502, "upstream request failed")
                except:
                    pass
            else:
                var too_large = "oversized" in message or "exceeds wire limit" in message
                try:
                    _reply(connection, 413 if too_large else 502, "proxied request body is too large" if too_large else "gateway request capture failed")
                except:
                    pass
    if captured:
        try:
            if not request_target_valid(request.target):
                _invalid_request_target(connection)
            else:
                var websocket_upgrade = False
                for header in request.headers:
                    if String(header[0]).lower() == "upgrade" and String(header[1]).lower() == "websocket":
                        websocket_upgrade = True
                        break
                if websocket_upgrade:
                    connection.keep_alive = False
                    _reply(connection, 426, "provider adapter requires HTTPS Responses transport fallback")
                else:
                    _serve(connection, request, address, path, messages_address, messages_path, request_id, state_ptr, connect_ms, idle_ms, lookahead_ms, allow_local_file_access, strict_tools, beta_address, beta_path, web_search_mode)
        except error:
            var message = String(error)
            var too_large = "oversized" in message or "exceeds wire limit" in message
            try:
                _reply(connection, 413 if too_large else 502, "proxied request body is too large" if too_large else "gateway request capture failed")
            except:
                pass


__async def _local_rewrite_worker(state_ptr: Pointer[LocalRewriteSharedState, MutUntrackedOrigin]):
    while not state_ptr[].is_stopping():
        var selected = state_ptr[].take_work()
        if not selected:
            sleep(0.005)
            continue
        var connection = selected.take()
        try:
            _serve_connection(connection, state_ptr[].address, state_ptr[].path, state_ptr[].messages_address, state_ptr[].messages_path, state_ptr, state_ptr[].connect_ms, state_ptr[].idle_ms, state_ptr[].lookahead_ms, state_ptr[].allow_local_file_access, state_ptr[].strict_tools, state_ptr[].beta_address, state_ptr[].beta_path, state_ptr[].web_search_mode)
        except:
            pass
        state_ptr[].finish_request(connection^)


# shortcut: default count has a four-lane floor; cap at twelve pending resource qualification.
comptime LOCAL_REWRITE_MAX_WORKERS = 12


def local_rewrite_worker_count() raises -> Int:
    var name = String("PRODEX_RUNTIME_PROXY_WORKER_COUNT")
    var error_prefix = String("runtime configuration is invalid; ") + name
    var parallelism = max(1, parallelism_level())
    var fallback = min(LOCAL_REWRITE_MAX_WORKERS, max(4, parallelism))
    var configured = getenv(name, "\x00")
    if configured == "\x00":
        return fallback
    if not configured:
        raise Error(error_prefix + " cannot be empty")
    for character in configured.codepoints():
        if is_whitespace(Int(character)):
            raise Error(error_prefix + " must not contain whitespace")
    var requested: UInt64
    try:
        requested = unsigned_value(configured)
    except:
        raise Error(error_prefix + " must be an unsigned integer")
    if requested == 0:
        raise Error(error_prefix + " must be greater than zero")
    return min(fallback, Int(min(requested, UInt64(LOCAL_REWRITE_MAX_WORKERS))))


def serve_local_rewrite(mut listener: LoopbackHTTPListener, upstream_url: String, api_keys: List[String], strict_tools: Bool, beta_address: String, beta_path: String, parent_fd: Int32 = -1, allow_local_file_access: Bool = False, web_search_mode: String = "auto") raises:
    var upstream = local_rewrite_upstream(upstream_url)
    var anthropic_upstream = local_rewrite_anthropic_messages_upstream(upstream_url)
    if not api_keys: raise Error("DeepSeek provider has no API keys configured")
    for key in api_keys:
        _ = deepseek_request_headers([], key)
    var connect_ms = _timeout("PRODEX_RUNTIME_PROXY_HTTP_CONNECT_TIMEOUT_MS", 5000)
    var idle_ms = _timeout("PRODEX_RUNTIME_PROXY_STREAM_IDLE_TIMEOUT_MS", 300000)
    var lookahead_ms = _timeout("PRODEX_RUNTIME_PROXY_SSE_LOOKAHEAD_TIMEOUT_MS", 1000)
    var parent_bytes = List[UInt8](length=1, fill=0)
    var parked = List[LoopbackHTTPConnection]()
    var overflow = List[LoopbackHTTPConnection]()
    if parent_fd >= 0:
        var flags = fcntl(parent_fd, F_GETFL, 0)
        if flags < 0 or fcntl(parent_fd, F_SETFL, flags | O_NONBLOCK) < 0:
            raise Error("could not configure local provider parent channel")
    # Worker pointers are untracked, so keep their state at a stable address until join.
    var state = OwnedPointer(LocalRewriteSharedState(api_keys, upstream_url, upstream[0], upstream[1], anthropic_upstream[0], anthropic_upstream[1], connect_ms, idle_ms, lookahead_ms, allow_local_file_access, strict_tools, beta_address, beta_path, web_search_mode))
    var state_ptr = state.ptr().unsafe_origin_cast[MutUntrackedOrigin]()
    var worker_count = local_rewrite_worker_count()
    # shortcut: cap extra request heads to worker lanes; add an aggregate memory budget before increasing.
    var overflow_capacity = max(2, worker_count)
    var workers = TaskGroup()
    try:
        for _ in range(worker_count):
            workers.create_task(_local_rewrite_worker(state_ptr))
        while True:
            if _parent_channel_closed(parent_fd, parent_bytes): break
            var completed = state_ptr[].take_completed()
            while completed:
                var connection = completed.pop()
                if connection.waiting_for_request:
                    if len(parked) < HTTP_KEEP_ALIVE_MAX_PARKED:
                        parked.insert(0, connection^)
                    elif len(overflow) < overflow_capacity:
                        overflow.append(connection^)
                    else:
                        connection.close()
                else:
                    connection.close()
            while len(parked) < HTTP_KEEP_ALIVE_MAX_PARKED and overflow:
                var waiting = overflow.pop(0)
                waiting.keep_alive_enabled = True
                waiting.include_default_response_headers = True
                parked.insert(0, waiting^)
            var accepted_before_scan = False
            if len(overflow) < overflow_capacity:
                var pending = listener.accept(0)
                if pending:
                    var incoming = pending.take()
                    accepted_before_scan = True
                    if len(parked) < HTTP_KEEP_ALIVE_MAX_PARKED:
                        incoming.keep_alive_enabled = True
                        incoming.include_default_response_headers = True
                        parked.insert(0, incoming^)
                    else:
                        incoming.keep_alive_enabled = True
                        incoming.include_default_response_headers = True
                        overflow.append(incoming^)
            var dispatched = False
            var capture_progress = False
            var parked_count = len(parked)
            for _ in range(parked_count):
                var idle = parked.pop()
                var has_request_bytes = idle.request_ready()
                var ready = False
                if has_request_bytes:
                    # Capture the head before reserving a provider worker for body parsing.
                    ready = idle.capture_request_headers(
                        120000,
                        HTTP_MAX_REQUEST_HEADER_LIMIT,
                        LOCAL_REWRITE_HEADER_CAPTURE_BYTES_PER_CONNECTION,
                    )
                    capture_progress = capture_progress or idle.request_capture_progress
                if ready and state_ptr[].has_capacity(worker_count):
                    idle.waiting_for_request = False
                    state_ptr[].enqueue(idle^)
                    dispatched = True
                elif not has_request_bytes and idle.client_disconnected():
                    idle.close()
                else:
                    parked.insert(0, idle^)
            var overflow_count = len(overflow)
            for _ in range(overflow_count):
                var incoming = overflow.pop(0)
                var has_request_bytes = incoming.request_ready()
                var ready = False
                if has_request_bytes:
                    # The overflow gets the same bounded capture turn as parked clients.
                    ready = incoming.capture_request_headers(
                        120000,
                        HTTP_MAX_REQUEST_HEADER_LIMIT,
                        LOCAL_REWRITE_HEADER_CAPTURE_BYTES_PER_CONNECTION,
                    )
                    capture_progress = capture_progress or incoming.request_capture_progress
                if not has_request_bytes and incoming.client_disconnected():
                    incoming.close()
                else:
                    var admitted = len(parked) < HTTP_KEEP_ALIVE_MAX_PARKED
                    if not admitted:
                        admitted = _evict_oldest_idle_connection(parked)
                    var can_dispatch = ready and state_ptr[].has_capacity(worker_count)
                    if admitted or can_dispatch:
                        incoming.keep_alive_enabled = True
                        incoming.include_default_response_headers = True
                        if can_dispatch:
                            incoming.waiting_for_request = False
                            state_ptr[].enqueue(incoming^)
                            dispatched = True
                        else:
                            parked.insert(0, incoming^)
                    else:
                        overflow.append(incoming^)
            if dispatched: continue
            if capture_progress: continue
            if accepted_before_scan: continue
            if len(overflow) >= overflow_capacity:
                # shortcut: 5 ms saturated scan interval; use readiness polling if measured latency is material.
                sleep(0.005)
                continue
            # Recheck worker completions promptly without polling an idle relay as often.
            # shortcut: 10 ms parked-socket rescan; use socket readiness polling if idle-pool CPU is material.
            var timeout = 5 if state_ptr[].has_pending_work() else (10 if len(parked) > 0 else (100 if parent_fd >= 0 else 1000))
            if len(overflow) < overflow_capacity:
                var accepted = listener.accept(UInt64(timeout))
                if accepted:
                    var incoming = accepted.take()
                    if len(parked) < HTTP_KEEP_ALIVE_MAX_PARKED:
                        incoming.keep_alive_enabled = True
                        incoming.include_default_response_headers = True
                        parked.insert(0, incoming^)
                    else:
                        incoming.keep_alive_enabled = True
                        incoming.include_default_response_headers = True
                        overflow.append(incoming^)
    except:
        state_ptr[].stop()
        for _ in range(len(parked)):
            var idle = parked.pop()
            idle.close()
        while overflow:
            var waiting = overflow.pop()
            waiting.close()
        workers.wait()
        _ = (state^).into_inner()
        raise
    state_ptr[].stop()
    for _ in range(len(parked)):
        var idle = parked.pop()
        idle.close()
    while overflow:
        var waiting = overflow.pop()
        waiting.close()
    workers.wait()
    _ = (state^).into_inner()
