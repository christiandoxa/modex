from std.collections import Dict, List, Optional, Span
from std.io import FileHandle, RawFileDescriptor
from std.os import getuid, listdir, lstat, stat, stat_result
from std.os.path import exists
from std.pathlib import cwd
from std.time.time import _realtime_nanoseconds

from .json import JSON_BOOL, JSON_NULL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json
from .local_time import format_local_epoch
from .paths import absolute_path, comparable_path, ensure_app_root, shared_root
from .session_time import integer_timestamp, timestamp_key
from .text import cli_width, pad_cell, section_header, status_panel, text_width, trim_text
from .zstd import ZstdReader
from .unicode_properties import is_cased, is_case_ignorable

comptime SESSION_LINE_LIMIT = 64 * 1024 * 1024
comptime STATE_FILE_LIMIT = 64 * 1024 * 1024
comptime SESSION_BINDING_LIMIT = 2048
comptime SESSION_BINDING_RETENTION = 30 * 24 * 60 * 60
comptime HARD_BINDING_CONFLICT_PROFILE = "__prodex_hard_binding_conflict__"


@fieldwise_init
struct SessionProfileBinding(Copyable):
    var session_id: String
    var profile_name: String
    var bound_at: Int
    var hard_conflict: Bool


def session_query_lowercase_override(code: Int) -> Int:
    # Mojo's lowercase table predates these Unicode 17 mappings.
    if code == 0xA7CB: return 0x0264
    if code == 0xA7DC: return 0x019B
    if code == 0x1C89 or code == 0xA7CC or code == 0xA7CE or code == 0xA7D2 or code == 0xA7D4 or code == 0xA7DA:
        return code + 1
    if 0x10D50 <= code <= 0x10D65: return code + 0x20
    if 0x16EA0 <= code <= 0x16EB8: return code + 0x1B
    return code


def session_query_lowercase(value: String) -> String:
    var needs_special_mapping = False
    for character in value.codepoints():
        var code = Int(character)
        if code == 0x0130 or code == 0x03A3 or session_query_lowercase_override(code) != code:
            needs_special_mapping = True
            break
    if not needs_special_mapping:
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
                if not is_case_ignorable(next_code):
                    after_cased = is_cased(next_code)
                    break
            output += chr(0x03C2 if before_cased and not after_cased else 0x03C3)
        elif session_query_lowercase_override(code) != code:
            output += chr(session_query_lowercase_override(code))
        else:
            output += chr(code).lower()
        if not is_case_ignorable(code):
            before_cased = is_cased(code)
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
    var profile: Optional[String]
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
        if options.profile and self.profile != options.profile:
            return False
        if options.current and (not self.directory or comparable_path(self.directory) != comparable_path(options.directory.value())):
            return False
        var query = session_query_lowercase(trim_text(options.query))
        if query:
            for field in [self.id, self.thread_name, self.directory, self.profile.value() if self.profile else String(), self.provider, self.path]:
                if query in session_query_lowercase(field):
                    return True
            return False
        return True

    def json(self) -> String:
        var output = String("  {\n    \"id\": ") + quote_json(self.id)
        output += ",\n    \"thread_name\": " + nullable_json(self.thread_name)
        output += ",\n    \"updated_at\": " + nullable_json(self.updated_at)
        output += ",\n    \"cwd\": " + nullable_json(self.directory)
        output += ",\n    \"profile\": " + (quote_json(self.profile.value()) if self.profile else "null")
        if self.provider:
            output += ",\n    \"model_provider\": " + quote_json(self.provider)
        output += ",\n    \"path\": " + quote_json(self.path)
        if self.parent:
            output += ",\n    \"parent_thread_id\": " + quote_json(self.parent)
        return output + "\n  }"


def nullable_json(text: String) -> String:
    return quote_json(text) if text else "null"


def session_profile_display(value: String) -> String:
    var output = String()
    for character in value.codepoints():
        var code = Int(character)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            var high = code // 16
            var low = code % 16
            output += "\\x"
            output += String(chr(48 + high)) if high < 10 else String(chr(87 + high))
            output += String(chr(48 + low)) if low < 10 else String(chr(87 + low))
        else:
            output += chr(code)
    return output^


def member_path(document: JsonDocument, path: StringSlice) -> Int:
    var index = document.root
    for name in path.split("."):
        index = document.get(index, name)
        if index < 0:
            break
    return index


def session_child_path(root: String, name: String) -> String:
    var root_bytes = root.as_bytes()
    if len(root_bytes) > 0 and root_bytes[len(root_bytes) - 1] == 0x2F:
        return root + name
    return root + "/" + name


def valid_session_name(name: String) -> Optional[String]:
    try:
        return String(from_utf8=name.as_bytes())
    except:
        return None


def read_private_state_file(path: String) raises -> List[UInt8]:
    var before = lstat(path)
    var permissions = before.st_mode & 0o077
    # Group/other writable state and externally exposed read aliases are unsafe.
    var unsafe_permissions = (permissions & 0o022) != 0 or (before.st_nlink > 1 and (permissions & 0o044) != 0)
    if (before.st_mode & 0o170000) != 0o100000 or before.st_uid != getuid() or unsafe_permissions or before.st_size > STATE_FILE_LIMIT:
        raise Error("unsafe state file")
    var file = open(path, "r")
    var descriptor = RawFileDescriptor(file).value
    var descriptor_path = "/proc/self/fd/" + String(descriptor)
    var opened = stat(descriptor_path)
    var current = lstat(path)
    if not same_private_state_file(before, opened) or not same_private_state_file(opened, current):
        raise Error("state path changed while opening")
    var bytes = file.read_bytes(STATE_FILE_LIMIT + 1)
    if len(bytes) > STATE_FILE_LIMIT:
        raise Error("state file exceeds safe size limit")
    var read_opened = stat(descriptor_path)
    var read_descriptor = RawFileDescriptor(file).value
    var read_current = lstat(path)
    if read_descriptor != descriptor or not same_private_state_file(opened, read_opened) or not same_private_state_file(read_opened, read_current):
        raise Error("state path changed while reading")
    return bytes^


def same_private_state_file(left: stat_result, right: stat_result) -> Bool:
    return (right.st_mode & 0o170000) == 0o100000 and right.st_uid == getuid() and left.st_mode == right.st_mode and left.st_uid == right.st_uid and left.st_nlink == right.st_nlink and left.st_ino == right.st_ino and left.st_dev == right.st_dev and left.st_size == right.st_size and left.st_mtimespec.tv_sec == right.st_mtimespec.tv_sec and left.st_mtimespec.tv_nsec == right.st_mtimespec.tv_nsec and left.st_ctimespec.tv_sec == right.st_ctimespec.tv_sec and left.st_ctimespec.tv_nsec == right.st_ctimespec.tv_nsec


def state_field(document: JsonDocument, node: Int, name: String) raises -> Int:
    if node < 0 or document.nodes[node].kind != JSON_OBJECT:
        raise Error("invalid state object")
    var count = 0
    for field in document.nodes[node].names:
        if field == name:
            count += 1
    if count > 1:
        raise Error("duplicate state field")
    return document.get(node, name)


def state_optional_string(document: JsonDocument, node: Int, name: String) raises:
    var value = state_field(document, node, name)
    if value >= 0 and document.nodes[value].kind != JSON_NULL and document.nodes[value].kind != JSON_STRING:
        raise Error("invalid state string")


def state_required_string(document: JsonDocument, node: Int, name: String) raises -> String:
    var value = state_field(document, node, name)
    if value < 0 or document.nodes[value].kind != JSON_STRING:
        raise Error("missing state string")
    return document.string(value)


def state_integer(document: JsonDocument, node: Int) raises -> Int:
    if node < 0 or document.nodes[node].kind != JSON_NUMBER:
        raise Error("invalid state integer")
    var parsed = integer_timestamp(document.nodes[node].text)
    if not parsed:
        raise Error("invalid state integer")
    return parsed.value()


def validate_state_identity(document: JsonDocument, node: Int) raises:
    if node < 0 or document.nodes[node].kind != JSON_OBJECT:
        raise Error("invalid binding identity")
    var provider = state_required_string(document, node, "provider")
    if provider not in ["openai", "anthropic", "copilot", "deepseek", "gemini", "kiro", "local"]:
        raise Error("invalid binding provider")
    for field in ["credential_identity", "endpoint_identity"]:
        if not public_state_digest(state_required_string(document, node, field)):
            raise Error("invalid binding digest")
    var profile = state_field(document, node, "profile_identity")
    if profile >= 0 and document.nodes[profile].kind != JSON_NULL and (document.nodes[profile].kind != JSON_STRING or not public_state_digest(document.string(profile))):
        raise Error("invalid binding digest")


def public_state_digest(value: String) -> Bool:
    if not value.startswith("sha256:") or value.byte_length() != 71:
        return False
    for raw_byte in value.as_bytes()[7:]:
        var byte = Int(raw_byte)
        if not (48 <= byte <= 57 or 97 <= byte <= 102):
            return False
    return True


def validate_state_profile(document: JsonDocument, node: Int) raises:
    if node < 0 or document.nodes[node].kind != JSON_OBJECT:
        raise Error("invalid state profile")
    _ = state_required_string(document, node, "codex_home")
    var managed = state_field(document, node, "managed")
    if managed < 0 or document.nodes[managed].kind != JSON_BOOL:
        raise Error("invalid state profile")
    state_optional_string(document, node, "email")
    var provider = state_field(document, node, "provider")
    if provider < 0:
        return
    if document.nodes[provider].kind != JSON_OBJECT:
        raise Error("invalid state provider")
    var kind = state_required_string(document, provider, "provider_kind")
    if kind == "openai":
        return
    if kind == "gemini":
        _ = state_required_string(document, provider, "email")
        state_optional_string(document, provider, "project_id")
    elif kind == "anthropic":
        state_optional_string(document, provider, "account")
        state_optional_string(document, provider, "auth_method")
    elif kind == "copilot":
        _ = state_required_string(document, provider, "host")
        _ = state_required_string(document, provider, "login")
        _ = state_required_string(document, provider, "api_url")
        state_optional_string(document, provider, "access_type_sku")
        state_optional_string(document, provider, "copilot_plan")
    elif kind == "kiro":
        _ = state_required_string(document, provider, "auth_key")
        for field in ["auth_kind", "profile_arn", "profile_name", "start_url", "region"]:
            state_optional_string(document, provider, field)
    elif kind == "agy":
        state_optional_string(document, provider, "account")
    else:
        raise Error("unknown state provider")


def validate_state_bindings(document: JsonDocument, node: Int, profile_names: Dict[String, Bool], now: Int, collect: Bool, mut bindings: List[SessionProfileBinding]) raises:
    if node < 0:
        return
    if document.nodes[node].kind != JSON_OBJECT:
        raise Error("invalid state bindings")
    var last_indices = Dict[String, Int]()
    if collect:
        for index in range(len(document.nodes[node].names)):
            last_indices[document.nodes[node].names[index]] = index
    for index in range(len(document.nodes[node].names)):
        var session_id = document.nodes[node].names[index]
        var binding = document.nodes[node].children[index]
        if document.nodes[binding].kind != JSON_OBJECT:
            raise Error("invalid state binding")
        var profile_name = state_required_string(document, binding, "profile_name")
        var bound_at = state_integer(document, state_field(document, binding, "bound_at"))
        var identity = state_field(document, binding, "binding_identity")
        var has_identity = identity >= 0 and document.nodes[identity].kind != JSON_NULL
        if has_identity:
            validate_state_identity(document, identity)
        if collect:
            var keep = profile_name == HARD_BINDING_CONFLICT_PROFILE or ((has_identity or state_profile_exists(profile_names, profile_name)) and bound_at >= max(0, now - SESSION_BINDING_RETENTION))
            var latest = last_indices.get(session_id)
            if keep and latest and latest.value() == index:
                bindings.append(SessionProfileBinding(session_id, profile_name, bound_at, profile_name == HARD_BINDING_CONFLICT_PROFILE))


def state_profile_exists(profile_names: Dict[String, Bool], profile_name: String) -> Bool:
    if profile_names.get(profile_name):
        return True
    return False


def current_state_time() -> Int:
    var now = _realtime_nanoseconds()
    return max(0, now // 1_000_000_000)


def load_session_profile_bindings(root: String, has_state_file: Bool) raises -> List[SessionProfileBinding]:
    var bindings = List[SessionProfileBinding]()
    if not has_state_file:
        return bindings^
    var path = session_child_path(root, "state.json")
    try:
        var bytes = read_private_state_file(path)
        var document = JsonDocument(String(from_utf8=Span(bytes)))
        if document.nodes[document.root].kind != JSON_OBJECT:
            raise Error("invalid state root")
        var schema = state_field(document, document.root, "schema_version")
        if schema >= 0 and document.nodes[schema].kind != JSON_NUMBER:
            raise Error("invalid state schema")
        if schema >= 0 and document.nodes[schema].text != "0" and document.nodes[schema].text != "1":
            raise Error("unsupported state schema")
        state_optional_string(document, document.root, "active_profile")
        var profiles = state_field(document, document.root, "profiles")
        var profile_names = Dict[String, Bool]()
        if profiles >= 0:
            if document.nodes[profiles].kind != JSON_OBJECT:
                raise Error("invalid state profiles")
            for index in range(len(document.nodes[profiles].children)):
                var profile = document.nodes[profiles].children[index]
                validate_state_profile(document, profile)
                profile_names[document.nodes[profiles].names[index]] = True
        var last_run = state_field(document, document.root, "last_run_selected_at")
        if last_run >= 0:
            if document.nodes[last_run].kind != JSON_OBJECT:
                raise Error("invalid state selection")
            for selected_at in document.nodes[last_run].children:
                _ = state_integer(document, selected_at)
        var response_bindings = state_field(document, document.root, "response_profile_bindings")
        var now = current_state_time()
        validate_state_bindings(document, response_bindings, profile_names, now, False, bindings)
        var session_bindings = state_field(document, document.root, "session_profile_bindings")
        validate_state_bindings(document, session_bindings, profile_names, now, True, bindings)
    except:
        raise Error("locked state loading and recovery are not implemented")
    sort(Span(bindings), lambda (left: SessionProfileBinding, right: SessionProfileBinding) -> Bool:
         not left.hard_conflict and right.hard_conflict or left.hard_conflict == right.hard_conflict and (left.bound_at < right.bound_at or left.bound_at == right.bound_at and left.session_id < right.session_id))
    if len(bindings) > SESSION_BINDING_LIMIT:
        var retained = List[SessionProfileBinding]()
        for index in range(len(bindings) - SESSION_BINDING_LIMIT, len(bindings)):
            var binding = bindings[index].copy()
            retained.append(binding^)
        return retained^
    return bindings^


def state_profile_for_session(bindings: Dict[String, String], session_id: String) -> Optional[String]:
    return bindings.get(session_id)


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
    for raw_name in listdir(root):
        var path = session_child_path(root, raw_name)
        var mode = lstat(path).st_mode & 0o170000
        if mode == 0o040000:
            session_paths(path, paths)
        elif mode == 0o100000:
            var name = valid_session_name(raw_name)
            if name and (name.value().endswith(".json") or name.value().endswith(".jsonl") or name.value().endswith(".jsonl.zst")):
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
    var display_path = String(from_utf8_lossy=path.as_bytes())
    var report = SessionReport(identifier^, "", "", "", "", Optional[String](), "", display_path^, stat(path).st_mtimespec.tv_sec)
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
    var has_state_file = False
    var has_state_lock = False
    var has_last_good = False
    for raw_name in listdir(root):
        var name = valid_session_name(raw_name)
        if not name:
            continue
        var candidate = name.value()
        if candidate == "state.json":
            # Path.exists() in Prodex treats a dangling primary symlink as absent.
            has_state_file = exists(session_child_path(root, candidate))
        elif candidate == "state.json.lock":
            has_state_lock = True
        elif candidate == "state.json.last-good":
            has_last_good = True
        elif candidate in ["profile-lifecycle-journal", "profile-import-auth-journal"] or (candidate.startswith("state.json.") and candidate.endswith(".tmp")):
            raise Error("locked state loading and recovery are not implemented")
    if (has_last_good or has_state_lock) and not has_state_file:
        raise Error("locked state loading and recovery are not implemented")
    var profile_bindings = load_session_profile_bindings(root, has_state_file)
    var profile_by_session = Dict[String, String]()
    for binding in profile_bindings:
        profile_by_session[binding.session_id] = binding.profile_name
    var paths = List[String]()
    var shared = shared_root(root)
    session_paths(session_child_path(shared, "sessions"), paths)
    session_paths(session_child_path(shared, "archived_sessions"), paths)
    sort(paths)
    var reports = List[SessionReport]()
    for path in paths:
        var report = read_session(path)
        if report:
            var value = report.take()
            value.profile = state_profile_for_session(profile_by_session, value.id)
            if value.matches(options):
                reports.append(value^)
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
        if report.profile:
            output += "\n  profile: " + session_profile_display(report.profile.value())
    return output^


def session_id_matches(id: String, selector: String, exact: Bool) -> Bool:
    if selector.byte_length() > id.byte_length() or (
        exact and selector.byte_length() != id.byte_length()
    ):
        return False
    var id_bytes = id.as_bytes()
    var selector_bytes = selector.as_bytes()
    # The frozen selector folds ASCII only, preserving arbitrary ID bytes.
    for index in range(selector.byte_length()):
        var left = Int(id_bytes[index])
        var right = Int(selector_bytes[index])
        if 65 <= left <= 90:
            left += 32
        if 65 <= right <= 90:
            right += 32
        if left != right:
            return False
    return True


def resolve_session_id(ids: List[String], selector: String) raises -> String:
    var selected = trim_text(selector)
    if not selected:
        raise Error("session could not be resolved")
    var exact_count = 0
    var exact_id = String()
    var prefix_count = 0
    var prefix_id = String()
    for id in ids:
        if session_id_matches(id, selected, True):
            exact_count += 1
            exact_id = id
        elif session_id_matches(id, selected, False):
            prefix_count += 1
            prefix_id = id
    if exact_count == 1:
        return exact_id^
    if exact_count > 1 or prefix_count > 1:
        raise Error("session selector is ambiguous")
    if prefix_count == 1:
        return prefix_id^
    raise Error("session could not be resolved")


def resolve_session_id_from_store(selector: String) raises -> String:
    var options = SessionOptions(False, "id-only", None, "", None, None, False)
    var ids = List[String]()
    for id in inspect_sessions(options^).split("\n"):
        if id:
            ids.append(String(id))
    return resolve_session_id(ids, selector)


# shortcut: only absent app state and shared config reach this path, when to upgrade: when managed session authorization is implemented.
def session_resume_has_no_profile_source() raises -> Bool:
    var root = ensure_app_root()
    for raw_name in listdir(root):
        var name = valid_session_name(raw_name)
        if name and name.value() == "state.json":
            return False
    if exists(shared_root(root) + "/config.toml"):
        return False
    return True


def session_row(fields: List[String], widths: List[Int]) raises -> String:
    var output = String()
    for index in range(len(fields)):
        if index:
            output += "  "
        output += pad_cell(fields[index], widths[index])
    return output^
