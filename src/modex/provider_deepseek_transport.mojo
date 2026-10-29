"""Native loopback DeepSeek POST and incremental Responses SSE exchange."""

from std.collections import Dict, List, Span
from std.time import perf_counter

from .json import JSON_ARRAY, JSON_OBJECT, JSON_STRING, JsonDocument, serialize_json
from .provider_chat_buffered import deepseek_buffered_assistant_messages, deepseek_buffered_response
from .provider_anthropic_messages import anthropic_buffered_assistant_messages, anthropic_buffered_response, deepseek_anthropic_messages_body, validate_deepseek_anthropic_request
from .loopback_http import HTTP_HEADER_LIMIT, LoopbackHTTPStream, _http_token_byte
from .provider_chat_reader import DeepSeekChatReader
from .provider_sse_wire import ProviderSSEFramer
from .provider_request import translate_deepseek_request
from .text import is_whitespace, trim_text


def _precommit_hold(lines: List[String], native_messages: Bool = False) -> Bool:
    try:
        var event = JsonDocument(String("\n").join(lines))
        var kind = event.string(event.get(event.root, "type"))
        if native_messages and kind == "ping": return True
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


comptime DEEPSEEK_ERROR_OTHER = 5


def _deepseek_error_code_class(code: String) -> Int:
    var value = trim_text(code).lower()
    if value in ["unauthenticated", "invalid_api_key", "authentication_error"]: return 0
    if value in ["insufficient_quota", "quota_exhausted", "quota_exceeded", "credit_balance_exhausted", "organization_spend_limit_exceeded", "project_spend_limit_exceeded", "resource_exhausted"]: return 1
    if value in ["rate_limit_error", "rate_limit_exceeded", "rate_limit_exceeded_error", "slow_down"]: return 2
    if value in ["overloaded_error", "server_is_overloaded"]: return 3
    if value in ["not_found_error", "model_not_supported"]: return 4
    return DEEPSEEK_ERROR_OTHER


def _deepseek_error_class_priority(error_class: Int) -> Int:
    if error_class == 0: return 0
    if error_class == 1: return 1
    if error_class == 2: return 2
    if error_class == 4: return 3
    if error_class == 3: return 4
    return 5


def _deepseek_json_error_class(source: String) -> Int:
    try:
        var doc = JsonDocument(source)
        var pending = List[Int](copy=[doc.root])
        var cursor = 0
        var selected = DEEPSEEK_ERROR_OTHER
        while cursor < len(pending):
            var node = pending[cursor]
            cursor += 1
            if doc.nodes[node].kind == JSON_OBJECT:
                var last_children = Dict[String, Int]()
                for child_index in range(len(doc.nodes[node].children)):
                    last_children[doc.nodes[node].names[child_index]] = child_index
                for child_index in range(len(doc.nodes[node].children)):
                    var child = doc.nodes[node].children[child_index]
                    var name = doc.nodes[node].names[child_index]
                    var last_child = last_children.get(name)
                    if last_child and last_child.value() != child_index: continue
                    if name in ["code", "status", "reason", "type"] and doc.nodes[child].kind == JSON_STRING:
                        var candidate = _deepseek_error_code_class(doc.string(child))
                        if _deepseek_error_class_priority(candidate) < _deepseek_error_class_priority(selected): selected = candidate
                    else:
                        pending.append(child)
            elif doc.nodes[node].kind == JSON_ARRAY:
                for child in doc.nodes[node].children: pending.append(child)
        return selected
    except:
        return DEEPSEEK_ERROR_OTHER


def _deepseek_error_body_class(body: List[UInt8]) -> Int:
    if not body or len(body) > 4 * 1024 * 1024:
        return DEEPSEEK_ERROR_OTHER
    var source: String
    try:
        source = String(from_utf8=Span(body))
    except:
        return DEEPSEEK_ERROR_OTHER
    var sse_data = List[String]()
    for raw_line in source.split("\n"):
        var line = String(raw_line)
        if line.startswith("data:"):
            var payload = trim_text(String(line[byte=5:]))
            if payload and payload != "[DONE]": sse_data.append(payload^)
    if sse_data:
        var selected = DEEPSEEK_ERROR_OTHER
        for payload in sse_data:
            var candidate = _deepseek_json_error_class(payload)
            if _deepseek_error_class_priority(candidate) < _deepseek_error_class_priority(selected): selected = candidate
        return selected
    return _deepseek_json_error_class(source)


def _deepseek_error_text_class(body: List[UInt8]) -> Int:
    var source: String
    try:
        source = String(from_utf8=Span(body)).lower()
    except:
        return DEEPSEEK_ERROR_OTHER
    if "model is not supported" in source: return 4
    if "overloaded" in source: return 3
    return DEEPSEEK_ERROR_OTHER


def _deepseek_error_response_class(status: Int, body: List[UInt8]) -> Int:
    var body_class = _deepseek_error_body_class(body)
    if status == 429: return body_class
    var text_class = _deepseek_error_text_class(body)
    if _deepseek_error_class_priority(text_class) < _deepseek_error_class_priority(body_class):
        body_class = text_class
    var status_class = DEEPSEEK_ERROR_OTHER
    if status in [401, 403]: status_class = 0
    elif status == 404: status_class = 4
    elif 500 <= status < 600: status_class = 3
    if _deepseek_error_class_priority(status_class) < _deepseek_error_class_priority(body_class):
        return status_class
    return body_class


def deepseek_retryable_api_key_response(status: Int, body: List[UInt8], attempt_index: Int, attempt_count: Int) -> Bool:
    if attempt_index + 1 >= attempt_count:
        return False
    var error_class = _deepseek_error_response_class(status, body)
    return error_class <= 3


def _deepseek_native_first_event_class(lines: List[String]) -> Int:
    try:
        var document = JsonDocument(String("\n").join(lines))
        var event_type = document.get(document.root, "type")
        var error = document.get(document.root, "error")
        var is_error = error >= 0
        if event_type >= 0 and document.nodes[event_type].kind == JSON_STRING:
            is_error = is_error or document.string(event_type).lower() == "error"
        if not is_error:
            return -1
        var code = document.get(error, "type")
        if code < 0 or document.nodes[code].kind != JSON_STRING:
            code = document.get(error, "code")
        if code < 0 or document.nodes[code].kind != JSON_STRING:
            code = document.get(document.root, "code")
        if code >= 0 and document.nodes[code].kind == JSON_STRING:
            return _deepseek_error_code_class(document.string(code))
        return DEEPSEEK_ERROR_OTHER
    except:
        return DEEPSEEK_ERROR_OTHER


def deepseek_request_headers(headers: List[Tuple[String, String]], api_key: String, passthrough: Bool = False, anthropic_messages: Bool = False) raises -> List[Tuple[String, String]]:
    if not api_key:
        raise Error("--api-key cannot be empty")
    for character in api_key.codepoints():
        if is_whitespace(Int(character)):
            raise Error("--api-key must not contain whitespace")
    for byte in api_key.as_bytes():
        if byte < 33 or byte > 126:
            raise Error("--api-key must contain only visible ASCII")
    var connection_tokens = Dict[String, Bool]()
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
                    connection_tokens[token.lower()] = True
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
        var skip = False
        if connection_tokens.get(normalized):
            skip = True
        skip = skip or normalized.startswith("sec-websocket-") or normalized.startswith("x-prodex-internal-")
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
    var downstream_body_incomplete: Bool

    var native_messages: Bool

    def __init__(out self, address: String, path: String, api_key: String, request: String, request_id: UInt64, response_id: String, created_at: UInt64, headers: List[Tuple[String, String]] = List[Tuple[String, String]](), history: String = "[]", strict_tools: Bool = False, web_search_mode: String = "auto", connect_timeout_ms: UInt64 = 1000, request_timeout_ms: UInt64 = 1000, idle_timeout_ms: UInt64 = 1000, max_body_bytes: Int = 4194304, line_max_bytes: Int = 4194304, event_max_bytes: Int = 4194304, accumulated_max_bytes: Int = 4194304, downstream_fd: Int32 = -1, previous_response_found: Bool = False, native_messages: Bool = False, request_method: String = "POST", request_header_limit: Int = HTTP_HEADER_LIMIT, request_field_limit: Int = HTTP_HEADER_LIMIT, ignore_web_search: Bool = False, cancel_fd: Int32 = -1) raises:
        if native_messages: validate_deepseek_anthropic_request(request)
        var prepared = JsonDocument(translate_deepseek_request(request, history, strict_tools, web_search_mode, previous_response_found, ignore_web_search))
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
        self.downstream_body_incomplete = False
        var bytes = List[UInt8]()
        for byte in self.body.as_bytes():
            bytes.append(byte)
        self.http = LoopbackHTTPStream(address, path, deepseek_request_headers(headers, api_key, anthropic_messages=native_messages), bytes, connect_timeout_ms, request_timeout_ms, idle_timeout_ms, max_body_bytes, downstream_fd, True, request_method, request_header_limit, request_field_limit, cancel_fd)

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

    def read_error_body(mut self) raises -> List[UInt8]:
        if self.successful():
            raise Error("DeepSeek successful response cannot be buffered as an error")
        var output = self.http.read_buffered()
        self._finish()
        return output^

    def prefetch(mut self, timeout_ms: UInt64) raises -> Int:
        self.http.lookahead_deadline = perf_counter() + Float64(timeout_ms) / 1000.0
        var retry_class = -1
        var retry_event_end = -1
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
                    if self.native_messages:
                        self.pending_error = True
                        retry_class = 3
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
                        if result[1]:
                            var event = result[1].take()
                            if self.native_messages:
                                var event_class = _deepseek_native_first_event_class(event)
                                if event_class >= 0 and event_class <= 3:
                                    retry_class = event_class
                                    retry_event_end = len(self.pending) + offset
                                    progress = True
                                    break
                            if not _precommit_hold(event, self.native_messages):
                                progress = True
                                break
                except:
                    # The strict event reader owns failures outside precommit inspection.
                    progress = True
                self.pending.extend(chunk^)
                if retry_event_end >= 0:
                    # Frozen precommit inspection consumes retryable first-error frames.
                    self.pending_offset = retry_event_end
        except:
            self.http.lookahead_deadline = 0.0
            raise
        self.http.lookahead_deadline = 0.0
        return retry_class

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
        var provider_stream_read_error = False
        try:
            while True:
                if self.pending_offset < len(self.pending):
                    var result: Tuple[Int, List[String]]
                    try:
                        result = self.reader.consume(Span(self.pending)[self.pending_offset:])
                    except:
                        provider_stream_read_error = True
                        raise
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
                    provider_stream_read_error = True
                    raise Error("error decoding response body")
                try:
                    self.pending = self.http.read_chunk()
                except:
                    # The frozen Rust body reader reports framing and read failures generically.
                    provider_stream_read_error = True
                    raise Error("error decoding response body")
                self.pending_offset = 0
                if not self.pending:
                    var events: List[String]
                    try:
                        events = self.reader.finish()
                    except:
                        provider_stream_read_error = True
                        raise
                    self._finish()
                    return events^
        except error:
            var leave_downstream_body_open = (
                provider_stream_read_error and self.native_messages
                and self.reader.state.completed
                and not self.reader.state.anthropic_stream_terminal
            )
            self._finish()
            if self.reader.state.completed and (
                not self.native_messages or self.reader.state.anthropic_stream_terminal
            ):
                raise
            self.reader.done = True
            if leave_downstream_body_open:
                self.downstream_body_incomplete = True
                return List[String]()
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
