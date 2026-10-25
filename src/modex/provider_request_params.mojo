"""DeepSeek request parameter validation, mapping and response metadata."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json, serialize_number
from .text import trim_text


def validate_request_shape(doc: JsonDocument) raises:
    if doc.nodes[doc.root].kind != JSON_OBJECT:
        raise Error("DeepSeek request body must be a JSON object")
    if serialize_json(doc, doc.root).byte_length() > 4194304:
        raise Error("DeepSeek request policy input exceeds 4194304 bytes")
    for key, message in [(String("prefix"), String("chat prefix completion requires the beta chat endpoint")), ("suffix", "FIM suffix completion requires the beta /completions endpoint"), ("prompt", "prompt completions require the beta /completions endpoint")]:
        if doc.get(doc.root, key) >= 0:
            raise Error("DeepSeek " + message + ", which is outside this Responses adapter")
    for key in [String("model"), "stream", "instructions", "previous_response_id"]:
        var node = doc.get(doc.root, key)
        if node < 0:
            continue
        var expected = JSON_BOOL if key == "stream" else JSON_STRING
        if doc.nodes[node].kind != expected:
            raise Error("DeepSeek " + key + " must be a " + ("boolean" if expected == JSON_BOOL else "string"))
        if key == "model" and not trim_text(doc.nodes[node].text):
            raise Error("DeepSeek model must not be empty")


def request_reasoning(doc: JsonDocument) raises -> Optional[String]:
    var reasoning = doc.get(doc.root, "reasoning")
    if reasoning >= 0:
        if doc.nodes[reasoning].kind != JSON_OBJECT:
            raise Error("DeepSeek reasoning must be an object")
        _only_key(doc, reasoning, "effort", "reasoning.", " is not supported by this Responses adapter")
        var effort = doc.get(reasoning, "effort")
        if effort >= 0:
            if doc.nodes[effort].kind != JSON_STRING:
                raise Error("DeepSeek reasoning.effort must be a string")
            return Optional[String](doc.nodes[effort].text)
    var effort = doc.get(doc.root, "reasoning_effort")
    if effort >= 0:
        if doc.nodes[effort].kind != JSON_STRING:
            raise Error("DeepSeek reasoning_effort must be a string")
        return Optional[String](doc.nodes[effort].text)
    return Optional[String]()


def reasoning_fields(effort: Optional[String]) raises -> String:
    if not effort:
        return "{}"
    var value = trim_text(effort.value()).lower()
    if value == "max" or value == "xhigh":
        return '{"thinking":{"type":"enabled"},"reasoning_effort":"max"}'
    if value == "high" or value == "medium" or value == "low":
        return '{"thinking":{"type":"enabled"},"reasoning_effort":"high"}'
    if value == "none" or value == "minimal":
        return '{"thinking":{"type":"disabled"}}'
    raise Error("DeepSeek reasoning effort is not supported")


def thinking_enabled(effort: Optional[String]) -> Bool:
    if not effort:
        return False
    var value = trim_text(effort.value()).lower()
    return value == "max" or value == "xhigh" or value == "high" or value == "medium" or value == "low"


def request_format(doc: JsonDocument) raises -> Optional[String]:
    var node = doc.get(doc.root, "response_format")
    if node < 0:
        node = doc.get(doc.get(doc.root, "text"), "format")
    if node < 0:
        return Optional[String]()
    var kind = doc.get(node, "type")
    if kind < 0 or doc.nodes[kind].kind != JSON_STRING or not trim_text(doc.nodes[kind].text):
        raise Error("DeepSeek response_format must include a type")
    var value = doc.nodes[kind].text
    if value == "text":
        return Optional[String]()
    if value != "json" and value != "json_object" and value != "json_schema" and value != "structured_output":
        raise Error("DeepSeek response_format type `" + value + "` is not supported")
    return Optional[String](value)


def request_metadata(doc: JsonDocument, format: Optional[String], thinking: Bool) raises -> String:
    var metadata = doc.get(doc.root, "metadata")
    if metadata >= 0 and doc.nodes[metadata].kind != JSON_OBJECT:
        raise Error("DeepSeek request metadata must be an object")
    var provider = doc.get(metadata, "deepseek")
    if provider >= 0 and doc.nodes[provider].kind != JSON_OBJECT:
        raise Error("DeepSeek request metadata.deepseek must be an object")
    for key in [String("client_metadata"), "prompt_cache_key", "prompt_cache_retention"]:
        var node = doc.get(doc.root, key)
        if node < 0:
            continue
        if key == "client_metadata" and doc.nodes[node].kind != JSON_OBJECT:
            raise Error("DeepSeek client_metadata must be an object")
        if key != "client_metadata" and doc.nodes[node].kind != JSON_STRING:
            raise Error("DeepSeek " + key + " must be a string")
    var fields = List[String]()
    if metadata >= 0:
        for index in range(len(doc.nodes[metadata].children)):
            if doc.nodes[metadata].names[index] != "deepseek":
                fields.append(quote_json(doc.nodes[metadata].names[index]) + ":" + serialize_json(doc, doc.nodes[metadata].children[index]))
    var input_bytes = fields_object(fields).byte_length() + 8
    if provider >= 0:
        input_bytes += serialize_json(doc, provider).byte_length()
    for key in [String("client_metadata"), "prompt_cache_key", "prompt_cache_retention"]:
        var node = doc.get(doc.root, key)
        if node >= 0 and (key != "prompt_cache_key" or trim_text(doc.nodes[node].text)):
            fields.append(quote_json(key) + ":" + serialize_json(doc, node))
            input_bytes += serialize_json(doc, node).byte_length() if key == "client_metadata" else doc.nodes[node].text.byte_length()
    var provider_fields = List[String]()
    if provider >= 0:
        for index in range(len(doc.nodes[provider].children)):
            provider_fields.append(quote_json(doc.nodes[provider].names[index]) + ":" + serialize_json(doc, doc.nodes[provider].children[index]))
    if format and (format.value() == "json_schema" or format.value() == "structured_output"):
        var reason = String("DeepSeek response_format supports json_object but not native JSON Schema enforcement")
        input_bytes += format.value().byte_length() + reason.byte_length()
        provider_fields.append('"degraded_response_format":{"from":' + quote_json(format.value()) + ',"to":"json_object","reason":' + quote_json(reason) + "}")
    if input_bytes > 4194304:
        raise Error("DeepSeek response metadata normalization failed: DeepSeek Mojo kernel failed: InvalidInput")
    if provider >= 0 or provider_fields:
        fields.append('"deepseek":' + fields_object(provider_fields))
    var result = JsonDocument(fields_object(fields))
    var choice = doc.get(doc.root, "tool_choice")
    if thinking and choice >= 0:
        var reason = String("DeepSeek thinking mode currently rejects explicit tool_choice on the OpenAI Chat route, so Prodex omits it while preserving translated function tools")
        var base_fields = List[String]()
        var note_bytes = 8 + serialize_json(doc, choice).byte_length() + reason.byte_length()
        for index in range(len(result.nodes[result.root].children)):
            var key = result.nodes[result.root].names[index]
            var value = serialize_json(result, result.nodes[result.root].children[index])
            if key == "deepseek":
                note_bytes += value.byte_length()
            else:
                base_fields.append(quote_json(key) + ":" + value)
        note_bytes += fields_object(base_fields).byte_length()
        # The frozen runtime keeps prior metadata when its optional note exceeds the kernel budget.
        if note_bytes <= 4194304:
            provider_fields.append('"omitted_tool_choice":{"from":' + serialize_json(doc, choice) + ',"reason":' + quote_json(reason) + "}")
            fields.append('"deepseek":' + fields_object(provider_fields))
            result = JsonDocument(fields_object(fields))
    return serialize_json(result, result.root) if result.nodes[result.root].children else "null"


def optional_request_fields(doc: JsonDocument, stream: Bool, format: Optional[String]) raises -> String:
    var fields = List[String]()
    for key in [String("temperature"), "top_p"]:
        var node = doc.get(doc.root, key)
        if node >= 0 and doc.nodes[node].kind != JSON_NUMBER:
            raise Error("DeepSeek " + key + " must be a number")
        if node >= 0:
            fields.append(quote_json(key) + ":" + serialize_json(doc, node))
    var maximum = -1
    for key in [String("max_output_tokens"), "max_tokens", "max_completion_tokens"]:
        var node = doc.get(doc.root, key)
        if node >= 0:
            if not _positive_integer(doc, node):
                raise Error("DeepSeek " + key + " must be a positive integer")
            maximum = node
    if maximum >= 0:
        fields.append('"max_tokens":' + serialize_json(doc, maximum))
    var logprobs = doc.get(doc.root, "logprobs")
    if logprobs >= 0:
        if doc.nodes[logprobs].kind != JSON_BOOL:
            raise Error("DeepSeek logprobs must be a boolean")
        fields.append('"logprobs":' + serialize_json(doc, logprobs))
    _validate_unsupported(doc, stream)
    var stop = first_present(doc, doc.root, ["stop", "stop_sequences", "stopSequences"])
    if stop >= 0:
        if doc.nodes[stop].kind == JSON_ARRAY:
            if len(doc.nodes[stop].children) > 16:
                raise Error("DeepSeek supports at most 16 stop sequences")
            for child in doc.nodes[stop].children:
                if doc.nodes[child].kind != JSON_STRING:
                    raise Error("DeepSeek stop sequences must be strings")
        elif doc.nodes[stop].kind != JSON_STRING:
            raise Error("DeepSeek stop must be a string or array of strings")
        fields.append('"stop":' + serialize_json(doc, stop))
    var top = doc.get(doc.root, "top_logprobs")
    if top >= 0:
        var count = _small_uint(doc, top)
        if count < 0:
            raise Error("DeepSeek top_logprobs must be an integer")
        if count > 20:
            raise Error("DeepSeek top_logprobs must be <= 20")
        if logprobs < 0 or doc.nodes[logprobs].text != "true":
            raise Error("DeepSeek top_logprobs requires logprobs=true")
        fields.append('"top_logprobs":' + serialize_json(doc, top))
    if stream:
        fields.append('"stream_options":{"include_usage":true}')
    if format:
        fields.append('"response_format":{"type":"json_object"}')
    var user = first_present(doc, doc.root, ["user_id", "user", "safety_identifier"])
    if user >= 0:
        if doc.nodes[user].kind != JSON_STRING:
            raise Error("DeepSeek user_id must be a string")
        var text = trim_text(doc.nodes[user].text)
        if text.byte_length() > 512:
            raise Error("DeepSeek user_id must use only letters, numbers, underscores, or dashes and be at most 512 bytes")
        for byte in text.as_bytes():
            var code = Int(byte)
            if not (48 <= code <= 57 or 65 <= code <= 90 or 97 <= code <= 122 or code == 45 or code == 95):
                raise Error("DeepSeek user_id must use only letters, numbers, underscores, or dashes and be at most 512 bytes")
        if text:
            fields.append('"user_id":' + quote_json(text))
    return fields_object(fields)


def _validate_unsupported(doc: JsonDocument, stream: Bool) raises:
    for key in [String("frequency_penalty"), "presence_penalty"]:
        if doc.get(doc.root, key) >= 0:
            raise Error("DeepSeek " + key + " is deprecated and is not forwarded by Prodex")
    for key in [String("n"), "seed", "service_tier", "prediction", "logit_bias", "functions", "function_call"]:
        if doc.get(doc.root, key) >= 0:
            raise Error("DeepSeek " + key + " is not supported by this Responses adapter")
    _typed_optional(doc, "include", JSON_ARRAY, "array")
    _typed_optional(doc, "store", JSON_BOOL, "boolean")
    var background = doc.get(doc.root, "background")
    if background >= 0:
        if doc.nodes[background].kind == JSON_BOOL and doc.nodes[background].text == "true":
            raise Error("DeepSeek background responses are not supported by this Responses adapter")
        _typed_optional(doc, "background", JSON_BOOL, "boolean")
    var truncation = doc.get(doc.root, "truncation")
    if truncation >= 0:
        _typed_optional(doc, "truncation", JSON_STRING, "string")
        var value = doc.nodes[truncation].text
        if value == "auto":
            raise Error("DeepSeek truncation=auto is not supported by this Responses adapter")
        if value != "disabled":
            raise Error("DeepSeek truncation `" + value + "` is not supported")
    if doc.get(doc.root, "max_tool_calls") >= 0:
        raise Error("DeepSeek max_tool_calls is not supported by this Responses adapter")
    var text = doc.get(doc.root, "text")
    if text >= 0:
        _typed_optional(doc, "text", JSON_OBJECT, "object")
        _only_key(doc, text, "format", "text.", " is not supported by this Responses adapter")
    var parallel = doc.get(doc.root, "parallel_tool_calls")
    if parallel >= 0:
        if doc.nodes[parallel].kind == JSON_BOOL and doc.nodes[parallel].text == "false":
            raise Error("DeepSeek does not expose a compatible parallel_tool_calls=false control")
        _typed_optional(doc, "parallel_tool_calls", JSON_BOOL, "boolean")
    var options = doc.get(doc.root, "stream_options")
    if options >= 0:
        _typed_optional(doc, "stream_options", JSON_OBJECT, "object")
        if not stream:
            raise Error("DeepSeek stream_options requires stream=true")
        _only_key(doc, options, "include_usage", "stream_options.", " is not supported")
        var include = doc.get(options, "include_usage")
        if include >= 0:
            if doc.nodes[include].kind != JSON_BOOL:
                raise Error("DeepSeek stream_options.include_usage must be a boolean")
            if doc.nodes[include].text == "false":
                raise Error("DeepSeek streaming adapter requires stream_options.include_usage=true")
    var modalities = doc.get(doc.root, "modalities")
    if modalities >= 0:
        _typed_optional(doc, "modalities", JSON_ARRAY, "array")
        for item in doc.nodes[modalities].children:
            if doc.nodes[item].kind != JSON_STRING or doc.nodes[item].text != "text":
                raise Error("DeepSeek Responses adapter only supports text modality; audio/image/video modalities are not supported")
    if doc.get(doc.root, "audio") >= 0:
        raise Error("DeepSeek Responses adapter does not support audio output")


def _typed_optional(doc: JsonDocument, key: String, kind: Int, label: String) raises:
    var node = doc.get(doc.root, key)
    if node >= 0 and doc.nodes[node].kind != kind:
        raise Error("DeepSeek " + key + " must be an " + label if label == "array" or label == "object" else "DeepSeek " + key + " must be a " + label)


def _only_key(doc: JsonDocument, node: Int, allowed: String, prefix: String, suffix: String) raises:
    for key in doc.nodes[node].names:
        if key != allowed:
            raise Error("DeepSeek " + prefix + key + suffix)


def _positive_integer(doc: JsonDocument, node: Int) -> Bool:
    if doc.nodes[node].kind != JSON_NUMBER:
        return False
    var value = serialize_number(doc.nodes[node].text)
    var nonzero = False
    for byte in value.as_bytes():
        if byte < 48 or byte > 57:
            return False
        nonzero = nonzero or byte != 48
    return nonzero


def _small_uint(doc: JsonDocument, node: Int) -> Int:
    if doc.nodes[node].kind != JSON_NUMBER:
        return -1
    var value = serialize_number(doc.nodes[node].text)
    var count = 0
    for byte in value.as_bytes():
        if byte < 48 or byte > 57:
            return -1
        count = count * 10 + Int(byte) - 48
        if count > 20:
            return 21
    return count


def first_present(doc: JsonDocument, parent: Int, keys: List[String]) -> Int:
    for key in keys:
        var node = doc.get(parent, key)
        if node >= 0:
            return node
    return -1


def fields_object(fields: List[String]) -> String:
    var result = String("{")
    for index in range(len(fields)):
        if index:
            result += ","
        result += fields[index]
    return result + "}"
