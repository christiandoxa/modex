from std.collections import List
from std.testing import assert_equal, assert_true

from modex.runtime_local_rewrite import _continuation_identity_valid, _history, _namespace, _response_headers, local_rewrite_upstream
from modex.gateway_cli import gateway_help, parse_gateway_arguments
from modex.json import JsonDocument, quote_json
from modex.provider_conversations import ProviderConversationStore


def main() raises:
    var args: List[String] = ["modex", "gateway", "--provider", " DeepSeek ", "--url=http://127.0.0.1:10000/v1", "--api-key=synthetic", "--no-presidio"]
    var options = parse_gateway_arguments(args, "modex")
    assert_equal(options.listen, "127.0.0.1:0")
    assert_equal(options.provider, "deepseek")
    assert_equal(options.base_url, "http://127.0.0.1:10000/v1")
    assert_equal(options.api_key.value(), "synthetic")
    assert_true(options.no_presidio and not options.presidio)
    assert_true(gateway_help("modex").find("Usage: modex gateway [OPTIONS]") >= 0)
    assert_true(parse_gateway_arguments(["modex", "gateway", "--help"], "modex").help)
    for invalid in [
        List[String](copy=["modex", "gateway", "--presidio", "--no-presidio"]),
        List[String](copy=["modex", "gateway", "--provider"]),
        List[String](copy=["modex", "gateway", "--listen=a", "--listen=b"]),
        List[String](copy=["modex", "gateway", "--smart-context=true"]),
        List[String](copy=["modex", "gateway", "--unknown"]),
    ]:
        var rejected = False
        try:
            _ = parse_gateway_arguments(invalid, "modex")
        except:
            rejected = True
        assert_true(rejected)
    var smart_context_error = String()
    try:
        _ = parse_gateway_arguments(["modex", "gateway", "--smart-context=true"], "modex")
    except error:
        smart_context_error = String(error)
    assert_equal(smart_context_error, "error: unexpected value 'true' for '--smart-context' found; no more were expected\n\nUsage: modex gateway --smart-context\n\nFor more information, try '--help'.\n")
    var presidio_error = String()
    try:
        _ = parse_gateway_arguments(["modex", "gateway", "--presidio=false"], "modex")
    except error:
        presidio_error = String(error)
    assert_equal(presidio_error, "error: unexpected value 'false' for '--presidio' found; no more were expected\n\nUsage: modex gateway --presidio\n\nFor more information, try '--help'.\n")
    var document = JsonDocument('{"session_id":" body ","client_metadata":{"session_id":"nested"}}')
    assert_equal(_namespace([], document), "body")
    assert_equal(_namespace([("session_id", " header "), ("x-session-id", "ignored")], document), "header")
    assert_equal(_namespace([("session_id", " "), ("x-session-id", "alias")], document), "alias")
    assert_equal(_namespace([("session_id", " "), ("session-id", "\t"), ("x-session-id", " ")], document), "body")
    assert_equal(_namespace([("session_id", " "), ("session_id", "duplicate"), ("x-session-id", "alias")], document), "alias")
    assert_equal(_namespace([("x-codex-turn-metadata", '{"client_metadata":{"session_id":" turn "}}')], document), "turn")
    assert_equal(_namespace([("x-codex-turn-metadata", "invalid"), ("x-codex-turn-metadata", '{"session_id":"ignored"}')], document), "body")
    var blocked_nested = JsonDocument('{"session_id":false,"client_metadata":{"session_id":"ignored"}}')
    assert_equal(_namespace([("x-prodex-internal-conversation-namespace", " raw ")], blocked_nested), " raw ")
    assert_equal(_namespace([], blocked_nested), "gateway")
    for identity in [String("a\0b"), "a\x1fb", "a\x7fb", "a\u0080b", "a\u009fb", String("x") * 1025, String("é") * 513]:
        var invalid_identity = JsonDocument('{"previous_response_id":' + quote_json(identity) + "}")
        assert_equal(_continuation_identity_valid([], invalid_identity), False)
        invalid_identity = JsonDocument('{"client_metadata":{"session_id":' + quote_json(identity) + "}}")
        assert_equal(_continuation_identity_valid([], invalid_identity), False)
        assert_equal(_continuation_identity_valid([("session_id", identity)], document), False)
        assert_equal(_continuation_identity_valid([("x-codex-turn-state", identity)], document), False)
    var boundary = JsonDocument('{"previous_response_id":' + quote_json(String("é") * 512) + "}")
    assert_equal(_continuation_identity_valid([], boundary), True)
    var trimmed_identity = JsonDocument('{"previous_response_id":" \\t valid \\n ","session_id":" \\r\\n "}')
    assert_equal(_continuation_identity_valid([], trimmed_identity), True)
    assert_equal(_continuation_identity_valid([("session_id", "valid"), ("x-session-id", String("x") * 1025)], document), True)
    assert_equal(_continuation_identity_valid([("session_id", " "), ("x-session-id", String("x") * 1025)], document), False)
    assert_equal(_continuation_identity_valid([("x-codex-turn-metadata", '{"session_id":"bad\\u0000id"}')], document), False)
    assert_equal(_continuation_identity_valid([("x-prodex-internal-conversation-namespace", String("x") * 1025)], document), True)
    var store = ProviderConversationStore()
    store.insert("saved", '[{"tool_calls":[{"id":"call-synthetic"}]}]', "a")
    var blank_call = JsonDocument('{"input":[{"type":"function_call_output","call_id":"","tool_call_id":"call-synthetic"}]}')
    assert_equal(_history(blank_call, store, "a"), "[]")
    var typed_fallback = JsonDocument('{"input":[{"type":"function_call_output","call_id":null,"tool_call_id":"call-synthetic"}]}')
    assert_equal(_history(typed_fallback, store, "a"), store.history("saved", "a").value())
    assert_equal(_history(typed_fallback, store, None), "[]")
    store.insert("unscoped", '[{"tool_calls":[{"id":"call-synthetic"}]}]')
    assert_equal(_history(typed_fallback, store, None), store.history("unscoped").value())
    assert_equal(_history(typed_fallback, store, "b"), "[]")
    var response_headers = _response_headers([("x-codex-turn-state", "synthetic\tmetadata"), ("x-utf8", "é"), ("x-lossy", "\ufffd"), ("x-empty", ""), ("connection", "X-Synthetic-Hop"), ("X-Synthetic-Hop", "private")])
    assert_equal(len(response_headers), 2)
    assert_equal(response_headers[0], (String("x-codex-turn-state"), String("synthetic\tmetadata")))
    assert_equal(response_headers[1], (String("x-empty"), String("")))
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/")[1], "/v1/chat/completions")
    assert_equal(local_rewrite_upstream("http://[::1]:1234")[0], "[::1]:1234")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/é/東京🧭")[1], "/v1/%C3%A9/%E6%9D%B1%E4%BA%AC%F0%9F%A7%AD/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/%C3%A9/%2f")[1], "/v1/%C3%A9/%2f/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/e\u0301")[1], "/v1/e%CC%81/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/\"<>`{}^|[]")[1], "/v1/%22%3C%3E%60%7B%7D^|[]/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/%22%7B%7D")[1], "/v1/%22%7B%7D/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/left\\right")[1], "/v1/left/right/chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/trailing\\/")[1], "/v1/trailing//chat/completions")
    assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/%5Cescaped")[1], "/v1/%5Cescaped/chat/completions")
    for dot in [".", "%2e", "%2E"]:
        assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/" + dot + "/keep")[1], "/v1/keep/chat/completions")
    for dot in ["..", ".%2e", ".%2E", "%2e.", "%2E.", "%2e%2e", "%2e%2E", "%2E%2e", "%2E%2E"]:
        assert_equal(local_rewrite_upstream("http://127.0.0.1:1234/v1/left/" + dot + "/right")[1], "/v1/right/chat/completions")
    for path, target in [
        ("/v1/.", "/v1/chat/completions"),
        ("/v1/..", "/chat/completions"),
        ("/../../other", "/other/chat/completions"),
        ("/v1//../other", "/v1/other/chat/completions"),
        ("/v1/left/..//right", "/v1//right/chat/completions"),
        ("/v1\\..\\other", "/other/chat/completions"),
        ("/v1/.\\", "/v1//chat/completions"),
        ("/v1/..\\", "//chat/completions"),
        ("//v1/../keep", "//keep/chat/completions"),
        ("/v1/%252e/%2e%2Fkeep/%5C", "/v1/%252e/%2e%2Fkeep/%5C/chat/completions"),
        ("/v1/%2efoo/.%2ex", "/v1/%2efoo/.%2ex/chat/completions"),
    ]:
        assert_equal(local_rewrite_upstream("http://127.0.0.1:1234" + path)[1], target)
    assert_equal(local_rewrite_upstream("http://[::1]:1234/../../other"), (String("[::1]:1234"), String("/other/chat/completions")))
    for url in ["https://127.0.0.1:1", "http://192.0.2.1:1", "http://localhost:1", "http://127.0.0.1:0", "http://user@127.0.0.1:1", "http://127.0.0.1:1?secret", "http://user:secret@127.0.0.1:1/v1/../other", "http://user%3Asecret%40127.0.0.1:1/v1/../other", "http://127.0.0.1:1/v1/../other?secret", "http://127.0.0.1:1/v1/../other#fragment", "http://127.0.0.1:1\\v1/../other"]:
        var rejected = False
        try:
            _ = local_rewrite_upstream(url)
        except:
            rejected = True
        assert_true(rejected)
    print("Gateway argument checks: PASS")
