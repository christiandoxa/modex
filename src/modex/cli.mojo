from std.collections import List, Optional, Set
from std.pathlib import cwd

from .paths import absolute_path
from .sessions import SessionOptions


def unsigned_value(text: String) raises -> UInt64:
    var bytes = text.as_bytes()
    var position = 1 if text.startswith("+") else 0
    if position == len(bytes):
        raise Error("expected a nonnegative integer for --limit")
    var result = UInt64(0)
    while position < len(bytes):
        var byte = bytes[position]
        if byte < 48 or byte > 57:
            raise Error("invalid nonnegative integer for --limit")
        var digit = UInt64(byte - 48)
        if result > (UInt64.MAX - digit) // 10:
            raise Error("--limit is out of range")
        result = result * 10 + digit
        position += 1
    return result


def parse_session_options(args: List[String]) raises -> SessionOptions:
    if len(args) < 3 or (args[2] != "list" and args[2] != "current"):
        raise Error("session list/current inspection requires a supported subcommand")
    var current = args[2] == "current"
    var output = String("text")
    var profile = Optional[String]()
    var query = String()
    var limit = Optional[UInt64]()
    var directory = String(cwd()) if current else String()
    var parent_only = False
    var seen = Set[String]()
    var index = 3
    while index < len(args):
        var pieces = args[index].split("=", maxsplit=1)
        var name = String(pieces[0])
        if name in seen:
            raise Error("an argument was supplied more than once")
        seen.add(name)
        if name == "--json" or name == "--id-only" or name == "--resume-command":
            if output != "text" or len(pieces) != 1:
                raise Error("--json, --id-only, and --resume-command cannot be combined or take values")
            output = String(name[byte=2:])
        elif name == "--parent-only" or name == "--include-subagents":
            if len(pieces) != 1 or ("--parent-only" in seen and "--include-subagents" in seen):
                raise Error("--parent-only and --include-subagents cannot be combined or take values")
            parent_only = name == "--parent-only"
        elif name == "--profile" or name == "--query" or name == "--limit" or (current and name == "--cwd"):
            var value: String
            if len(pieces) == 2:
                value = String(pieces[1])
            else:
                index += 1
                if index >= len(args) or args[index].startswith("-"):
                    raise Error("an option requires a value")
                value = args[index]
            if name == "--profile":
                profile = value^
            elif name == "--query":
                query = value^
            elif name == "--limit":
                limit = unsigned_value(value)
            else:
                directory = absolute_path(value)
        else:
            raise Error("unsupported session inspection argument")
        index += 1
    return SessionOptions(current, output^, profile^, query^, limit^, directory^, parent_only)
