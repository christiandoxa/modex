"""Synthetic Anthropic server-search event fixtures shared by release tests."""

from test_anthropic_text_stream_04392 import MESSAGE_DELTA, START, STOP, stream


def repeated_search_case(shared_id=False):
    request = {
        "model": "deepseek-chat",
        "input": "synthetic query",
        "stream": True,
        "tools": [{"type": "web_search_preview"}],
    }
    first_id = "shared_search" if shared_id else "search_1"
    second_id = "shared_search" if shared_id else "search_2"
    events = [
        START,
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "server_tool_use", "id": first_id, "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"first"}',
        }},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": first_id, "content": [
                {"type": "web_search_result", "url": "https://one.example.test", "title": "One"},
            ],
        }},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {
            "type": "server_tool_use", "id": second_id, "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 2, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"second"}',
        }},
        {"type": "content_block_stop", "index": 2},
        {"type": "content_block_start", "index": 3, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": second_id, "content": [
                {"type": "web_search_result", "url": "https://two.example.test", "title": "Two"},
            ],
        }},
        {"type": "content_block_stop", "index": 3},
        {"type": "content_block_start", "index": 4, "content_block": {
            "type": "text", "text": "",
        }},
        {"type": "content_block_delta", "index": 4, "delta": {
            "type": "text_delta", "text": "Found both.",
        }},
        {"type": "content_block_stop", "index": 4},
        MESSAGE_DELTA,
        STOP,
    ]
    reply = {
        "status": 200,
        "content_type": "text/event-stream",
        "body": stream(events),
    }
    return request, reply


def overlapping_search_result_case():
    request = {
        "model": "deepseek-chat",
        "input": "synthetic mixed prompt",
        "stream": True,
        "tools": [
            {"type": "function", "name": "lookup", "parameters": {"type": "object"}},
            {"type": "web_search_preview"},
        ],
    }
    events = [
        START,
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "server_tool_use", "id": "search_0", "name": "web_search", "input": {},
        }},
        {"type": "content_block_start", "index": 1, "content_block": {
            "type": "server_tool_use", "id": "search_1", "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"query-0"}',
        }},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 2, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": "search_0", "content": [
                {"type": "web_search_result", "url": "https://example.test/0", "title": "Result 0"},
            ],
        }},
        {"type": "content_block_delta", "index": 1, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":',
        }},
        {"type": "content_block_stop", "index": 2},
        {"type": "content_block_delta", "index": 1, "delta": {
            "type": "input_json_delta", "partial_json": '"query-1"}',
        }},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 3, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": "search_1", "content": [
                {"type": "web_search_result", "url": "https://example.test/1", "title": "Result 1"},
            ],
        }},
        {"type": "content_block_stop", "index": 3},
        MESSAGE_DELTA,
        STOP,
    ]
    return request, {
        "status": 200,
        "content_type": "text/event-stream",
        "body": stream(events),
    }


def empty_search_result_case():
    request = {
        "model": "deepseek-chat",
        "input": "synthetic mixed prompt",
        "stream": True,
        "tools": [
            {"type": "function", "name": "lookup", "parameters": {"type": "object"}},
            {"type": "web_search_preview"},
        ],
    }
    events = [
        START,
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "server_tool_use", "id": "search_empty", "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"empty"}',
        }},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": "search_empty", "content": [],
        }},
        {"type": "content_block_stop", "index": 1},
        MESSAGE_DELTA,
        STOP,
    ]
    return request, {
        "status": 200,
        "content_type": "text/event-stream",
        "body": stream(events),
    }


def interleaved_mixed_search_case(
    search_count=2, shared_id=False, include_results=True, query_case="valid",
):
    request = {
        "model": "deepseek-chat",
        "input": "synthetic mixed query",
        "stream": True,
        "tools": [
            {"type": "function", "name": "lookup", "parameters": {
                "type": "object", "properties": {"q": {"type": "string"}},
            }},
            {"type": "web_search_preview"},
        ],
    }
    events = [{"type": "message_start", "message": {
        "id": "msg_mixed_interleaved", "role": "assistant", "model": "deepseek-chat",
        "usage": {"input_tokens": 3, "output_tokens": 0},
    }}]
    search_ids = ["shared_search" if shared_id else f"search_{index}" for index in range(search_count)]
    for index, search_id in enumerate(search_ids):
        search_input = {"query": 7} if query_case == "initial-nonstr" and index == 0 else {}
        events.append({"type": "content_block_start", "index": index, "content_block": {
            "type": "server_tool_use", "id": search_id, "name": "web_search", "input": search_input,
        }})
    function_index = search_count
    events.append({"type": "content_block_start", "index": function_index, "content_block": {
        "type": "tool_use", "id": "call_lookup", "name": "lookup", "input": {},
    }})
    for index in reversed(range(search_count)):
        if not (query_case in ("missing", "initial-nonstr") and index == 0):
            events.append({"type": "content_block_delta", "index": index, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":',
            }})
    events.append({"type": "content_block_delta", "index": function_index, "delta": {
        "type": "input_json_delta", "partial_json": '{"q":',
    }})
    for index in range(search_count):
        fragment = f'"query-{index}"}}'
        if query_case == "malformed" and index == 0:
            fragment = '"query-0'
        elif query_case == "nonstring" and index == 0:
            fragment = "7}"
        if not (query_case in ("missing", "initial-nonstr") and index == 0):
            events.append({"type": "content_block_delta", "index": index, "delta": {
                "type": "input_json_delta", "partial_json": fragment,
            }})
    events.append({"type": "content_block_delta", "index": function_index, "delta": {
        "type": "input_json_delta", "partial_json": '"mixed"}',
    }})
    for index in reversed(range(search_count)):
        events.append({"type": "content_block_stop", "index": index})
        if index == search_count - 1:
            events.append({"type": "content_block_stop", "index": function_index})
    if not search_count:
        events.append({"type": "content_block_stop", "index": function_index})
    if include_results:
        result_indices = []
        for result_offset, index in enumerate(reversed(range(search_count))):
            result_index = search_count + 1 + result_offset
            events.append({"type": "content_block_start", "index": result_index,
                           "content_block": {
                    "type": "web_search_tool_result", "tool_use_id": search_ids[index],
                    "content": [{"type": "web_search_result",
                                 "url": f"https://example.test/{index}", "title": f"Result {index}"}],
            }})
            result_indices.append(result_index)
        for result_index in reversed(result_indices):
            events.append({"type": "content_block_stop", "index": result_index})
    events.extend([
        {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
         "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ])
    return request, {"status": 200, "content_type": "text/event-stream", "body": stream(events)}
