"""Super option extraction and launch-boundary validation."""

from std.collections import List

from .cli import session_cli_error
from .json import quote_json
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


def _validate_unsigned_value(name: String, value: String, parsed_value: String, clap_diagnostic: Bool) raises:
    try:
        _ = unsigned_value(parsed_value)
    except error:
        raise _typed_value_error(name, value, String(error), clap_diagnostic)


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
    if name in ["--base-url", "--sub-agent-url", "--url"] and not _valid_http_url(value):
        raise Error("invalid " + name + ": expected an absolute http(s) URL with host and no credentials, query, or fragment")
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
        raise Error("only --cli agy is retained; use --provider gemini|copilot|kiro for other providers")
    if name == "--sub-agent-model" and not trim_text(value):
        raise _typed_value_error(name, value, "--sub-agent-model must be nonempty", clap_diagnostic)
    if name == "--sub-agent-model-reasoning-effort":
        var effort = ascii_lower(trim_text(value))
        if effort not in ["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"]:
            raise _typed_value_error(name, value, "invalid sub-agent reasoning effort: expected none, minimal, low, medium, high, xhigh, max, or ultra, got " + quote_json(effort), clap_diagnostic)
        return effort^
    if name == "--web-search" and value not in ["disabled", "cached", "indexed", "live"]:
        raise Error("invalid --web-search: supported values are disabled, cached, indexed, live")
    if name == "--current-time-clock-source" and value not in ["system", "external"]:
        raise Error("invalid --current-time-clock-source: supported values are system, external")
    if name in ["--context-window", "--auto-compact-token-limit", "--rollout-budget-tokens", "--current-time-reminder-interval"]:
        _validate_unsigned_value(name, value, value, clap_diagnostic)
    if name == "--rollout-budget-reminders":
        for threshold in value.split(","):
            _validate_unsigned_value(name, value, String(threshold), clap_diagnostic)
    return value


def parse_super_arguments(args: List[String], executable: String) raises -> SuperOptions:
    # shortcut: full clap diagnostics and value normalization remain incomplete; finish them before widening the guarded Super launch.
    var options = SuperOptions([], [], [], False)
    var positional = False
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
    return options^


def validate_super_options(options: SuperOptions) raises:
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
        if argument in ["--add-dir", "--enable", "--disable", "--thread-source"]:
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


def run_super(options: SuperOptions) raises -> Int:
    validate_super_options(options)
    var supported = options.value("--provider") == "deepseek" and options.has("--no-presidio") and options.has("--no-sub-agent") and options.has("--base-url")
    for name in options.names:
        supported = supported and name in ["--provider", "--no-presidio", "--no-sub-agent", "--base-url", "--api-key", "--model", "--profile", "--skip-quota-check", "--context-window", "--auto-compact-token-limit", "--full-access", "--no-proxy", "--dry-run"]
    if supported and _supported_exec_arguments(options.codex_args):
        var prompt = List[String]()
        for index in range(1, len(options.codex_args)):
            prompt.append(options.codex_args[index])
        var context_window = unsigned_value(options.value("--context-window")) if options.has("--context-window") else UInt64(0)
        var compact_limit = unsigned_value(options.value("--auto-compact-token-limit")) if options.has("--auto-compact-token-limit") else UInt64(0)
        return run_clean_deepseek_super(options.value("--model"), options.value("--base-url"), options.value("--api-key"), prompt, context_window, compact_limit, options.value("--profile"), options.has("--profile"), options.has("--model"), options.has("--api-key"), options.has("--dry-run"))
    raise Error("Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable")
