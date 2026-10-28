from std.testing import assert_equal, assert_true

from modex.json import JsonDocument, serialize_json
from modex.provider_request_params import optional_request_fields, request_format, request_metadata, request_reasoning, reasoning_fields, thinking_enabled, validate_request_shape


def reject(source: String, stage: Int, expected: String, stream: Bool = False) raises:
    var doc = JsonDocument(source)
    var actual = String()
    try:
        if stage == 0: validate_request_shape(doc)
        elif stage == 1: _ = request_reasoning(doc)
        elif stage == 2: _ = request_format(doc)
        elif stage == 3: _ = request_metadata(doc, request_format(doc), False)
        elif stage == 4: _ = optional_request_fields(doc, stream, Optional[String]())
        else: _ = reasoning_fields(request_reasoning(doc))
    except error:
        actual = String(error)
    assert_equal(actual, expected)


def options(source: String, expected: String, stream: Bool = False) raises:
    var doc = JsonDocument(source)
    var actual = JsonDocument(optional_request_fields(doc, stream, Optional[String]()))
    var wanted = JsonDocument(expected)
    assert_equal(serialize_json(actual, actual.root), serialize_json(wanted, wanted.root))


def main() raises:
    reject('{"prefix":null,"model":null}', 0, "DeepSeek chat prefix completion requires the beta chat endpoint, which is outside this Responses adapter")
    reject("[]", 0, "DeepSeek request body must be a JSON object")
    reject('{"stream":null}', 0, "DeepSeek stream must be a boolean")
    for model in [String("7"), "false", "true", "[]", "{}", "null", '""', '"  "', '"deepseek-flash"']:
        var model_request = JsonDocument('{"model":' + model + "}")
        validate_request_shape(model_request)
    reject('{"reasoning":{"summary":true,"effort":null}}', 1, "DeepSeek reasoning.summary is not supported by this Responses adapter")
    reject('{"reasoning":{"effort":null},"reasoning_effort":"high"}', 1, "DeepSeek reasoning.effort must be a string")
    reject('{"response_format":null,"text":{"format":{"type":"json"}}}', 2, "DeepSeek response_format must include a type")
    for format in [String("{}"), '{"type":null}', '{"type":7}', '{"type":false}', '{"type":[]}', '{"type":{}}']:
        reject('{"response_format":' + format + "}", 2, "DeepSeek response_format must include a type")
    reject('{"metadata":{"deepseek":null},"client_metadata":false}', 3, "DeepSeek request metadata.deepseek must be an object")
    reject('{"temperature":null,"frequency_penalty":1}', 4, "DeepSeek temperature must be a number")
    reject('{"frequency_penalty":null,"presence_penalty":0}', 4, "DeepSeek frequency_penalty is deprecated and is not forwarded by Prodex")
    reject('{"max_tokens":0}', 4, "DeepSeek max_tokens must be a positive integer")
    reject('{"max_tokens":1.0}', 4, "DeepSeek max_tokens must be a positive integer")
    reject('{"stop":null,"stop_sequences":["later"]}', 4, "DeepSeek stop must be a string or array of strings")
    reject('{"stop":[1,"a","a","a","a","a","a","a","a","a","a","a","a","a","a","a","a"]}', 4, "DeepSeek supports at most 16 stop sequences")
    reject('{"top_logprobs":21.5}', 4, "DeepSeek top_logprobs must be <= 20")
    reject('{"top_logprobs":1}', 4, "DeepSeek top_logprobs requires logprobs=true")
    reject('{"stream_options":{}}', 4, "DeepSeek stream_options requires stream=true")
    reject('{"text":{"verbosity":"low"}}', 4, "DeepSeek text.verbosity is not supported by this Responses adapter")
    for key, label in [(String("stream"), String("boolean")), ("instructions", "string"), ("previous_response_id", "string")]:
        reject('{"' + key + '":null}', 0, "DeepSeek " + key + " must be a " + label)
    reject('{"suffix":null,"prompt":null}', 0, "DeepSeek FIM suffix completion requires the beta /completions endpoint, which is outside this Responses adapter")
    reject('{"prompt":null}', 0, "DeepSeek prompt completions require the beta /completions endpoint, which is outside this Responses adapter")
    reject('{"reasoning":null}', 1, "DeepSeek reasoning must be an object")
    reject('{"reasoning_effort":true}', 1, "DeepSeek reasoning_effort must be a string")
    reject('{"reasoning_effort":"unknown"}', 5, "DeepSeek reasoning effort is not supported")
    reject('{"response_format":{"type":"JSON"}}', 2, "DeepSeek response_format type `JSON` is not supported")
    reject('{"response_format":{"type":" "}}', 2, "DeepSeek response_format must include a type")
    for key, expected in [
        (String("metadata"), String("request metadata must be an object")),
        ("client_metadata", "client_metadata must be an object"),
        ("prompt_cache_key", "prompt_cache_key must be a string"),
        ("prompt_cache_retention", "prompt_cache_retention must be a string"),
    ]:
        reject('{"' + key + '":null}', 3, "DeepSeek " + expected)

    for key, expected in [
        (String("include"), String("include must be an array")),
        ("store", "store must be a boolean"),
        ("background", "background must be a boolean"),
        ("truncation", "truncation must be a string"),
        ("text", "text must be an object"),
        ("parallel_tool_calls", "parallel_tool_calls must be a boolean"),
        ("stream_options", "stream_options must be an object"),
        ("modalities", "modalities must be an array"),
    ]:
        reject('{"' + key + '":null}', 4, "DeepSeek " + expected)
    for key in [String("n"), "seed", "service_tier", "prediction", "logit_bias", "functions", "function_call", "max_tool_calls"]:
        reject('{"' + key + '":null}', 4, "DeepSeek " + key + " is not supported by this Responses adapter")
    reject('{"background":true}', 4, "DeepSeek background responses are not supported by this Responses adapter")
    reject('{"truncation":"auto"}', 4, "DeepSeek truncation=auto is not supported by this Responses adapter")
    reject('{"truncation":"東京"}', 4, "DeepSeek truncation `東京` is not supported")
    reject('{"parallel_tool_calls":false}', 4, "DeepSeek does not expose a compatible parallel_tool_calls=false control")
    reject('{"stream_options":{"unknown":true,"include_usage":false}}', 4, "DeepSeek stream_options.unknown is not supported", True)
    reject('{"stream_options":{"include_usage":false}}', 4, "DeepSeek streaming adapter requires stream_options.include_usage=true", True)
    reject('{"stream_options":{"include_usage":null}}', 4, "DeepSeek stream_options.include_usage must be a boolean", True)
    reject('{"modalities":["text","image"]}', 4, "DeepSeek Responses adapter only supports text modality; audio/image/video modalities are not supported")
    reject('{"audio":null}', 4, "DeepSeek Responses adapter does not support audio output")
    reject('{"stop":[1]}', 4, "DeepSeek stop sequences must be strings")
    reject('{"top_logprobs":1.0,"logprobs":true}', 4, "DeepSeek top_logprobs must be an integer")
    reject('{"max_tokens":18446744073709551616}', 4, "DeepSeek max_tokens must be a positive integer")
    reject('{"max_output_tokens":0,"max_tokens":5}', 4, "DeepSeek max_output_tokens must be a positive integer")
    reject('{"user_id":null,"user":"valid"}', 4, "DeepSeek user_id must be a string")
    reject('{"user":"東京"}', 4, "DeepSeek user_id must use only letters, numbers, underscores, or dashes and be at most 512 bytes")
    reject('{"user":"' + String("x") * 513 + '"}', 4, "DeepSeek user_id must use only letters, numbers, underscores, or dashes and be at most 512 bytes")

    options('{"temperature":-1000,"top_p":500,"max_tokens":18446744073709551615,"stopSequences":["","end"],"user":"  user_123- "}', '{"temperature":-1000,"top_p":500,"max_tokens":18446744073709551615,"stop":["","end"],"user_id":"user_123-"}')
    options('{"stop":"","stop_sequences":["ignored"],"stopSequences":null,"user_id":" ","user":"ignored"}', '{"stop":""}')
    options('{"max_output_tokens":1,"max_tokens":2}', '{"max_tokens":2}')
    options('{"safety_identifier":"safety_1","logprobs":true,"top_logprobs":20}', '{"user_id":"safety_1","logprobs":true,"top_logprobs":20}')
    options('{"user_id":"' + String("x") * 512 + '"}', '{"user_id":"' + String("x") * 512 + '"}')
    options('{"stream":true,"include":[null],"store":false,"background":false,"truncation":"disabled","parallel_tool_calls":true,"stream_options":{},"modalities":["text"],"unknown":null}', '{"stream_options":{"include_usage":true}}', True)
    var numeric = JsonDocument('{"max_output_tokens":1,"max_tokens":2,"max_completion_tokens":3,"user_id":"  id-123_ ","logprobs":true,"top_logprobs":0}')
    var fields = JsonDocument(optional_request_fields(numeric, True, Optional[String]("json_schema")))
    assert_equal(serialize_json(fields, fields.root), '{"logprobs":true,"max_tokens":3,"response_format":{"type":"json_object"},"stream_options":{"include_usage":true},"top_logprobs":0,"user_id":"id-123_"}')
    var reasoning = JsonDocument('{"reasoning":{"effort":"  MeDIuM "},"reasoning_effort":"none"}')
    var effort = request_reasoning(reasoning)
    assert_true(thinking_enabled(effort))
    assert_equal(reasoning_fields(effort), '{"thinking":{"type":"enabled"},"reasoning_effort":"high"}')
    var metadata = JsonDocument('{"metadata":{"deepseek":{"x":1},"trace":false},"prompt_cache_key":"  key  ","prompt_cache_retention":"","tool_choice":null}')
    var rendered = request_metadata(metadata, Optional[String]("json_schema"), True)
    assert_true(rendered.find('"prompt_cache_key":"  key  "') >= 0)
    assert_true(rendered.find('"degraded_response_format"') >= 0)
    assert_true(rendered.find('"omitted_tool_choice":{"from":null') >= 0)
    for effort, expected in [
        (String("max"), String('{"thinking":{"type":"enabled"},"reasoning_effort":"max"}')),
        ("XHIGH", '{"thinking":{"type":"enabled"},"reasoning_effort":"max"}'),
        ("low", '{"thinking":{"type":"enabled"},"reasoning_effort":"high"}'),
        (" LoW ", '{"thinking":{"type":"enabled"},"reasoning_effort":"high"}'),
        ("none", '{"thinking":{"type":"disabled"}}'),
        (" minimal ", '{"thinking":{"type":"disabled"}}'),
    ]:
        assert_equal(reasoning_fields(Optional[String](effort)), expected)
    assert_true(thinking_enabled(Optional[String]("low")))
    assert_true(thinking_enabled(Optional[String]("  LOW  ")))
    assert_equal(reasoning_fields(Optional[String]()), "{}")
    var fallback = JsonDocument('{"reasoning":{},"reasoning_effort":"none"}')
    assert_equal(request_reasoning(fallback).value(), "none")
    var absent = JsonDocument("{}")
    assert_equal(request_metadata(absent, Optional[String](), False), "null")
    var empty_provider = JsonDocument('{"metadata":{"deepseek":{}}}')
    assert_equal(request_metadata(empty_provider, Optional[String](), False), '{"deepseek":{}}')
    var overwritten = JsonDocument('{"metadata":{"client_metadata":"old","prompt_cache_key":"old","deepseek":{"degraded_response_format":"old","omitted_tool_choice":"old","keep":false}},"client_metadata":{},"prompt_cache_key":" ","tool_choice":true}')
    var updated = JsonDocument(request_metadata(overwritten, Optional[String]("structured_output"), True))
    assert_equal(serialize_json(updated, updated.get(updated.root, "client_metadata")), "{}")
    assert_equal(updated.string(updated.get(updated.root, "prompt_cache_key")), "old")
    var provider = updated.get(updated.root, "deepseek")
    assert_equal(updated.string(updated.get(updated.get(provider, "degraded_response_format"), "from")), "structured_output")
    assert_equal(serialize_json(updated, updated.get(updated.get(provider, "omitted_tool_choice"), "from")), "true")

    var limit = JsonDocument('{"padding":"' + String("x") * (4194304 - 14) + '"}')
    validate_request_shape(limit)
    reject('{"padding":"' + String("x") * (4194304 - 13) + '"}', 0, "DeepSeek request policy input exceeds 4194304 bytes")
    var schema_envelope = String('{"metadata":{"padding":""},"response_format":{"type":"json_schema"}}')
    var schema_limit = String('{"metadata":{"padding":"') + String("x") * (4194304 - schema_envelope.byte_length()) + '"},"response_format":{"type":"json_schema"}}'
    var schema_doc = JsonDocument(schema_limit)
    validate_request_shape(schema_doc)
    reject(schema_limit, 3, "DeepSeek response metadata normalization failed: DeepSeek Mojo kernel failed: InvalidInput")
    var note_envelope = String('{"metadata":{"padding":""},"tool_choice":null,"reasoning_effort":"high"}')
    var note_limit = JsonDocument('{"metadata":{"padding":"' + String("x") * (4194304 - note_envelope.byte_length()) + '"},"tool_choice":null,"reasoning_effort":"high"}')
    validate_request_shape(note_limit)
    var retained = JsonDocument(request_metadata(note_limit, Optional[String](), True))
    assert_equal(retained.get(retained.root, "deepseek"), -1)
    assert_equal(retained.string(retained.get(retained.root, "padding")).byte_length(), 4194304 - note_envelope.byte_length())
    print("Provider request parameter checks: PASS")
