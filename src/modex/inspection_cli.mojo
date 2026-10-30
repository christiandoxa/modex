"""Inspection-command help and argument validation before runtime dispatch."""

from std.collections import List

from .cli import argument_name, session_cli_error, similar_names
from .text import unsigned_value


def _inspection_prefix(command: String, executable: String) -> String:
    # shortcut: main drops trailing argv0 components; upgrade when it passes raw argv0.
    return command if not executable else executable + " " + command


def inspection_usage(command: String, executable: String) -> String:
    return _inspection_prefix(command, executable) + ("" if command == "current" else " [OPTIONS]")


def inspection_help(command: String, executable: String) -> String:
    var usage = "\n\nUsage: " + inspection_usage(command, executable) + "\n\nOptions:\n"
    if command == "current":
        return "Show the active profile and its CODEX_HOME details." + usage + "  -h, --help  Print help\n"
    if command == "info":
        return "Summarize Prodex version, profiles, runtime policy, logs, and secret backend." + usage + "      --json    Emit machine-readable JSON\n      --tokens  Include token usage totals parsed from recent runtime logs\n  -h, --help    Print help\n"
    if command == "doctor":
        return "Inspect local state, Codex resolution, quota readiness, and runtime logs." + usage + "      --quota                        Also probe each profile's quota endpoint\n      --runtime                      Also summarize runtime proxy state and recent logs from the configured log directory\n      --install                      Also check install/runtime prerequisites without mutating local state\n      --repair-import-auth-journals  Recover orphaned profile import auth rollback journals before reporting\n      --repair-session-index         Explicitly run Codex's full active and archived thread-index repair\n      --tail-bytes <BYTES>           Bytes of runtime log tail to inspect for --runtime/--json [default: 131072]\n      --suggest-policy               Suggest policy.toml tuning snippets from recent runtime markers\n      --json                         Emit machine-readable JSON output for --runtime diagnostics\n      --bundle [<PATH>]              Emit a redacted diagnostic bundle as JSON. Omit PATH or use '-' for stdout\n      --redacted                     Required for --bundle; secret values are never emitted\n  -h, --help                         Print help\n\nExamples:\n  " + executable + " doctor\n  " + executable + " doctor --install\n  " + executable + " doctor --quota\n  " + executable + " doctor --runtime\n  " + executable + " doctor --runtime --json\n  " + executable + " doctor --bundle ./prodex-doctor.json --redacted\n  " + executable + " doctor --repair-session-index\n"
    return "Monitor profiles, quota resets, token efficiency, and Prodex resource usage." + usage + "      --once                Render one snapshot instead of the live dashboard\n      --interval <SECONDS>  Resource sampling interval in seconds [default: 1]\n  -h, --help                Print help\n"


def inspection_flags(command: String) -> List[String]:
    if command == "info":
        return [String("--json"), "--tokens", "--help"]
    if command == "status":
        return [String("--once"), "--interval", "--help"]
    if command == "doctor":
        return [String("--quota"), "--runtime", "--install", "--repair-import-auth-journals", "--repair-session-index", "--tail-bytes", "--suggest-policy", "--json", "--bundle", "--redacted", "--help"]
    return [String("--help")]


def inspection_label(name: String) -> String:
    if name == "--interval": return name + " <SECONDS>"
    if name == "--tail-bytes": return name + " <BYTES>"
    if name == "--bundle": return name + " [<PATH>]"
    return name


def inspection_unknown(argument: String, command: String, executable: String, seen: List[String], literal: Bool = False) -> Error:
    var flag = not literal and argument.startswith("-") and argument != "-"
    var name = argument_name(argument) if flag else argument
    var message = "unexpected argument '" + name + "' found"
    var suggestion = String()
    if flag and name.startswith("--"):
        var choices = List[String]()
        for choice in inspection_flags(command):
            choices.append(String(choice[byte=2:]))
        var candidates = similar_names(String(name[byte=2:]), choices)
        if candidates:
            suggestion = "--" + candidates[len(candidates) - 1]
            message += "\n\n  tip: a similar argument exists: '" + suggestion + "'"
    var usage = inspection_usage(command, executable)
    if flag and (seen or suggestion):
        usage = _inspection_prefix(command, executable)
        for option in seen:
            usage += " " + inspection_label(option)
        if suggestion and suggestion not in seen:
            usage += " " + inspection_label(suggestion)
    return session_cli_error(message, usage)


def inspection_value_error(name: String, value: String, command: String, executable: String, seen: List[String]) -> Error:
    var usage = _inspection_prefix(command, executable)
    if command == "doctor":
        usage += " " + name
        return session_cli_error("unexpected value '" + value + "' for '" + name + "' found; no more were expected", usage)
    var boolean_seen = "--json" in seen or "--tokens" in seen or "--once" in seen
    if name == "--help" or not boolean_seen:
        usage += " " + name
    if boolean_seen:
        usage += " <--json|--tokens>" if command == "info" else " <--once|--interval <SECONDS>>"
    return session_cli_error("unexpected value '" + value + "' for '" + name + "' found; no more were expected", usage)


def inspection_help_requested(args: List[String], executable: String) raises -> Bool:
    var command = args[1]
    var flags = inspection_flags(command)
    var seen = List[String]()
    var literal = False
    var index = 2
    while index < len(args):
        var argument = args[index]
        if not literal and (argument == "--help" or (argument.startswith("-h") and not argument.startswith("--"))):
            return True
        if not literal and argument == "--":
            literal = True
            index += 1
            continue
        var name = argument_name(argument)
        if literal or name not in flags:
            raise inspection_unknown(argument, command, executable, seen, literal)
        if name not in ["--interval", "--tail-bytes", "--bundle"] and "=" in argument:
            raise inspection_value_error(name, String(argument.split("=", maxsplit=1)[1]), command, executable, seen)
        if name in seen:
            raise session_cli_error("the argument '" + inspection_label(name) + "' cannot be used multiple times", inspection_usage(command, executable))
        if name == "--bundle":
            if "=" in argument:
                if not String(argument.split("=", maxsplit=1)[1]):
                    raise session_cli_error("a value is required for '--bundle [<PATH>]' but none was supplied")
            elif index + 1 < len(args) and args[index + 1] == "":
                raise session_cli_error("a value is required for '--bundle [<PATH>]' but none was supplied")
            elif index + 1 < len(args) and args[index + 1] != "--" and (args[index + 1] == "-" or not args[index + 1].startswith("-")):
                index += 1
        elif name == "--tail-bytes":
            var value: String
            if "=" in argument:
                value = String(argument.split("=", maxsplit=1)[1])
            else:
                if index + 2 < len(args) and args[index + 1] == "--":
                    raise inspection_unknown(args[index + 2], command, executable, seen, True)
                if index + 1 >= len(args) or args[index + 1] == "--" or argument_name(args[index + 1]) in flags or args[index + 1].startswith("-h"):
                    raise session_cli_error("a value is required for '--tail-bytes <BYTES>' but none was supplied")
                index += 1
                value = args[index]
                if value.startswith("-") and value != "-":
                    raise inspection_unknown(value, command, executable, seen)
            var parsed: UInt64
            try:
                parsed = unsigned_value(value)
            except error:
                raise session_cli_error("invalid value '" + value + "' for '--tail-bytes <BYTES>': " + String(error))
        elif name == "--interval":
            var value: String
            if "=" in argument:
                value = String(argument.split("=", maxsplit=1)[1])
            else:
                if index + 1 < len(args) and args[index + 1] == "--" and index + 2 < len(args):
                    raise inspection_unknown(args[index + 2], command, executable, seen, True)
                if index + 1 >= len(args) or args[index + 1] == "--" or argument_name(args[index + 1]) in flags or args[index + 1].startswith("-h"):
                    raise session_cli_error("a value is required for '--interval <SECONDS>' but none was supplied")
                index += 1
                value = args[index]
                if value.startswith("-") and value != "-":
                    raise inspection_unknown(value, command, executable, seen)
            var parsed: UInt64
            try:
                parsed = unsigned_value(value)
            except error:
                raise session_cli_error("invalid value '" + value + "' for '--interval <SECONDS>': " + String(error))
            if parsed < 1 or parsed > 60:
                raise session_cli_error("invalid value '" + value + "' for '--interval <SECONDS>': " + String(parsed) + " is not in 1..=60")
        seen.append(name)
        index += 1
    if command == "doctor":
        var missing = List[String]()
        if ("--json" in seen or "--suggest-policy" in seen) and "--runtime" not in seen:
            missing.append("--runtime")
        if "--bundle" in seen and "--redacted" not in seen:
            missing.append("--redacted")
        if "--redacted" in seen and "--bundle" not in seen:
            missing.append("--bundle")

        if "--json" in seen and "--bundle" in seen:
            var conflict_usage = _inspection_prefix(command, executable)
            if "--runtime" not in seen:
                conflict_usage += " --runtime"
            for name in seen:
                if name != "--bundle":
                    conflict_usage += " " + inspection_label(name)
            raise session_cli_error("the argument '--json' cannot be used with '--bundle [<PATH>]'", conflict_usage)

        if missing:
            var message = "the following required arguments were not provided:"
            for name in missing:
                message += "\n  " + inspection_label(name)
            var error_usage = _inspection_prefix(command, executable)
            var combined_json_bundle = "--runtime" in missing and "--bundle" in missing and "--json" in seen and "--redacted" in seen
            if "--runtime" in missing:
                error_usage += " --runtime"
            for name in seen:
                if combined_json_bundle and name == "--json":
                    continue
                error_usage += " " + inspection_label(name)
            if "--redacted" in missing:
                error_usage += " --redacted"
            if "--bundle" in missing:
                error_usage += " " + inspection_label("--bundle")
            if combined_json_bundle:
                error_usage += " --json"
            raise session_cli_error(message, error_usage)
    return False
