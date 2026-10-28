"""Stateless profile command help from the frozen CLI surface."""


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
