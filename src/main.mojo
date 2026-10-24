from std.collections import List
from std.sys import argv, exit, stderr

from modex.cli import parse_session_options, session_help
from modex.log_cli import log_help, log_short_help, parse_log_arguments
from modex.logs import log_last
from modex.log_upstream_follow import follow_upstream
from modex.root_help import root_help
from modex.sessions import inspect_sessions


def main():
    var args = List[String]()
    for arg in argv():
        args.append(String(arg))
    if len(args) >= 3 and args[1] == "help" and args[2] == "session":
        var rewritten: List[String] = [args[0], "session", "help"]
        for index in range(3, len(args)):
            rewritten.append(args[index])
        args = rewritten^
    if len(args) >= 3 and args[1] == "help" and args[2] == "log":
        if len(args) == 3:
            var rewritten: List[String] = [args[0], "log", "--help"]
            args = rewritten^
        else:
            var executable_parts = args[0].split("/")
            var executable = String(executable_parts[len(executable_parts) - 1])
            print("error: unrecognized subcommand '" + String(args[3]) + "'\n\nUsage: " + executable + " log [OPTIONS] [MODE]\n\nFor more information, try '--help'.\n", file=stderr, end="")
            exit(2)
    if len(args) >= 2 and (args[1] == "--version" or args[1] == "-V"):
        print("modex 0.1.0-dev")
        return
    if len(args) >= 2 and (args[1] == "--help" or args[1] == "-h" or (args[1] == "help" and len(args) == 2)):
        var executable_parts = args[0].split("/")
        print(root_help(String(executable_parts[len(executable_parts) - 1])), end="")
        return
    if len(args) >= 2 and args[1] == "log":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            var options = parse_log_arguments(args, executable)
            if options[2]:
                print(log_help(executable, log_short_help(args)), end="")
                return
            if options[0] == "last":
                try:
                    print(log_last(options[1]), end="")
                except error:
                    print("Error:", error, file=stderr)
                    exit(1)
                return
            if options[0] == "upstream":
                try:
                    follow_upstream(options[1])
                except error:
                    print("Error:", error, file=stderr)
                    exit(1)
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
        print("Error: this Modex development build has not implemented the requested command", file=stderr)
        exit(1)
    if len(args) >= 2 and args[1] == "session":
        try:
            var options = parse_session_options(args)
            if options.output == "help":
                var executable_parts = args[0].split("/")
                print(session_help(options.query, String(executable_parts[len(executable_parts) - 1])), end="")
                return
            if options.output == "resume":
                print("Error: session resume is not implemented", file=stderr)
                exit(1)
            try:
                var output = inspect_sessions(options^)
                print(output, end="")
            except error:
                print("Error:", error, file=stderr)
                exit(1)
        except error:
            print(error, end="", file=stderr)
            exit(2)
        return
    print(
        "Error: this Modex development build has not implemented the requested command",
        file=stderr,
    )
    exit(1)
