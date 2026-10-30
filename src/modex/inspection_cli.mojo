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
    if flag and name.startswith("--") and (seen or suggestion):
        usage = _inspection_prefix(command, executable)
        for option in seen:
            usage += " " + inspection_label(option)
        if suggestion and suggestion not in seen:
            usage += " " + inspection_label(suggestion)
    return session_cli_error(message, usage)


def inspection_value_error(name: String, value: String, command: String, executable: String, seen: List[String], doctor_group: Bool) -> Error:
    var usage = _inspection_prefix(command, executable)
    if command == "doctor":
        if doctor_group:
            var choices = List[String]()
            for flag in inspection_flags(command):
                if flag != "--help": choices.append(inspection_label(flag))
            usage += (" --help" if name == "--help" else "") + " <" + "|".join(choices) + ">"
        else:
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
    var doctor_group = False
    var pending_interval_error = String()
    var index = 2
    while index < len(args):
        var argument = args[index]
        var help = not literal and (
            argument == "--help" or (argument.startswith("-h") and not argument.startswith("--"))
        )
        var name = argument_name(argument)
        var attached_value = (
            name not in ["--interval", "--tail-bytes", "--bundle"] and "=" in argument
        )
        # Clap keeps separated values pending but validates attached values immediately.
        if (
            pending_interval_error
            and not literal
            and argument != "--"
            and not attached_value
            and (help or name in flags)
        ):
            raise session_cli_error(pending_interval_error)
        if help:
            return True
        if not literal and argument == "--":
            literal = True
            index += 1
            continue
        if literal or name not in flags:
            raise inspection_unknown(argument, command, executable, seen, literal)
        if name not in ["--interval", "--tail-bytes", "--bundle"] and "=" in argument:
            raise inspection_value_error(name, String(argument.split("=", maxsplit=1)[1]), command, executable, seen, doctor_group)
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
            var parsed: UInt64 = 0
            var interval_error = String()
            try:
                parsed = unsigned_value(value)
            except error:
                interval_error = "invalid value '" + value + "' for '--interval <SECONDS>': " + String(error)
            if not interval_error and (parsed < 1 or parsed > 60):
                interval_error = "invalid value '" + value + "' for '--interval <SECONDS>': " + String(parsed) + " is not in 1..=60"
            if interval_error:
                if "=" in argument:
                    raise session_cli_error(interval_error)
                pending_interval_error = interval_error
        if command == "doctor" and (name not in ["--tail-bytes", "--bundle"] or "=" in argument):
            doctor_group = True
        seen.append(name)
        index += 1
    if pending_interval_error:
        raise session_cli_error(pending_interval_error)
    if command == "doctor":
        var missing = List[String]()
        for name in seen:
            var requirement = String()
            if name in ["--json", "--suggest-policy"] and "--runtime" not in seen:
                requirement = "--runtime"
            elif name == "--bundle" and "--redacted" not in seen:
                requirement = "--redacted"
            elif name == "--redacted" and "--bundle" not in seen:
                requirement = "--bundle"
            if requirement and requirement not in missing:
                missing.append(requirement)

        if "--json" in seen and "--bundle" in seen:
            var conflict_usage = _inspection_prefix(command, executable)
            var json_index = -1
            var bundle_index = -1
            for index in range(len(seen)):
                if seen[index] == "--json": json_index = index
                if seen[index] == "--bundle": bundle_index = index
            var json_first = json_index < bundle_index
            var first = String("--json" if json_first else "--bundle")
            var second = String("--bundle" if json_first else "--json")
            var first_requirement = String("--runtime" if json_first else "--redacted")
            var message = "the argument '" + inspection_label(first) + "' cannot be used with '" + inspection_label(second) + "'"
            for index in range(len(seen)):
                var name = seen[index]
                if name == second:
                    continue
                if name == first and first_requirement not in seen:
                    conflict_usage += " " + first_requirement
                conflict_usage += " " + inspection_label(name)
            raise session_cli_error(message, conflict_usage)

        if missing:
            var message = "the following required arguments were not provided:"
            for name in missing:
                message += "\n  " + inspection_label(name)
            var error_usage = _inspection_prefix(command, executable)
            var emitted = List[String]()
            for requirement in missing:
                if requirement == "--runtime":
                    error_usage += " --runtime"
                    emitted.append("--runtime")
                elif requirement == "--redacted":
                    error_usage += " " + inspection_label("--bundle") + " --redacted"
                    emitted.append("--bundle")
                    emitted.append("--redacted")
                elif requirement == "--bundle":
                    if "--redacted" in seen:
                        error_usage += " --redacted " + inspection_label("--bundle")
                        emitted.append("--redacted")
                        emitted.append("--bundle")
                    else:
                        error_usage += " " + inspection_label("--bundle")
                        emitted.append("--bundle")
            for name in seen:
                if name not in emitted:
                    error_usage += " " + inspection_label(name)
            raise session_cli_error(message, error_usage)
    return False


def doctor_install_requested(args: List[String]) -> Bool:
    if len(args) < 3 or args[1] != "doctor":
        return False
    var install = False
    var index = 2
    while index < len(args):
        var argument = args[index]
        if argument == "--install":
            if install:
                return False
            install = True
        elif argument == "--tail-bytes":
            index += 1
        elif argument.startswith("--tail-bytes="):
            pass
        else:
            return False
        index += 1
    return install
