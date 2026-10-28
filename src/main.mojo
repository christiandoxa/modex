from std.collections import List
from std.sys import argv, exit, stderr

from modex.cli import parse_session_options, session_help
from modex.gateway_cli import GatewayOptions, gateway_help, parse_gateway_arguments, run_gateway
from modex.inspection_cli import inspection_help, inspection_help_requested, inspection_usage
from modex.log_cli import log_help, log_short_help, parse_log_arguments
from modex.logs import log_last
from modex.log_upstream_follow import follow_upstream
from modex.log_stream import follow_stream
from modex.profile_cli import parse_profile_help_arguments, profile_help, profile_short_help
from modex.root_help import root_help
from modex.sessions import inspect_sessions
from modex.super_cli import parse_super_arguments, run_super
from modex.super_help import super_help
from modex.super_launch import run_local_rewrite_child


def main():
    var args = List[String]()
    for arg in argv():
        args.append(String(arg))
    if len(args) == 2 and args[1] == "__modex-local-rewrite":
        try:
            run_local_rewrite_child()
        except:
            print("Error: local provider relay failed", file=stderr)
            exit(1)
        return
    if len(args) >= 2 and args[1] == "profile":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 2:
            print(profile_help("", executable), file=stderr, end="")
            exit(2)
            return
        try:
            var request = parse_profile_help_arguments(args, 2, executable)
            if request.help:
                var output = profile_help(request.command, executable) if not request.short_help else profile_short_help(request.command, executable)
                print(output, end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
        print("Error: this Modex development build has not implemented the requested command", file=stderr)
        exit(1)
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "profile":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            var request = parse_profile_help_arguments(args, 3, executable, True)
            if request.help:
                print(profile_help(request.command, executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 3 and args[1] == "help" and (args[2] == "super" or args[2] == "s"):
        var parts = args[0].split("/")
        var executable = String(parts[len(parts) - 1])
        if len(args) > 3:
            print("error: unrecognized subcommand '" + args[3] + "'\n\nUsage: " + executable + " super [OPTIONS] [CODEX_ARG]...\n\nFor more information, try '--help'.\n", file=stderr, end="")
            exit(2)
        print(super_help(executable), end="")
        return
    if len(args) >= 2 and (args[1] == "super" or args[1] == "s"):
        var parts = args[0].split("/")
        var executable = String(parts[len(parts) - 1])
        try:
            var options = parse_super_arguments(args, executable)
            if options.help:
                print(super_help(executable), end="")
                return
            try:
                exit(run_super(options))
            except error:
                print("Error:", error, file=stderr)
                exit(1)
        except error:
            if String(error).startswith("error:"):
                print(error, file=stderr, end="")
                exit(2)
            print("Error:", error, file=stderr)
            exit(1)
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "gateway":
        var parts = args[0].split("/")
        if len(args) > 3:
            print("error: unrecognized subcommand '" + args[3] + "'\n\nUsage: " + String(parts[len(parts) - 1]) + " gateway [OPTIONS]\n\nFor more information, try '--help'.\n", file=stderr, end="")
            exit(2)
        print(gateway_help(String(parts[len(parts) - 1])), end="")
        return
    if len(args) >= 2 and args[1] == "gateway":
        var parts = args[0].split("/")
        var options: GatewayOptions
        try:
            options = parse_gateway_arguments(args, String(parts[len(parts) - 1]))
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
        if options.help:
            print(gateway_help(String(parts[len(parts) - 1])), end="")
            return
        try:
            run_gateway(options)
        except error:
            print("Error:", error, file=stderr)
            exit(1)
        return
    if len(args) >= 3 and args[1] == "help" and (args[2] == "current" or args[2] == "info" or args[2] == "status"):
        var parts = args[0].split("/")
        var executable = String(parts[len(parts) - 1])
        if len(args) > 3:
            print("error: unrecognized subcommand '" + args[3] + "'\n\nUsage: " + inspection_usage(args[2], executable) + "\n\nFor more information, try '--help'.\n", file=stderr, end="")
            exit(2)
        print(inspection_help(args[2], executable), end="")
        return
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
    if len(args) >= 2 and (args[1] == "current" or args[1] == "info" or args[1] == "status"):
        var parts = args[0].split("/")
        var executable = String(parts[len(parts) - 1])
        try:
            if inspection_help_requested(args, executable):
                print(inspection_help(args[1], executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
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
            if not options[0] or options[0] == "stream":
                try:
                    follow_stream(options[1])
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
