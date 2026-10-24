"""Inspection-command help and argument validation before runtime dispatch."""

from std.collections import List

from .cli import argument_name, session_cli_error, similar_names
from .text import unsigned_value


def inspection_usage(command: String, executable: String) -> String:
    return executable + " " + command + ("" if command == "current" else " [OPTIONS]")


def inspection_help(command: String, executable: String) -> String:
    var usage = "\n\nUsage: " + inspection_usage(command, executable) + "\n\nOptions:\n"
    if command == "current":
        return "Show the active profile and its CODEX_HOME details." + usage + "  -h, --help  Print help\n"
    if command == "info":
        return "Summarize Prodex version, profiles, runtime policy, logs, and secret backend." + usage + "      --json    Emit machine-readable JSON\n      --tokens  Include token usage totals parsed from recent runtime logs\n  -h, --help    Print help\n"
    return "Monitor profiles, quota resets, token efficiency, and Prodex resource usage." + usage + "      --once                Render one snapshot instead of the live dashboard\n      --interval <SECONDS>  Resource sampling interval in seconds [default: 1]\n  -h, --help                Print help\n"


def inspection_flags(command: String) -> List[String]:
    if command == "info":
        return [String("--json"), "--tokens", "--help"]
    if command == "status":
        return [String("--once"), "--interval", "--help"]
    return [String("--help")]


def inspection_label(name: String) -> String:
    return name + (" <SECONDS>" if name == "--interval" else "")


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
        usage = executable + " " + command
        for option in seen:
            usage += " " + inspection_label(option)
        if suggestion and suggestion not in seen:
            usage += " " + inspection_label(suggestion)
    return session_cli_error(message, usage)


def inspection_value_error(name: String, value: String, command: String, executable: String, seen: List[String]) -> Error:
    var usage = executable + " " + command
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
        if name != "--interval" and "=" in argument:
            raise inspection_value_error(name, String(argument.split("=", maxsplit=1)[1]), command, executable, seen)
        if name in seen:
            raise session_cli_error("the argument '" + inspection_label(name) + "' cannot be used multiple times", inspection_usage(command, executable))
        if name == "--interval":
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
    return False
