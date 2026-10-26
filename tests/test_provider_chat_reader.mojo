from std.collections import List, Span
from std.testing import assert_equal, assert_true

from modex.provider_chat_reader import DeepSeekChatReader


def collect(mut reader: DeepSeekChatReader, source: String) raises -> List[String]:
    var output = List[String]()
    var bytes = source.as_bytes()
    var offset = 0
    while offset < len(bytes) and not reader.done:
        var next = reader.consume(Span(bytes)[offset:])
        assert_true(next[0] > 0)
        offset += next[0]
        output.extend(next[1].copy())
    return output^


def main() raises:
    var reader = DeepSeekChatReader(7, "resp_deepseek_initial", 1)
    var events = collect(reader, 'data: {"choices":[{"delta":{"content":"kept"}}]}\ndata: {"error":{"message":"synthetic failure"}}\n\ndata: [DONE]\n\n')
    assert_true(reader.done and reader.state.completed)
    assert_equal(len(events), 4)
    assert_true(events[0].startswith("event: response.created\r\n"))
    assert_true(events[2].startswith("event: response.output_text.delta\r\n"))
    assert_true('"delta":"kept"' in events[2])
    assert_true(events[3].startswith("event: response.failed\r\n"))
    assert_true("synthetic failure" in events[3])
    reader = DeepSeekChatReader(8, "resp_deepseek_initial", 1)
    events = collect(reader, 'data: {"choices":[{"delta":{"content":"one"}}]}\ndata: {"choices":[{"delta":{"content":"two"}}]}\n\ndata: [DONE]\n\n')
    assert_true(reader.done and reader.state.completed)
    assert_true('"delta":"one"' in events[2])
    assert_true('"delta":"two"' in events[3])
    assert_true(events[len(events) - 1].startswith("event: response.completed\r\n"))
    assert_equal(len(reader.finish()), 0)
    print("Provider chat reader checks: PASS")
