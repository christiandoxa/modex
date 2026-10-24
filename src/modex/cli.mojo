from std.collections import List, Optional, Set
from std.pathlib import cwd

from .paths import absolute_path
from .sessions import SessionOptions


def unsigned_value(text: String) raises -> UInt64:
    var bytes = text.as_bytes()
    var position = 1 if text.startswith("+") else 0
    if position == len(bytes):
        raise Error("cannot parse integer from empty string")
    var result = UInt64(0)
    while position < len(bytes):
        var byte = bytes[position]
        if byte < 48 or byte > 57:
            raise Error("invalid digit found in string")
        var digit = UInt64(byte - 48)
        if result > (UInt64.MAX - digit) // 10:
            raise Error("number too large to fit in target type")
        result = result * 10 + digit
        position += 1
    return result


def session_help(command: String, executable: String = "modex") -> String:
    var prefix = executable + " session"
    if not command:
        return "Inspect shared Codex session metadata.\n\nUsage: " + prefix + " <COMMAND>\n\nCommands:\n  list     List shared Codex sessions\n  current  List shared Codex sessions started from the current directory\n  resume   Resume a shared Codex session by unique partial or full id\n  help     Print this message or the help of the given subcommand(s)\n\nOptions:\n  -h, --help  Print help\n\nExamples:\n  " + prefix + " list\n  " + prefix + " list --json\n  " + prefix + " list --id-only\n  " + prefix + " list --resume-command\n  " + prefix + " list --parent-only\n  " + prefix + " list --profile main --query triage\n  " + prefix + " current\n  " + prefix + " current --resume-command\n  " + prefix + " current --limit 20\n  " + prefix + " resume 1234abcd\n"
    if command == "resume":
        return "Resume a shared Codex session by unique partial or full id\n\nUsage: " + prefix + " resume <ID>\n\nArguments:\n  <ID>  Unique full or partial shared Codex session id\n\nOptions:\n  -h, --help  Print help\n"
    var title = String("List shared Codex sessions")
    if command == "current":
        title += " started from the current directory"
    return title + "\n\nUsage: " + prefix + " " + command + " [OPTIONS]\n\nOptions:\n      --json               Emit machine-readable JSON\n      --id-only            Print only full session ids, one per line\n      --resume-command     Print a resume command for each matching session\n      --profile <NAME>     Show only sessions attached to this profile binding\n      --query <TEXT>       Show only sessions whose id, thread name, cwd, profile, or path contains this text\n      --limit <N>          Limit the number of sessions shown after sorting newest first\n      --include-subagents  Include spawned subagent sessions. This is the default; kept for compatibility\n      --parent-only        Show only resumable parent sessions\n  -h, --help               Print help\n"


def session_cli_error(message: String, usage: String = "") -> Error:
    var output = String("error: ") + message
    if usage:
        output += "\n\nUsage: " + usage
    return Error(output + "\n\nFor more information, try '--help'.")


def option_label(name: String) -> String:
    if name == "--profile":
        return name + " <NAME>"
    if name == "--query":
        return name + " <TEXT>"
    if name == "--limit":
        return name + " <N>"
    if name == "--cwd":
        return name + " <PATH>"
    return name


def parse_session_options(args: List[String]) raises -> SessionOptions:
    var executable_parts = args[0].split("/")
    var executable = String(executable_parts[len(executable_parts) - 1])
    var usage = executable + " session"
    if len(args) < 3:
        raise Error(session_help("", executable))
    if args[2] == "--help" or args[2] == "-h":
        return SessionOptions(False, "help", None, "", None, "", False)
    if args[2] == "help":
        var command = args[3] if len(args) > 3 else String()
        if command and command != "list" and command != "current" and command != "resume":
            raise session_cli_error("unrecognized subcommand '" + command + "'", usage + " <COMMAND>")
        return SessionOptions(False, "help", None, command, None, "", False)
    if args[2] != "list" and args[2] != "current" and args[2] != "resume":
        raise session_cli_error("unrecognized subcommand '" + args[2] + "'", usage + " <COMMAND>")
    usage += " " + args[2]
    if args[2] == "resume":
        if len(args) == 4 and (args[3] == "--help" or args[3] == "-h"):
            return SessionOptions(False, "help", None, "resume", None, "", False)
        if len(args) == 3:
            raise session_cli_error("the following required arguments were not provided:\n  <ID>", usage + " <ID>")
        return SessionOptions(False, "resume", None, "", None, "", False)
    var current = args[2] == "current"
    var output = String("text")
    var profile = Optional[String]()
    var query = String()
    var limit = Optional[UInt64]()
    var directory = String(cwd()) if current else String()
    var parent_only = False
    var seen = Set[String]()
    var conflict_first = String()
    var conflict_second = String()
    var parent_flag = String()
    var index = 3
    while index < len(args):
        var pieces = args[index].split("=", maxsplit=1)
        var name = String(pieces[0])
        if name == "--help" or name == "-h":
            return SessionOptions(current, "help", None, args[2], None, "", False)
        var value_option = name == "--profile" or name == "--query" or name == "--limit" or (current and name == "--cwd")
        var switch_option = name == "--json" or name == "--id-only" or name == "--resume-command" or name == "--parent-only" or name == "--include-subagents"
        if not value_option and not switch_option:
            raise session_cli_error("unexpected argument '" + name + "' found", usage + " [OPTIONS]")
        if name in seen:
            raise session_cli_error("the argument '" + option_label(name) + "' cannot be used multiple times", usage + " [OPTIONS]")
        seen.add(name)
        if switch_option and len(pieces) != 1:
            raise session_cli_error("unexpected value '" + String(pieces[1]) + "' for '" + name + "' found; no more were expected", usage + " " + name)
        if name == "--json" or name == "--id-only" or name == "--resume-command":
            if output != "text":
                if not conflict_first:
                    conflict_first = "--" + output
                    conflict_second = name
            else:
                output = String(name[byte=2:])
        elif name == "--parent-only" or name == "--include-subagents":
            if parent_flag and not conflict_first:
                conflict_first = parent_flag
                conflict_second = name
            parent_flag = name
            parent_only = name == "--parent-only"
        else:
            var value: String
            if len(pieces) == 2:
                value = String(pieces[1])
            else:
                index += 1
                if index < len(args) and args[index].startswith("-") and not args[index].startswith("--") and args[index] != "-h":
                    raise session_cli_error("unexpected argument '" + args[index] + "' found", usage + " [OPTIONS]")
                if index >= len(args) or args[index].startswith("-"):
                    raise session_cli_error("a value is required for '" + option_label(name) + "' but none was supplied")
                value = args[index]
            if name == "--profile":
                profile = value^
            elif name == "--query":
                query = value^
            elif name == "--limit":
                try:
                    limit = unsigned_value(value)
                except error:
                    raise session_cli_error("invalid value '" + value + "' for '--limit <N>': " + String(error))
            else:
                directory = absolute_path(value)
        index += 1
    if conflict_first:
        raise session_cli_error("the argument '" + conflict_first + "' cannot be used with '" + conflict_second + "'", usage + " " + conflict_first)
    return SessionOptions(current, output^, profile^, query^, limit^, directory^, parent_only)
