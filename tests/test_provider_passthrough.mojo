from std.collections import List
from std.testing import assert_equal, assert_true
from modex.provider_passthrough import deepseek_chat_completions_path
from modex.provider_deepseek_transport import deepseek_request_headers


def main() raises:
    assert_equal(deepseek_chat_completions_path("/chat/completions", "/v1/chat/completions?x=%2B&x=2"), "/chat/completions?x=%2B&x=2")
    assert_equal(deepseek_chat_completions_path("/chat/completions", "/v1/chat/completions"), "/chat/completions")
    var headers = deepseek_request_headers([("Content-Type", "custom/type"), ("Authorization", "inbound"), ("Connection", "X-Hidden"), ("X-Hidden", "secret")], "fake-key", passthrough=True)
    assert_equal(headers, List[Tuple[String, String]]([("accept-encoding", "identity"), ("authorization", "Bearer fake-key"), ("Content-Type", "custom/type")]))
    for key in ["fake\r\nx: y", "fake\x00key", "fake\x7fkey", "faké"]:
        var rejected = False
        try:
            _ = deepseek_request_headers([], key)
        except:
            rejected = True
        assert_true(rejected)
    for pair in [("Authorization ", "bad"), ("Authorization", "bad\r\nX: y"), ("X-Test", "bad\x00value")]:
        var rejected = False
        try:
            _ = deepseek_request_headers([pair], "fake-key", passthrough=True)
        except:
            rejected = True
        assert_true(rejected)
    print("Provider passthrough checks: PASS")
