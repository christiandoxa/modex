"""Frozen-oracle coverage for the detached runtime operational projection."""

import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

import test_cli
from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess, runtime_record


EVENTS = (
    "route_decision selection_plan selection_pick selection_keep_affinity "
    "selection_keep_current selection_skip_current selection_skip_affinity "
    "selection_skip_sync_probe local_selection_blocked route_affinity_recompute "
    "route_affinity_recompute_result profile_commit previous_response_owner "
    "previous_response_not_found previous_response_negative_cache "
    "previous_response_fresh_fallback previous_response_fresh_fallback_blocked "
    "previous_response_turn_state_rehydrated session_rotation_release_affinity "
    "binding_prompt_cache upgrade upgraded profile_quota_exhausted quota_exhausted "
    "quota_blocked quota_critical_floor_before_send profile_quota_quarantine "
    "profile_probe_refresh_start profile_probe_refresh_ok "
    "compact_pre_send_allow_quota_exhausted upstream_usage_limit_passthrough "
    "upstream_overload_passthrough profile_retry_backoff compact_retryable_failure "
    "compact_overload_conservative_retry local_rewrite_gemini_quota_rotate "
    "local_rewrite_gemini_rate_limit_retry local_rewrite_gemini_invalid_stream_retry "
    "websocket_reuse_owner_fresh_retry websocket_reuse_nonreplayable_fresh_retry "
    "websocket_reuse_locked_affinity_owner_fresh_retry profile_transport_backoff "
    "rotation_waiting_for_recovery profile_circuit_open profile_circuit_half_open_probe "
    "websocket_reuse_watchdog_timeout profile_auth_backoff profile_transport_failure "
    "profile_health profile_bad_pairing profile_auth_recovery_failed "
    "profile_auth_background_refresh_failed profile_auth_recovered upstream_start "
    "upstream_response upstream_async_start upstream_async_response upstream_connect_start "
    "upstream_connect_ok upstream_connect_error first_upstream_chunk first_local_chunk "
    "stream_complete committed buffered_response_complete terminal_event "
    "local_rewrite_gemini_builtin_tool_fallback runtime_proxy_queue_overloaded "
    "runtime_proxy_active_limit_reached runtime_proxy_lane_limit_reached "
    "runtime_proxy_overload_backoff runtime_proxy_admission_wait_exhausted "
    "runtime_proxy_queue_wait_exhausted profile_inflight_saturated "
    "websocket_dns_overflow_reject websocket_connect_overflow_reject "
    "websocket_connect_overflow_rejected smart_context_autopilot "
    "smart_context_prepare_error smart_context_disabled local_rewrite_request_detail "
    "local_rewrite_provider_model_fallback local_rewrite_provider_auth_failure "
    "websocket_precommit_frame_timeout websocket_precommit_hold_timeout "
    "websocket_dns_resolve_timeout websocket_proxy_tunnel_failure upstream_connect_timeout "
    "upstream_connect_dns_error upstream_tls_handshake_error runtime_log_gap "
    "runtime_proxy_async_log_dropped upstream_read_error upstream_send_error "
    "upstream_stream_error upstream_close_before_completed upstream_connection_closed "
    "stream_read_error local_writer_error invalid_previous_response_id session_error "
    "local_connection_closed profile_probe_refresh_error "
    "smart_context_token_calibration_save_error"
).split()


BASE_FIELDS = {
    "request": "17", "profile": "fixture", "route": "responses", "provider": "openai",
    "model": "fixture-model", "from_model": "old-model", "to_model": "new-model",
    "effort": "high", "transport": "http", "method": "POST", "command": "codex exec",
    "cwd": "/synthetic/workspace", "arg_count": "3", "env_count": "2",
    "stdin_bytes": "5", "timeout_ms": "1000", "path": "/responses?secret=path-query",
    "url": "https://example.test/responses?secret=url-query", "tool_surface": "mcp,functions",
    "continuation": "previous", "status": "200", "class": "fixture-class",
    "event_type": "fixture-event", "state": "ready", "code": "fixture-code",
    "reason": "busy-marker", "elapsed_ms": "12", "duration_ms": "13",
    "exit_code": "0", "exit_status": "success", "outcome": "ok", "active": "2",
    "limit": "8", "count": "4", "dropped": "1", "quota_band": "low",
    "five_hour_remaining": "12.5", "weekly_remaining": "34.5", "until": "2030-01-01",
    "attempt": "1", "retry_index": "2", "seconds": "3", "score": "4",
    "delta": "-1", "chunks": "3", "bytes": "1024", "decision": "rewrite",
    "tier": "balanced", "rewrite_kind": "summary", "tokens_before": "100",
    "tokens_after": "50", "body_bytes_saved": "200", "rewrite_ratio_percent": "50",
    "tool_outputs_condensed": "2", "rehydrated_refs": "1", "pressure_band": "normal",
    "self_check": "pass", "exit": "ok", "attempts": "2", "lane": "responses",
    "hard_limit": "16", "stage": "send",
}


def record(event, fields, sequence):
    return runtime_record(event, fields, f"2026-10-24T01:02:{sequence % 60:02d}Z")


def operational_corpus():
    lines = []
    sequence = 0
    for name in EVENTS:
        fields = dict(BASE_FIELDS)
        if name == "profile_commit":
            fields["switched"] = "true"
        elif name == "compat_request_surface":
            fields["tool_surface"] = "mcp,functions"
        elif name == "smart_context_prepare_fallback":
            fields["decision"] = "rewrite"
        lines.append(record(name, fields, sequence))
        sequence += 1

    for name, fields in [
        ("stream_payload", {"source": "fixture", "stream": "ignored-stream"}),
        ("upstream_payload", {"payload_b64": "aWdub3JlZC11cHN0cmVhbQ=="}),
        ("token_usage", {"input_tokens": "1", "output_tokens": "1"}),
        ("token_usage_progress", {"output_tokens": "1"}),
        ("profile_commit", {"switched": "false"}),
        ("profile_commit", {"switched": "TRUE"}),
        ("compat_request_surface", {"tool_surface": "none", "continuation": "none", "family": "codex"}),
        ("compat_request_surface", {"tool_surface": "sub_agent"}),
        ("compat_request_surface", {"tool_surface": "functions", "family": "codex"}),
        ("smart_context_prepare_fallback", {"decision": "pass_through"}),
        ("smart_context_prepare_fallback", {}),
        ("custom_compaction_trace", {"reason": "dynamic-compact"}),
        ("expose_tool_result", {"reason": "dynamic-mcp"}),
        ("custom_subagent_trace", {"reason": "dynamic-agent"}),
        ("local_rewrite_fixture_retry", {"reason": "dynamic-retry"}),
        ("local_rewrite_fixture_error", {"reason": "dynamic-error"}),
        ("new_fixture_event", {"reason": "dynamic-event"}),
        ("_custom__event_", {}),
        ("request_captured", {"request": "0"}),
        ("request_captured", {"request": "65535"}),
        ("request_captured", {"request": "65536"}),
        ("request_captured", {"request": "18446744073709551615"}),
        ("request_captured", {"request": "18446744073709551616"}),
        ("request_captured", {"request": "+17"}),
        ("request_captured", {"request": "017"}),
        ("request_captured", {"request": "-1"}),
        ("request_captured", {"command": "Authorization: Bearer synthetic-secret"}),
        ("upstream_start", {"url": "https://example.test"}),
        ("upstream_start", {"url": "https://example.test/a/../responses?secret=x#fragment"}),
        ("upstream_start", {"url": "https://example.test/%E2%98%83"}),
        ("upstream_start", {"url": "https://example.test/雪"}),
        ("upstream_start", {"url": "mailto:user@example.test"}),
        ("upstream_start", {"url": "https://example.test?return=/wrong-path"}),
        ("upstream_start", {"url": "https://user:pass@example.test/private?token=x"}),
        ("upstream_start", {"url": "ftp://example.test/resource"}),
        ("upstream_start", {"url": "https://example.test/a b"}),
        ("upstream_start", {"url": "https://"}),
        ("upstream_start", {"url": "https://example.test/a%2Fb"}),
        ("upstream_start", {"url": "https://example.test/a/%2e%2e/encoded-dot"}),
        ("upstream_start", {"url": "https://example.test/a/./b//c"}),
        ("upstream_start", {"url": "https://example.test/x%7e"}),
        ("upstream_start", {"url": "mailto:user@example.test?subject=x"}),
        ("upstream_start", {"url": "https://example.test/ASCII~!$&'()*+,;=:@[]%25"}),
        ("upstream_start", {"url": "https:///path?query=x"}),
        ("upstream_start", {"url": "http://:80/path"}),
        ("upstream_start", {"url": "https://example.test:bad/path"}),
        ("upstream_start", {"url": "https://exa mple.test/path"}),
        ("upstream_start", {"url": "https://?query=/path"}),
        ("upstream_start", {"url": "https:\\\\example.test\\path?query=x"}),
        ("upstream_start", {"url": "https:/example.test/path"}),
        ("upstream_start", {"url": "not a url"}),
        ("request_captured", {"path": "/responses?query-secret#fragment", "model": "é" * 191 + "e\u0301"}),
        ("request_captured", {"profile": "hidden\tcontrol", "provider": "line\ncontrol", "reason": "control\u0085"}),
        ("quota_blocked", {"quota_band": "-", "five_hour_remaining": "-", "weekly_remaining": "", "reason": " "}),
        ("quota_blocked", {"weekly_remaining": "7" * 33}),
        ("upstream_start", {"url": "https://example.test/" + "a" * 193}),
    ]:
        lines.append(record(name, fields, sequence))
        sequence += 1

    # Duplicate names exercise the upstream parser's last-value and type filtering.
    raw = (f'{{"timestamp":"2026-10-24T01:03:01Z","event":"request_captured",'
           f'"fields":{{"profile":"first","profile":"last",'
           f'"model":"visible","model":{{"nested":true}},'
           f'"request":"17","request":{{"nested":true}}}}}}\n').encode()
    lines.append(raw)
    for sequence, request in enumerate(("-0", "1e0", "1.0", "18446744073709551615", "18446744073709551616", "1e400"), 3):
        lines.append((f'{{"timestamp":"2026-10-24T01:03:{sequence:02d}Z","event":"request_captured",'
                      f'"fields":{{"request":{request}}}}}\n').encode())
    lines.append(b'{"timestamp":"2026-10-24T01:03:12Z","event":"upstream_response","fields":{"status":1e2,"elapsed_ms":1.00}}\n')
    lines.append(b'{"timestamp":"2026-10-24T01:03:13Z","event":"quota_blocked","fields":{"five_hour_remaining":1e2,"weekly_remaining":-0.0}}\n')
    lines.append(b'{"timestamp":"2026-10-24T01:03:14Z","event":"smart_context_autopilot","fields":{"rewrite_ratio_percent":5e1}}\n')
    numeric_values = ("1e-7", "1e-6", "1e-5", "1e15", "1e16",
                      "9007199254740992", "9007199254740993", "-1e-7", "-1e-6",
                      "-1e-5", "-1e15", "-1e16", "-9007199254740992",
                      "-9007199254740993", "-0", "-0.0")
    for sequence, numeric in enumerate(numeric_values, 15):
        lines.append((f'{{"timestamp":"2026-10-24T01:03:{sequence:02d}Z","event":"upstream_response",'
                      f'"fields":{{"profile":{numeric},"status":{numeric},"elapsed_ms":{numeric}}}}}\n').encode())
        sequence += 1
        lines.append((f'{{"timestamp":"2026-10-24T01:03:{sequence:02d}Z","event":"quota_blocked",'
                      f'"fields":{{"five_hour_remaining":{numeric},"weekly_remaining":{numeric}}}}}\n').encode())
    rng = random.Random(0x4D4F444558)
    float_values = []
    for exponent in range(-324, 309, 4):
        for sign in (0, 1):
            fraction = rng.getrandbits(52)
            exponent_bits = min(2046, max(0, exponent + 1023))
            bits = (sign << 63) | (exponent_bits << 52) | fraction
            value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
            if value == value and abs(value) != float("inf"):
                float_values.append(value)
    for _ in range(64):
        bits = rng.getrandbits(64)
        value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        if value == value and abs(value) != float("inf"):
            float_values.append(value)
    for index, value in enumerate(float_values):
        numeric = repr(value).lower()
        lines.append((f'{{"timestamp":"2026-10-24T01:04:{index % 60:02d}Z","event":"upstream_response",'
                      f'"fields":{{"status":{numeric},"reason":"float-case-{index}"}}}}\n').encode())
    lines.append(b"bare_request_captured request=17 profile=must-not-project\n")
    lines.append(b"[2026-10-24T01:03:02Z] request_captured request=17 profile=plain-envelope\n")
    end_marker = "operational-corpus-end-marker"
    lines.append(record("operational_corpus_end", {"reason": end_marker}, sequence))
    return b"".join(lines), end_marker


def trace_with_corpus(binary, mode):
    corpus, end_marker = operational_corpus()
    with tempfile.TemporaryDirectory(prefix="modex-operational-compare-") as directory:
        root = Path(directory)
        follower = StreamProcess(binary, mode, root, b"", b"invalid startup line\n")
        try:
            follower.require_marker("Waiting for transcript, upstream payload, or token events.")
            follower.require_quiet(2.2)
            with follower.log.open("ab") as stream:
                stream.write(corpus)
            follower.require_marker(end_marker, timeout=8)
            follower.require_quiet(0.25)
            return follower.stop()
        finally:
            follower.stop()


class OperationalLogProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_full_operational_catalog_and_boundary_corpus_matches_frozen_stream(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                expected = trace_with_corpus(ORACLE, mode)
                actual = trace_with_corpus(MODEX, mode)
                if actual != expected:
                    mismatch_dir = Path(__file__).resolve().parents[1] / "test-results/log-operational/mismatches"
                    mismatch_dir.mkdir(parents=True, exist_ok=True)
                    corpus, _ = operational_corpus()
                    (mismatch_dir / f"{mode}-input.jsonl").write_bytes(corpus)
                    (mismatch_dir / f"{mode}-oracle.stdout").write_bytes(expected["stdout"])
                    (mismatch_dir / f"{mode}-oracle.stderr").write_bytes(expected["stderr"])
                    (mismatch_dir / f"{mode}-modex.stdout").write_bytes(actual["stdout"])
                    (mismatch_dir / f"{mode}-modex.stderr").write_bytes(actual["stderr"])
                self.assertEqual(actual, expected)
                self.assertNotIn(b"synthetic-secret", actual["stdout"])


if __name__ == "__main__":
    unittest.main()
