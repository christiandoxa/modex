from std.collections import List, Optional, Span

from .log_redaction import redact_log_text
from .log_time import local_log_timestamp
from .logs import LogEvent, RuntimeRecord


def operational_event(record: RuntimeRecord) raises -> Optional[LogEvent]:
    var event = record.event
    if not record.envelope or not event or is_suppressed_operational_event(event):
        return None
    var source = operational_source(record)
    if not source:
        return None
    if is_load_event(event) and not is_routine_load_event(event):
        source = "error"
    var request = short_request_id(record.field("request"))
    var summary = operational_summary(record, event, source)
    var timestamp = local_log_timestamp(record.timestamp if record.timestamp_present else "-")
    return Optional(LogEvent(timestamp, source, request + "  " + summary))


def is_suppressed_operational_event(event: String) -> Bool:
    return event == "stream_payload" or event == "upstream_payload" or event == "token_usage" or event == "token_usage_progress"


def is_load_event(event: String) -> Bool:
    return event == "runtime_proxy_queue_overloaded" or event == "runtime_proxy_active_limit_reached" or event == "runtime_proxy_lane_limit_reached" or event == "runtime_proxy_overload_backoff" or event == "runtime_proxy_admission_wait_exhausted" or event == "runtime_proxy_queue_wait_exhausted" or event == "profile_inflight_saturated" or event == "websocket_dns_overflow_reject" or event == "websocket_connect_overflow_reject" or event == "websocket_connect_overflow_rejected"


def is_routine_load_event(event: String) -> Bool:
    return event == "profile_inflight_saturated" or event == "runtime_proxy_active_limit_reached" or event == "runtime_proxy_lane_limit_reached"


def operational_source(record: RuntimeRecord) -> String:
    var event = record.event
    if event == "request_captured": return "request"
    if event == "compat_request_surface":
        var tools = record.field("tool_surface")
        var continuation = record.field("continuation")
        var family = record.field("family")
        var interesting = (record.has("tool_surface") and tools != "none") or (record.has("continuation") and continuation != "none") or (record.has("family") and family != "codex")
        if record.has("tool_surface") and tools.find("mcp") >= 0: return "mcp"
        if record.has("tool_surface") and (tools.find("sub_agent") >= 0 or tools.find("subagent") >= 0): return "agent"
        return "request" if interesting else ""
    if event == "smart_context_prepare_fallback":
        if record.has("decision"):
            return "" if record.field("decision") == "pass_through" else "smart"
        return "event"
    if event == "profile_commit":
        return "route" if record.has("switched") and record.field("switched") == "true" else ""
    if contains_event("|route_decision|selection_plan|selection_pick|selection_keep_affinity|selection_keep_current|selection_skip_current|selection_skip_affinity|selection_skip_sync_probe|local_selection_blocked|route_affinity_recompute|route_affinity_recompute_result|profile_commit|previous_response_owner|previous_response_not_found|previous_response_negative_cache|previous_response_fresh_fallback|previous_response_fresh_fallback_blocked|previous_response_turn_state_rehydrated|session_rotation_release_affinity|binding_prompt_cache|upgrade|upgraded|", event): return "route"
    if contains_event("|profile_quota_exhausted|quota_exhausted|quota_blocked|quota_critical_floor_before_send|profile_quota_quarantine|profile_probe_refresh_start|profile_probe_refresh_ok|compact_pre_send_allow_quota_exhausted|upstream_usage_limit_passthrough|upstream_overload_passthrough|", event): return "quota"
    if contains_event("|profile_retry_backoff|compact_retryable_failure|compact_overload_conservative_retry|local_rewrite_gemini_quota_rotate|local_rewrite_gemini_rate_limit_retry|local_rewrite_gemini_invalid_stream_retry|websocket_reuse_owner_fresh_retry|websocket_reuse_nonreplayable_fresh_retry|websocket_reuse_locked_affinity_owner_fresh_retry|", event): return "retry"
    if contains_event("|profile_transport_backoff|rotation_waiting_for_recovery|profile_circuit_open|profile_circuit_half_open_probe|websocket_reuse_watchdog_timeout|profile_auth_backoff|", event): return "backoff"
    if contains_event("|profile_transport_failure|profile_health|profile_bad_pairing|", event): return "health"
    if event == "profile_auth_recovery_failed" or event == "profile_auth_background_refresh_failed": return "error"
    if event == "profile_auth_recovered" or event == "local_rewrite_request_detail" or event == "local_rewrite_provider_model_fallback" or event == "local_rewrite_provider_auth_failure": return "model"
    if contains_event("|upstream_start|upstream_response|upstream_async_start|upstream_async_response|upstream_connect_start|upstream_connect_ok|upstream_connect_error|", event): return "upstream"
    if contains_event("|first_upstream_chunk|first_local_chunk|stream_complete|committed|", event): return "stream"
    if event == "buffered_response_complete": return "response"
    if event == "terminal_event": return "terminal"
    if event == "local_rewrite_gemini_builtin_tool_fallback": return "tool"
    if is_load_event(event): return "load"
    if event == "smart_context_autopilot" or event == "smart_context_prepare_error" or event == "smart_context_disabled": return "smart"
    if contains_event("|websocket_precommit_frame_timeout|websocket_precommit_hold_timeout|websocket_dns_resolve_timeout|websocket_proxy_tunnel_failure|upstream_connect_timeout|upstream_connect_dns_error|upstream_tls_handshake_error|runtime_log_gap|runtime_proxy_async_log_dropped|upstream_read_error|upstream_send_error|upstream_stream_error|upstream_close_before_completed|upstream_connection_closed|stream_read_error|local_writer_error|invalid_previous_response_id|session_error|local_connection_closed|profile_probe_refresh_error|smart_context_token_calibration_save_error|", event): return "error"
    if event.find("compact") >= 0 or event.find("compaction") >= 0: return "compact"
    if event.startswith("super_expose_exec_"): return "tool"
    if event.find("mcp") >= 0 or event.startswith("expose_") or event.startswith("super_expose_"): return "mcp"
    if event.find("sub_agent") >= 0 or event.find("subagent") >= 0: return "agent"
    if event.startswith("local_rewrite_") and event.find("retry") >= 0: return "retry"
    if event.startswith("local_rewrite_") and event.find("error") >= 0: return "error"
    return "event"


def contains_event(candidates: String, event: String) -> Bool:
    return candidates.find("|" + event + "|") >= 0


def operational_summary(record: RuntimeRecord, event: String, source: String) -> String:
    var summary = human_event_name(event)
    var keys = List[String]()
    var labels = List[String]()
    var formats = List[Int]()
    if source == "request" or source == "model" or source == "route" or source == "mcp" or source == "agent" or source == "tool" or source == "event":
        add_standard_details(keys, labels, formats)
    elif source == "quota":
        push_detail(keys, labels, formats, "profile", "profile")
        push_detail(keys, labels, formats, "route", "route")
        push_detail(keys, labels, formats, "quota_band", "band")
        push_detail(keys, labels, formats, "five_hour_remaining", "5h", 1)
        push_detail(keys, labels, formats, "weekly_remaining", "week", 1)
        push_detail(keys, labels, formats, "reason", "reason")
        push_detail(keys, labels, formats, "until", "until")
    elif source == "retry" or source == "backoff":
        for key, label in [("profile", "profile"), ("route", "route"), ("provider", "provider"), ("reason", "reason"), ("class", "class"), ("attempt", "attempt"), ("retry_index", "retry"), ("seconds", "backoff_s"), ("until", "until")]: push_detail(keys, labels, formats, key, label)
    elif source == "health":
        for key, label in [("profile", "profile"), ("route", "route"), ("score", "score"), ("delta", "delta"), ("reason", "reason")]: push_detail(keys, labels, formats, key, label)
    elif source == "upstream":
        for key, label in [("profile", "profile"), ("route", "route"), ("transport", "transport"), ("method", "method")]: push_detail(keys, labels, formats, key, label)
        push_detail(keys, labels, formats, "url", "path", 2)
        for key, label in [("status", "status"), ("elapsed_ms", "latency_ms"), ("reason", "reason")]: push_detail(keys, labels, formats, key, label)
    elif source == "smart":
        for key, label in [("profile", "profile"), ("route", "route"), ("decision", "decision"), ("tier", "tier"), ("rewrite_kind", "rewrite"), ("tokens_before", "tokens_before"), ("tokens_after", "tokens_after"), ("body_bytes_saved", "bytes_saved")]: push_detail(keys, labels, formats, key, label)
        push_detail(keys, labels, formats, "rewrite_ratio_percent", "rewrite", 1)
        for key, label in [("tool_outputs_condensed", "tools_condensed"), ("rehydrated_refs", "rehydrated"), ("pressure_band", "pressure"), ("self_check", "check"), ("reason", "reason")]: push_detail(keys, labels, formats, key, label)
    elif source == "compact":
        for key, label in [("profile", "profile"), ("route", "route"), ("provider", "provider"), ("status", "status"), ("decision", "decision"), ("exit", "exit"), ("reason", "reason"), ("attempts", "attempts"), ("elapsed_ms", "latency_ms")]: push_detail(keys, labels, formats, key, label)
    elif source == "load":
        for key, label in [("route", "route"), ("lane", "lane"), ("profile", "profile"), ("active", "active"), ("limit", "limit"), ("hard_limit", "limit"), ("reason", "reason")]: push_detail(keys, labels, formats, key, label)
    elif source == "terminal" or source == "error":
        for key, label in [("profile", "profile"), ("route", "route"), ("transport", "transport"), ("stage", "stage"), ("event_type", "event"), ("status", "status"), ("class", "class"), ("reason", "reason"), ("outcome", "outcome"), ("exit_code", "exit"), ("exit_status", "exit"), ("dropped", "dropped")]: push_detail(keys, labels, formats, key, label)
    elif source == "stream" or source == "response":
        for key, label in [("profile", "profile"), ("route", "route"), ("transport", "transport")]: push_detail(keys, labels, formats, key, label)
        push_detail(keys, labels, formats, "elapsed_ms", "ttft_ms" if event == "first_local_chunk" else "latency_ms")
        for key, label in [("chunks", "chunks"), ("bytes", "bytes"), ("status", "status"), ("event_type", "event")]: push_detail(keys, labels, formats, key, label)

    for index in range(len(keys)):
        var original = record.field(keys[index])
        if not displayable_detail(original):
            continue
        if formats[index] == 0 and (not original or original == "-"):
            continue
        var prepared: String
        if formats[index] == 2:
            prepared = safe_endpoint(original)
        else:
            prepared = redact_field(keys[index], original)
        if not prepared or has_control(original):
            continue
        if summary == human_event_name(event):
            summary += "  "
        else:
            summary += " · "
        summary += labels[index] + "=" + scalar_clip(prepared, 32 if formats[index] == 1 else 192)
        if formats[index] == 1:
            summary += "%"
    return summary^


def add_standard_details(mut keys: List[String], mut labels: List[String], mut formats: List[Int]):
    for key, label in [("profile", "profile"), ("route", "route"), ("provider", "provider"), ("model", "model"), ("from_model", "from"), ("to_model", "to"), ("effort", "effort"), ("transport", "transport"), ("method", "method"), ("command", "command"), ("cwd", "cwd"), ("arg_count", "args"), ("env_count", "env"), ("stdin_bytes", "stdin_bytes"), ("timeout_ms", "timeout_ms")]: push_detail(keys, labels, formats, key, label)
    push_detail(keys, labels, formats, "path", "path", 2)
    push_detail(keys, labels, formats, "url", "path", 2)
    for key, label in [("tool_surface", "tools"), ("continuation", "continuation"), ("status", "status"), ("class", "class"), ("event_type", "event"), ("state", "state"), ("code", "code"), ("reason", "reason"), ("elapsed_ms", "latency_ms"), ("duration_ms", "duration_ms"), ("exit_code", "exit"), ("exit_status", "exit"), ("outcome", "outcome"), ("active", "active"), ("limit", "limit"), ("count", "count"), ("dropped", "dropped")]: push_detail(keys, labels, formats, key, label)


def push_detail(mut keys: List[String], mut labels: List[String], mut formats: List[Int], key: String, label: String, format: Int = 0):
    keys.append(key)
    labels.append(label)
    formats.append(format)


def displayable_detail(value: String) -> Bool:
    return value.byte_length() > 0 and value.byte_length() <= 67_108_864 and not has_control(value)


def has_control(value: String) -> Bool:
    for character in value.codepoints():
        var code = Int(character)
        if code < 32 or (0x7F <= code <= 0x9F): return True
    return False


def redact_field(key: String, value: String) -> String:
    if key == "tokens_before" or key == "tokens_after":
        return redact_log_text(value)
    var combined = redact_log_text(key + "=" + value)
    return String(combined[byte=key.byte_length() + 1:])


def safe_endpoint(value: String) -> String:
    if value.startswith("/"):
        var end = value.find("?")
        var fragment = value.find("#")
        if end < 0 or (fragment >= 0 and fragment < end): end = fragment
        return String(value[byte=:end]) if end >= 0 else value
    var colon = value.find(":")
    if colon <= 0 or not valid_scheme(value, colon):
        return "upstream"
    var scheme = String(value[byte=:colon]).lower()
    var rest = String(value[byte=colon + 1:])
    if scheme == "file":
        rest = rest.replace("\\", "/")
    var path: String
    if scheme == "http" or scheme == "https" or scheme == "ftp" or scheme == "ws" or scheme == "wss":
        var special = rest.replace("\\", "/")
        var start = 0
        while start < special.byte_length() and special.as_bytes()[start] == 47:
            start += 1
        var input = String(special[byte=start:])
        if not input or input.startswith("?") or input.startswith("#"):
            return "upstream"
        var authority_end = input.byte_length()
        for delimiter in ["/", "?", "#"]:
            var found = input.find(delimiter)
            if found >= 0 and found < authority_end:
                authority_end = found
        var authority = String(input[byte=:authority_end])
        if not valid_url_authority(authority):
            return "upstream"
        path = String(input[byte=authority_end:]) if authority_end < input.byte_length() and input.as_bytes()[authority_end] == 47 else "/"
    elif rest.startswith("//"):
        if scheme == "file":
            var authority = String(rest[byte=2:])
            var authority_end = authority.byte_length()
            for delimiter in ["/", "?", "#"]:
                var found = authority.find(delimiter)
                if found >= 0 and found < authority_end:
                    authority_end = found
            if authority_end == authority.byte_length():
                if not valid_file_authority(authority):
                    return "upstream"
                return "/" if authority else "upstream"
            if authority_end > 0 and not valid_file_authority(String(authority[byte=:authority_end])):
                return "upstream"
            path = String(authority[byte=authority_end:]) if authority.as_bytes()[authority_end] == 47 else "/"
        else:
            var authority = String(rest[byte=2:])
            var authority_end = authority.find("/")
            var query = authority.find("?")
            var fragment = authority.find("#")
            if (query >= 0 and (authority_end < 0 or query < authority_end)) or (fragment >= 0 and (authority_end < 0 or fragment < authority_end)):
                return "upstream"
            if authority_end < 0:
                return "upstream"
            if authority_end == 0:
                return "upstream"
            path = String(authority[byte=authority_end:])
    else:
        path = rest
        if scheme == "file" and not path.startswith("/"):
            path = "/" + path
    var end = path.find("?")
    var fragment_end = path.find("#")
    if end < 0 or (fragment_end >= 0 and fragment_end < end): end = fragment_end
    if end >= 0:
        var clipped_path = String(path[byte=:end])
        path = clipped_path^
    if not path:
        path = "/" if scheme == "http" or scheme == "https" or rest.startswith("//") else "upstream"
    if not path.startswith("/") and (scheme == "http" or scheme == "https" or rest.startswith("//")):
        path = "/" + path
    return encode_url_path(normalize_url_path(path))


def valid_url_authority(authority: String) -> Bool:
    var at = -1
    for index in range(authority.byte_length()):
        if authority.as_bytes()[index] == 64:
            at = index
        var byte = Int(authority.as_bytes()[index])
        if byte <= 32 or byte == 127:
            return False
    var host_start = at + 1
    if host_start >= authority.byte_length():
        return False
    var host_port = String(authority[byte=host_start:])
    var port_start = -1
    if host_port.startswith("["):
        var close = host_port.find("]")
        if close <= 1:
            return False
        if not valid_ipv6_literal(String(host_port[byte=1:close])):
            return False
        if close + 1 < host_port.byte_length():
            if host_port.as_bytes()[close + 1] != 58:
                return False
            port_start = close + 2
    else:
        var separator = host_port.find(":")
        if separator >= 0:
            if host_port.find(":", separator + 1) >= 0:
                return False
            if separator == 0:
                return False
            port_start = separator + 1
    if not host_port.startswith("["):
        var host_end = port_start - 1 if port_start >= 0 else host_port.byte_length()
        var host = String(host_port[byte=:host_end])
        if host_ends_in_number(host) and not valid_ipv4_host(host):
            return False
    if port_start < 0:
        return True
    if port_start >= host_port.byte_length():
        return True
    var port = 0
    for index in range(port_start, host_port.byte_length()):
        var byte = Int(host_port.as_bytes()[index])
        if byte < 48 or byte > 57:
            return False
        port = port * 10 + byte - 48
        if port > 65535:
            return False
    return True


def valid_file_authority(authority: String) -> Bool:
    if not authority:
        return True
    if not valid_url_authority(authority):
        return False
    if authority.startswith("["):
        var close = authority.find("]")
        return close + 1 == authority.byte_length() or (close + 2 == authority.byte_length() and authority.as_bytes()[close + 1] == 58)
    var separator = authority.find(":")
    return separator < 0 or separator == authority.byte_length() - 1


def host_ends_in_number(host: String) -> Bool:
    var parts = host.split(".")
    if len(parts) and not parts[len(parts) - 1]:
        _ = parts.pop()
    if not len(parts):
        return False
    var last = String(parts[len(parts) - 1])
    var decimal = last.byte_length() > 0
    for byte in last.as_bytes():
        if byte < 48 or byte > 57:
            decimal = False
            break
    return decimal or is_ipv4_number(last)


def is_ipv4_number(part: String) -> Bool:
    if not part:
        return False
    var base = 10
    var start = 0
    if part.byte_length() >= 2 and part.as_bytes()[0] == 48 and (part.as_bytes()[1] == 120 or part.as_bytes()[1] == 88):
        base = 16
        start = 2
    elif part.byte_length() >= 2 and part.as_bytes()[0] == 48:
        base = 8
        start = 1
    for index in range(start, part.byte_length()):
        var byte = Int(part.as_bytes()[index])
        var digit = byte - 48 if 48 <= byte <= 57 else (byte - 65 + 10 if 65 <= byte <= 70 else (byte - 97 + 10 if 97 <= byte <= 102 else 99))
        if digit >= base:
            return False
    return True


def parse_ipv4_number(part: String) -> UInt64:
    if not part:
        return UInt64.MAX
    var base = UInt64(10)
    var start = 0
    if part.byte_length() >= 2 and part.as_bytes()[0] == 48 and (part.as_bytes()[1] == 120 or part.as_bytes()[1] == 88):
        base = 16
        start = 2
    elif part.byte_length() >= 2 and part.as_bytes()[0] == 48:
        base = 8
        start = 1
    var value = UInt64(0)
    for index in range(start, part.byte_length()):
        var byte = Int(part.as_bytes()[index])
        var digit = byte - 48 if 48 <= byte <= 57 else (byte - 65 + 10 if 65 <= byte <= 70 else (byte - 97 + 10 if 97 <= byte <= 102 else 99))
        if UInt64(digit) >= base or value > (UInt64(4294967295) - UInt64(digit)) // base:
            return UInt64.MAX
        value = value * base + UInt64(digit)
    return value


def valid_ipv4_host(host: String) -> Bool:
    var parts = host.split(".")
    if len(parts) and not parts[len(parts) - 1] and len(parts) > 1:
        _ = parts.pop()
    if not len(parts) or len(parts) > 4:
        return False
    var last = UInt64(0)
    for index in range(len(parts)):
        var value = parse_ipv4_number(String(parts[index]))
        if value == UInt64.MAX or (index < len(parts) - 1 and value > 255):
            return False
        last = value
    var last_limit = UInt64(1)
    for _ in range(5 - len(parts)):
        last_limit *= 256
    return last < last_limit


def valid_ipv4_tail(host: String) -> Bool:
    var parts = host.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part or part.byte_length() > 3 or (part.byte_length() > 1 and part.as_bytes()[0] == 48):
            return False
        var value = UInt64(0)
        for byte in part.as_bytes():
            if byte < 48 or byte > 57:
                return False
            value = value * 10 + UInt64(byte - 48)
        if value > 255:
            return False
    return True


def valid_ipv6_piece(part: String) -> Bool:
    if not part or part.byte_length() > 4:
        return False
    for byte in part.as_bytes():
        var value = Int(byte)
        if not ((48 <= value <= 57) or (65 <= value <= 70) or (97 <= value <= 102)):
            return False
    return True


def valid_ipv6_literal(host: String) -> Bool:
    var compressed_at = host.find("::")
    var compressed = compressed_at >= 0
    if compressed and String(host[byte=compressed_at + 2:]).find("::") >= 0:
        return False
    var ipv4 = host.find(".") >= 0
    if ipv4 and host.endswith(":"):
        return False
    var left = String(host[byte=:compressed_at]) if compressed else host
    var right = String(host[byte=compressed_at + 2:]) if compressed else String()
    var parts = List[String]()
    if left:
        for part in left.split(":"):
            if not part:
                return False
            parts.append(String(part))
    if compressed and right:
        for part in right.split(":"):
            if not part:
                return False
            parts.append(String(part))
    if ipv4:
        if not len(parts) or not valid_ipv4_tail(String(parts[len(parts) - 1])):
            return False
        _ = parts.pop()
        if len(parts) > 6:
            return False
    for part in parts:
        if not valid_ipv6_piece(String(part)):
            return False
    var groups = len(parts) + (2 if ipv4 else 0)
    return groups < 8 if compressed else groups == 8


def valid_scheme(value: String, colon: Int) -> Bool:
    var first = Int(value.as_bytes()[0])
    if not ((65 <= first <= 90) or (97 <= first <= 122)):
        return False
    for index in range(1, colon):
        var byte = Int(value.as_bytes()[index])
        if not ((65 <= byte <= 90) or (97 <= byte <= 122) or (48 <= byte <= 57) or byte == 43 or byte == 45 or byte == 46):
            return False
    return True


def normalize_url_path(path: String) -> String:
    var absolute = path.startswith("/")
    var trailing = path.endswith("/") or path.endswith("/.") or path.endswith("/..")
    var parts = path.split("/")
    var kept = List[String]()
    for index in range(len(parts)):
        var part = parts[index]
        if is_single_dot_segment(String(part)):
            if index == len(parts) - 1: kept.append(String())
        elif is_double_dot_segment(String(part)):
            if len(kept) and (not absolute or len(kept) > 1):
                _ = kept.pop()
            if index == len(parts) - 1: kept.append(String())
        else:
            kept.append(String(part))
    var normalized = String()
    for index in range(len(kept)):
        if index: normalized += "/"
        normalized += kept[index]
    if absolute and not normalized.startswith("/"):
        normalized = "/" + normalized
    if trailing and not normalized.endswith("/"):
        normalized += "/"
    return normalized if normalized else ("/" if absolute else String())


def is_single_dot_segment(part: String) -> Bool:
    var lower = part.lower()
    return lower == "." or lower == "%2e"


def is_double_dot_segment(part: String) -> Bool:
    var lower = part.lower()
    return lower == ".." or lower == ".%2e" or lower == "%2e." or lower == "%2e%2e"


def encode_url_path(path: String) -> String:
    var output = String()
    var bytes = path.as_bytes()
    for index in range(len(bytes)):
        var byte = Int(bytes[index])
        if safe_path_byte(byte):
            output += chr(byte)
        else:
            output += "%" + hex_byte(byte)
    return output^


def safe_path_byte(byte: Int) -> Bool:
    return (65 <= byte <= 90) or (97 <= byte <= 122) or (48 <= byte <= 57) or byte == 45 or byte == 46 or byte == 95 or byte == 126 or byte == 33 or byte == 36 or byte == 38 or byte == 39 or byte == 40 or byte == 41 or byte == 42 or byte == 43 or byte == 44 or byte == 59 or byte == 61 or byte == 58 or byte == 64 or byte == 47 or byte == 37 or byte == 91 or byte == 93


def hex_byte(byte: Int) -> String:
    var high = (byte >> 4) & 15
    var low = byte & 15
    return hex_digit(high) + hex_digit(low)


def hex_digit(value: Int) -> String:
    return chr(48 + value) if value < 10 else chr(55 + value)


def scalar_clip(value: String, limit: Int) -> String:
    var out = String()
    var count = 0
    for character in value.codepoints():
        if count == limit: return out + "…"
        out += chr(Int(character))
        count += 1
    return out^


def short_request_id(value: String) -> String:
    var number = UInt64(0)
    if not value: return "-"
    var bytes = value.as_bytes()
    var start = 1 if bytes[0] == 43 else 0
    if start == len(bytes): return "-"
    for index in range(start, len(bytes)):
        var byte = bytes[index]
        if byte < 48 or byte > 57: return "-"
        var digit = UInt64(byte - 48)
        if number > (UInt64.MAX - digit) // 10: return "-"
        number = number * 10 + digit
    var hex = String()
    for shift in [12, 8, 4, 0]:
        var digit = Int((number & 0xffff) >> UInt64(shift)) & 15
        hex += chr(48 + digit) if digit < 10 else chr(87 + digit)
    return "r" + hex


def human_event_name(event: String) -> String:
    if event == "request_captured": return "received request"
    if event == "route_decision": return "route decided"
    if event == "selection_plan": return "route planned"
    if event == "selection_pick": return "profile picked"
    if event == "selection_keep_affinity": return "owner kept"
    if event == "selection_keep_current": return "current profile kept"
    if event == "selection_skip_current": return "profile skipped"
    if event == "selection_skip_affinity": return "affinity skipped"
    if event == "selection_skip_sync_probe": return "quota probe skipped"
    if event == "local_selection_blocked": return "route blocked"
    if event == "profile_commit": return "profile committed"
    if event == "route_affinity_recompute": return "affinity recomputed"
    if event == "route_affinity_recompute_result": return "affinity resolved"
    if event == "previous_response_owner": return "continuation owner"
    if event == "previous_response_not_found": return "continuation missing"
    if event == "previous_response_negative_cache": return "continuation cached missing"
    if event == "previous_response_fresh_fallback": return "fresh fallback"
    if event == "previous_response_fresh_fallback_blocked": return "fallback blocked"
    if event == "previous_response_turn_state_rehydrated": return "turn state restored"
    if event == "session_rotation_release_affinity": return "session affinity released"
    if event == "binding_prompt_cache": return "prompt cache bound"
    if event == "upgrade" or event == "upgraded": return "request upgraded"
    if event == "profile_quota_exhausted" or event == "quota_exhausted": return "quota exhausted"
    if event == "quota_blocked": return "quota blocked"
    if event == "quota_critical_floor_before_send": return "quota floor blocked"
    if event == "profile_quota_quarantine": return "quota quarantine"
    if event == "profile_probe_refresh_start": return "quota refresh started"
    if event == "profile_probe_refresh_ok": return "quota refreshed"
    if event == "upstream_usage_limit_passthrough": return "upstream limit passed through"
    if event == "upstream_overload_passthrough": return "upstream overload passed through"
    if event == "profile_retry_backoff": return "retry backoff"
    if event == "compact_retryable_failure": return "compaction retry"
    if event == "compact_overload_conservative_retry": return "compaction retry (overload)"
    if event == "profile_transport_backoff": return "transport backoff"
    if event == "rotation_waiting_for_recovery": return "waiting for recovery"
    if event == "profile_circuit_open": return "circuit open"
    if event == "profile_circuit_half_open_probe": return "circuit probe"
    if event == "profile_transport_failure": return "transport failed"
    if event == "profile_health": return "health penalty"
    if event == "profile_bad_pairing": return "affinity penalty"
    if event == "upstream_start" or event == "upstream_async_start": return "upstream request"
    if event == "upstream_response" or event == "upstream_async_response": return "upstream response"
    if event == "upstream_connect_start": return "upstream connecting"
    if event == "upstream_connect_ok": return "upstream connected"
    if event == "upstream_connect_error": return "upstream connect failed"
    if event == "first_upstream_chunk": return "first upstream chunk"
    if event == "first_local_chunk": return "first local chunk"
    if event == "stream_complete": return "stream complete"
    if event == "buffered_response_complete": return "response complete"
    if event == "terminal_event": return "terminal event"
    if event == "runtime_proxy_queue_overloaded": return "proxy queue full"
    if event == "runtime_proxy_active_limit_reached": return "proxy busy"
    if event == "runtime_proxy_lane_limit_reached": return "lane full"
    if event == "profile_inflight_saturated": return "profile busy"
    if event == "smart_context_autopilot": return "Smart Context"
    if event == "smart_context_prepare_error": return "Smart Context failed"
    if event == "smart_context_prepare_fallback": return "Smart Context fallback"
    if event == "smart_context_disabled": return "Smart Context disabled"
    if event == "local_rewrite_request_detail": return "provider request"
    if event == "local_rewrite_provider_model_fallback": return "model fallback"
    if event == "local_rewrite_provider_auth_failure": return "provider auth failed"
    if event == "upstream_read_error": return "upstream read failed"
    if event == "upstream_send_error": return "upstream send failed"
    if event == "upstream_stream_error": return "upstream stream failed"
    if event == "upstream_close_before_completed": return "upstream closed early"
    if event == "upstream_connection_closed": return "upstream disconnected"
    if event == "stream_read_error": return "stream read failed"
    if event == "local_writer_error": return "terminal write failed"
    if event == "invalid_previous_response_id": return "continuation invalid"
    if event == "session_error": return "session failed"
    if event == "local_connection_closed": return "local connection closed"
    if event == "profile_probe_refresh_error": return "quota refresh failed"
    if event == "smart_context_token_calibration_save_error": return "Smart Context calibration failed"
    if event.find("compact") >= 0 or event.find("compaction") >= 0: return "compaction"
    if event.find("mcp") >= 0 or event.startswith("expose_"): return "MCP"
    if event.find("sub_agent") >= 0 or event.find("subagent") >= 0: return "sub-agent"
    return event.replace("_", " ")
