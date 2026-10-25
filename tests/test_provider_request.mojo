"""Frozen chat_compatible_request.rs ordering and body-only conformance override."""

from std.testing import assert_equal

from modex.json import JsonDocument, serialize_json
from modex.provider_request import canonical_deepseek_model, translate_deepseek_request


def check(source: String, expected: String, history: String = "[]", strict_tools: Bool = False) raises:
    var doc = JsonDocument(expected)
    assert_equal(translate_deepseek_request(source, history, strict_tools), serialize_json(doc, doc.root))


def reject(source: String, expected: String) raises:
    var actual = String()
    try:
        _ = translate_deepseek_request(source)
    except error:
        actual = String(error)
    assert_equal(actual, expected)


def main() raises:
    for model, expected in [
        (String(" pro "), String("deepseek-v4-pro")),
        ("AUTO", "deepseek-v4-pro"),
        ("Flash", "deepseek-v4-flash"),
        (" default ", "default"),
        (" 東京🧭 ", "東京🧭"),
        ("combo: , flash > pro", "flash"),
        ("combo: ;東京🧭|flash", "東京🧭"),
        ("COMBO:flash", "COMBO:flash"),
        (" combo: , ; ", " combo: , ; "),
        ("combo: , ;>", "combo: , ;>"),
    ]:
        assert_equal(canonical_deepseek_model(model), expected)

    check("{}", '{"body":{"model":"deepseek-v4-pro","stream":false,"messages":[{"role":"user","content":""}]},"messages":[{"role":"user","content":""}],"response_metadata":null}')
    check('{"input":"hello"}', '{"body":{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"hello"}]},"messages":[{"role":"user","content":"hello"}],"response_metadata":null}')
    check('{"model":"combo:flash>pro"}', '{"body":{"model":"flash","stream":false,"messages":[{"role":"user","content":""}]},"messages":[{"role":"user","content":""}],"response_metadata":null}')

    check('{"model":"pro","input":"hello","stream":true,"text":{"format":{"type":"json_object"}}}', '{"body":{"model":"deepseek-v4-pro","stream":true,"messages":[{"role":"user","content":"hello"}]},"messages":[{"role":"system","content":"Respond with valid JSON only."},{"role":"user","content":"hello"}],"response_metadata":null}')
    check('{"input":"hello","messages":[{"role":"developer","content":"raw"}]}', '{"body":{"model":"deepseek-chat","stream":false,"messages":[{"role":"developer","content":"raw"}]},"messages":[{"role":"user","content":"hello"}],"response_metadata":null}')
    check('{"stream":true,"text":{"format":{"type":"json"}},"instructions":"Return JsOn"}', '{"body":{"model":"deepseek-v4-pro","stream":true,"stream_options":{"include_usage":true},"response_format":{"type":"json_object"},"messages":[{"role":"system","content":"Return JsOn"}]},"messages":[{"role":"system","content":"Return JsOn"}],"response_metadata":null}')

    check('{"previous_response_id":"resp_1","input":"next","instructions":"rules","stream":true,"reasoning":{"effort":"minimal"}}', '{"body":{"model":"deepseek-v4-pro","stream":true,"stream_options":{"include_usage":true},"thinking":{"type":"disabled"},"messages":[{"role":"system","content":"rules"},{"role":"user","content":"old"},{"role":"user","content":"next"}]},"messages":[{"role":"system","content":"rules"},{"role":"user","content":"old"},{"role":"user","content":"next"}],"response_metadata":null}', '[{"role":"user","content":"old"}]')

    check('{"metadata":{"trace":1,"deepseek":{}},"client_metadata":{},"prompt_cache_key":"  key  ","prompt_cache_retention":""}', '{"body":{"model":"deepseek-v4-pro","stream":false,"messages":[{"role":"user","content":""}]},"messages":[{"role":"user","content":""}],"response_metadata":{"trace":1,"deepseek":{},"client_metadata":{},"prompt_cache_key":"  key  ","prompt_cache_retention":""}}')
    check('{"metadata":{"trace":1},"metadata":{"last":2},"temperature":0,"temperature":1}', '{"body":{"model":"deepseek-v4-pro","stream":false,"temperature":1,"messages":[{"role":"user","content":""}]},"messages":[{"role":"user","content":""}],"response_metadata":{"last":2}}')
    check('{"model":"deepseek-chat","input":"x","tools":[{"type":"mcp","server_label":"s","allowed_tools":["run"]}]}', '{"body":{"model":"deepseek-chat","stream":false,"messages":[{"role":"user","content":"x"}],"tools":[{"type":"function","function":{"name":"mcp__s__run","description":"MCP tool run from s.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":false},"strict":true}}]},"messages":[{"role":"user","content":"x"}],"response_metadata":null}', strict_tools=True)

    reject('{"prefix":null,', "failed to parse Codex Responses request JSON")
    reject("{} trailing", "failed to parse Codex Responses request JSON")
    reject("[]", "DeepSeek request body must be a JSON object")
    reject('{"prefix":null,"model":false}', "DeepSeek chat prefix completion requires the beta chat endpoint, which is outside this Responses adapter")
    reject('{"model":"","stream":null}', "DeepSeek model must not be empty")
    reject('{"reasoning":{"effort":null},"input":null}', "DeepSeek reasoning.effort must be a string")
    reject('{"reasoning":{"effort":"unknown"},"input":null}', "DeepSeek input must be a string or array of input items")
    reject('{"input":null,"response_format":null}', "DeepSeek input must be a string or array of input items")
    reject('{"response_format":null,"metadata":null}', "DeepSeek response_format must include a type")
    reject('{"metadata":{"deepseek":null},"reasoning_effort":"unknown"}', "DeepSeek request metadata.deepseek must be an object")
    reject('{"reasoning_effort":"unknown","tools":[{"type":"file_search"}]}', "DeepSeek reasoning effort is not supported")
    reject('{"tools":[{"type":"file_search"}],"temperature":null}', "DeepSeek tool type `file_search` is not supported")
    reject('{"frequency_penalty":0,"temperature":null}', "DeepSeek temperature must be a number")
    reject('{"stop":null,"top_logprobs":21}', "DeepSeek stop must be a string or array of strings")
    reject('{"top_logprobs":21,"user":"invalid!"}', "DeepSeek top_logprobs must be <= 20")
    print("Provider request integration checks: PASS")
