from std.testing import assert_equal, assert_true

from modex.provider_sse_events import sse_event, sse_failed_event, sse_text_item_added, sse_text_item_done


def main() raises:
    assert_equal(sse_event("custom", "{\"z\":1,\"a\":[true,null]}"), "event: custom\r\ndata: {\"a\":[true,null],\"z\":1}\r\n\r\n")
    assert_equal(sse_text_item_added(7, "resp_1", "item_1"), "event: response.output_item.added\r\ndata: {\"item\":{\"content\":[],\"id\":\"item_1\",\"role\":\"assistant\",\"type\":\"message\"},\"response_id\":\"resp_1\",\"sequence_number\":7,\"type\":\"response.output_item.added\"}\r\n\r\n")
    assert_equal(sse_text_item_done(8, "resp_1", "item_1", "hello\nworld"), "event: response.output_item.done\r\ndata: {\"item\":{\"content\":[{\"text\":\"hello\\nworld\",\"type\":\"output_text\"}],\"id\":\"item_1\",\"role\":\"assistant\",\"type\":\"message\"},\"response_id\":\"resp_1\",\"sequence_number\":8,\"type\":\"response.output_item.done\"}\r\n\r\n")
    var failed = sse_failed_event(1, 2, "resp_1", "provider_stream_error", "Authorization: Bearer fixture_token_123")
    assert_true(failed.find("Authorization: Bearer <redacted>") >= 0)
    assert_true(failed.find("fixture_token_123") < 0)
    print("Provider SSE event checks: PASS")
