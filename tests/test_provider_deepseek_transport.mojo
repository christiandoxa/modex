from std.collections import List
from std.sys import argv
from std.testing import assert_equal, assert_true

from modex.json import JsonDocument, serialize_json
from modex.provider_deepseek_transport import DeepSeekExchange, deepseek_event_stream, deepseek_request_headers
from modex.provider_rate_limits import _reset_epoch, deepseek_codex_rate_limit_headers


def values(headers: List[Tuple[String, String]], name: String) -> List[String]:
    var output = List[String]()
    for key, value in headers:
        if key.lower() == name:
            output.append(value)
    return output^


def check(headers: List[Tuple[String, String]], name: String, expected: List[String]) raises:
    assert_equal(values(headers, name), expected)


def rate_limits() raises:
    var headers: List[Tuple[String, String]] = [
        ("X-RateLimit-Limit-Requests", "1e2"),
        ("x-ratelimit-remaining-requests", "+4e1"),
        ("x-ratelimit-reset-requests", "1700000000000"),
        ("x-ratelimit-limit-tokens", "200"),
        ("x-ratelimit-remaining-tokens", "150"),
        ("x-ratelimit-reset-tokens", "1970-01-01T00:00:00Z"),
        ("x-ratelimit-limit-model", "100"),
        ("x-ratelimit-remaining-model", "50"),
    ]
    var projected = deepseek_codex_rate_limit_headers(headers)
    check(projected, "x-deepseek-requests-limit-name", ["DeepSeek requests"])
    check(projected, "x-deepseek-requests-primary-used-percent", ["60"])
    check(projected, "x-deepseek-requests-primary-reset-at", ["1700000000"])
    check(projected, "x-deepseek-tokens-limit-name", ["DeepSeek tokens"])
    check(projected, "x-deepseek-tokens-primary-used-percent", ["25"])
    check(projected, "x-deepseek-tokens-primary-reset-at", ["0"])
    assert_equal(len(projected), 6)

    var rounded: List[Tuple[String, String]] = [
        ("x-ratelimit-limit-requests", "3"),
        ("x-ratelimit-remaining-requests", "1"),
        ("x-ratelimit-reset-requests", "1h30m"),
        ("x-ratelimit-limit-tokens", "0"),
        ("x-ratelimit-remaining-tokens", "0"),
    ]
    projected = deepseek_codex_rate_limit_headers(rounded)
    check(projected, "x-deepseek-requests-primary-used-percent", ["66.7"])
    assert_equal(len(projected), 3)
    assert_equal(len(values(projected, "x-deepseek-requests-primary-reset-at")), 1)

    var invalid: List[Tuple[String, String]] = [
        ("x-ratelimit-limit-requests", "100f"),
        ("x-ratelimit-remaining-requests", "1"),
        ("x-ratelimit-limit-tokens", "1_00"),
        ("x-ratelimit-remaining-tokens", "0"),
    ]
    assert_equal(len(deepseek_codex_rate_limit_headers(invalid)), 0)

    var malformed_date: List[Tuple[String, String]] = [
        ("x-ratelimit-limit-requests", "100"),
        ("x-ratelimit-remaining-requests", "20"),
        ("x-ratelimit-reset-requests", "1970-+1-01T00:00:00Z"),
    ]
    projected = deepseek_codex_rate_limit_headers(malformed_date)
    assert_equal(len(projected), 2)
    assert_equal(len(values(projected, "x-deepseek-requests-primary-reset-at")), 0)

    var overflow = _reset_epoch(String("9") * 400 + "d", 1234)
    assert_true(overflow and overflow.value() == Int.MAX)
    var underflow = _reset_epoch("0." + String("0") * 330 + "1ms", 1234)
    assert_true(underflow and underflow.value() == 1234)
    assert_true(not _reset_epoch("1.2.3s", 1234))
    assert_true(not _reset_epoch("1..2s", 1234))
    assert_true(not _reset_epoch(".s", 1234))
    var many_segments = _reset_epoch(String("0s") * 65537, 1234)
    assert_true(many_segments and many_segments.value() == 1234)


def drop_exchange(address: String) raises:
    var exchange = DeepSeekExchange(address, "/v1/chat/completions", "synthetic-provider-key", '{"input":"synthetic lifecycle","stream":true}', 1, "resp_deepseek_1", 1)
    assert_equal(exchange.status(), 200)


def lifecycle(address: String, mode: String) raises:
    if mode == "drop":
        drop_exchange(address)
        return
    var exchange = DeepSeekExchange(address, "/v1/chat/completions", "synthetic-provider-key", '{"input":"synthetic lifecycle","stream":true}', 1, "resp_deepseek_1", 1)
    if mode == "body":
        assert_true(len(exchange.read_body()) > 0)
        assert_true(exchange.done and not exchange.cancelled)
        var error = String()
        try:
            _ = exchange.read_events()
        except failure:
            error = String(failure)
        assert_equal(error, "DeepSeek response body was already read as bytes")
    elif mode == "events":
        assert_true(len(exchange.read_events()) > 0)
        assert_true(not exchange.done)
        var error = String()
        try:
            _ = exchange.read_body()
        except failure:
            error = String(failure)
        assert_equal(error, "DeepSeek response body was already handed to the event reader")
        assert_true(exchange.done and not exchange.cancelled)
        assert_equal(len(exchange.pending), 0)
        assert_equal(exchange.pending_offset, 0)
    elif mode == "cancel":
        exchange.close()
        exchange.close()
        assert_true(exchange.done and exchange.cancelled)
        assert_equal(len(exchange.read_events()), 0)
        assert_equal(len(exchange.read_body()), 0)
    elif mode == "buffered" or mode == "buffered_events":
        var response = JsonDocument(exchange.read_buffered())
        assert_equal(response.string(response.get(response.root, "id")), "chat-buffered-lifecycle")
        assert_equal(response.nodes[response.get(response.root, "created_at")].text, "7")
        assert_equal(response.get(response.root, "error"), -1)
        var history = JsonDocument('[{"role":"user","content":"synthetic lifecycle"},{"role":"assistant","content":"synthetic buffered","tool_calls":[{"id":"call-lifecycle","function":{"name":"shell","arguments":"{\\"cmd\\":\\"rtk cargo test\\"}"}}]}]')
        assert_equal(exchange.conversation_messages, serialize_json(history, history.root))
        assert_true(exchange.done and not exchange.cancelled)
        if mode == "buffered_events":
            var error = String()
            try:
                _ = exchange.read_events()
            except failure:
                error = String(failure)
            assert_equal(error, "DeepSeek response body was already read as bytes")
    elif mode == "buffered_failed":
        var response = JsonDocument(exchange.read_buffered())
        assert_equal(response.string(response.get(response.root, "status")), "failed")
        var error = response.get(response.root, "error")
        assert_equal(response.string(response.get(error, "code")), "invalid_tool_call_arguments")
        assert_equal(exchange.conversation_messages, "[]")
        assert_true(exchange.done and not exchange.cancelled)
    elif mode == "buffered_blank_id":
        var response = JsonDocument(exchange.read_buffered())
        assert_equal(response.string(response.get(response.root, "id")), "   ")
        assert_equal(exchange.conversation_messages, "[]")
        assert_true(exchange.done and not exchange.cancelled)
    elif mode == "events_buffered":
        assert_true(len(exchange.read_events()) > 0)
        assert_true(not exchange.done)
        var error = String()
        try:
            _ = exchange.read_buffered()
        except failure:
            error = String(failure)
        assert_equal(error, "DeepSeek buffered reader requires a non-event-stream response")
        assert_true(exchange.done and not exchange.cancelled)
        assert_equal(exchange.conversation_messages, "[]")
    else:
        raise Error("unknown lifecycle test mode")
    assert_equal(exchange.http.fd, -1)
    assert_equal(len(exchange.pending), 0)
    assert_equal(exchange.pending_offset, 0)


def main() raises:
    var source: List[Tuple[String, String]] = [
        ("Authorization", "Bearer obsolete-synthetic-key"),
        ("ChatGPT-Account-Id", "synthetic-account"),
        ("Host", "untrusted.invalid"),
        ("Content-Length", "999"),
        ("Transfer-Encoding", "chunked"),
        ("Connection", "keep-alive, X-Private, invalid token, , X-Public"),
        ("x-private", "discard"),
        ("X-Public", "discard"),
        ("X-Prodex-Internal-Origin", "discard"),
        ("sec-WebSocket-Key", "discard"),
        ("x-prodex-internal", "forward"),
        ("sec-websocket", "forward"),
        ("session_id", "session-synthetic"),
        ("x-codex-turn-state", "turn-synthetic"),
        ("User-Agent", "synthetic-agent"),
        ("User-Agent", "synthetic-second"),
        ("Content-Type", "application/custom+json"),
    ]
    var headers = deepseek_request_headers(source, "synthetic-provider-key")
    check(headers, "authorization", ["Bearer synthetic-provider-key"])
    for name in ["chatgpt-account-id", "host", "content-length", "transfer-encoding", "connection", "x-private", "x-public", "x-prodex-internal-origin", "sec-websocket-key"]:
        assert_equal(len(values(headers, name)), 0)
    check(headers, "accept", ["text/event-stream, application/json"])
    check(headers, "accept-encoding", ["identity"])
    check(headers, "content-type", ["application/json", "application/custom+json"])
    check(headers, "user-agent", ["synthetic-agent", "synthetic-agent", "synthetic-second"])
    check(headers, "session_id", ["session-synthetic"])
    check(headers, "x-codex-turn-state", ["turn-synthetic"])
    check(headers, "x-prodex-internal", ["forward"])
    check(headers, "sec-websocket", ["forward"])

    var nominated: List[Tuple[String, String]] = [("Connection", "User-Agent"), ("User-Agent", "synthetic-agent")]
    check(deepseek_request_headers(nominated, "synthetic"), "user-agent", ["synthetic-agent"])
    var rejected = False
    try:
        var oversized: List[Tuple[String, String]] = [(String("x") * 4097, "synthetic")]
        _ = deepseek_request_headers(oversized, "synthetic")
    except error:
        rejected = String(error) == "DeepSeek request header name exceeds limit"
    assert_true(rejected)
    for key in ["", " ", "synthetic key", "synthetic\tkey", "synthetic\u00a0key", "synthetic\u3000key"]:
        var error = String()
        try:
            _ = deepseek_request_headers(source, key)
        except failure:
            error = String(failure)
        assert_equal(error, "--api-key cannot be empty" if not key else "--api-key must not contain whitespace")

    assert_true(deepseek_event_stream([("Content-Type", "Text/Event-Stream; Charset=UTF-8")]))
    assert_true(deepseek_event_stream([("Content-Type", "application/custom; stream=TEXT/EVENT-STREAM")]))
    assert_true(not deepseek_event_stream([("Content-Type", "text/event-stream; marker=é")]))
    assert_true(not deepseek_event_stream([]))
    assert_true(not deepseek_event_stream([("Content-Type", "application/json"), ("Content-Type", "text/event-stream")]))
    assert_true(deepseek_event_stream([("Content-Type", "text/event-stream"), ("Content-Type", "application/json")]))
    rate_limits()
    var args = argv()
    if len(args) == 3:
        lifecycle(args[1], args[2])
    elif len(args) != 1:
        raise Error("usage: test_provider_deepseek_transport [ADDRESS MODE]")
    print("Provider DeepSeek transport header checks: PASS")
