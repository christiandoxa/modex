from std.collections import List, Optional, Span
from std.io import FileHandle, RawFileDescriptor
from std.os import isatty, listdir, lstat, stat
from std.os.path import exists
from std.pathlib import cwd

from .json import JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json
from .local_time import format_local_epoch
from .paths import absolute_path, comparable_path, ensure_app_root, shared_root
from .session_time import integer_timestamp, timestamp_key
from .text import cli_width, pad_cell, section_header, status_panel, text_width, trim_text
from .zstd import ZstdReader

comptime SESSION_LINE_LIMIT = 64 * 1024 * 1024


def session_query_case_ignorable(code: Int) -> Bool:
    # shortcut: skips common combining diacritics and apostrophes; use full Unicode Case_Ignorable data before claiming all contextual sigma cases.
    return 0x0300 <= code <= 0x036F or code == 0x0027 or code == 0x2019


def session_query_cased(code: Int) -> Bool:
    if code < 128:
        return 65 <= code <= 90 or 97 <= code <= 122
    var character = chr(code)
    return character.lower() != character.upper()


def session_query_lowercase(value: String) -> String:
    if value.find(chr(0x0130)) < 0 and value.find(chr(0x03A3)) < 0:
        return value.lower()
    var characters = value.codepoints()
    var before_cased = False
    var output = String()
    while True:
        var character = characters.next()
        if not character:
            break
        var code = Int(character.value())
        if code == 0x0130:
            output += "i\u0307"
        elif code == 0x03A3:
            var after = characters.copy()
            var after_cased = False
            while True:
                var next_character = after.next()
                if not next_character:
                    break
                var next_code = Int(next_character.value())
                if not session_query_case_ignorable(next_code):
                    after_cased = session_query_cased(next_code)
                    break
            output += chr(0x03C2 if before_cased and not after_cased else 0x03C3)
        else:
            output += chr(code).lower()
        if not session_query_case_ignorable(code):
            before_cased = session_query_cased(code)
    return output^


@fieldwise_init
struct SessionOptions(Copyable):
    var current: Bool
    var output: String
    var profile: Optional[String]
    var query: String
    var limit: Optional[UInt64]
    var directory: Optional[String]
    var parent_only: Bool


@fieldwise_init
struct SessionReport(Copyable):
    var id: String
    var thread_name: String
    var updated_at: String
    var directory: String
    var provider: String
    var parent: String
    var path: String
    var sort_key: Int

    def __lt__(self, other: Self) -> Bool:
        if self.sort_key != other.sort_key:
            return self.sort_key > other.sort_key
        if self.id != other.id:
            return self.id < other.id
        return self.path < other.path

    def apply(mut self, document: JsonDocument) raises:
        var type_index = document.get(document.root, "type")
        var kind = document.string(type_index)
        if type_index < 0 or document.nodes[type_index].kind != JSON_STRING or kind == "session_meta":
            var identifier = first_string(document, ["payload.id", "payload.session_id", "id", "session_id"])
            if identifier:
                self.id = identifier^
        var name = first_string(document, ["payload.thread_name", "payload.title", "payload.metadata.thread_name", "thread_name", "title", "metadata.thread_name"])
        if name:
            self.thread_name = name^
        var directory = first_string(document, ["payload.cwd", "payload.metadata.cwd", "payload.workdir", "cwd", "metadata.cwd", "workdir"])
        if directory:
            self.directory = directory^
        var updated = first_string(document, ["updated_at", "timestamp", "payload.updated_at", "payload.timestamp"])
        if updated:
            var parsed = timestamp_key(updated)
            if parsed:
                self.sort_key = parsed.value()
            self.updated_at = updated^
        else:
            for path in ["updated_at", "ts", "timestamp", "payload.updated_at", "payload.ts", "payload.timestamp"]:
                var index = member_path(document, path)
                if index >= 0 and document.nodes[index].kind == JSON_NUMBER:
                    var epoch = integer_timestamp(document.nodes[index].text)
                    if epoch:
                        self.sort_key = epoch.value()
                        self.updated_at = format_local_epoch(epoch.value())
                        break
        var parent = first_string(document, ["payload.source.subagent.thread_spawn.parent_thread_id", "source.subagent.thread_spawn.parent_thread_id", "payload.parent_thread_id", "parent_thread_id"])
        if parent:
            self.parent = parent^
        var provider = first_string(document, ["payload.model_provider", "payload.metadata.model_provider", "model_provider", "metadata.model_provider"])
        if provider:
            self.provider = provider^

    def matches(self, options: SessionOptions) -> Bool:
        if options.parent_only and self.parent:
            return False
        if options.profile:
            return False
        if options.current and (not self.directory or comparable_path(self.directory) != comparable_path(options.directory.value())):
            return False
        var query = session_query_lowercase(trim_text(options.query))
        if query:
            for field in [self.id, self.thread_name, self.directory, self.provider, self.path]:
                if query in session_query_lowercase(field):
                    return True
            return False
        return True

    def json(self) -> String:
        var output = String("  {\n    \"id\": ") + quote_json(self.id)
        output += ",\n    \"thread_name\": " + nullable_json(self.thread_name)
        output += ",\n    \"updated_at\": " + nullable_json(self.updated_at)
        output += ",\n    \"cwd\": " + nullable_json(self.directory)
        output += ",\n    \"profile\": null"
        if self.provider:
            output += ",\n    \"model_provider\": " + quote_json(self.provider)
        output += ",\n    \"path\": " + quote_json(self.path)
        if self.parent:
            output += ",\n    \"parent_thread_id\": " + quote_json(self.parent)
        return output + "\n  }"


def nullable_json(text: String) -> String:
    return quote_json(text) if text else "null"


def member_path(document: JsonDocument, path: StringSlice) -> Int:
    var index = document.root
    for name in path.split("."):
        index = document.get(index, name)
        if index < 0:
            break
    return index


def first_string(document: JsonDocument, paths: List[String]) -> String:
    for path in paths:
        var value = trim_text(document.string(member_path(document, path)))
        if value:
            return String(value)
    return ""


def starts_session(document: JsonDocument) -> Bool:
    if document.nodes[document.root].kind != JSON_OBJECT:
        return False
    var type_index = document.get(document.root, "type")
    if type_index >= 0 and document.nodes[type_index].kind == JSON_STRING:
        if document.string(type_index) != "session_meta":
            return False
    return first_string(document, ["payload.id", "payload.session_id", "id", "session_id"]) != ""


def session_paths(root: String, mut paths: List[String]) raises:
    if not exists(root):
        return
    for name in listdir(root):
        var path = root + "/" + name
        var mode = lstat(path).st_mode & 0o170000
        if mode == 0o040000:
            session_paths(path, paths)
        elif mode == 0o100000 and (name.endswith(".json") or name.endswith(".jsonl") or name.endswith(".jsonl.zst")):
            paths.append(path^)


def checked_session_file(path: String) raises -> FileHandle:
    var before = lstat(path)
    if (before.st_mode & 0o170000) != 0o100000:
        raise Error("session path is not a regular file")
    var file = open(path, "r")
    # Linux /proc identifies the opened descriptor without adding an fstat binding.
    var opened = stat("/proc/self/fd/" + String(RawFileDescriptor(file).value))
    var current = lstat(path)
    if (current.st_mode & 0o170000) != 0o100000 or before.st_ino != opened.st_ino or before.st_dev != opened.st_dev or current.st_ino != opened.st_ino or current.st_dev != opened.st_dev:
        raise Error("session path changed while opening")
    return file^


def apply_line(mut report: SessionReport, line: String, mut started: Bool) raises -> Bool:
    var trimmed = trim_text(line)
    if not trimmed:
        return True
    var document: JsonDocument
    try:
        document = JsonDocument(line if not started else trimmed)
    except:
        return started
    if not started:
        if not starts_session(document):
            return False
        started = True
    if document.nodes[document.root].kind == JSON_OBJECT:
        report.apply(document)
    return True


def decode_session_line(bytes: List[UInt8], path: String) raises -> String:
    try:
        return String(from_utf8=Span(bytes))
    except:
        raise Error("failed to read session " + path + ": stream did not contain valid UTF-8")


def apply_session_block(mut report: SessionReport, block: List[UInt8], mut pending: List[UInt8], mut started: Bool, path: String) raises -> Bool:
    for byte in block:
        pending.append(byte)
        if len(pending) > SESSION_LINE_LIMIT:
            raise Error("session line " + path + " exceeds safe size limit (67108864 bytes)")
        if byte == 10:
            var line = decode_session_line(pending, path)
            pending.clear()
            if not apply_line(report, line, started):
                return False
    return True


def read_session(path: String) raises -> Optional[SessionReport]:
    var compressed = path.endswith(".jsonl.zst")
    var components = path.split("/")
    var filename = components[len(components) - 1]
    var suffix = 10 if compressed else 5 if path.endswith(".json") else 6
    var identifier = String(filename[byte=:filename.byte_length() - suffix])
    var report = SessionReport(identifier^, "", "", "", "", "", path, stat(path).st_mtimespec.tv_sec)
    var started = False
    if compressed:
        var decoder = ZstdReader(checked_session_file(path))
        var pending = List[UInt8]()
        while True:
            var block: List[UInt8]
            try:
                block = decoder.read_chunk()
            except error:
                raise Error("failed to read session " + path + ": " + String(error))
            if not block:
                break
            if not apply_session_block(report, block, pending, started, path):
                return None
        if pending and not apply_line(report, decode_session_line(pending, path), started):
            return None
        if not started:
            return None
        if not report.updated_at:
            report.updated_at = format_local_epoch(report.sort_key)
        return report^
    with checked_session_file(path) as file:
        if path.endswith(".json"):
            var bytes = file.read_bytes(SESSION_LINE_LIMIT + 1)
            if len(bytes) > SESSION_LINE_LIMIT:
                raise Error("session exceeds safe size limit (67108864 bytes)")
            var text = String(from_utf8=Span(bytes))
            var parsed = False
            try:
                var document = JsonDocument(text)
                parsed = True
                if not starts_session(document):
                    return None
                report.apply(document)
            except:
                if parsed:
                    raise
            if parsed:
                if not report.updated_at:
                    report.updated_at = format_local_epoch(report.sort_key)
                return report^
            for line in text.split("\n"):
                if not apply_line(report, trim_text(line), started):
                    return None
        else:
            var pending = List[UInt8]()
            while True:
                var block = file.read_bytes(64 * 1024)
                if not block:
                    break
                if not apply_session_block(report, block, pending, started, path):
                    return None
            if pending:
                if not apply_line(report, decode_session_line(pending, path), started):
                    return None
    if not started:
        return None
    if not report.updated_at:
        report.updated_at = format_local_epoch(report.sort_key)
    return report^


def inspect_sessions(var options: SessionOptions) raises -> String:
    if options.current:
        options.directory = absolute_path(options.directory.value()) if options.directory else String(cwd())
    var root = ensure_app_root()
    # shortcut: state/journal recovery is unavailable; reject these homes until locking and durable writes are proven.
    for name in listdir(root):
        if name in ["state.json", "state.json.lock", "state.json.last-good", "profile-lifecycle-journal", "profile-import-auth-journal"] or (name.startswith("state.json.") and name.endswith(".tmp")):
            raise Error("locked state loading and recovery are not implemented")
    var paths = List[String]()
    var shared = shared_root(root)
    session_paths(shared + "/sessions", paths)
    session_paths(shared + "/archived_sessions", paths)
    sort(paths)
    var reports = List[SessionReport]()
    for path in paths:
        var report = read_session(path)
        if report and report.value().matches(options):
            reports.append(report.take())
    sort(Span(reports), lambda (left: SessionReport, right: SessionReport) -> Bool: left < right)
    var count = len(reports)
    if options.limit:
        count = Int(min(UInt64(count), options.limit.value()))
    var output = String()
    if options.output == "json":
        if count == 0:
            return "[]\n"
        output = "[\n"
        for index in range(count):
            if index:
                output += ",\n"
            output += reports[index].json()
        return output + "\n]\n"
    if options.output == "id-only" or options.output == "resume-command":
        for index in range(count):
            if options.output == "resume-command":
                output += "modex run "
            output += reports[index].id + "\n"
        return output^
    if isatty(1):
        raise Error("session terminal rendering is not implemented")
    var width = cli_width()
    if count == 0:
        var message = String("No sessions found")
        if options.current:
            message += " for " + options.directory.value()
        return status_panel("Sessions", message, width)
    var available = max(width - 8, 5)
    var fifth = available // 5
    var widths: List[Int] = [min(fifth, 26), min(fifth, 22), min(fifth, 24)]
    var remaining = available - widths[0] - widths[1] - widths[2]
    widths.append(remaining // 2)
    widths.append(remaining - remaining // 2)
    var header = session_row(["ID", "UPDATED", "THREAD", "CWD", "PATH"], widths)
    output = section_header("Sessions", width) + "\n" + header + "\n" + String("-") * header.byte_length()
    for index in range(count):
        ref report = reports[index]
        output += "\n" + session_row([
            report.id,
            report.updated_at if report.updated_at else String("-"),
            report.thread_name if report.thread_name else String("-"),
            report.directory if report.directory else String("-"),
            report.path,
        ], widths)
        if text_width(report.id) > widths[0]:
            output += "\n  id: " + report.id
    return output^


def session_row(fields: List[String], widths: List[Int]) raises -> String:
    var output = String()
    for index in range(len(fields)):
        if index:
            output += "  "
        output += pad_cell(fields[index], widths[index])
    return output^
