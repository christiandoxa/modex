"""Project runtime options onto the Codex app-server configuration argv."""

from std.collections import List


def _toml_string(value: StringSlice) -> String:
    # Preserve the pinned TOML serializer's byte-for-byte argv choices.
    var max_single_quotes = 0
    var max_double_quotes = 0
    var single_quotes = 0
    var double_quotes = 0
    var has_control = False
    var has_backslash = False
    var has_newline = False
    for character in value.codepoints():
        var code = Int(character)
        if code == 39:
            single_quotes += 1
            max_single_quotes = max(max_single_quotes, single_quotes)
        else:
            single_quotes = 0
        if code == 34:
            double_quotes += 1
            max_double_quotes = max(max_double_quotes, double_quotes)
        else:
            double_quotes = 0
        if code == 92:
            has_backslash = True
        elif code == 10:
            has_newline = True
        elif (code < 32 and code != 9 and code != 10) or code == 127:
            has_control = True

    var encoding = 0
    if not has_control and not has_backslash and max_double_quotes == 0 and not has_newline:
        encoding = 0
    elif not has_control and max_single_quotes == 0 and not has_newline:
        encoding = 1
    elif not has_control and not has_backslash and max_double_quotes <= 2:
        encoding = 2
    elif not has_control and max_single_quotes <= 2:
        encoding = 3
    elif has_newline:
        encoding = 2

    var multiline = encoding == 2 or encoding == 3
    var basic = encoding == 0 or encoding == 2
    var result = String("\"" if encoding == 0 else "'" if encoding == 1 else "\"\"\"" if encoding == 2 else "'''" )
    if multiline and has_newline:
        result += "\n"
    comptime HEX = StaticString("0123456789ABCDEF")
    var output_double_quotes = 0
    for character in value.codepoints():
        var code = Int(character)
        if not basic:
            result += chr(code)
        elif code == 34:
            if not multiline or output_double_quotes >= 2:
                result += "\\\""
                output_double_quotes = 0
            else:
                result += chr(code)
                output_double_quotes += 1
        elif code == 92:
            result += "\\\\"
            output_double_quotes = 0
        elif code == 8:
            result += "\\b"
            output_double_quotes = 0
        elif code == 9:
            result += "\\t"
            output_double_quotes = 0
        elif code == 10:
            result += "\n" if multiline else "\\n"
            output_double_quotes = 0
        elif code == 12:
            result += "\\f"
            output_double_quotes = 0
        elif code == 13:
            result += "\\r"
            output_double_quotes = 0
        elif code < 32 or code == 127:
            result += "\\u00" + HEX[byte=code // 16] + HEX[byte=code % 16]
            output_double_quotes = 0
        else:
            result += chr(code)
            output_double_quotes = 0
    return result + ("\"" if encoding == 0 else "'" if encoding == 1 else "\"\"\"" if encoding == 2 else "'''")


def project_app_server_config_args(runtime_args: List[String], include_inline_config: Bool) -> List[String]:
    var result = List[String]()
    var index = 0
    while index < len(runtime_args):
        ref argument = runtime_args[index]
        if argument == "-c" or argument == "--config" or argument == "--enable" or argument == "--disable" or argument == "--code-mode-host":
            if index + 1 < len(runtime_args):
                result.append(argument)
                result.append(runtime_args[index + 1])
                index += 2
                continue
        elif argument == "--strict-config":
            result.append(argument)
        elif argument == "-m" or argument == "--model":
            if index + 1 < len(runtime_args):
                result.append("-c")
                result.append("model=" + _toml_string(runtime_args[index + 1]))
                index += 2
                continue
        elif argument.startswith("--model="):
            result.append("-c")
            result.append("model=" + _toml_string(argument[byte=8:]))
        elif include_inline_config and (argument.startswith("--config=") or argument.startswith("-c=")):
            result.append(argument)
        index += 1
    return result^
