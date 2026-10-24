from std.testing import assert_equal, assert_true

from modex.json import JsonDocument
from modex.provider_chat_chunk import chat_first_choice, chat_choice_metadata, chat_choice_delta, chat_stream_error


def main() raises:
    var missing = JsonDocument("{}")
    var choice = chat_first_choice(missing)
    assert_equal(choice, -1)
    assert_equal(chat_choice_metadata(missing, choice), '{"finish_reason":null,"logprobs":null}')
    var empty_delta = '{"annotations":[],"content":null,"reasoning_content":null,"refusal":null,"tool_calls":[]}'
    assert_equal(chat_choice_delta(missing, choice), empty_delta)
    assert_equal(chat_stream_error(missing), "null")

    var doc = JsonDocument('{"choices":[{"delta":{"content":"","reasoning_content":4,"refusal":"text","annotations":false,"tool_calls":[null,7]},"finish_reason":"","logprobs":false},{"delta":{"content":"ignored"}}]}')
    choice = chat_first_choice(doc)
    assert_equal(choice, doc.nodes[doc.get(doc.root, "choices")].children[0])
    assert_equal(chat_choice_metadata(doc, choice), '{"finish_reason":"","logprobs":false}')
    assert_equal(chat_choice_delta(doc, choice), '{"annotations":[],"content":null,"reasoning_content":null,"refusal":"text","tool_calls":[null,7]}')

    var message = JsonDocument('{"choices":[{"message":{"content":"ignored"},"delta":null}]}')
    assert_equal(chat_choice_delta(message, chat_first_choice(message)), empty_delta)

    var minimum = JsonDocument('{"error":{"code":-9223372036854775808}}')
    assert_equal(chat_stream_error(minimum), '{"code":"-9223372036854775808","message":"Provider stream returned an embedded error"}')
    var shadow = JsonDocument('{"error":{"type":null,"code":"ignored","message":null,"detail":"ignored"}}')
    assert_equal(chat_stream_error(shadow), '{"code":"provider_stream_error","message":"Provider stream returned an embedded error"}')
    var empty_error = JsonDocument('{"error":""}')
    assert_equal(chat_stream_error(empty_error), '{"code":"provider_stream_error","message":""}')

    var invalid = JsonDocument('{"choices":[null]}')
    choice = chat_first_choice(invalid)
    var rejected = False
    try:
        _ = chat_choice_metadata(invalid, choice)
    except error:
        rejected = String(error) == "chat stream choice is not an object"
    assert_true(rejected)
    rejected = False
    try:
        _ = chat_choice_delta(invalid, choice)
    except error:
        rejected = String(error) == "chat stream choice is not an object"
    assert_true(rejected)
    print("Provider chat chunk checks: PASS")
