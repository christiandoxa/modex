"""Super option extraction and launch-boundary validation."""

from std.collections import List

from .cli import session_cli_error
from .text import trim_text, unsigned_value


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


def _provider(value: String) raises -> String:
    var provider = trim_text(value).lower()
    if provider == "claude": provider = "anthropic"
    if provider == "github-copilot" or provider == "github_copilot": provider = "copilot"
    if provider not in ["anthropic", "copilot", "deepseek", "gemini", "kiro"]:
        raise Error("invalid --provider: supported values are anthropic, copilot, deepseek, gemini, kiro, got \"" + provider + "\"")
    return provider^


def _validate_value(name: String, value: String) raises -> String:
    if name == "--provider": return _provider(value)
    if name == "--cli" and value != "agy":
        raise Error("only --cli agy is retained; use --provider gemini|copilot|kiro for other providers")
    if name == "--sub-agent-model" and not trim_text(value):
        raise Error("--sub-agent-model must be nonempty")
    if name == "--sub-agent-model-reasoning-effort" and value not in ["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"]:
        raise Error("invalid sub-agent reasoning effort")
    if name == "--web-search" and value not in ["disabled", "cached", "indexed", "live"]:
        raise Error("invalid --web-search: supported values are disabled, cached, indexed, live")
    if name == "--current-time-clock-source" and value not in ["system", "external"]:
        raise Error("invalid --current-time-clock-source: supported values are system, external")
    if name in ["--context-window", "--auto-compact-token-limit", "--rollout-budget-tokens", "--current-time-reminder-interval"]:
        _ = unsigned_value(value)
    if name == "--sub-agent-max-concurrency":
        var count = unsigned_value(value)
        if count < 1 or count > 64:
            raise Error("maximum active sub-agents must be between 1 and 64")
    if name == "--rollout-budget-reminders":
        for threshold in value.split(","):
            _ = unsigned_value(String(threshold))
    return value


def parse_super_arguments(args: List[String], executable: String) raises -> SuperOptions:
    # shortcut: full clap diagnostics and value normalization remain incomplete; finish them before enabling Super startup.
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
                if index + 1 == len(args) or args[index + 1] == "--" or _value_option(_name(args[index + 1])) or _switch_option(_name(args[index + 1])):
                    raise Error(name + " requires a value")
                index += 1
                value = args[index]
            value = _validate_value(name, value)
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


def run_super(options: SuperOptions) raises:
    validate_super_options(options)
    raise Error("Super startup is not implemented: secure temporary overlays, Smart Context initialization, and Codex launch supervision remain unavailable")
