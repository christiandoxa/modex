def update_help(executable: String) -> String:
    return "Update Prodex from the latest verified GitHub release binary.\n\nUsage: " + executable + " update\n\nOptions:\n  -h, --help  Print help\n"


def login_help(executable: String) -> String:
    return String("""Run provider login flows, using Prodex profiles where supported.

Usage: prodex login [OPTIONS] [PROFILE_OR_LOGIN_ARG]...

Arguments:
  [PROFILE_OR_LOGIN_ARG]...  Optional profile name first, followed by login-method flags or provider arguments

Options:
  -p, --profile <NAME>  Existing profile to log into. If omitted, prodex creates or reuses a profile by workspace identity
  -h, --help            Print help

Examples:
  prodex login
  prodex login main
  prodex login --profile main
  prodex login --device-auth
  prodex login --with-claude
  prodex login --with-antigravity

Notes:
  A leading non-option argument selects the profile; `status` remains Codex login status.
  Use --profile when selecting a profile literally named `status`.
  OpenAI/Codex, Claude, and API-key login paths create or update Prodex profiles.
  Google Gemini OAuth profiles are unsupported; native Gemini CLI / Vertex AI compatibility is retired. Use a Gemini API key with `prodex s gemini`; native Antigravity remains available through `prodex s gemini --cli agy`.
  Antigravity login delegates to `agy auth login` and does not create a Prodex profile.
""").replace("Usage: prodex ", "Usage: " + executable + " ")


def logout_usage(executable: String) -> String:
    return executable + " logout [OPTIONS] [NAME]"


def logout_help(executable: String) -> String:
    return String("""Run codex logout for the selected or active profile.

Usage: prodex logout [OPTIONS] [NAME]

Arguments:
  [NAME]  Profile name. If omitted, prodex uses the active profile

Options:
  -p, --profile <NAME>  Profile name. If omitted, prodex uses the active profile
  -h, --help            Print help
""").replace("Usage: prodex ", "Usage: " + executable + " ")


def quota_help(executable: String) -> String:
    return String("""Inspect live quota for one profile or the whole profile pool.

Usage: prodex quota [OPTIONS]

Options:
  -p, --profile <NAME>
          Inspect a single profile instead of the default detailed pool view

      --all
          Show every configured profile in a compact aggregated view

      --auth <AUTH>
          Show only profiles whose auth label or compatibility matches this filter.
\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20
          Supported values: no-auth, chatgpt, api-key, invalid-auth, unreadable-auth, quota-compatible, non-quota-compatible, all.

      --provider <PROVIDER>
          Show only profiles for one provider in aggregated views.
\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20
          Supported values: all, openai, gemini, anthropic, claude, copilot, kiro, deepseek, local, agy.

      --detail
          Include exact reset timestamps and expanded window details

      --raw
          Print raw usage JSON for a single profile and disable the live refresh view

      --once
          Render one human-readable snapshot instead of refreshing every 5 seconds

      --base-url <URL>
          Override the ChatGPT backend base URL used for quota requests

  -h, --help
          Print help (see a summary with '-h')

Best practice:
  `prodex quota` defaults to the detailed live view across all profiles.

Examples:
  prodex quota
  prodex quota --once
  prodex quota --provider openai
  prodex quota --profile main --detail
  prodex quota --all --detail
  prodex quota --all --provider deepseek --base-url https://api.deepseek.com --once
  prodex quota --all --provider local --base-url http://127.0.0.1:8131/v1 --once
  prodex quota --all --once
  prodex quota --all --auth no-auth --once
  prodex quota --raw --profile main

Notes:
  `prodex quota` supports OpenAI/Codex, Anthropic OAuth, imported Copilot, DeepSeek API-key, Antigravity CLI, local OpenAI-compatible, and custom provider snapshots.
  Use `--provider` to filter the default pool view by provider: `openai`, `gemini`, `anthropic`, `claude`, `copilot`, `kiro`, `deepseek`, `local`, or `agy`.
  Use `--auth` to filter the default pool view by auth label or compatibility, for example `no-auth` or `quota-compatible`.
  Explicit `--all` without `--detail` preserves the compact aggregate view.
  If a profile's `config.toml` sets `model_provider` to a non-OpenAI backend such as `amazon-bedrock` or `amazon-bedrock-runtime`, prodex shows a provider snapshot instead of failing the quota view.
""").replace("Usage: prodex ", "Usage: " + executable + " ").replace(
        "prodex quota", "modex quota"
    )


def quota_short_help(executable: String) -> String:
    return String("""Inspect live quota for one profile or the whole profile pool.

Usage: prodex quota [OPTIONS]

Options:
  -p, --profile <NAME>       Inspect a single profile instead of the default detailed pool view
      --all                  Show every configured profile in a compact aggregated view
      --auth <AUTH>          Show only profiles whose auth label or compatibility matches this filter
      --provider <PROVIDER>  Show only profiles for one provider in aggregated views
      --detail               Include exact reset timestamps and expanded window details
      --raw                  Print raw usage JSON for a single profile and disable the live refresh view
      --once                 Render one human-readable snapshot instead of refreshing every 5 seconds
      --base-url <URL>       Override the ChatGPT backend base URL used for quota requests
  -h, --help                 Print help (see more with '--help')

Best practice:
  `prodex quota` defaults to the detailed live view across all profiles.

Examples:
  prodex quota
  prodex quota --once
  prodex quota --provider openai
  prodex quota --profile main --detail
  prodex quota --all --detail
  prodex quota --all --provider deepseek --base-url https://api.deepseek.com --once
  prodex quota --all --provider local --base-url http://127.0.0.1:8131/v1 --once
  prodex quota --all --once
  prodex quota --all --auth no-auth --once
  prodex quota --raw --profile main

Notes:
  `prodex quota` supports OpenAI/Codex, Anthropic OAuth, imported Copilot, DeepSeek API-key, Antigravity CLI, local OpenAI-compatible, and custom provider snapshots.
  Use `--provider` to filter the default pool view by provider: `openai`, `gemini`, `anthropic`, `claude`, `copilot`, `kiro`, `deepseek`, `local`, or `agy`.
  Use `--auth` to filter the default pool view by auth label or compatibility, for example `no-auth` or `quota-compatible`.
  Explicit `--all` without `--detail` preserves the compact aggregate view.
  If a profile's `config.toml` sets `model_provider` to a non-OpenAI backend such as `amazon-bedrock` or `amazon-bedrock-runtime`, prodex shows a provider snapshot instead of failing the quota view.
""").replace("Usage: prodex ", "Usage: " + executable + " ").replace(
        "prodex quota", "modex quota"
    )


def ping_help(executable: String) -> String:
    return String("""Send lightweight prompt checks through ready profiles.

Usage: prodex ping <COMMAND>

Commands:
  openai  Send a minimal application request through the OpenAI/Codex runtime path.
  help    Print this message or the help of the given subcommand(s)

Options:
  -h, --help  Print help
""").replace("Usage: prodex ", "Usage: " + executable + " ")


def ping_openai_help(executable: String) -> String:
    return String("""Send a minimal application request through the OpenAI/Codex runtime path.

Usage: prodex ping openai [OPTIONS]

Options:
  -p, --profile <NAME>  Probe only this OpenAI profile; omitted probes every configured eligible OpenAI profile
      --model <MODEL>   Model passed through to the normal Codex request path
      --effort <LEVEL>  Reasoning effort passed through to the normal Codex request path
      --base-url <URL>  Override the ChatGPT backend base URL used by the normal OpenAI request path
      --no-proxy        Bypass proxy environment variables for the normal OpenAI request path
      --json            Emit one stable JSON result instead of human-readable output
  -h, --help            Print help
""").replace("Usage: prodex ", "Usage: " + executable + " ")


def root_help(executable: String) -> String:
    return "Manage multiple Codex account profiles with profile-local auth and shared Codex state.\n\nUsage: " + executable + " <COMMAND>\n\nCommands:\n  profile  Add, inspect, remove, and activate managed profiles.\n  use      Set the active profile used by commands that omit --profile.\n  current  Show the active profile and its CODEX_HOME details.\n  info     Summarize Prodex version, profiles, runtime policy, logs, and secret backend.\n  status   Monitor profiles, quota resets, token efficiency, and Prodex resource usage.\n  log      Follow redacted Prodex runtime logs.\n  session  Inspect shared Codex session metadata.\n  doctor   Inspect local state, Codex resolution, quota readiness, and runtime logs.\n  login    Run provider login flows, using Prodex profiles where supported.\n  logout   Run codex logout for the selected or active profile.\n  update   Update Prodex from the latest verified GitHub release binary.\n  quota    Inspect live quota for one profile or the whole profile pool.\n  redeem   Redeem one reset credit manually for a named OpenAI/Codex profile.\n  ping     Send lightweight prompt checks through ready profiles.\n  run      Run codex through prodex with quota preflight and eligible pre-commit rotation.\n  super    YOLO shortcut for the Super tool stack with opt-in Presidio. [alias: s]\n  gateway  Run a lean OpenAI-compatible provider gateway.\n  help     Print this message or the help of the given subcommand(s)\n\nOptions:\n  -h, --help     Print help\n  -V, --version  Print version\n\nTips:\n  Bare `modex` invocation defaults to `modex run`.\n  Use `modex status` for the live quota, token, and resource dashboard.\n  Use `modex quota` for the detailed live quota view across profiles.\n  Use `modex <command> -h` to see every parameter for that command.\n\nExamples:\n  modex\n  modex exec \"review this repo\"\n  modex profile list\n  modex status\n  modex quota\n  modex redeem main\n  modex run --profile main\n"
