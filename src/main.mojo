from std.collections import List
from std.sys import argv, exit, stderr

from modex.cli import argument_name, login_help_requested, logout_help_requested, parse_session_options, parse_update_help_arguments, quota_help_requested, redeem_help_requested, session_cli_error, session_help
from modex.doctor_install import run_doctor_install
from modex.gateway_cli import GatewayOptions, gateway_help, parse_gateway_arguments, run_gateway
from modex.inspection_cli import doctor_install_requested, inspection_help, inspection_help_requested, inspection_usage
from modex.log_cli import log_help, log_short_help, parse_log_arguments
from modex.logs import log_last
from modex.log_upstream_follow import follow_upstream
from modex.log_stream import follow_stream
from modex.paths import app_root_is_absent
from modex.profile_cli import parse_profile_help_arguments, profile_help, profile_list_empty_panel, profile_short_help, top_level_profile_use_help
from modex.root_help import login_help, logout_help, logout_usage, ping_help, ping_openai_help, quota_help, quota_short_help, redeem_help, root_help, run_help, update_help
from modex.sessions import inspect_sessions, resolve_session_id_from_store, session_resume_has_no_profile_source
from modex.super_cli import parse_super_arguments, run_super
from modex.super_help import super_help
from modex.super_launch import run_local_rewrite_child
from modex.text import cli_width, status_panel


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
        if len(args) == 2 or (len(args) == 3 and args[2] == "--"):
            print(profile_help("", executable), file=stderr, end="")
            exit(2)
            return
        try:
            var request = parse_profile_help_arguments(args, 2, executable)
            if request.help:
                var output = profile_help(request.command, executable) if not request.short_help else profile_short_help(request.command, executable)
                print(output, end="")
                return
            if request.command == "list":
                try:
                    if app_root_is_absent():
                        print(profile_list_empty_panel(), end="")
                        return
                except error:
                    print("Error:", error, file=stderr)
                    exit(1)
                    return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
        print("Error: this Modex development build has not implemented the requested command", file=stderr)
        exit(1)
        return
    if len(args) >= 2 and args[1] == "use":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        var rewritten: List[String] = [args[0], "profile", "use"]
        for index in range(2, len(args)):
            rewritten.append(args[index])
        try:
            var request = parse_profile_help_arguments(rewritten, 2, executable)
            if request.help:
                print(top_level_profile_use_help(executable), end="")
                return
        except error:
            var message = String(error).replace(
                "Usage: " + executable + " profile use",
                "Usage: " + executable + " use",
            )
            print(message, file=stderr, end="")
            exit(2)
            return
        print("Error: this Modex development build has not implemented the requested command", file=stderr)
        exit(1)
        return
    if len(args) >= 3 and args[1] == "ping" and args[2].startswith("--help="):
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        var value = String(args[2][byte=7:])
        print(session_cli_error("unexpected value '" + value + "' for '--help' found; no more were expected", executable + " ping --help <COMMAND>"), file=stderr, end="")
        exit(2)
        return
    if len(args) >= 3 and args[1] == "ping" and args[2] == "help":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 3:
            print(ping_help(executable), end="")
            return
        if args[3] == "openai":
            if len(args) > 4:
                print(session_cli_error("unrecognized subcommand '" + args[4] + "'", executable + " ping openai [OPTIONS]"), file=stderr, end="")
                exit(2)
                return
            print(ping_openai_help(executable), end="")
            return
        print(session_cli_error("unrecognized subcommand '" + args[3] + "'", executable + " ping <COMMAND>"), file=stderr, end="")
        exit(2)
        return
    if len(args) >= 3 and args[1] == "ping" and args[2] == "openai" and len(args) >= 4:
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if String(args[3]).startswith("--help="):
            var value = String(args[3][byte=7:])
            print(session_cli_error("unexpected value '" + value + "' for '--help' found; no more were expected", executable + " ping openai --help"), file=stderr, end="")
            exit(2)
            return
        if args[3] == "--help" or args[3].startswith("-h"):
            print(ping_openai_help(executable), end="")
            return
    if len(args) >= 3 and args[1] == "ping" and (
        args[2] == "--help" or args[2].startswith("-h")
    ):
        var executable_parts = args[0].split("/")
        print(ping_help(String(executable_parts[len(executable_parts) - 1])), end="")
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "ping":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 3:
            print(ping_help(executable), end="")
            return
        if args[3] == "openai":
            if len(args) > 4:
                print(session_cli_error("unrecognized subcommand '" + args[4] + "'", executable + " ping openai [OPTIONS]"), file=stderr, end="")
                exit(2)
                return
            print(ping_openai_help(executable), end="")
            return
        if len(args) > 3:
            print(session_cli_error("unrecognized subcommand '" + args[3] + "'", executable + " ping <COMMAND>"), file=stderr, end="")
            exit(2)
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
    if len(args) >= 3 and args[1] == "help" and args[2] == "use":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            var request = parse_profile_help_arguments(args, 2, executable, True)
            if request.help:
                print(top_level_profile_use_help(executable), end="")
                return
        except error:
            var message = String(error).replace(
                "Usage: " + executable + " profile use",
                "Usage: " + executable + " use",
            )
            print(message, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 3 and args[1] == "help" and (
        args[2] == "current" or args[2] == "info" or args[2] == "status" or args[2] == "doctor"
    ):
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) > 3:
            print(session_cli_error(
                "unrecognized subcommand '" + args[3] + "'",
                inspection_usage(args[2], executable),
            ), file=stderr, end="")
            exit(2)
            return
        print(inspection_help(args[2], executable), end="")
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "update":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) > 3:
            var name = String(args[3])
            print(session_cli_error("unrecognized subcommand '" + name + "'", executable + " update"), file=stderr, end="")
            exit(2)
            return
        print(update_help(executable), end="")
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "redeem":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) > 3:
            print(session_cli_error("unrecognized subcommand '" + args[3] + "'", executable + " redeem [OPTIONS] <PROFILE>"), file=stderr, end="")
            exit(2)
            return
        print(redeem_help(executable), end="")
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "login":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) > 3:
            print(session_cli_error(
                "unrecognized subcommand '" + args[3] + "'",
                executable + " login [OPTIONS] [PROFILE_OR_LOGIN_ARG]...",
            ), file=stderr, end="")
            exit(2)
            return
        print(login_help(executable), end="")
        return
    if len(args) >= 2 and args[1] == "login":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            if login_help_requested(args, executable):
                print(login_help(executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 3 and args[1] == "help" and args[2] == "logout":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 3:
            print(logout_help(executable), end="")
            return
        print(session_cli_error("unrecognized subcommand '" + args[3] + "'", logout_usage(executable)), file=stderr, end="")
        exit(2)
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "quota":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 3:
            print(quota_help(executable), end="")
            return
        print(session_cli_error("unrecognized subcommand '" + args[3] + "'", executable + " quota [OPTIONS]"), file=stderr, end="")
        exit(2)
        return
    if len(args) >= 3 and args[1] == "help" and args[2] == "run":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) == 3:
            print(run_help(executable), end="")
            return
        print(session_cli_error("unrecognized subcommand '" + args[3] + "'", executable + " run [OPTIONS] [CODEX_ARG]..."), file=stderr, end="")
        exit(2)
        return
    if len(args) >= 2 and args[1] == "update":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            if parse_update_help_arguments(args, executable):
                print(update_help(executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 2 and args[1] == "logout":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            if logout_help_requested(args, executable):
                print(logout_help(executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 2 and args[1] == "redeem":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            if redeem_help_requested(args, executable):
                print(redeem_help(executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
            return
    if len(args) >= 2 and args[1] == "run":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if len(args) >= 3:
            var help_argument = String(args[2])
            if help_argument.startswith("--help="):
                print(session_cli_error(
                    "unexpected value '" + String(help_argument[byte=7:]) + "' for '--help' found; no more were expected",
                    executable + " run --help [CODEX_ARG]...",
                ), file=stderr, end="")
                exit(2)
                return
            # shortcut: handles direct help and --full-access before help; widen when run argument parsing is implemented.
            if help_argument == "--help" or help_argument == "-h":
                print(run_help(executable), end="")
                return
            if len(args) >= 4 and help_argument == "--full-access" and (
                args[3] == "--help" or args[3] == "-h"
            ):
                print(run_help(executable), end="")
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
    if len(args) >= 3 and args[1] == "help" and (args[2] == "current" or args[2] == "info" or args[2] == "status" or args[2] == "doctor"):
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
    if len(args) >= 3 and args[1] == "help":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        if args[2] == "help":
            if len(args) == 3:
                print("Print this message or the help of the given subcommand(s)\n\nUsage: " + executable + " help [COMMAND]...\n\nArguments:\n  [COMMAND]...  Print help for the subcommand(s)\n", end="")
            else:
                print("error: unrecognized subcommand '" + args[3] + "'\n\nUsage: " + executable + " help [COMMAND]...\n", file=stderr, end="")
                exit(2)
            return
        # Hidden release commands are valid root help targets too.
        var known_commands: List[String] = [
            "profile", "use", "current", "info", "status", "log", "session", "doctor",
            "login", "logout", "update", "quota", "redeem", "ping", "run", "super", "s",
            "gateway", "help", "__super-expose", "__runtime-broker", "__mcp-jsonl-bridge",
            "__sub-agent-exec",
        ]
        if args[2] not in known_commands:
            print(
                session_cli_error(
                    "unrecognized subcommand '" + args[2] + "'",
                    executable + " <COMMAND>",
                ),
                file=stderr,
                end="",
            )
            exit(2)
            return
    if len(args) >= 2 and (args[1] == "--version" or args[1] == "-V"):
        print("modex 0.1.0-dev")
        return
    if len(args) >= 2 and (args[1] == "--help" or args[1] == "-h" or (args[1] == "help" and len(args) == 2)):
        var executable_parts = args[0].split("/")
        print(root_help(String(executable_parts[len(executable_parts) - 1])), end="")
        return
    if len(args) >= 2 and (args[1] == "current" or args[1] == "info" or args[1] == "status" or args[1] == "doctor"):
        var parts = args[0].split("/")
        var executable = String(parts[len(parts) - 1])
        try:
            if inspection_help_requested(args, executable):
                print(inspection_help(args[1], executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
    if doctor_install_requested(args):
        try:
            run_doctor_install()
        except error:
            print("Error:", error, file=stderr)
            exit(1)
        return
    if len(args) >= 2 and args[1] == "current":
        try:
            if app_root_is_absent():
                print(status_panel("Active Profile", "No active profile.", cli_width()) + "\n", end="")
                return
        except error:
            print("Error:", error, file=stderr)
            exit(1)
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
                try:
                    _ = resolve_session_id_from_store(options.query)
                except error:
                    print("Error:", error, file=stderr)
                    exit(1)
                if session_resume_has_no_profile_source():
                    print("Prodex launch: preparing runtime launch...", file=stderr)
                    print(
                        "Error: no active profile selected and no Codex-compatible profiles are available; use `prodex use --profile <name>` or pass --profile",
                        file=stderr,
                    )
                    exit(1)
                print(
                    "Error: session resume requires managed profile authorization and launch, "
                    + "which are not implemented",
                    file=stderr,
                )
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
    if len(args) >= 2 and args[1] == "quota":
        var executable_parts = args[0].split("/")
        var executable = String(executable_parts[len(executable_parts) - 1])
        try:
            var help_mode = quota_help_requested(args, executable)
            if help_mode:
                print(quota_short_help(executable) if help_mode == "short" else quota_help(executable), end="")
                return
        except error:
            print(error, file=stderr, end="")
            exit(2)
        print("Error: this Modex development build has not implemented the requested command", file=stderr)
        exit(1)
        return
    print(
        "Error: this Modex development build has not implemented the requested command",
        file=stderr,
    )
    exit(1)
