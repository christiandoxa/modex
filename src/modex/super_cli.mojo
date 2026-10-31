"""Super option extraction and launch-boundary validation."""

from std.collections import List, Span

from .cli import session_cli_error, similar_names
from .log_operational import valid_url_authority
from .super_launch import run_clean_deepseek_super
from .text import ascii_lower, trim_text, unsigned_value


@fieldwise_init
struct SuperOptions(Copyable):
    var names: List[String]
    var values: List[String]
    var codex_args: List[String]
    var help: Bool

    def has(self, name: String) -> Bool:
        return name in self.names

    def value(self, name: String) -> String:
        for index in range(len(self.names) - 1, -1, -1):
            if self.names[index] == name:
                return self.values[index]
        return ""


def _name(argument: String) -> String:
    var name = String(argument.split("=", maxsplit=1)[0])
    if name == "--local-model": return "--model"
    if name == "--local-context-window": return "--context-window"
    if name == "--local-auto-compact-token-limit": return "--auto-compact-token-limit"
    return name


def _value_option(name: String) -> Bool:
    return name in ["--provider", "--cli", "--api-key", "--sub-agent-provider", "--sub-agent-model", "--sub-agent-model-reasoning-effort", "--sub-agent-url", "--sub-agent-max-concurrency", "--model", "--profile", "--base-url", "--url", "--context-window", "--auto-compact-token-limit", "--tool", "--require-tool", "--web-search", "--rollout-budget-tokens", "--rollout-budget-reminders", "--rollout-budget-sampling-weight", "--rollout-budget-prefill-weight", "--current-time-reminder-interval", "--current-time-clock-source"]


def _switch_option(name: String) -> Bool:
    return name in ["--auto-rotate", "--no-auto-rotate", "--auto-redeem", "--skip-quota-check", "--dry-run", "--no-proxy", "--presidio", "--no-presidio", "--sub-agent", "--no-sub-agent", "--full-access", "--current-time-reminder", "--respect-system-proxy", "--no-respect-system-proxy"]


def _value_label(name: String) -> String:
    if name == "--profile": return name + " <NAME>"
    if name == "--base-url" or name == "--url" or name == "--sub-agent-url": return name + " <URL>"
    if name == "--sub-agent-provider" or name == "--provider": return name + " <PROVIDER>"
    if name == "--sub-agent-model" or name == "--model": return name + " <MODEL>"
    if name == "--sub-agent-model-reasoning-effort": return name + " <EFFORT>"
    if name == "--sub-agent-max-concurrency": return name + " <VALUE>"
    if name == "--tool" or name == "--require-tool": return name + " <TOOL>"
    if name == "--cli": return name + " <CLI>"
    if name == "--api-key": return name + " <KEY>"
    if name == "--context-window" or name == "--auto-compact-token-limit" or name == "--rollout-budget-tokens" or name == "--rollout-budget-reminders": return name + " <TOKENS>"
    if name == "--web-search": return name + " <MODE>"
    if name == "--rollout-budget-sampling-weight" or name == "--rollout-budget-prefill-weight": return name + " <WEIGHT>"
    if name == "--current-time-reminder-interval": return name + " <REQUESTS>"
    if name == "--current-time-clock-source": return name + " <SOURCE>"
    return name


def _missing_value_error(name: String) -> Error:
    var message = "a value is required for '" + _value_label(name) + "' but none was supplied"
    if name == "--cli":
        message += "\n  [possible values: agy]"
    elif name == "--web-search":
        message += "\n  [possible values: disabled, cached, indexed, live]"
    elif name == "--current-time-clock-source":
        message += "\n  [possible values: system, external]"
    return session_cli_error(message)


def _typed_value_error(name: String, value: String, reason: String, clap_diagnostic: Bool) -> Error:
    if clap_diagnostic:
        return session_cli_error("invalid value '" + value + "' for '" + _value_label(name) + "': " + reason)
    return Error(reason)


def _hex_codepoint(value: Int) -> String:
    var digits = String()
    var remaining = value
    while remaining > 0:
        var digit = remaining % 16
        digits = String(chr(48 + digit if digit < 10 else 87 + digit)) + digits
        remaining = remaining // 16
    return String("0") if not digits else digits^


def _debug_quoted(value: String) -> String:
    # shortcut: escape observed codepoints only; use Rust's Unicode tables before claiming full Debug parity.
    var output = String("\"")
    for character in value.codepoints():
        var code = Int(character)
        if code == 0: output += "\\0"
        elif code == 9: output += "\\t"
        elif code == 10: output += "\\n"
        elif code == 13: output += "\\r"
        elif code == 34: output += "\\\""
        elif code == 92: output += "\\\\"
        elif code < 32 or 127 <= code <= 159:
            output += "\\u{" + _hex_codepoint(code) + "}"
        elif code in [
            0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x180E,
            0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x2060,
            0xFE00, 0xFEFF,
        ] or 0x2066 <= code <= 0x2069:
            output += "\\u{" + _hex_codepoint(code) + "}"
        else:
            output += chr(code)
    return output + "\""


def _clap_value(value: String) -> String:
    var output = String()
    # States: ground, escape, CSI, OSC, control string, escape intermediate.
    var state = 0
    for character in value.codepoints():
        var code = Int(character)
        if code == 27:
            state = 1
            continue
        if code == 24 or code == 26:
            state = 0
            continue
        if state == 3 or state == 4:
            if state == 3 and code == 7: state = 0
            continue
        if state != 0 and code < 32:
            if code in [9, 10, 12, 13]:
                output += chr(code)
                state = 0
            continue
        if state == 1:
            if code == 91:
                state = 2
            elif code == 93:
                state = 3
            elif code == 80 or code == 88 or code == 94 or code == 95:
                state = 4
            elif 0x20 <= code <= 0x2F:
                state = 5
            elif 0x30 <= code <= 0x7E:
                state = 0
            continue
        if state == 2:
            if 0x40 <= code <= 0x7E: state = 0
            continue
        if state == 5:
            if 0x30 <= code <= 0x7E: state = 0
            continue
        if code == 127 or (code < 32 and code not in [9, 10, 12, 13]):
            continue
        output += chr(code)
    return output^


def _enum_value_error(name: String, value: String, choices: List[String], runtime_error: String, clap_diagnostic: Bool) -> Error:
    if not clap_diagnostic:
        return Error(runtime_error)
    if not value:
        return _missing_value_error(name)
    var message = "invalid value '" + _clap_value(value) + "' for '" + _value_label(name) + "'\n  [possible values: " + String(", ").join(choices) + "]"
    var matches = similar_names(value, choices)
    if matches:
        message += "\n\n  tip: a similar value exists: '" + matches[len(matches) - 1] + "'"
    return session_cli_error(message)


def _validate_unsigned_value(name: String, value: String, parsed_value: String, clap_diagnostic: Bool) raises:
    try:
        _ = unsigned_value(parsed_value)
    except error:
        raise _typed_value_error(name, value, String(error), clap_diagnostic)


def _valid_float_value(value: String) -> Bool:
    var bytes = value.as_bytes()
    var end = len(bytes)
    if end == 0:
        return False
    var index = 0
    if bytes[0] == 43 or bytes[0] == 45:
        index = 1
        if index == end:
            return False
    var special = ascii_lower(value)
    if index == 1:
        var signless = String(special[byte=1:])
        special = signless^
    if special in ["nan", "inf", "infinity"]:
        return True
    var digits = 0
    while index < end and Byte(48) <= bytes[index] and bytes[index] <= Byte(57):
        index += 1
        digits += 1
    if index < end and bytes[index] == 46:
        index += 1
        var fraction_start = index
        while index < end and Byte(48) <= bytes[index] and bytes[index] <= Byte(57):
            index += 1
        digits += index - fraction_start
    if digits == 0:
        return False
    if index < end and (bytes[index] == 69 or bytes[index] == 101):
        index += 1
        if index < end and (bytes[index] == 43 or bytes[index] == 45):
            index += 1
        var exponent_start = index
        while index < end and Byte(48) <= bytes[index] and bytes[index] <= Byte(57):
            index += 1
        if index == exponent_start:
            return False
    return index == end


def _valid_http_url(value: String) -> Bool:
    var scheme_end = value.find("://")
    if scheme_end < 0 or value.find("?") >= 0 or value.find("#") >= 0:
        return False
    var scheme = String(value[byte=:scheme_end]).lower()
    if scheme != "http" and scheme != "https":
        return False
    var authority_start = scheme_end + 3
    var authority_end = value.byte_length()
    for delimiter in ["/", "\\"]:
        var found = value.find(delimiter, authority_start)
        if found >= 0 and found < authority_end:
            authority_end = found
    var authority = String(value[byte=authority_start:authority_end])
    return authority.find("@") < 0 and valid_url_authority(authority)


def _url_validation_input(value: String) -> String:
    # Preserve plain-space compatibility without admitting control bytes downstream.
    var bytes = value.as_bytes()
    var start = 0
    var end = len(bytes)
    while start < end and bytes[start] == Byte(32):
        start += 1
    while end > start and bytes[end - 1] == Byte(32):
        end -= 1
    return String(value[byte=start:end])


def _has_url_control(value: String) -> Bool:
    var bytes = value.as_bytes()
    for index in range(len(bytes)):
        if bytes[index] < Byte(32) or bytes[index] == Byte(127):
            return True
    return False


def _known_optional_tool(value: String) -> Bool:
    var tool = ascii_lower(trim_text(value))
    return tool in [
        "rtk", "codebase-memory-mcp", "codebase-memory", "cbm",
        "playwright", "playwright-mcp", "ponytail", "presidio",
    ]


def _provider(value: String, clap_diagnostic: Bool) raises -> String:
    var provider = trim_text(value).lower()
    if provider == "claude": provider = "anthropic"
    if provider == "github-copilot" or provider == "github_copilot": provider = "copilot"
    if provider not in ["anthropic", "copilot", "deepseek", "gemini", "kiro"]:
        var error = "invalid --provider: supported values are anthropic, copilot, deepseek, gemini, kiro, got \"" + provider + "\""
        if clap_diagnostic:
            raise session_cli_error("invalid value '" + value + "' for '--provider <PROVIDER>': " + error)
        raise Error(error)
    return provider^


def _validate_value(name: String, value: String, clap_diagnostic: Bool) raises -> String:
    if name == "--provider": return _provider(value, clap_diagnostic)
    if name == "--sub-agent-provider":
        var provider = ascii_lower(trim_text(value))
        if provider in ["openai", "openai-responses", "openai_compatible", "openai-compatible"]: return "openai"
        if provider in ["anthropic", "claude"]: return "anthropic"
        if provider in ["copilot", "github-copilot", "github_copilot"]: return "copilot"
        if provider == "deepseek": return "deepseek"
        if provider in ["gemini", "google"]: return "gemini"
        if provider == "kiro": return "kiro"
        if provider in ["local", "local-openai", "local_openai"]: return "local"
        var reason = "invalid --sub-agent-provider: supported values are openai, anthropic, copilot, deepseek, gemini, kiro, local, got " + _debug_quoted(value)
        raise _typed_value_error(name, _clap_value(value), reason, clap_diagnostic)
    if name == "--sub-agent-url" and (
        _has_url_control(value) or not _valid_http_url(_url_validation_input(value))
    ):
        var display_value = value
        if clap_diagnostic:
            display_value = _clap_value(value)
        raise _typed_value_error(
            name, display_value,
            "invalid " + name + ": expected an absolute http(s) URL with host and no credentials, query, or fragment",
            clap_diagnostic,
        )
    if (name == "--tool" or name == "--require-tool") and not _known_optional_tool(value):
        raise _typed_value_error(name, value, "unknown optional tool " + value, clap_diagnostic)
    if name == "--sub-agent-max-concurrency":
        var parsed_value = trim_text(value)
        if parsed_value == "default": return parsed_value^
        if not parsed_value:
            raise _typed_value_error(name, value, "invalid maximum active sub-agents: expected default or an integer from 1 to 64", clap_diagnostic)
        var count = UInt64(0)
        var overflow = False
        for byte in parsed_value.as_bytes():
            if byte < 48 or byte > 57:
                raise _typed_value_error(name, value, "invalid maximum active sub-agents: expected default or an integer from 1 to 64", clap_diagnostic)
            var digit = UInt64(byte - 48)
            if not overflow:
                if count > 6553 or (count == 6553 and digit > 5):
                    overflow = True
                else:
                    count = count * 10 + digit
        if overflow:
            raise _typed_value_error(name, value, "invalid maximum active sub-agents: expected an integer from 1 to 64", clap_diagnostic)
        if count == 0 or count > 64:
            raise _typed_value_error(name, value, "maximum active sub-agents must be between 1 and 64", clap_diagnostic)
        return String(count)
    if name == "--cli" and value != "agy":
        raise _enum_value_error(name, value, [String("agy")], "only --cli agy is retained; use --provider gemini|copilot|kiro for other providers", clap_diagnostic)
    if name == "--sub-agent-model" and not trim_text(value):
        raise _typed_value_error(name, value, "--sub-agent-model must be nonempty", clap_diagnostic)
    if name == "--sub-agent-model-reasoning-effort":
        var effort = ascii_lower(trim_text(value))
        if effort not in ["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"]:
            raise _typed_value_error(name, _clap_value(value), "invalid sub-agent reasoning effort: expected none, minimal, low, medium, high, xhigh, max, or ultra, got " + _debug_quoted(effort), clap_diagnostic)
        return effort^
    if name == "--web-search":
        var mode = value if clap_diagnostic else ascii_lower(value)
        if mode not in ["disabled", "cached", "indexed", "live"]:
            raise _enum_value_error(name, value, [String("disabled"), "cached", "indexed", "live"], "expected disabled, cached, indexed, or live", clap_diagnostic)
        return mode^
    if name == "--current-time-clock-source":
        var source = value if clap_diagnostic else ascii_lower(value)
        if source not in ["system", "external"]:
            raise _enum_value_error(name, value, [String("system"), "external"], "expected system or external", clap_diagnostic)
        return source^
    if name in ["--rollout-budget-sampling-weight", "--rollout-budget-prefill-weight"]:
        if not value:
            raise _typed_value_error(name, value, "cannot parse float from empty string", clap_diagnostic)
        if not _valid_float_value(value):
            raise _typed_value_error(name, value, "invalid float literal", clap_diagnostic)
    if name in ["--context-window", "--auto-compact-token-limit", "--rollout-budget-tokens", "--current-time-reminder-interval"]:
        _validate_unsigned_value(name, value, value, clap_diagnostic)
    if name == "--rollout-budget-reminders":
        for threshold in value.split(","):
            var element = String(threshold)
            if clap_diagnostic:
                _validate_unsigned_value(name, element, element, clap_diagnostic)
            else:
                try:
                    _ = unsigned_value(element)
                except error:
                    raise Error("expected comma-separated unsigned integers")
    return value


def parse_super_arguments(args: List[String], executable: String) raises -> SuperOptions:
    # shortcut: full clap diagnostics and value normalization remain incomplete; finish them before widening the guarded Super launch.
    var options = SuperOptions([], [], [], False)
    var positional = False
    var pre_positional_option_count = -1
    var index = 2
    while index < len(args):
        var argument = args[index]
        if argument == "--":
            if positional:
                options.codex_args.append(argument)
            for remaining in range(index + 1, len(args)):
                options.codex_args.append(args[remaining])
            break
        if not positional and (argument == "--help" or argument == "-h"):
            options.help = True
            return options^
        var name = _name(argument)
        if not positional and (name == "-p" or name.startswith("-p")):
            if name.byte_length() > 2:
                argument = "--profile=" + String(argument[byte=2:])
            name = "--profile"
        var takes_value = _value_option(name)
        var switch = _switch_option(name)
        if not takes_value and not switch:
            if not positional:
                pre_positional_option_count = len(options.names)
            positional = True
            options.codex_args.append(argument)
            index += 1
            continue
        var pieces = argument.split("=", maxsplit=1)
        if switch and len(pieces) == 2:
            if positional:
                options.codex_args.append(argument)
                index += 1
                continue
            raise session_cli_error("unexpected value '" + String(pieces[1]) + "' for '" + name + "' found; no more were expected", executable + " super [OPTIONS] [CODEX_ARG]...")
        var value = String()
        if takes_value:
            if len(pieces) == 2:
                value = String(pieces[1])
            else:
                var missing = index + 1 == len(args)
                if not missing:
                    var next_argument = args[index + 1]
                    missing = next_argument == "--" or _value_option(_name(next_argument)) or _switch_option(_name(next_argument))
                    if not positional and (next_argument == "--help" or next_argument == "-h"):
                        missing = True
                if missing:
                    if positional:
                        raise Error(name + " requires a value")
                    raise _missing_value_error(name)
                index += 1
                value = args[index]
            value = _validate_value(name, value, not positional)
        if not positional and options.has(name) and name != "--tool" and name != "--require-tool" and name != "--rollout-budget-reminders":
            raise session_cli_error("the argument '" + name + "' cannot be used multiple times", executable + " super [OPTIONS] [CODEX_ARG]...")
        if not positional or name != "--profile" or not options.has(name):
            if positional and (name == "--auto-rotate" or name == "--no-auto-rotate"):
                var opposite = String("--auto-rotate" if name == "--no-auto-rotate" else "--no-auto-rotate")
                for candidate in range(len(options.names)):
                    if options.names[candidate] == opposite:
                        options.names[candidate] = name
            options.names.append(name)
            options.values.append(value)
        index += 1
    if pre_positional_option_count < 0:
        pre_positional_option_count = len(options.names)
    var parsed_options = SuperOptions([], [], [], False)
    for option_index in range(pre_positional_option_count):
        parsed_options.names.append(options.names[option_index])
        parsed_options.values.append(options.values[option_index])
    var has_codex_args = False
    if options.codex_args:
        has_codex_args = True
    _validate_super_argument_constraints(parsed_options, executable, has_codex_args)
    return options^


def _clap_super_conflict(options: SuperOptions, left: String, right: String, executable: String, has_codex_args: Bool) -> Error:
    var first = String()
    var second = String()
    for name in options.names:
        if name == left or name == right:
            first = name
            second = String(right if name == left else left)
            break
    var usage = executable + " super"
    for name in options.names:
        if name != second:
            usage += " " + _value_label(name)
    if has_codex_args:
        usage += " <CODEX_ARG>..."
    else:
        usage += " [CODEX_ARG]..."
    return session_cli_error(
        "the argument '" + _value_label(first) + "' cannot be used with '" + _value_label(second) + "'",
        usage,
    )


def _validate_super_argument_constraints(options: SuperOptions, executable: String, has_codex_args: Bool) raises:
    if options.has("--sub-agent") and options.has("--no-sub-agent"):
        raise _clap_super_conflict(options, "--sub-agent", "--no-sub-agent", executable, has_codex_args)
    if options.has("--provider") and options.has("--url"):
        raise _clap_super_conflict(options, "--provider", "--url", executable, has_codex_args)

    var missing = List[String]()
    var requires_provider = options.has("--api-key") and not options.has("--provider")
    var requires_provider_or_url = (
        (options.has("--context-window") or options.has("--auto-compact-token-limit"))
        and not options.has("--provider") and not options.has("--url")
    )
    requires_provider = requires_provider and not requires_provider_or_url
    if requires_provider:
        missing.append("--provider <PROVIDER>")
    if requires_provider_or_url:
        missing.append("<--provider <PROVIDER>|--url <URL>>")
    if missing:
        var usage = executable + " super"
        if requires_provider:
            usage += " --provider <PROVIDER>"
        for name in options.names:
            usage += " " + _value_label(name)
        if requires_provider_or_url:
            usage += " <--provider <PROVIDER>|--url <URL>>"
        if has_codex_args:
            usage += " <CODEX_ARG>..."
        else:
            usage += " [CODEX_ARG]..."
        raise session_cli_error(
            "the following required arguments were not provided:\n  " + "\n  ".join(missing),
            usage,
        )


def validate_super_options(options: SuperOptions) raises:
    for name in ["--base-url", "--url"]:
        if options.has(name) and not _valid_http_url(options.value(name)):
            raise Error("invalid " + name + ": expected an absolute http(s) URL with host and no credentials, query, or fragment")
    if options.has("--sub-agent") and options.has("--no-sub-agent"):
        raise Error("--sub-agent conflicts with --no-sub-agent")
    var details = False
    for name in ["--sub-agent-provider", "--sub-agent-model", "--sub-agent-model-reasoning-effort", "--sub-agent-url", "--sub-agent-max-concurrency"]:
        details = details or options.has(name)
    if details and not options.has("--sub-agent"):
        raise Error("sub-agent detail flags require explicit --sub-agent")
    if options.value("--sub-agent-provider") == "local" and not options.has("--sub-agent-url"):
        raise Error("local sub-agent provider requires --sub-agent-url")
    if options.has("--sub-agent-url") and options.value("--sub-agent-provider") != "local":
        raise Error("--sub-agent-url requires --sub-agent-provider local")
    for left, right in [("--auto-rotate", "--no-auto-rotate"), ("--presidio", "--no-presidio"), ("--provider", "--url"), ("--base-url", "--url"), ("--respect-system-proxy", "--no-respect-system-proxy")]:
        if options.has(left) and options.has(right):
            raise Error(left + " conflicts with " + right)
    if options.has("--no-presidio"):
        for index in range(len(options.names)):
            if options.names[index] == "--require-tool" and options.values[index] == "presidio":
                raise Error("--no-presidio conflicts with --require-tool presidio")
    if options.has("--api-key") and not options.has("--provider"):
        raise Error("--api-key requires --provider")
    if (options.has("--context-window") or options.has("--auto-compact-token-limit")) and not options.has("--provider") and not options.has("--url"):
        raise Error("context-window options require --provider or --url")
    if options.has("--sub-agent") and options.codex_args and options.codex_args[0] == "gui":
        raise Error("--sub-agent is unsupported with the Codex Desktop frontend")
    if options.has("--cli") and options.value("--cli") == "agy" and options.value("--provider") != "gemini":
        raise Error("--cli agy requires --provider gemini; use modex s gemini --cli agy")


def _supported_exec_arguments(arguments: List[String]) -> Bool:
    # shortcut: other Codex flags remain guarded until their launch effects are verified.
    if not arguments or arguments[0] != "exec":
        return False
    var index = 1
    var has_prompt = False
    while index < len(arguments):
        var argument = arguments[index]
        if argument == "--":
            return True
        if argument in ["--json", "--skip-git-repo-check", "--ephemeral", "--strict-config", "--worktree"]:
            index += 1
            continue
        if argument == "--reasoning-effort":
            if index + 1 < len(arguments):
                var value = arguments[index + 1]
                index += 2 if value and (not value.startswith("-") or value == "-") else 1
            else:
                index += 1
            continue
        if argument.startswith("--reasoning-effort="):
            index += 1
            continue
        if argument in ["--cd", "-C"]:
            if index + 1 >= len(arguments):
                return False
            var directory = arguments[index + 1]
            if not directory or (directory.startswith("-") and directory != "-"):
                return False
            index += 2
            continue
        if argument.startswith("--cd=") or (argument.startswith("-C") and argument.byte_length() > 2):
            index += 1
            continue
        if argument in ["--add-dir", "--enable", "--disable"]:
            if index + 1 >= len(arguments) or (arguments[index + 1].startswith("-") and arguments[index + 1] != "-"):
                index += 1
                continue
            var value = arguments[index + 1]
            if not value:
                return False
            index += 2
            continue
        if argument == "--thread-source":
            if index + 1 >= len(arguments):
                return False
            var value = arguments[index + 1]
            if not value or (value.startswith("-") and value != "-"):
                return False
            index += 2
            continue
        if argument.startswith("--add-dir=") or argument.startswith("--enable=") or argument.startswith("--disable=") or argument.startswith("--thread-source="):
            if argument.endswith("="):
                return False
            index += 1
            continue
        if argument in ["--output-last-message", "--output-schema", "-o", "--image", "-i"]:
            if index + 1 >= len(arguments):
                return False
            var value = arguments[index + 1]
            if not value or (value.startswith("-") and value != "-"):
                return False
            index += 2
            continue
        if argument.startswith("--output-last-message=") or argument.startswith("--output-schema=") or argument.startswith("--image=") or ((argument.startswith("-o") or argument.startswith("-i")) and argument.byte_length() > 2):
            index += 1
            continue
        if argument == "--color":
            if index + 1 >= len(arguments) or arguments[index + 1] not in ["auto", "always", "never"]:
                return False
            index += 2
            continue
        if argument in ["--color=auto", "--color=always", "--color=never"]:
            index += 1
            continue
        if (argument.startswith("-") and argument != "-") or has_prompt:
            return False
        has_prompt = True
        index += 1
    return True


def _rollout_budget_codex_arguments(options: SuperOptions) raises -> List[String]:
    var arguments = List[String]()
    if not options.has("--rollout-budget-tokens"):
        return arguments^
    var limit = unsigned_value(options.value("--rollout-budget-tokens"))
    if limit <= 1:
        return arguments^
    var reminders = List[UInt64]()
    for index in range(len(options.names)):
        if options.names[index] == "--rollout-budget-reminders":
            for value in options.values[index].split(","):
                var reminder = unsigned_value(String(value))
                if reminder > 0 and reminder < limit:
                    reminders.append(reminder)
    if not reminders:
        for percent in [UInt64(75), UInt64(50), UInt64(25)]:
            var reminder = UInt64.MAX // 100
            if limit <= UInt64.MAX // percent:
                reminder = limit * percent // 100
            if reminder > 0 and reminder < limit:
                reminders.append(reminder)
        if not reminders:
            reminders.append(limit - 1)
    sort(Span(reminders), lambda (left: UInt64, right: UInt64) -> Bool: left > right)
    var serialized = String()
    var previous = UInt64.MAX
    for reminder in reminders:
        if reminder != previous:
            if serialized:
                serialized += ","
            serialized += String(reminder)
            previous = reminder
    arguments.append("-c")
    arguments.append("features.rollout_budget.enabled=true")
    arguments.append("-c")
    arguments.append("features.rollout_budget.limit_tokens=" + String(limit))
    arguments.append("-c")
    arguments.append("features.rollout_budget.reminder_at_remaining_tokens=[" + serialized + "]")
    return arguments^


def run_super(options: SuperOptions) raises -> Int:
    validate_super_options(options)
    var supported = options.value("--provider") == "deepseek" and options.has("--no-presidio") and options.has("--no-sub-agent") and options.has("--base-url")
    for name in options.names:
        supported = supported and name in ["--provider", "--no-presidio", "--no-sub-agent", "--base-url", "--api-key", "--model", "--profile", "--skip-quota-check", "--context-window", "--auto-compact-token-limit", "--full-access", "--no-proxy", "--dry-run", "--rollout-budget-tokens", "--rollout-budget-reminders"]
    if supported and _supported_exec_arguments(options.codex_args):
        var prompt = _rollout_budget_codex_arguments(options)
        for index in range(1, len(options.codex_args)):
            prompt.append(options.codex_args[index])
        var context_window = unsigned_value(options.value("--context-window")) if options.has("--context-window") else UInt64(0)
        var compact_limit = unsigned_value(options.value("--auto-compact-token-limit")) if options.has("--auto-compact-token-limit") else UInt64(0)
        return run_clean_deepseek_super(options.value("--model"), options.value("--base-url"), options.value("--api-key"), prompt, context_window, compact_limit, options.value("--profile"), options.has("--profile"), options.has("--model"), options.has("--api-key"), options.has("--dry-run"))
    raise Error("Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable")
