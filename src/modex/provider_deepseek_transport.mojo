"""Native loopback DeepSeek POST and incremental Responses SSE exchange."""

from std.collections import List, Span
from std.time import perf_counter

from .json import JSON_STRING, JsonDocument, serialize_json
from .provider_chat_buffered import deepseek_buffered_assistant_messages, deepseek_buffered_response
from .provider_anthropic_messages import anthropic_buffered_assistant_messages, anthropic_buffered_response, deepseek_anthropic_messages_body, validate_deepseek_anthropic_request
from .loopback_http import LoopbackHTTPStream, _http_token_byte
from .provider_chat_reader import DeepSeekChatReader
from .provider_sse_wire import ProviderSSEFramer
from .provider_request import translate_deepseek_request
from .text import is_whitespace, trim_text


def _precommit_hold(lines: List[String]) -> Bool:
    try:
        var event = JsonDocument(String("\n").join(lines))
        var kind = event.string(event.get(event.root, "type"))
        return kind in ["keepalive", "codex.rate_limits", "codex.response.metadata", "response.metadata", "response.created", "response.in_progress", "response.queued", "response.output_item.added", "response.content_part.added", "response.reasoning_summary_part.added"]
    except:
        return False


def _policy_name(name: String) -> String:
    var start = 0
    var end = name.byte_length()
    while start < end and name.as_bytes()[start] <= 32:
        start += 1
    while end > start and name.as_bytes()[end - 1] <= 32:
        end -= 1
    return String(name[byte=start:end]).lower()


def _header_token(value: String) -> Bool:
    if not value:
        return False
    for byte in value.as_bytes():
        if not _http_token_byte(byte):
            return False
    return True


def deepseek_request_headers(headers: List[Tuple[String, String]], api_key: String, passthrough: Bool = False, anthropic_messages: Bool = False) raises -> List[Tuple[String, String]]:
    if not api_key:
        raise Error("--api-key cannot be empty")
    for character in api_key.codepoints():
        if is_whitespace(Int(character)):
            raise Error("--api-key must not contain whitespace")
    for byte in api_key.as_bytes():
        if byte < 33 or byte > 126:
            raise Error("--api-key must contain only visible ASCII")
    var connection_tokens = List[String]()
    for name, value in headers:
        if name.byte_length() > 4096:
            raise Error("DeepSeek request header name exceeds limit")
        if not _header_token(name):
            raise Error("invalid HTTP header name")
        for byte in value.as_bytes():
            if (byte < 32 and byte != 9) or byte == 127:
                raise Error("invalid HTTP header value")
        if name.lower() == "connection":
            for part in value.split(","):
                var token = trim_text(String(part))
                if _header_token(token):
                    connection_tokens.append(token.lower())
    var output: List[Tuple[String, String]] = [
        ("content-type", "application/json"),
        ("accept-encoding", "identity"),
        ("accept", "text/event-stream, application/json"),
    ]
    if anthropic_messages:
        output.append(("x-api-key", api_key))
        output.append(("anthropic-version", "2023-06-01"))
    else:
        output.append(("authorization", "Bearer " + api_key))
    if passthrough:
        output = [("accept-encoding", "identity"), ("authorization", "Bearer " + api_key)]
    # The frozen auth pass adds the first user agent before copying inbound headers.
    for name, value in headers:
        if not passthrough and name.lower() == "user-agent":
            output.append(("user-agent", value))
            break
    for name, value in headers:
        var normalized = _policy_name(name)
        var skip = normalized in connection_tokens or normalized.startswith("sec-websocket-") or normalized.startswith("x-prodex-internal-")
        for local_name in ["connection", "content-length", "host", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "authorization", "chatgpt-account-id"]:
            skip = skip or normalized == local_name
        if anthropic_messages and normalized in ["x-api-key", "anthropic-version"]:
            skip = True
        if passthrough and normalized == "accept-encoding":
            skip = True
        if not skip:
            output.append((name, value))
    return output^


def deepseek_event_stream(headers: List[Tuple[String, String]]) -> Bool:
    for name, value in headers:
        if name.lower() == "content-type":
            for byte in value.as_bytes():
                if (byte < 32 and byte != 9) or byte >= 127:
                    return False
            return "text/event-stream" in value.lower()
    return False


struct DeepSeekExchange(Movable):
    var http: LoopbackHTTPStream
    var reader: DeepSeekChatReader
    var body: String
    var messages: String
    var response_metadata: String
    var conversation_messages: String
    var max_body_bytes: Int
    var pending: List[UInt8]
    var pending_offset: Int
    var pending_error: Bool
    var read_mode: Int
    var done: Bool
    var cancelled: Bool

    var native_messages: Bool

    def __init__(out self, address: String, path: String, api_key: String, request: String, request_id: UInt64, response_id: String, created_at: UInt64, headers: List[Tuple[String, String]] = List[Tuple[String, String]](), history: String = "[]", strict_tools: Bool = False, web_search_mode: String = "auto", connect_timeout_ms: UInt64 = 1000, request_timeout_ms: UInt64 = 1000, idle_timeout_ms: UInt64 = 1000, max_body_bytes: Int = 4194304, line_max_bytes: Int = 4194304, event_max_bytes: Int = 4194304, accumulated_max_bytes: Int = 4194304, downstream_fd: Int32 = -1, previous_response_found: Bool = False, native_messages: Bool = False) raises:
        if native_messages: validate_deepseek_anthropic_request(request)
        var prepared = JsonDocument(translate_deepseek_request(request, history, strict_tools, web_search_mode, previous_response_found))
        if max_body_bytes < 0 or max_body_bytes > 4 * 1024 * 1024:
            raise Error("invalid or unsupported HTTP stream limits")
        var translated_body = serialize_json(prepared, prepared.get(prepared.root, "body"))
        self.body = deepseek_anthropic_messages_body(serialize_json(prepared, prepared.root)) if native_messages else translated_body
        self.messages = serialize_json(prepared, prepared.get(prepared.root, "messages"))
        self.response_metadata = serialize_json(prepared, prepared.get(prepared.root, "response_metadata"))
        self.conversation_messages = "[]"
        self.reader = DeepSeekChatReader(request_id, response_id, created_at, self.response_metadata, line_max_bytes, event_max_bytes, accumulated_max_bytes, native_messages)
        self.native_messages = native_messages
        self.max_body_bytes = max_body_bytes
        self.pending = List[UInt8]()
        self.pending_offset = 0
        self.pending_error = False
        self.read_mode = 0
        self.done = False
        self.cancelled = False
        var bytes = List[UInt8]()
        for byte in self.body.as_bytes():
            bytes.append(byte)
        self.http = LoopbackHTTPStream(address, path, deepseek_request_headers(headers, api_key, anthropic_messages=native_messages), bytes, connect_timeout_ms, request_timeout_ms, idle_timeout_ms, max_body_bytes, downstream_fd, True)

    def status(self) -> Int:
        return self.http.status

    def headers(self) -> List[Tuple[String, String]]:
        return self.http.headers.copy()

    def successful(self) -> Bool:
        return 200 <= self.http.status < 300

    def close(mut self):
        if not self.done:
            self.cancelled = True
        self._finish()

    def _finish(mut self):
        self.done = True
        self.pending.clear()
        self.pending_offset = 0
        self.http.close()

    def read_body(mut self) raises -> List[UInt8]:
        if self.read_mode == 2:
            self._finish()
            raise Error("DeepSeek response body was already handed to the event reader")
        self.read_mode = 1
        var output = List[UInt8]()
        try:
            while not self.done:
                var chunk = self.http.read_chunk()
                if len(chunk) > self.max_body_bytes - len(output):
                    raise Error("oversized HTTP response body")
                output.extend(chunk^)
                if self.http.done:
                    self.done = True
            self._finish()
            return output^
        except:
            self._finish()
            raise

    def prefetch(mut self, timeout_ms: UInt64) raises:
        self.http.lookahead_deadline = perf_counter() + Float64(timeout_ms) / 1000.0
        try:
            var inspector = ProviderSSEFramer(inspection=True)
            var progress = False
            while len(self.pending) < 8192 and not progress:
                var chunk: List[UInt8]
                try:
                    chunk = self.http.read_chunk()
                except error:
                    var message = String(error)
                    if message == "loopback HTTP lookahead elapsed":
                        break
                    if not self.pending:
                        raise
                    self.pending_error = True
                    break
                if not chunk:
                    break
                var inspect_length = min(len(chunk), 8192 - len(self.pending))
                var offset = 0
                try:
                    while offset < inspect_length:
                        var result = inspector.consume(Span(chunk)[offset:inspect_length])
                        offset += result[0]
                        if result[1] and not _precommit_hold(result[1].value()):
                            progress = True
                            break
                except:
                    # The strict event reader owns failures outside precommit inspection.
                    progress = True
                self.pending.extend(chunk^)
        except:
            self.http.lookahead_deadline = 0.0
            raise
        self.http.lookahead_deadline = 0.0

    def read_events(mut self) raises -> List[String]:
        if self.read_mode == 1:
            self._finish()
            raise Error("DeepSeek response body was already read as bytes")
        if self.done:
            return List[String]()
        if not self.successful():
            self._finish()
            raise Error("DeepSeek HTTP error body must be read without SSE translation")
        if not deepseek_event_stream(self.http.headers):
            self._finish()
            raise Error("DeepSeek event reader requires a text/event-stream response")
        self.read_mode = 2
        try:
            while True:
                if self.pending_offset < len(self.pending):
                    var result = self.reader.consume(Span(self.pending)[self.pending_offset:])
                    if result[0] <= 0:
                        raise Error("DeepSeek event reader made no progress")
                    self.pending_offset += result[0]
                    if self.reader.done:
                        self._finish()
                    if result[1] or self.done:
                        return result[1].copy()
                    continue
                if self.pending_error:
                    self.pending_error = False
                    raise Error("error decoding response body")
                try:
                    self.pending = self.http.read_chunk()
                except:
                    # The frozen Rust body reader reports framing and read failures generically.
                    raise Error("error decoding response body")
                self.pending_offset = 0
                if not self.pending:
                    var events = self.reader.finish()
                    self._finish()
                    return events^
        except error:
            self._finish()
            if self.reader.state.completed:
                raise
            self.reader.done = True
            return self.reader.state.fail("provider_stream_error", String(error))

    def read_buffered(mut self) raises -> String:
        if not self.successful():
            self._finish()
            raise Error("DeepSeek HTTP error body must be read without JSON translation")
        if deepseek_event_stream(self.http.headers):
            self._finish()
            raise Error("DeepSeek buffered reader requires a non-event-stream response")
        var bytes = self.read_body()
        var source: String
        try:
            source = String(from_utf8=Span(bytes))
        except:
            raise Error("failed to parse DeepSeek chat response JSON")
        var response = anthropic_buffered_response(source, self.reader.state.created_at, self.response_metadata) if self.native_messages else deepseek_buffered_response(source, self.reader.state.created_at, self.reader.state.response_id, self.response_metadata)
        var translated = JsonDocument(response)
        var id = translated.get(translated.root, "id")
        if translated.string(translated.get(translated.root, "status")) != "failed" and id >= 0 and translated.nodes[id].kind == JSON_STRING and trim_text(translated.nodes[id].text):
            var assistant = anthropic_buffered_assistant_messages(source) if self.native_messages else deepseek_buffered_assistant_messages(source)
            self.conversation_messages = self.messages
            if assistant != "[]":
                if self.messages == "[]":
                    self.conversation_messages = assistant
                else:
                    self.conversation_messages = String(self.messages[byte=0:self.messages.byte_length() - 1]) + "," + String(assistant[byte=1:])
        return response
