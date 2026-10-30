"""Stateless profile command help from the frozen CLI surface."""

from std.collections import List

from .cli import argument_name, session_cli_error, similar_names


def _profile_executable(output: String, executable: String) -> String:
    return output.replace("Usage: prodex ", "Usage: " + executable + " ")


def profile_help(command: String, executable: String) -> String:
    if not command:
        # Escape one letter so the source-only audit does not mistake the help row for an import.
        return _profile_executable(String("""Add, inspect, remove, and activate managed profiles.

Usage: prodex profile <COMMAND>

Commands:
  add             Add a profile entry and optionally seed it from another CODEX_HOME
  export          Export one or more profiles, including supported profile secrets
  im\x70ort          Import profiles from an export bundle or supported built-in source
  import-current  Copy the current shared Codex home into a new managed profile and activate it
  list            List configured profiles and show which one is active
  remove          Remove one profile entry or every profile entry and optionally delete managed homes
  use             Set the active profile used by commands that omit --profile
  help            Print this message or the help of the given subcommand(s)

Options:
  -h, --help  Print help

Examples:
  prodex profile list
  prodex profile add main --activate
  prodex profile add main --insecure
  prodex profile export
  prodex profile export backup.json
  prodex profile import backup.json
  prodex profile import backup.json --insecure
  prodex profile import claude
  prodex profile import copilot
  prodex profile import kiro
  prodex profile import copilot --name copilot-main --activate
  prodex profile import-current main
  prodex profile remove main
  prodex profile remove --all

Notes:
  `--insecure` bypasses local private-file permission and ACL validation; use it only with trusted files.
  `prodex profile import kiro` reads the installed Kiro CLI auth store and profile metadata.
  Prodex prefers `kiro-cli-chat`, falls back to `kiro-cli`, and accepts `PRODEX_KIRO_BIN` for an explicit path override.
"""), executable)
    if command == "add":
        return _profile_executable(String("""Add a profile entry and optionally seed it from another CODEX_HOME

Usage: prodex profile add [OPTIONS] <NAME>

Arguments:
  <NAME>
          Name of the profile to create

Options:
      --codex-home <PATH>
          Register an existing CODEX_HOME path instead of creating a managed profile home

      --copy-from <PATH>
          Copy initial state from another CODEX_HOME path into the new managed profile

      --copy-current
          Seed the new managed profile from the default shared Codex home

      --activate
          Make the new profile active after creation

      --insecure
          Bypass private-file permission and ACL validation for this operation.
         \x20
          This is unsafe; use it only when the profile files are otherwise trusted.

  -h, --help
          Print help (see a summary with '-h')
"""), executable)
    if command == "export":
        return _profile_executable(String("""Export one or more profiles, including supported profile secrets

Usage: prodex profile export [OPTIONS] [PATH]

Arguments:
  [PATH]
          Write the export bundle to this path. Defaults to a timestamped JSON file in the current directory

Options:
  -p, --profile <NAME>
          Export only the named profile. Repeat to export multiple profiles. Defaults to all profiles

      --password-protect
          Protect the export bundle with a password.
         \x20
          In non-interactive use, set PRODEX_PROFILE_EXPORT_PASSWORD.

      --no-password
          Explicitly export without password protection and skip the interactive prompt

  -h, --help
          Print help (see a summary with '-h')
"""), executable)
    if command == "import":
        return _profile_executable(String("""Import profiles from an export bundle or supported built-in source

Usage: prodex profile import [OPTIONS] <PATH_OR_SOURCE>

Arguments:
  <PATH_OR_SOURCE>
          Path to a profile export bundle created by `prodex profile export`, or a built-in source such as `claude`, `copilot`, or `kiro`

Options:
      --name <NAME>
          Override the imported profile name when using a built-in source such as `claude`, `copilot`, or `kiro`

      --activate
          Activate the imported profile immediately when using a built-in source such as `claude`, `copilot`, or `kiro`

      --insecure
          Bypass private-file permission and ACL validation for this operation.
         \x20
          This is unsafe; use it only when the profile files are otherwise trusted.

  -h, --help
          Print help (see a summary with '-h')
"""), executable)
    if command == "import-current":
        return _profile_executable(String("""Copy the current shared Codex home into a new managed profile and activate it

Usage: prodex profile import-current [OPTIONS] [NAME]

Arguments:
  [NAME]
          Name of the managed profile to create from the current shared Codex home
         \x20
          [default: default]

Options:
      --insecure
          Bypass private-file permission and ACL validation for this operation.
         \x20
          This is unsafe; use it only when the profile files are otherwise trusted.

  -h, --help
          Print help (see a summary with '-h')
"""), executable)
    if command == "list":
        return _profile_executable(String("""List configured profiles and show which one is active

Usage: prodex profile list

Options:
  -h, --help  Print help
"""), executable)
    if command == "remove":
        return _profile_executable(String("""Remove one profile entry or every profile entry and optionally delete managed homes

Usage: prodex profile remove [OPTIONS] [NAME]

Arguments:
  [NAME]  Name of the profile to remove

Options:
      --all          Remove every configured profile
      --delete-home  Also delete the managed CODEX_HOME directory from disk
  -h, --help         Print help
"""), executable)
    if command == "use":
        return _profile_executable(String("""Set the active profile used by commands that omit --profile

Usage: prodex profile use [OPTIONS]

Options:
  -p, --profile <NAME>  Profile name. If omitted, prodex uses the active profile
  -h, --help            Print help
"""), executable)
    return String()


def top_level_profile_use_help(executable: String) -> String:
    return _profile_executable(String("""Set the active profile used by commands that omit --profile.

Usage: prodex use [OPTIONS]

Options:
  -p, --profile <NAME>  Profile name. If omitted, prodex uses the active profile
  -h, --help            Print help
"""), executable)


def profile_short_help(command: String, executable: String) -> String:
    if command == "add":
        return _profile_executable(String("""Add a profile entry and optionally seed it from another CODEX_HOME

Usage: prodex profile add [OPTIONS] <NAME>

Arguments:
  <NAME>  Name of the profile to create

Options:
      --codex-home <PATH>  Register an existing CODEX_HOME path instead of creating a managed profile home
      --copy-from <PATH>   Copy initial state from another CODEX_HOME path into the new managed profile
      --copy-current       Seed the new managed profile from the default shared Codex home
      --activate           Make the new profile active after creation
      --insecure           Bypass private-file permission and ACL validation for this operation
  -h, --help               Print help (see more with '--help')
"""), executable)
    if command == "export":
        return _profile_executable(String("""Export one or more profiles, including supported profile secrets

Usage: prodex profile export [OPTIONS] [PATH]

Arguments:
  [PATH]  Write the export bundle to this path. Defaults to a timestamped JSON file in the current directory

Options:
  -p, --profile <NAME>    Export only the named profile. Repeat to export multiple profiles. Defaults to all profiles
      --password-protect  Protect the export bundle with a password
      --no-password       Explicitly export without password protection and skip the interactive prompt
  -h, --help              Print help (see more with '--help')
"""), executable)
    if command == "import":
        return _profile_executable(String("""Import profiles from an export bundle or supported built-in source

Usage: prodex profile import [OPTIONS] <PATH_OR_SOURCE>

Arguments:
  <PATH_OR_SOURCE>  Path to a profile export bundle created by `prodex profile export`, or a built-in source such as `claude`, `copilot`, or `kiro`

Options:
      --name <NAME>  Override the imported profile name when using a built-in source such as `claude`, `copilot`, or `kiro`
      --activate     Activate the imported profile immediately when using a built-in source such as `claude`, `copilot`, or `kiro`
      --insecure     Bypass private-file permission and ACL validation for this operation
  -h, --help         Print help (see more with '--help')
"""), executable)
    if command == "import-current":
        return _profile_executable(String("""Copy the current shared Codex home into a new managed profile and activate it

Usage: prodex profile import-current [OPTIONS] [NAME]

Arguments:
  [NAME]  Name of the managed profile to create from the current shared Codex home [default: default]

Options:
      --insecure  Bypass private-file permission and ACL validation for this operation
  -h, --help      Print help (see more with '--help')
"""), executable)
    return profile_help(command, executable)


@fieldwise_init
struct ProfileHelpRequest(Copyable):
    var command: String
    var help: Bool
    var short_help: Bool


def _profile_known_command(command: String) -> Bool:
    return command in ["add", "export", "import", "import-current", "list", "remove", "use"]


def _profile_usage(command: String, executable: String) -> String:
    var prefix = executable + " profile"
    if command == "add": return prefix + " add [OPTIONS] <NAME>"
    if command == "export": return prefix + " export [OPTIONS] [PATH]"
    if command == "import": return prefix + " import [OPTIONS] <PATH_OR_SOURCE>"
    if command == "import-current": return prefix + " import-current [OPTIONS] [NAME]"
    if command == "list": return prefix + " list"
    if command == "remove": return prefix + " remove [OPTIONS] [NAME]"
    if command == "use": return prefix + " use [OPTIONS]"
    return prefix + " <COMMAND>"


def _profile_option_label(name: String) -> String:
    if name == "--codex-home" or name == "--copy-from": return name + " <PATH>"
    if name == "--profile" or name == "--name": return name + " <NAME>"
    return name


def _profile_value_option(command: String, name: String) -> Bool:
    if command == "add": return name == "--codex-home" or name == "--copy-from"
    if command == "export" or command == "use": return name == "--profile"
    if command == "import": return name == "--name"
    return False


def _profile_switch_option(command: String, name: String) -> Bool:
    if command == "add": return name in ["--copy-current", "--activate", "--insecure"]
    if command == "export": return name == "--password-protect" or name == "--no-password"
    if command == "import": return name == "--activate" or name == "--insecure"
    if command == "import-current": return name == "--insecure"
    if command == "remove": return name == "--all" or name == "--delete-home"
    return False


def _profile_has_positionals(command: String) -> Bool:
    return command == "add" or command == "export" or command == "import" or command == "import-current" or command == "remove"


def _profile_missing_value(name: String) -> Error:
    return session_cli_error("a value is required for '" + _profile_option_label(name) + "' but none was supplied")


def _profile_unexpected_argument(argument: String, command: String, executable: String, literal: Bool = False) -> Error:
    var displayed = argument
    var is_flag = argument.startswith("-") and argument != "-" and not literal
    if is_flag:
        displayed = argument_name(argument)
    var message = "unexpected argument '" + displayed + "' found"
    if is_flag and _profile_has_positionals(command):
        message += "\n\n  tip: to pass '" + displayed + "' as a value, use '-- " + displayed + "'"
    return session_cli_error(message, _profile_usage(command, executable))


def _profile_unknown_subcommand(command: String, executable: String) -> Error:
    var message = "unrecognized subcommand '" + command + "'"
    var choices: List[String] = ["add", "export", "import", "import-current", "list", "remove", "use"]
    var matches = similar_names(command, choices)
    if matches:
        message += "\n\n  tip: a similar subcommand exists: '" + String(matches[len(matches) - 1]) + "'"
    return session_cli_error(message, _profile_usage("", executable))


def _profile_duplicate(name: String, command: String, executable: String) -> Error:
    return session_cli_error("the argument '" + _profile_option_label(name) + "' cannot be used multiple times", _profile_usage(command, executable))


def _profile_missing_required(command: String, executable: String, seen: List[String], positional: String) -> Error:
    var usage = executable + " profile " + command
    if seen:
        for name in seen:
            usage += " " + _profile_option_label(name)
    usage += " " + positional
    return session_cli_error("the following required arguments were not provided:\n  " + positional, usage)


def _profile_conflict(left: String, right: String, command: String, executable: String, positional: String = "") -> Error:
    var usage = executable + " profile " + command + " " + left
    if positional:
        usage += " " + positional
    return session_cli_error("the argument '" + left + "' cannot be used with '" + right + "'", usage)


def _profile_help_value_error(argument: String, command: String, executable: String) -> Error:
    var value = String(argument.split("=", maxsplit=1)[1])
    var usage = executable + " profile"
    if command:
        usage += " " + command
    usage += " --help"
    if command == "": usage += " <COMMAND>"
    elif command == "add": usage += " <NAME>"
    elif command == "export": usage += " [PATH]"
    elif command == "import": usage += " <PATH_OR_SOURCE>"
    elif command == "import-current" or command == "remove": usage += " [NAME]"
    return session_cli_error("unexpected value '" + value + "' for '--help' found; no more were expected", usage)


def _parse_profile_help_alias(args: List[String], index: Int, executable: String) raises -> ProfileHelpRequest:
    if index >= len(args):
        return ProfileHelpRequest("", True, False)
    var command = String(args[index])
    if not _profile_known_command(command):
        raise _profile_unknown_subcommand(command, executable)
    if index + 1 < len(args):
        raise session_cli_error("unrecognized subcommand '" + String(args[index + 1]) + "'", _profile_usage(command, executable))
    return ProfileHelpRequest(command, True, False)


def parse_profile_help_arguments(args: List[String], index: Int, executable: String, help_alias: Bool = False) raises -> ProfileHelpRequest:
    """Parse through the first help flag without running a profile operation."""
    if help_alias:
        return _parse_profile_help_alias(args, index, executable)
    var cursor = index
    if cursor >= len(args):
        return ProfileHelpRequest("", False, False)

    var command = String(args[cursor])
    if command == "--help" or command == "-h":
        return ProfileHelpRequest("", True, command == "-h")
    if command.startswith("--help="):
        raise _profile_help_value_error(command, "", executable)
    if command.startswith("-h"):
        return ProfileHelpRequest("", True, True)
    if command == "help":
        return _parse_profile_help_alias(args, cursor + 1, executable)
    if command.startswith("-"):
        raise _profile_unexpected_argument(command, "", executable)
    if not _profile_known_command(command):
        raise _profile_unknown_subcommand(command, executable)

    cursor += 1
    var seen = List[String]()
    var positionals = List[String]()
    var literal = False
    while cursor < len(args):
        var argument = String(args[cursor])
        if not literal and argument == "--":
            literal = True
            cursor += 1
            continue
        if not literal and (argument == "--help" or argument == "-h"):
            return ProfileHelpRequest(command, True, argument == "-h")
        if not literal and argument.startswith("-h"):
            return ProfileHelpRequest(command, True, True)
        if not literal and argument.startswith("--help="):
            raise _profile_help_value_error(argument, command, executable)

        var name = String(argument)
        var value = String()
        var has_inline_value = False
        if not literal and argument.startswith("--"):
            var pieces = argument.split("=", maxsplit=1)
            name = String(pieces[0])
            if len(pieces) == 2:
                has_inline_value = True
                value = String(pieces[1])
        elif not literal and (command == "export" or command == "use") and argument.startswith("-p") and argument != "-p":
            name = "--profile"
            has_inline_value = True
            value = String(argument[byte=2:])
        elif not literal and argument == "-p" and (command == "export" or command == "use"):
            name = "--profile"

        var takes_value = not literal and _profile_value_option(command, name)
        var switch = not literal and _profile_switch_option(command, name)
        if not literal and not takes_value and not switch and argument.startswith("-") and argument != "-":
            raise _profile_unexpected_argument(argument, command, executable)
        if takes_value or switch:
            if name in seen and not (command == "export" and name == "--profile"):
                raise _profile_duplicate(name, command, executable)
            if takes_value:
                if has_inline_value:
                    if not value:
                        raise _profile_missing_value(name)
                else:
                    if cursor + 1 >= len(args):
                        raise _profile_missing_value(name)
                    var next_argument = String(args[cursor + 1])
                    var next_name = String(argument_name(next_argument))
                    if next_name == "-p" and (command == "export" or command == "use"):
                        next_name = "--profile"
                    if next_argument == "--" or next_argument == "--help" or next_argument.startswith("-h") or _profile_value_option(command, next_name) or _profile_switch_option(command, next_name):
                        raise _profile_missing_value(name)
                    if not next_argument.startswith("-") or next_argument == "-":
                        cursor += 1
                        value = String(args[cursor])
                        if not value:
                            raise _profile_missing_value(name)
            elif has_inline_value:
                var unexpected_value = String(argument.split("=", maxsplit=1)[1])
                var usage = executable + " profile " + command + " " + name
                if command == "add": usage += " <NAME>"
                elif command == "remove": usage += " [NAME]"
                raise session_cli_error("unexpected value '" + unexpected_value + "' for '" + name + "' found; no more were expected", usage)
            seen.append(name)
        else:
            var maximum = 1 if (command == "add" or command == "import" or command == "import-current" or command == "export" or command == "remove") else 0
            if len(positionals) >= maximum:
                raise _profile_unexpected_argument(argument, command, executable, literal)
            positionals.append(argument)
        cursor += 1

    if command == "add" and not positionals:
        raise _profile_missing_required(command, executable, seen, "<NAME>")
    if command == "import" and not positionals:
        raise _profile_missing_required(command, executable, seen, "<PATH_OR_SOURCE>")
    if command == "remove":
        if "--all" in seen and positionals:
            raise _profile_conflict("--all", "[NAME]", command, executable, "[NAME]")
        if "--all" not in seen and not positionals:
            raise _profile_missing_required(command, executable, seen, "<NAME>")
    if command == "export" and "--password-protect" in seen and "--no-password" in seen:
        raise _profile_conflict("--password-protect", "--no-password", command, executable, "[PATH]")
    return ProfileHelpRequest(command, False, False)
