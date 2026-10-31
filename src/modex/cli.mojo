from std.collections import List, Optional

from .sessions import SessionOptions
from .text import unsigned_value


def session_help(command: String, executable: String = "modex") -> String:
    var prefix = executable + " session"
    if not command:
        return "Inspect shared Codex session metadata.\n\nUsage: " + prefix + " <COMMAND>\n\nCommands:\n  list     List shared Codex sessions\n  current  List shared Codex sessions started from the current directory\n  resume   Resume a shared Codex session by unique partial or full id\n  help     Print this message or the help of the given subcommand(s)\n\nOptions:\n  -h, --help  Print help\n\nExamples:\n  " + prefix + " list\n  " + prefix + " list --json\n  " + prefix + " list --id-only\n  " + prefix + " list --resume-command\n  " + prefix + " list --parent-only\n  " + prefix + " list --profile main --query triage\n  " + prefix + " current\n  " + prefix + " current --resume-command\n  " + prefix + " current --limit 20\n  " + prefix + " resume 1234abcd\n"
    if command == "resume":
        return "Resume a shared Codex session by unique partial or full id\n\nUsage: " + prefix + " resume <ID>\n\nArguments:\n  <ID>  Unique full or partial shared Codex session id\n\nOptions:\n  -h, --help  Print help\n"
    if command == "help":
        return "Print this message or the help of the given subcommand(s)\n\nUsage: " + prefix + " help [COMMAND]...\n\nArguments:\n  [COMMAND]...  Print help for the subcommand(s)\n"
    var title = String("List shared Codex sessions")
    if command == "current":
        title += " started from the current directory"
    return title + "\n\nUsage: " + prefix + " " + command + " [OPTIONS]\n\nOptions:\n      --json               Emit machine-readable JSON\n      --id-only            Print only full session ids, one per line\n      --resume-command     Print a resume command for each matching session\n      --profile <NAME>     Show only sessions attached to this profile binding\n      --query <TEXT>       Show only sessions whose id, thread name, cwd, profile, or path contains this text\n      --limit <N>          Limit the number of sessions shown after sorting newest first\n      --include-subagents  Include spawned subagent sessions. This is the default; kept for compatibility\n      --parent-only        Show only resumable parent sessions\n  -h, --help               Print help\n"


def session_cli_error(message: String, usage: String = "") -> Error:
    var output = String("error: ") + message
    if usage:
        output += "\n\nUsage: " + usage
    return Error(output + "\n\nFor more information, try '--help'.\n")


def parse_update_help_arguments(args: List[String], executable: String) raises -> Bool:
    var usage = executable + " update"
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
        if not literal and name == "--help" and argument.startswith("--help="):
            var value = String(argument[byte=7:])
            raise session_cli_error(
                "unexpected value '" + value + "' for '--help' found; no more were expected",
                usage + " --help",
            )
        var message = "unexpected argument '" + name + "' found"
        var suggestion = String()
        if not literal and name.startswith("--"):
            var choices = List[String]()
            choices.append("help")
            var matches = similar_names(String(name[byte=2:]), choices)
            if matches:
                suggestion = "--" + matches[len(matches) - 1]
                message += "\n\n  tip: a similar argument exists: '" + suggestion + "'"
        var error_usage = usage + (" " + suggestion if suggestion else "")
        raise session_cli_error(message, error_usage)
    return False


def logout_help_requested(args: List[String], executable: String) raises -> Bool:
    var usage = executable + " logout [OPTIONS] [NAME]"
    var help_index = -1
    var help_value = String()
    var has_help_value = False
    var literal = False
    for index in range(2, len(args)):
        var argument = args[index]
        if not literal and (argument == "--help" or (argument.startswith("-h") and not argument.startswith("--"))):
            help_index = index
            break
        if not literal and argument.startswith("--help="):
            help_index = index
            help_value = String(argument[byte=7:])
            has_help_value = True
            break
        if not literal and argument == "--":
            literal = True
    if help_index < 0:
        return False

    var profile_seen = False
    var positional_seen = False
    literal = False
    var index = 2
    while index < help_index:
        var argument = args[index]
        if not literal and argument == "--":
            literal = True
            index += 1
            continue
        if not literal and (argument == "--profile" or argument == "-p"):
            if profile_seen:
                raise session_cli_error("the argument '--profile <NAME>' cannot be used multiple times", usage)
            if index + 1 >= help_index or (args[index + 1].startswith("-") and args[index + 1] != "-"):
                raise session_cli_error("a value is required for '--profile <NAME>' but none was supplied")
            profile_seen = True
            index += 2
            continue
        if not literal and (argument.startswith("--profile=") or (argument.startswith("-p") and not argument.startswith("--") and argument != "-p")):
            if profile_seen:
                raise session_cli_error("the argument '--profile <NAME>' cannot be used multiple times", usage)
            profile_seen = True
            index += 1
            continue
        if not literal and argument.startswith("-") and argument != "-":
            var name = argument_name(argument)
            var message = "unexpected argument '" + name + "' found"
            if name.startswith("-"):
                message += "\n\n  tip: to pass '" + name + "' as a value, use '-- " + name + "'"
            raise session_cli_error(message, usage)
        if positional_seen:
            raise session_cli_error("unexpected argument '" + argument + "' found", usage)
        positional_seen = True
        index += 1

    if has_help_value:
        raise session_cli_error(
            "unexpected value '" + help_value + "' for '--help' found; no more were expected",
            executable + " logout --help [NAME]",
        )
    return True


def quota_help_requested(args: List[String], executable: String) raises -> String:
    var usage = executable + " quota"
    var help_index = -1
    var help_value = String()
    var has_help_value = False
    var help_mode = String()
    var literal = False
    for index in range(2, len(args)):
        var argument = args[index]
        if not literal and argument == "--help":
            help_index = index
            help_mode = "full"
            break
        if not literal and argument.startswith("-h") and not argument.startswith("--"):
            help_index = index
            help_mode = "short"
            break
        if not literal and argument.startswith("--help="):
            help_index = index
            help_mode = "full"
            help_value = String(argument[byte=7:])
            has_help_value = True
            break
        if not literal and argument == "--":
            literal = True
    if help_index < 0:
        help_index = len(args)

    var choices: List[String] = ["profile", "all", "auth", "provider", "detail", "raw", "watch", "once", "base-url", "help"]
    var seen = List[String]()
    literal = False
    var index = 2
    while index < help_index:
        var argument = args[index]
        if not literal and argument == "--":
            literal = True
            index += 1
            continue
        if literal or not argument.startswith("-") or argument == "-":
            raise session_cli_error("unexpected argument '" + argument + "' found", usage + " [OPTIONS]")

        var name = argument_name(argument)
        var pieces = argument.split("=", maxsplit=1)
        var canonical = name
        var takes_value = name == "--profile" or name == "--auth" or name == "--provider" or name == "--base-url" or name == "-p"
        var short_profile_value = False
        if name == "-p":
            canonical = "--profile"
        elif not name.startswith("--") or String(name[byte=2:]) not in choices:
            var detail = String("unexpected argument '") + name + "' found"
            var suggestion = String()
            if name.startswith("--"):
                var matches = similar_names(String(name[byte=2:]), choices)
                if matches:
                    suggestion = "--" + matches[len(matches) - 1]
                    detail += "\n\n  tip: a similar argument exists: '" + suggestion + "'"
            var error_usage = String(usage)
            for option in seen:
                error_usage += " " + quota_option_label(option)
            if suggestion and suggestion not in seen:
                error_usage += " " + quota_option_label(suggestion)
            if error_usage == usage:
                error_usage += " [OPTIONS]"
            raise session_cli_error(detail, error_usage)

        if argument.startswith("-p") and not argument.startswith("--") and argument != "-p":
            canonical = "--profile"
            takes_value = True
            short_profile_value = True

        if not takes_value and len(pieces) == 2:
            raise session_cli_error(
                "unexpected value '" + String(pieces[1]) + "' for '" + canonical + "' found; no more were expected",
                usage + " " + quota_option_label(canonical),
            )
        if takes_value:
            if len(pieces) == 2 or short_profile_value:
                pass
            else:
                index += 1
                if index >= help_index:
                    raise session_cli_error(
                        "a value is required for '" + quota_option_label(canonical) + "' but none was supplied"
                    )
                if args[index].startswith("-") and args[index] != "-":
                    var next_name = argument_name(args[index])
                    if next_name == "-p" or (next_name.startswith("--") and String(next_name[byte=2:]) in choices):
                        raise session_cli_error(
                            "a value is required for '" + quota_option_label(canonical) + "' but none was supplied"
                        )
                    continue
        if canonical in seen:
            raise session_cli_error(
                "the argument '" + quota_option_label(canonical) + "' cannot be used multiple times",
                usage + " [OPTIONS]",
            )
        seen.append(canonical)
        index += 1

    if has_help_value:
        raise session_cli_error(
            "unexpected value '" + help_value + "' for '--help' found; no more were expected",
            usage + " --help",
        )
    return help_mode


def quota_option_label(name: String) -> String:
    if name == "--profile": return name + " <NAME>"
    if name == "--auth": return name + " <AUTH>"
    if name == "--provider": return name + " <PROVIDER>"
    if name == "--base-url": return name + " <URL>"
    return name


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


def jaro_similarity(left: String, right: String) -> Float64:
    if left == right:
        return 1.0
    var a = List[Int]()
    var b = List[Int]()
    for character in left.codepoints():
        a.append(Int(character))
    for character in right.codepoints():
        b.append(Int(character))
    if not a or not b:
        return 0.0
    var distance = max(0, max(len(a), len(b)) // 2 - 1)
    var used = List[Bool](length=len(b), fill=False)
    var matched = List[Int]()
    for index in range(len(a)):
        for candidate in range(max(0, index - distance), min(len(b), index + distance + 1)):
            if not used[candidate] and a[index] == b[candidate]:
                used[candidate] = True
                matched.append(a[index])
                break
    if not matched:
        return 0.0
    var position = 0
    var transposed = 0
    for index in range(len(b)):
        if used[index]:
            if matched[position] != b[index]:
                transposed += 1
            position += 1
    var count = Float64(len(matched))
    # The frozen scorer halves the transposition count as an integer.
    return (count / Float64(len(a)) + count / Float64(len(b)) + (count - Float64(transposed // 2)) / count) / 3.0


def similar_names(value: String, choices: List[String]) -> List[String]:
    var result = List[String]()
    var scores = List[Float64]()
    for choice in choices:
        var score = jaro_similarity(value, choice)
        if score > 0.7:
            var index = len(scores)
            while index > 0 and scores[index - 1] > score:
                index -= 1
            scores.insert(index, score)
            result.insert(index, choice)
    return result^


def session_flags(command: String) -> List[String]:
    if command != "list" and command != "current":
        return [String("--help")]
    var result: List[String] = ["--json", "--id-only", "--resume-command", "--profile", "--query", "--limit"]
    if command == "current":
        result.append("--cwd")
    result.extend([String("--include-subagents"), "--parent-only", "--help"])
    return result^


def takes_value(name: String, command: String) -> Bool:
    return name == "--profile" or name == "--query" or name == "--limit" or (command == "current" and name == "--cwd")


def argument_name(argument: String) -> String:
    if argument.startswith("--"):
        return String(argument.split("=", maxsplit=1)[0])
    if argument.startswith("-") and argument != "-":
        var index = 0
        for character in argument.codepoints():
            if index == 1:
                return "-" + chr(Int(character))
            index += 1
    return argument


def arguments_usage(usage: String, seen: List[String], extra: String = "") -> String:
    var result = usage
    for name in seen:
        if name != "--cwd":
            result += " " + option_label(name)
    if extra and extra not in seen and extra != "--cwd":
        result += " " + option_label(extra)
    if result == usage:
        result += " [OPTIONS]"
    return result


def flag_suggestion(name: String, command: String) -> String:
    if not name.startswith("--"):
        return ""
    var choices = List[String]()
    for choice in session_flags(command):
        choices.append(String(choice[byte=2:]))
    var matches = similar_names(String(name[byte=2:]), choices)
    return "--" + matches[len(matches) - 1] if matches else String()


def value_error(
    usage: String,
    command: String,
    name: String,
    value: String,
    seen: List[String],
    attached_value_seen: Bool = False,
    pending_value: Bool = False,
) -> Error:
    var detail = usage
    var choice_usage = attached_value_seen or (pending_value and len(seen) > 0)
    for previous in seen:
        if not takes_value(previous, command):
            choice_usage = True
    if choice_usage and name == "--help":
        detail += " " + name
    elif not choice_usage:
        detail += " " + name
    if not command:
        detail += " <COMMAND>"
    elif command == "resume":
        detail += " <ID>"
    elif choice_usage:
        detail += " <"
        var first = True
        for flag in session_flags(command):
            if flag == "--help":
                continue
            if not first:
                detail += "|"
            detail += option_label(flag)
            first = False
        detail += ">"
    return session_cli_error("unexpected value '" + value + "' for '" + name + "' found; no more were expected", detail)


def unknown_argument(argument: String, usage: String, command: String, seen: List[String], literal: Bool = False) -> Error:
    var flag = argument.startswith("-") and argument != "-" and not literal
    var name = argument_name(argument) if flag else argument
    var detail = String("unexpected argument '") + name + "' found"
    var suggestion = String()
    if flag:
        suggestion = flag_suggestion(name, command)
    if suggestion:
        detail += "\n\n  tip: a similar argument exists: '" + suggestion + "'"
    if flag and command == "resume" and not suggestion:
        detail += "\n\n  tip: to pass '" + name + "' as a value, use '-- " + name + "'"
    var formatted = usage
    if not command:
        if suggestion:
            formatted += " " + suggestion
        formatted += " <COMMAND>"
    elif command == "resume":
        if suggestion:
            formatted += " " + suggestion
        formatted += " <ID>"
    else:
        formatted = arguments_usage(usage, seen, suggestion) if flag and name.startswith("--") else usage + " [OPTIONS]"
    return session_cli_error(detail, formatted)


def unrecognized_subcommand(command: String, usage: String, commands: List[String]) -> Error:
    var detail = String("unrecognized subcommand '") + command + "'"
    var matches = similar_names(command, commands)
    if len(matches) == 1:
        detail += "\n\n  tip: a similar subcommand exists: '" + matches[0] + "'"
    elif matches:
        detail += "\n\n  tip: some similar subcommands exist: "
        for index in range(len(matches)):
            if index:
                detail += ", "
            detail += "'" + matches[index] + "'"
    return session_cli_error(detail, usage + " <COMMAND>")


def conflicting(left: String, right: String) -> Bool:
    if left == right:
        return False
    var outputs: List[String] = ["--json", "--id-only", "--resume-command"]
    var parents: List[String] = ["--include-subagents", "--parent-only"]
    return (left in outputs and right in outputs) or (left in parents and right in parents)


def parse_session_options(args: List[String]) raises -> SessionOptions:
    var executable_parts = args[0].split("/")
    var executable = String(executable_parts[len(executable_parts) - 1])
    var usage = executable + " session"
    if len(args) < 3 or (len(args) == 3 and args[2] == "--"):
        raise Error(session_help("", executable))
    var commands: List[String] = ["list", "current", "resume", "help"]
    if args[2] == "help":
        var command = String()
        for index in range(3, len(args)):
            if command or args[index] not in commands:
                var suffix = " <COMMAND>" if not command else " <ID>" if command == "resume" else " [COMMAND]..." if command == "help" else " [OPTIONS]"
                if command == "help":
                    raise Error("error: unrecognized subcommand '" + args[index] + "'\n\nUsage: " + usage + " " + command + suffix + "\n")
                raise session_cli_error("unrecognized subcommand '" + args[index] + "'", usage + (" " + command if command else String()) + suffix)
            command = args[index]
        return SessionOptions(False, "help", None, command^, None, None, False)
    if args[2] == "--":
        var detail = String("unexpected argument '") + args[3] + "' found"
        if args[3] in commands:
            detail += "\n\n  tip: subcommand '" + args[3] + "' exists; to use it, remove the '--' before it"
            raise session_cli_error(detail, usage + " <COMMAND>")
        raise unrecognized_subcommand(args[3], usage, commands)
    if args[2] == "--help" or args[2].startswith("-h"):
        return SessionOptions(False, "help", None, "", None, None, False)
    if args[2].startswith("--help="):
        raise value_error(usage, "", "--help", String(args[2][byte=7:]), [])
    if args[2] not in commands:
        if args[2].startswith("-") and args[2] != "-":
            var name = argument_name(args[2])
            if not flag_suggestion(name, ""):
                for index in range(3, len(args)):
                    if args[index] == "list" or args[index] == "current" or args[index] == "resume":
                        var suggestion = flag_suggestion(name, args[index])
                        if suggestion:
                            raise session_cli_error("unexpected argument '" + name + "' found\n\n  tip: '" + args[index] + " " + suggestion + "' exists", usage + " <COMMAND>")
            raise unknown_argument(args[2], usage, "", [])
        raise unrecognized_subcommand(args[2], usage, commands)
    var command = args[2]
    usage += " " + command
    var output = String("resume" if command == "resume" else "text")
    var profile = Optional[String]()
    var query = String()
    var limit = Optional[UInt64]()
    var directory = Optional[String]()
    var parent_only = False
    var seen = List[String]()
    var literal = False
    var resume_id = False
    var attached_value_seen = False
    var index = 3
    var flags = session_flags(command)
    while index < len(args):
        var argument = args[index]
        if argument == "--" and not literal:
            literal = True
            index += 1
            continue
        if literal or not argument.startswith("-") or argument == "-":
            if command != "resume" or resume_id:
                raise unknown_argument(argument, usage, command, seen, True)
            query = argument
            resume_id = True
            index += 1
            continue
        var name = argument_name(argument)
        if name == "-h":
            return SessionOptions(False, "help", None, command, None, None, False)
        var pieces = argument.split("=", maxsplit=1)
        if name not in flags:
            raise unknown_argument(argument, usage, command, seen)
        var value_option = takes_value(name, command)
        if not value_option and len(pieces) == 2:
            raise value_error(
                usage,
                command,
                name,
                String(pieces[1]),
                seen,
                attached_value_seen,
            )
        if name == "--help":
            return SessionOptions(False, "help", None, command, None, None, False)
        var value = String()
        if value_option:
            if len(pieces) == 2:
                value = String(pieces[1])
            else:
                index += 1
                if index + 1 < len(args) and args[index] == "--":
                    raise unknown_argument(args[index + 1], usage, command, seen, True)
                if index < len(args) and args[index].startswith("-") and args[index] != "-" and args[index] != "--":
                    var next = argument_name(args[index])
                    var next_pieces = args[index].split("=", maxsplit=1)
                    if next in flags and not takes_value(next, command) and len(next_pieces) == 2:
                        raise value_error(
                            usage,
                            command,
                            next,
                            String(next_pieces[1]),
                            seen,
                            attached_value_seen,
                            True,
                        )
                    if next not in flags and next != "-h":
                        raise unknown_argument(args[index], usage, command, seen)
                if index >= len(args) or (args[index].startswith("-") and args[index] != "-"):
                    raise session_cli_error("a value is required for '" + option_label(name) + "' but none was supplied")
                value = args[index]
            if name == "--cwd" and not value:
                raise session_cli_error("a value is required for '--cwd <PATH>' but none was supplied")
        if name in seen:
            raise session_cli_error("the argument '" + option_label(name) + "' cannot be used multiple times", usage + " [OPTIONS]")
        seen.append(name)
        if value_option and len(pieces) == 2:
            attached_value_seen = True
        if name == "--json" or name == "--id-only" or name == "--resume-command":
            output = String(name[byte=2:])
        elif name == "--parent-only" or name == "--include-subagents":
            parent_only = name == "--parent-only"
        elif name == "--profile":
            profile = value^
        elif name == "--query":
            query = value^
        elif name == "--cwd":
            directory = value^
        elif name == "--limit":
            try:
                limit = unsigned_value(value)
            except error:
                if len(pieces) == 1 and index + 1 < len(args):
                    var following = args[index + 1]
                    var following_name = argument_name(following)
                    var following_pieces = following.split("=", maxsplit=1)
                    if following_name in flags and not takes_value(following_name, command) and len(following_pieces) == 2:
                        raise value_error(
                            usage,
                            command,
                            following_name,
                            String(following_pieces[1]),
                            seen,
                            attached_value_seen or len(seen) > 1,
                        )
                # Clap reports a direct stray argument before split-limit conversion.
                if len(pieces) == 1 and index + 1 < len(args):
                    var following = args[index + 1]
                    if following == "--":
                        if index + 2 < len(args):
                            raise unknown_argument(args[index + 2], usage, command, seen, True)
                    elif not following.startswith("-") or following == "-":
                        raise unknown_argument(following, usage, command, seen, True)
                    else:
                        var following_name = argument_name(following)
                        if following_name not in flags and following_name != "-h":
                            raise unknown_argument(following, usage, command, seen)
                raise session_cli_error("invalid value '" + value + "' for '--limit <N>': " + String(error))
        index += 1
    if command == "resume" and not resume_id:
        raise session_cli_error("the following required arguments were not provided:\n  <ID>", usage + " <ID>")
    for name in seen:
        var others = List[String]()
        var kept = List[String]()
        for other in seen:
            if conflicting(name, other):
                others.append(other)
            else:
                kept.append(other)
        if others:
            var detail = String("the argument '") + name + "' cannot be used with"
            if len(others) == 1:
                detail += " '" + others[0] + "'"
            else:
                detail += ":"
                for other in others:
                    detail += "\n  " + other
            raise session_cli_error(detail, arguments_usage(usage, kept))
    return SessionOptions(command == "current", output^, profile^, query^, limit^, directory^, parent_only)
