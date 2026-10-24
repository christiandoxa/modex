"""Read and render one detached redacted runtime log snapshot."""

from std.collections import List, Optional, Span
from std.io import RawFileDescriptor
from std.math import isfinite
from std.memory import bitcast
from std.os import getenv, lstat, listdir, stat
from std.os.path import exists

from .json import JSON_BOOL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json
from .log_payload import readable_upstream_payload
from .log_payload_render import payload_lines
from .log_redaction import redact_log_text
from .log_time import local_log_timestamp as local_timestamp
from .log_transcript import transcript_event as project_transcript
from .paths import ensure_app_root, shared_root
from .runtime_policy import runtime_log_dir
from .text import cli_width, text_width, wrap_text

comptime SESSION_TAIL_BYTES = 2 * 1024 * 1024
comptime RUNTIME_TAIL_BYTES = 1024 * 1024


@fieldwise_init
struct LogEvent(Copyable):
    var timestamp: String
    var source: String
    var text: String

    def json(self) -> String:
        return "{\"timestamp\":" + quote_json(self.timestamp) + ",\"source\":" + quote_json(self.source) + ",\"text\":" + quote_json(self.text) + "}"


@fieldwise_init
struct UpstreamEvent(Copyable):
    var timestamp: String
    var request: String
    var transport: String
    var route: String
    var profile: String
    var bytes: String
    var logged_bytes: String
    var truncated: Bool
    var payload: String

    def json(self) -> String:
        var request = "null" if not self.request else self.request
        return "{\"timestamp\":" + quote_json(self.timestamp) + ",\"request\":" + request + ",\"transport\":" + quote_json(self.transport) + ",\"route\":" + quote_json(self.route) + ",\"profile\":" + quote_json(self.profile) + ",\"bytes\":" + self.bytes + ",\"logged_bytes\":" + self.logged_bytes + ",\"truncated\":" + ("true" if self.truncated else "false") + ",\"payload\":" + quote_json(self.payload) + "}"


@fieldwise_init
struct TokenEvent(Copyable):
    var timestamp: String
    var request: String
    var profile: String
    var transport: String
    var source: String
    var input_tokens: String
    var cached_input_tokens: String
    var output_tokens: String
    var reasoning_tokens: String
    var generation_ms: String
    var output_tokens_per_second: String

    def json(self) -> String:
        var output = "{"
        if self.cached_input_tokens:
            output += "\"cached_input_tokens\":" + self.cached_input_tokens + ","
        output += "\"event\":\"token_usage\",\"fields\":{" + self.fields_json() + "}"
        if self.generation_ms:
            output += ",\"generation_ms\":" + self.generation_ms
        output += ",\"input_tokens\":" + self.input_tokens + ",\"output_tokens\":" + self.output_tokens
        if self.output_tokens_per_second:
            output += ",\"output_tokens_per_second\":" + self.output_tokens_per_second
        output += ",\"profile\":" + quote_json(self.profile) + ",\"reasoning_tokens\":" + self.reasoning_tokens
        output += ",\"request\":" + (self.request if self.request else "null")
        output += ",\"source\":" + quote_json(self.source) + ",\"timestamp\":" + quote_json(self.timestamp) + ",\"transport\":" + quote_json(self.transport)
        return output + "}"

    def fields_json(self) -> String:
        var fields = String()
        if self.cached_input_tokens:
            fields += "\"cached_input_tokens\":" + self.cached_input_tokens + ","
        if self.generation_ms:
            fields += "\"generation_ms\":" + self.generation_ms + ","
        fields += "\"input_tokens\":" + self.input_tokens + ",\"output_tokens\":" + self.output_tokens
        if self.output_tokens_per_second:
            fields += ",\"output_tokens_per_second\":" + self.output_tokens_per_second
        fields += ",\"profile\":" + quote_json(self.profile)
        if self.reasoning_tokens:
            fields += ",\"reasoning_tokens\":" + self.reasoning_tokens
        if self.request:
            fields += ",\"request\":" + quote_json(self.request)
        fields += ",\"source\":" + quote_json(self.source) + ",\"transport\":" + quote_json(self.transport)
        return fields^


def log_last(json: Bool) raises -> String:
    var root = ensure_app_root()
    var sessions = List[String]()
    collect_files(shared_root(root) + "/sessions", sessions, ".jsonl")
    sort(Span(sessions), lambda (left: String, right: String) -> Bool: file_newer(left, right, True))
    var transcript = Optional[LogEvent]()
    for index in range(min(32, len(sessions))):
        transcript = latest_transcript(sessions[index])
        if transcript:
            break

    var recognized = recent_runtime_log_paths(root)
    var upstream = Optional[UpstreamEvent]()
    var token = Optional[TokenEvent]()
    for index in range(min(32, len(recognized))):
        var path = recognized[index]
        var contents: String
        try:
            contents = read_tail(path, RUNTIME_TAIL_BYTES)
        except:
            continue
        for line_span in contents.split("\n"):
            var line = String(line_span)
            var record = RuntimeRecord(line)
            if record.event == "upstream_payload":
                var candidate = upstream_event(record)
                if candidate and (not upstream or timestamp_wins(upstream.value().timestamp, candidate.value().timestamp)):
                    upstream = candidate^
            elif record.event == "token_usage":
                var candidate = token_event(record)
                if candidate and (not token or timestamp_wins(token.value().timestamp, candidate.value().timestamp)):
                    token = candidate^

    if json:
        var output = String()
        if transcript:
            output += transcript.value().json() + "\n"
        if upstream:
            output += upstream.value().json() + "\n"
        if token:
            output += token.value().json() + "\n"
        return output^
    if not transcript and not upstream and not token:
        return "No transcript, upstream payload, or token events found.\n"
    var output = String()
    if transcript:
        output += render_event(transcript.value().timestamp, event_label(transcript.value().source), transcript.value().text)
    if upstream:
        output += render_upstream(upstream.value())
    if token:
        output += render_token(token.value())
    return output^


def recent_runtime_log_paths(root: String) raises -> List[String]:
    var runtime = List[String]()
    var runtime_dir = runtime_log_dir(root)
    try:
        collect_files(runtime_dir, runtime, ".log", False)
    except:
        pass
    var recognized = List[String]()
    for path in runtime:
        var name_parts = path.split("/")
        var name = name_parts[len(name_parts) - 1]
        if name.startswith("prodex-runtime-"):
            recognized.append(String(path))
    sort(Span(recognized), lambda (left: String, right: String) -> Bool: file_newer(left, right))
    while len(recognized) > 32:
        _ = recognized.pop()
    return recognized^


def collect_files(root: String, mut paths: List[String], suffix: String, recursive: Bool = True) raises:
    if not exists(root):
        return
    for name in listdir(root):
        var path = root + "/" + name
        var mode = lstat(path).st_mode & 0o170000
        if mode == 0o040000 and recursive:
            collect_files(path, paths, suffix)
        elif mode == 0o100000 and name.endswith(suffix):
            paths.append(path^)


def file_newer(left: String, right: String, session: Bool = False) -> Bool:
    try:
        var left_time = lstat(left).st_mtimespec
        var right_time = lstat(right).st_mtimespec
        var left_sec = max(0, left_time.tv_sec) if session else left_time.tv_sec
        var right_sec = max(0, right_time.tv_sec) if session else right_time.tv_sec
        var left_ns = (left_time.tv_nsec // 1000000 if left_time.tv_sec >= 0 else 0) if session else left_time.tv_nsec
        var right_ns = (right_time.tv_nsec // 1000000 if right_time.tv_sec >= 0 else 0) if session else right_time.tv_nsec
        if left_sec != right_sec:
            return left_sec > right_sec
        if left_ns != right_ns:
            return left_ns > right_ns
    except:
        pass
    return left < right if session else left > right


def read_tail(path: String, limit: Int) raises -> String:
    var before = lstat(path)
    if (before.st_mode & 0o170000) != 0o100000:
        raise Error("log path is not a regular file")
    var file = open(path, "r")
    var opened = stat("/proc/self/fd/" + String(RawFileDescriptor(file).value))
    var current = lstat(path)
    if before.st_ino != opened.st_ino or before.st_dev != opened.st_dev or current.st_ino != opened.st_ino or current.st_dev != opened.st_dev:
        raise Error("log path changed while opening")
    var start = max(0, opened.st_size - limit)
    _ = file.seek(start)
    var bytes = file.read_bytes()
    var offset = 0
    if start:
        while offset < len(bytes) and bytes[offset] != 10:
            offset += 1
        offset = min(offset + 1, len(bytes))
    return String(from_utf8_lossy=Span(bytes)[offset:])


def latest_transcript(path: String) raises -> Optional[LogEvent]:
    var content: String
    try:
        content = read_tail(path, SESSION_TAIL_BYTES)
    except:
        return None
    var latest = Optional[LogEvent]()
    for line_span in content.split("\n"):
        var line = String(line_span)
        var projected = project_transcript(line)
        if projected:
            var parts = projected.value()
            var event = LogEvent(local_timestamp(parts[0]), parts[1], parts[2])
            if not latest or timestamp_wins(latest.value().timestamp, event.timestamp):
                latest = event^
    return latest^


struct RuntimeRecord:
    var timestamp: String
    var event: String
    var fields: List[Tuple[String, String, Bool]]
    var envelope: Bool
    var timestamp_present: Bool

    def __init__(out self, line: String):
        self.timestamp = ""
        self.event = ""
        self.fields = List[Tuple[String, String, Bool]]()
        self.envelope = False
        self.timestamp_present = False
        try:
            var doc = JsonDocument(line)
            self.envelope = True
            var timestamp = doc.get(doc.root, "timestamp")
            self.timestamp_present = timestamp >= 0 and doc.nodes[timestamp].kind == JSON_STRING
            self.timestamp = doc.string(timestamp)
            self.event = doc.string(doc.get(doc.root, "event"))
            var fields = doc.get(doc.root, "fields")
            if fields >= 0 and doc.nodes[fields].kind == JSON_OBJECT:
                for index in range(len(doc.nodes[fields].children)):
                    var child = doc.nodes[fields].children[index]
                    var kind = doc.nodes[child].kind
                    self.fields.append((doc.nodes[fields].names[index], doc.nodes[child].text,
                                        kind == JSON_STRING or kind == JSON_NUMBER or kind == JSON_BOOL))
            return
        except:
            pass
        var message = line
        var closing = line.find("] ")
        if line.startswith("[") and closing >= 1:
            self.envelope = True
            self.timestamp_present = True
            self.timestamp = String(line[byte=1:closing])
            message = String(line[byte=closing + 2:])
        var first = True
        for part in message.split():
            var separator = part.find("=")
            if first:
                if separator < 0:
                    self.event = String(part)
                first = False
            if separator > 0:
                self.fields.append((String(part[byte=0:separator]), String(part[byte=separator + 1:]), True))

    def has(self, name: String) -> Bool:
        for index in range(len(self.fields) - 1, -1, -1):
            if self.fields[index][0] == name:
                return self.fields[index][2]
        return False

    def field(self, name: String, fallback: String = "") -> String:
        for index in range(len(self.fields) - 1, -1, -1):
            if self.fields[index][0] == name:
                return self.fields[index][1] if self.fields[index][2] else fallback
        return fallback


def unsigned_log_number(value: String) -> String:
    if not value:
        return ""
    var result = UInt64(0)
    var index = 1 if value.as_bytes()[0] == 43 else 0
    if index == value.byte_length():
        return ""
    while index < value.byte_length():
        var byte = Int(value.as_bytes()[index])
        if not 48 <= byte <= 57:
            return ""
        var digit = UInt64(byte - 48)
        if result > (UInt64.MAX - digit) // 10:
            return ""
        result = result * 10 + digit
        index += 1
    return String(result)


def positive_log_decimal(value: String) -> Bool:
    if not value:
        return False
    var index = 1 if value.as_bytes()[0] == 43 else 0
    var digits = 0
    var dot = False
    while index < value.byte_length() and value.as_bytes()[index] != 101 and value.as_bytes()[index] != 69:
        var byte = Int(value.as_bytes()[index])
        if byte == 46 and not dot:
            dot = True
        elif 48 <= byte <= 57:
            digits += 1
        else:
            return False
        index += 1
    if digits == 0:
        return False
    if index < value.byte_length():
        index += 1
        if index < value.byte_length() and (value.as_bytes()[index] == 43 or value.as_bytes()[index] == 45):
            index += 1
        var start = index
        while index < value.byte_length() and 48 <= Int(value.as_bytes()[index]) <= 57:
            index += 1
        if start == index or index != value.byte_length():
            return False
    try:
        var parsed = atof(value)
        return isfinite(parsed) and parsed > 0
    except:
        return False


def upstream_event(record: RuntimeRecord) raises -> Optional[UpstreamEvent]:
    if not record.envelope or not record.has("payload_b64"):
        return None
    var decoded = decode_base64(record.field("payload_b64"))
    if not decoded:
        return None
    var paths = List[String]()
    var present = List[Bool]()
    for key in ["path", "file_path", "local_path", "absolute_path", "image_path", "attachment_path", "uri"]:
        paths.append(record.field(key))
        present.append(record.has(key))
    var payload = redact_log_text(readable_upstream_payload(decoded.value(), paths, present))
    var byte_count = unsigned_log_number(record.field("bytes"))
    var logged = unsigned_log_number(record.field("logged_bytes"))
    var count = String(len(decoded.value()))
    return UpstreamEvent(local_timestamp(record.timestamp if record.timestamp_present else "-"),
        unsigned_log_number(record.field("request")), record.field("transport", "-"),
        record.field("route", "-"), record.field("profile", "-"),
        byte_count if byte_count else count, logged if logged else count,
        record.field("truncated") == "true", payload)


def token_event(record: RuntimeRecord) -> Optional[TokenEvent]:
    var input = unsigned_log_number(record.field("input_tokens"))
    var output = unsigned_log_number(record.field("output_tokens"))
    if not input or (record.has("output_tokens") and not output):
        return None
    var cached = unsigned_log_number(record.field("cached_input_tokens"))
    var reasoning = unsigned_log_number(record.field("reasoning_tokens"))
    var generation = unsigned_log_number(record.field("generation_ms"))
    var rate = String()
    if generation == "0" or (record.has("output_tokens_per_second") and not positive_log_decimal(record.field("output_tokens_per_second"))):
        generation = ""
    if not output:
        output = "0"
    if generation and output != "0":
        try:
            rate = String(atof(output) * 1000.0 / atof(generation))
        except:
            return None
    return TokenEvent(local_timestamp(record.timestamp), unsigned_log_number(record.field("request")),
        record.field("profile", "unknown"), record.field("transport", "unknown"), record.field("source", "unknown"),
        input, cached if cached else "0", output, reasoning if reasoning else "0", generation, rate)


def decode_base64(encoded: String) -> Optional[List[UInt8]]:
    if encoded.byte_length() % 4:
        return None
    var result = List[UInt8]()
    var bytes = encoded.as_bytes()
    for index in range(0, len(bytes), 4):
        var first = base64_value(Int(bytes[index]))
        var second = base64_value(Int(bytes[index + 1]))
        if first < 0 or second < 0:
            return None
        result.append(UInt8((first << 2) | (second >> 4)))
        if bytes[index + 2] == 61:
            if index + 4 != len(bytes) or bytes[index + 3] != 61 or second & 15:
                return None
        else:
            var third = base64_value(Int(bytes[index + 2]))
            if third < 0:
                return None
            result.append(UInt8(((second & 15) << 4) | (third >> 2)))
            if bytes[index + 3] == 61:
                if index + 4 != len(bytes) or third & 3:
                    return None
            else:
                var fourth = base64_value(Int(bytes[index + 3]))
                if fourth < 0:
                    return None
                result.append(UInt8(((third & 3) << 6) | fourth))
    return result^


def base64_value(character: Int) -> Int:
    if 65 <= character <= 90:
        return character - 65
    if 97 <= character <= 122:
        return character - 71
    if 48 <= character <= 57:
        return character + 4
    if character == 43:
        return 62
    if character == 47:
        return 63
    return -1


def timestamp_wins(current: String, incoming: String) -> Bool:
    return incoming >= current


def default_field(value: String, fallback: String) -> String:
    return fallback if not value else value


def event_label(source: String) -> String:
    if source == "ws": return "WEBSOCKET"
    if source == "turn-context": return "MODEL"
    if source == "session-context": return "SESSION"
    if source == "prompt-engineering": return "PROMPT"
    if source == "tool-output": return "TOOL RESULT"
    if source.startswith("tool-call:"): return "TOOL CALL"
    for label in ["request", "mcp", "agent", "route", "quota", "retry", "backoff", "health", "error", "model", "upstream", "stream", "response", "terminal", "tool", "load", "smart", "compact", "event", "tokens", "hook", "user", "assistant", "reasoning"]:
        if source == label:
            return source.upper()
    return "stream " + source


def render_block(timestamp: String, title: String, meta: List[Tuple[String, String]], body: List[String]) raises -> String:
    var width = cli_width()
    var prefix = "[" + timestamp + "] " + title
    var output = prefix
    if text_width(prefix) < width - 1:
        output += " " + String("-") * (width - text_width(prefix) - 1)
    var metadata = String()
    for pair in meta:
        if metadata:
            metadata += "  "
        metadata += pair[0] + "=" + pair[1]
    if meta:
        for line in wrap_text(metadata, max(width - 2, 20)):
            output += "\n  " + line
    for block in body:
        for line in wrap_text(block, max(width - 4, 20)):
            output += "\n  | " + line
    return output + "\n"


def render_event(timestamp: String, title: String, body: String) raises -> String:
    return render_block(timestamp, title, [], [body])


def render_upstream(event: UpstreamEvent) raises -> String:
    var meta: List[Tuple[String, String]] = [
        ("profile", event.profile), ("request", event.request if event.request else "-"),
        ("transport", event.transport), ("route", event.route), ("bytes", event.bytes),
        ("logged", event.logged_bytes), ("truncated", "true" if event.truncated else "false"),
        ("snapshot", "truncated at configured cap" if event.truncated else "complete"),
    ]
    return render_block(event.timestamp, "UPSTREAM", meta, payload_lines(event.payload, cli_width()))


def render_token(event: TokenEvent) raises -> String:
    var meta: List[Tuple[String, String]] = [
        ("profile", event.profile), ("request", event.request if event.request else "-"),
        ("transport", event.transport), ("source", event.source), ("input", event.input_tokens),
        ("cache", event.cached_input_tokens), ("output", event.output_tokens),
        ("reasoning", event.reasoning_tokens), ("generation", event.generation_ms + "ms" if event.generation_ms else "unavailable"),
        ("avg_output", display_rate(event.output_tokens_per_second)),
    ]
    return render_block(event.timestamp, "TOKENS", meta, [])


def display_rate(text: String) raises -> String:
    if not text:
        return "— t/s"
    var rate = atof(text)
    if rate < 100.0:
        var tenths = Int(rate * 10.0 + 0.5)
        return String(tenths // 10) + ("." + String(tenths % 10) if tenths % 10 else "") + " t/s"
    var bits = bitcast[DType.uint64](rate)
    var mantissa = (bits & ((UInt64(1) << 52) - 1)) | (UInt64(1) << 52)
    var exponent = Int((bits >> 52) & 2047) - 1023 - 52
    if exponent < 0:
        var shift = UInt64(-exponent)
        var integer = mantissa >> shift
        var remainder = mantissa & ((UInt64(1) << shift) - 1)
        var half = UInt64(1) << (shift - 1)
        if remainder > half or (remainder == half and integer & 1):
            integer += 1
        return String(integer) + " t/s"
    var digits = String(mantissa)
    for _ in range(exponent):
        var reversed = String()
        var carry = 0
        for index in range(digits.byte_length() - 1, -1, -1):
            var doubled = (Int(digits.as_bytes()[index]) - 48) * 2 + carry
            reversed += chr(48 + doubled % 10)
            carry = doubled // 10
        if carry:
            reversed += "1"
        digits = ""
        for index in range(reversed.byte_length() - 1, -1, -1):
            digits += chr(Int(reversed.as_bytes()[index]))
    return digits + " t/s"
