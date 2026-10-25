from std.collections import List
from std.sys import argv
from std.testing import assert_equal, assert_true

from modex.provider_deepseek_transport import DeepSeekExchange, deepseek_event_stream, deepseek_request_headers


def values(headers: List[Tuple[String, String]], name: String) -> List[String]:
    var output = List[String]()
    for key, value in headers:
        if key.lower() == name:
            output.append(value)
    return output^


def check(headers: List[Tuple[String, String]], name: String, expected: List[String]) raises:
    assert_equal(values(headers, name), expected)


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
    else:
        raise Error("unknown lifecycle test mode")
    assert_equal(exchange.http.fd, -1)


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
    var args = argv()
    if len(args) == 3:
        lifecycle(args[1], args[2])
    elif len(args) != 1:
        raise Error("usage: test_provider_deepseek_transport [ADDRESS body|events|cancel|drop]")
    print("Provider DeepSeek transport header checks: PASS")
