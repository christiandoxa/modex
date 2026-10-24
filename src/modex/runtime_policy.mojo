"""Runtime policy settings needed by runtime log selection."""

from std.collections import List, Span
from std.os import getenv
from std.os.path import exists

from .toml import (
    TOMLDocument,
    TOML_INTEGER,
    TOML_STRING,
    TOML_TABLE,
)
from .text import is_whitespace
from .log_text import trim_unicode


def _integer(node: String) raises -> Tuple[Bool, UInt64]:
    var bytes = node.as_bytes()
    var index = 0
    var negative = False
    if bytes[0] == 45:
        negative = True
        index = 1
    elif bytes[0] == 43:
        index = 1
    var radix = UInt64(10)
    if index + 1 < len(bytes) and bytes[index] == 48:
        if bytes[index + 1] == 120:
            radix = 16
            index += 2
        elif bytes[index + 1] == 111:
            radix = 8
            index += 2
        elif bytes[index + 1] == 98:
            radix = 2
            index += 2
    if negative and radix != 10:
        raise Error("invalid runtime policy integer")
    var value = UInt64(0)
    var digit_seen = False
    var previous_digit = False
    for i in range(index, len(bytes)):
        var byte = Int(bytes[i])
        if byte == 95:
            if not previous_digit or i + 1 == len(bytes):
                raise Error("invalid runtime policy integer")
            previous_digit = False
            continue
        var digit = -1
        if 48 <= byte <= 57:
            digit = byte - 48
        elif radix == 16 and 65 <= byte <= 70:
            digit = byte - 55
        elif radix == 16 and 97 <= byte <= 102:
            digit = byte - 87
        if digit < 0 or UInt64(digit) >= radix:
            raise Error("invalid runtime policy integer")
        if value > (UInt64.MAX - UInt64(digit)) // radix:
            raise Error("runtime policy integer is out of range")
        value = value * radix + UInt64(digit)
        digit_seen = True
        previous_digit = True
    if not digit_seen or not previous_digit:
        raise Error("invalid runtime policy integer")
    if negative and value > (UInt64(1) << 63):
        raise Error("runtime policy integer is out of range")
    return negative and value != 0, value


def _unsigned_integer(node: String, maximum: UInt64) raises -> UInt64:
    var parsed = _integer(node)
    if parsed[0] or parsed[1] > maximum:
        raise Error("runtime policy integer is out of range")
    return parsed[1]


def _signed_integer(node: String, minimum: Int64, maximum: Int64) raises -> Int64:
    var parsed = _integer(node)
    var value = parsed[1]
    if parsed[0]:
        var signed = Int64.MIN if value == (UInt64(1) << 63) else -Int64(value)
        if signed < minimum or signed > maximum:
            raise Error("runtime policy integer is out of range")
        return signed
    if value > UInt64(Int64.MAX):
        raise Error("runtime policy integer is out of range")
    var signed = Int64(value)
    if signed < minimum or signed > maximum:
        raise Error("runtime policy integer is out of range")
    return signed


def _field(doc: TOMLDocument, table: Int, key: String, kind: Int) raises -> Int:
    var node = doc.get(table, key)
    if node >= 0 and doc.nodes[node].kind != kind:
        raise Error("invalid runtime policy field type")
    return node


def _validate_policy(doc: TOMLDocument, root: String) raises -> String:
    if doc.nodes[doc.root].kind != TOML_TABLE:
        raise Error("runtime policy must be a TOML table")
    var version = _field(doc, doc.root, "version", TOML_INTEGER)
    if version < 0 or _unsigned_integer(doc.nodes[version].text, 4294967295) != 1:
        raise Error("unsupported runtime policy version")

    var runtime = doc.get(doc.root, "runtime")
    var runtime_proxy = doc.get(doc.root, "runtime_proxy")
    var secrets = doc.get(doc.root, "secrets")
    if runtime >= 0 and doc.nodes[runtime].kind != TOML_TABLE:
        raise Error("runtime policy runtime must be a table")
    if runtime_proxy >= 0 and doc.nodes[runtime_proxy].kind != TOML_TABLE:
        raise Error("runtime policy runtime_proxy must be a table")
    if secrets >= 0 and doc.nodes[secrets].kind != TOML_TABLE:
        raise Error("runtime policy secrets must be a table")

    var format = _field(doc, runtime, "log_format", TOML_STRING)
    if format >= 0 and doc.nodes[format].text != "text" and doc.nodes[format].text != "json":
        raise Error("invalid runtime policy log_format")
    var log_dir = _field(doc, runtime, "log_dir", TOML_STRING)
    var selected_dir = String()
    if log_dir >= 0:
        selected_dir = doc.nodes[log_dir].text
        if not trim_unicode(selected_dir):
            raise Error("runtime policy log_dir cannot be empty")

    var proxy_keys: List[String] = [
        "preset", "worker_count", "long_lived_worker_count", "probe_refresh_worker_count",
        "async_worker_count", "long_lived_queue_capacity", "active_request_limit",
        "profile_inflight_soft_limit", "profile_inflight_hard_limit", "responses_active_limit",
        "compact_active_limit", "websocket_active_limit", "standard_active_limit",
        "http_connect_timeout_ms", "stream_idle_timeout_ms", "compact_request_timeout_ms",
        "sse_lookahead_timeout_ms", "prefetch_backpressure_retry_ms",
        "prefetch_backpressure_timeout_ms", "prefetch_max_buffered_bytes",
        "websocket_connect_timeout_ms", "websocket_happy_eyeballs_delay_ms",
        "websocket_precommit_progress_timeout_ms", "websocket_connect_worker_count",
        "websocket_connect_queue_capacity", "websocket_connect_overflow_capacity",
        "websocket_dns_worker_count", "websocket_dns_queue_capacity",
        "websocket_dns_overflow_capacity", "broker_ready_timeout_ms",
        "broker_health_connect_timeout_ms", "broker_health_read_timeout_ms",
        "websocket_previous_response_reuse_stale_ms", "admission_wait_budget_ms",
        "pressure_admission_wait_budget_ms", "long_lived_queue_wait_budget_ms",
        "pressure_long_lived_queue_wait_budget_ms", "sync_probe_pressure_pause_ms",
        "startup_sync_probe_warm_limit", "responses_critical_floor_percent",
    ]
    for index in range(len(doc.nodes[runtime_proxy].names)) if runtime_proxy >= 0 else range(0):
        var key = doc.nodes[runtime_proxy].names[index]
        var known = False
        for candidate in proxy_keys:
            if key == candidate:
                known = True
                break
        if not known:
            raise Error("unknown runtime_proxy policy field")
        var value = doc.nodes[runtime_proxy].children[index]
        if key == "preset":
            if doc.nodes[value].kind != TOML_STRING:
                raise Error("invalid runtime_proxy preset type")
            var preset = doc.nodes[value].text.lower()
            if preset != "low" and preset != "default" and preset != "many-terminals" and preset != "many_terminals" and preset != "aggressive":
                raise Error("invalid runtime_proxy preset")
        elif key == "responses_critical_floor_percent":
            if doc.nodes[value].kind != TOML_INTEGER:
                raise Error("invalid runtime_proxy integer type")
            _ = _signed_integer(doc.nodes[value].text, Int64.MIN, Int64.MAX)
        else:
            if doc.nodes[value].kind != TOML_INTEGER:
                raise Error("invalid runtime_proxy integer type")
            _ = _unsigned_integer(doc.nodes[value].text, UInt64.MAX)

    var backend = _field(doc, secrets, "backend", TOML_STRING)
    var service = _field(doc, secrets, "keyring_service", TOML_STRING)
    var backend_name = String()
    if backend >= 0:
        backend_name = doc.nodes[backend].text
        if trim_unicode(backend_name) != backend_name:
            raise Error("invalid secrets backend")
        backend_name = backend_name.lower()
        if backend_name != "file" and backend_name != "keyring":
            raise Error("invalid secrets backend")
    if service >= 0:
        var service_name = doc.nodes[service].text
        var invalid_service = not service_name
        for character in service_name.codepoints():
            if is_whitespace(Int(character)):
                invalid_service = True
                break
        if invalid_service:
            raise Error("invalid secrets keyring_service")
    if service >= 0 and backend_name != "keyring":
        raise Error("keyring_service requires keyring backend")
    if backend_name == "keyring" and service < 0:
        raise Error("keyring_service is required for keyring backend")

    if log_dir < 0:
        return String()
    if selected_dir.startswith("/"):
        return selected_dir^
    return (root if root.endswith("/") else root + "/") + selected_dir


def _policy_log_dir(root: String) raises -> String:
    var path = root + "/policy.toml"
    if not exists(path):
        return String()
    var file = open(path, "r")
    var bytes = file.read_bytes()
    var source = String(from_utf8=Span(bytes))
    var doc = TOMLDocument(source)
    return _validate_policy(doc, root)


def runtime_log_dir(root: String) raises -> String:
    var environment = getenv("PRODEX_RUNTIME_LOG_DIR", "")
    if environment:
        return environment^
    try:
        var configured = _policy_log_dir(root)
        if configured:
            return configured^
    except:
        pass
    var temporary = getenv("TMPDIR", "/tmp")
    return temporary if temporary else String("/tmp")
