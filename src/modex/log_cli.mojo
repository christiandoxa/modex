from std.collections import List

from .cli import similar_names


def log_help(executable: String, summary: Bool = False) -> String:
    var usage = executable + " log [OPTIONS] [MODE]"
    if summary:
        return "Follow redacted Prodex runtime logs.\n\nUsage: " + usage + "\n\nArguments:\n  [MODE]  Log view. Omit for the live stream [default: stream] [possible values: stream, last, upstream]\n\nOptions:\n      --json  Emit one JSON object per line\n  -h, --help  Print help (see more with '--help')\n\nExamples:\n  prodex log\n  prodex log last\n  prodex log upstream\n  prodex log --json\n"
    return "Follow redacted Prodex runtime logs.\n\nUsage: " + usage + "\n\nArguments:\n  [MODE]\n          Log view. Omit for the live stream\n\n          Possible values:\n          - stream:   Follow redacted runtime logs\n          - last:     Print the latest matching runtime-log line and exit\n          - upstream: Follow only upstream request/response log events\n          \n          [default: stream]\n\nOptions:\n      --json\n          Emit one JSON object per line\n\n  -h, --help\n          Print help (see a summary with '-h')\n\nExamples:\n  prodex log\n  prodex log last\n  prodex log upstream\n  prodex log --json\n"


def log_error(message: String, usage: String) -> Error:
    return Error("error: " + message + "\n\nUsage: " + usage + "\n\nFor more information, try '--help'.\n")


def log_short_help(args: List[String]) -> Bool:
    for arg in args:
        if arg == "--":
            return False
        if arg == "--help":
            return False
        if arg.startswith("-h") and not arg.startswith("--"):
            return True
    return False


def log_value_error(value: String, executable: String) -> Error:
    var message = "invalid value '" + value + "' for '[MODE]'\n  [possible values: stream, last, upstream]"
    var matches = similar_names(value, [String("stream"), "last", "upstream"])
    if matches:
        message += "\n\n  tip: a similar value exists: '" + matches[len(matches) - 1] + "'"
    return Error("error: " + message + "\n\nFor more information, try '--help'.\n")


def parse_log_arguments(args: List[String], executable: String) raises -> Tuple[String, Bool, Bool]:
    var mode = String()
    var json = False
    var literal = False
    var seen_json = False
    var index = 2
    while index < len(args):
        var arg = String(args[index])
        if not literal and (arg == "--help" or (arg.startswith("-h") and not arg.startswith("--"))):
            if mode and mode != "stream" and mode != "last" and mode != "upstream":
                raise log_value_error(mode, executable)
            return mode^, json, True
        if not literal and arg == "--":
            literal = True
            index += 1
            continue
        if not literal and arg == "--json":
            if mode and mode != "stream" and mode != "last" and mode != "upstream":
                raise log_value_error(mode, executable)
            if seen_json:
                raise log_error("the argument '--json' cannot be used multiple times", executable + " log [OPTIONS] [MODE]")
            seen_json = True
            json = True
        elif not literal and arg.startswith("--json="):
            var value = String(arg[byte=7:])
            var usage = executable + " log --json [MODE]"
            if seen_json:
                usage = executable + " log <MODE|--json>"
            raise log_error("unexpected value '" + value + "' for '--json' found; no more were expected", usage)
        elif not literal and arg.startswith("--help="):
            var value = String(arg[byte=7:])
            var usage = executable + " log --help [MODE]"
            if seen_json:
                usage = executable + " log --help <MODE|--json>"
            raise log_error("unexpected value '" + value + "' for '--help' found; no more were expected", usage)
        elif not literal and arg.startswith("-") and arg != "-":
            if arg.startswith("--"):
                var option = String(arg.split("=", maxsplit=1)[0])
                var choices: List[String] = ["help", "json"]
                var candidates = similar_names(String(option[byte=2:]), choices)
                var suggestion = String()
                if candidates:
                    suggestion = "--" + candidates[len(candidates) - 1]
                var message = "unexpected argument '" + option + "' found"
                if suggestion:
                    message += "\n\n  tip: a similar argument exists: '" + suggestion + "'"
                else:
                    message += "\n\n  tip: to pass '" + option + "' as a value, use '-- " + option + "'"
                var usage = executable + " log [OPTIONS] [MODE]"
                if suggestion == "--help":
                    usage = executable + " log --help [MODE]"
                    if mode:
                        usage = executable + " log --help <MODE>"
                    if seen_json:
                        usage = executable + " log --json --help [MODE]"
                        if mode:
                            usage = executable + " log --json --help <MODE>"
                elif suggestion:
                    usage = executable + " log --json [MODE]"
                    if mode:
                        usage = executable + " log --json <MODE>"
                elif mode:
                    usage = executable + " log <MODE>"
                elif seen_json:
                    usage = executable + " log --json [MODE]"
                raise log_error(message, usage)
            var short_name = String(arg[byte=0:2])
            raise log_error("unexpected argument '" + short_name + "' found\n\n  tip: to pass '" + short_name + "' as a value, use '-- " + short_name + "'", executable + " log [OPTIONS] [MODE]")
        elif not mode:
            mode = arg
        else:
            raise log_error("unexpected argument '" + arg + "' found", executable + " log [OPTIONS] [MODE]")
        index += 1
    if mode and mode != "stream" and mode != "last" and mode != "upstream":
        raise log_value_error(mode, executable)
    return mode^, json, False
