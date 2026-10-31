"""Super command help, including its unimplemented runtime obligations."""


def super_help(executable: String) -> String:
    var output = String("""YOLO shortcut for the Super tool stack with opt-in Presidio.

Usage: prodex super [OPTIONS] [CODEX_ARG]...

Arguments:
  [CODEX_ARG]...  Arguments passed through to `codex` after Prodex's generated options

Options:
  -p, --profile <NAME>
          Starting profile for the run. If omitted, prodex uses the active profile
      --auto-rotate
          Allow eligible pre-commit rotation. This is the default behavior
      --no-auto-rotate
          Keep the selected profile fixed and fail instead of rotating
      --auto-redeem
          Allow Prodex to redeem one earned reset credit automatically when all configured OpenAI/Codex profiles are weekly-exhausted
      --skip-quota-check
          Skip the preflight quota gate before launching codex
      --full-access
          Compatibility flag. Super already starts Codex with launch-time full access
      --dry-run
          Print resolved launch diagnostics without starting Codex
      --base-url <URL>
          Override the upstream ChatGPT base URL used for quota preflight and the runtime proxy
      --no-proxy
          Disable system and environment proxy settings for upstream OpenAI/quota HTTP requests
      --presidio
          Enable Presidio request-body and WebSocket text redaction without prompting. Unsupported by native Kiro and Antigravity CLIs
      --no-presidio
          Disable Presidio redaction and skip the interactive opt-in prompt
      --sub-agent
          Enable Codex sub-agent support for this Super launch
      --no-sub-agent
          Disable Codex sub-agent support for this Super launch
      --sub-agent-provider <PROVIDER>
          Provider used by sub-agents. Detail flags require explicit sub-agent
      --sub-agent-model <MODEL>
          Model used by sub-agents. Any nonempty model id is accepted
      --sub-agent-model-reasoning-effort <EFFORT>
          Reasoning effort used by the sub-agent model
      --sub-agent-url <URL>
          Local HTTP(S) endpoint used by sub-agents
      --sub-agent-max-concurrency <VALUE>
          Maximum number of child sub-agent processes active at once (1-64)
      --tool <TOOL>
          Add an optional tool to the default Super tool set
      --require-tool <TOOL>
          Require an optional tool; launch fails before the TUI if it is missing or invalid
      --url <URL>
          Route Codex directly to a local OpenAI-compatible /v1 endpoint
      --provider <PROVIDER>
          External provider preset to use through Codex/Super
      --cli <CLI>
          Compatibility native CLI. Prodex 0.430 retains Antigravity (agy) only [possible values: agy]
      --api-key <KEY>
          API key for --provider. Prefer the provider-specific environment variable for shells/history
      --model <MODEL>
          Model id to use with Codex, --url, or --provider [alias: --local-model]
      --context-window <TOKENS>
          Context window advertised to Codex when using --url or --provider [alias: --local-context-window]
      --auto-compact-token-limit <TOKENS>
          Auto-compact threshold advertised to Codex when using --url or --provider [alias: --local-auto-compact-token-limit]
      --web-search <MODE>
          Override Codex hosted web search mode: disabled, cached, indexed, or live [possible values: disabled, cached, indexed, live]
      --rollout-budget-tokens <TOKENS>
          Enable Codex rollout token-budget reminders with this total token limit
      --rollout-budget-reminders <TOKENS>
          Remaining-token thresholds for rollout budget reminders. Defaults to 75%,50%,25% of the limit
      --rollout-budget-sampling-weight <WEIGHT>
          Sampling token weight used by Codex rollout budget accounting
      --rollout-budget-prefill-weight <WEIGHT>
          Prefill token weight used by Codex rollout budget accounting
      --current-time-reminder
          Enable Codex current-time reminders
      --current-time-reminder-interval <REQUESTS>
          Model-request interval for Codex current-time reminders
      --current-time-clock-source <SOURCE>
          Clock source for Codex current-time reminders [possible values: system, external]
      --respect-system-proxy
          Enable Codex auth clients to respect the OS system proxy when upstream Codex supports it
      --no-respect-system-proxy
          Disable Codex auth system-proxy routing even when the profile config enables it
  -h, --help
          Print help

Examples:
  prodex super
  prodex super --model gpt-5.3-codex
  prodex super --url http://127.0.0.1:8131
  prodex super deepseek --model deepseek-v4-pro
  prodex super gemini
  prodex super gemini
  prodex super --provider copilot
  prodex super --provider kiro --profile kiro-main
  prodex super gemini --cli agy
  prodex super --sub-agent --sub-agent-provider openai --sub-agent-model gpt-5.3-codex
  prodex super --sub-agent --sub-agent-model-reasoning-effort xhigh
  prodex super --sub-agent --sub-agent-max-concurrency 8
  prodex super --no-sub-agent
  prodex super exec "review latest diff in super mode"
  prodex super 019c9e3d-45a0-7ad0-a6ee-b194ac2d44f9
  prodex super --profile main
  prodex super --web-search indexed
  prodex super --rollout-budget-tokens 100000

Notes:
  `prodex super` enables Smart Context and the available typed optimizer tools in the temporary Prodex overlay.
  Missing optional tools are skipped unless named with `--require-tool`; use `prodex doctor --install` to inspect local prerequisites.
  Super is the explicit YOLO path: it bypasses approvals and the sandbox, bypasses hook-trust confirmation, and trusts the current workspace for this invocation.
  Codex runtime feature overrides from `prodex run` also work here; explicit `--web-search` overrides Super provider defaults.
  Interactive Super launches ask whether to enable Presidio. Use `--presidio` or `--no-presidio` to answer non-interactively. With default endpoints, Presidio opt-in best-effort starts local Docker services unless PRODEX_PRESIDIO_AUTO_START=0.
  Use `prodex run` instead when normal Codex approvals and workspace-trust prompts are desired.
  Use `prodex doctor --install` to inspect local runtime prerequisites without launching Codex.
  Use `--url` to point Codex directly at a local OpenAI-compatible /v1 endpoint, for example a llama-server on port 8131.
  When `--url` is set, Prodex injects a temporary `prodex-local` model provider, skips quota/rotation, and uses a local Smart Context rewrite proxy.
  Use `--provider anthropic` to route through Anthropic's OpenAI-compatible Chat Completions API. Sign in with `prodex login --with-claude`, or supply `--api-key`, ANTHROPIC_API_KEY, or ANTHROPIC_API_KEYS.
  Use `--provider copilot` to keep Codex/Super and route through a local Responses-to-Copilot adapter. Import Copilot profiles first for account routing/rotation, or supply `--api-key`, GITHUB_COPILOT_API_KEY, or GITHUB_COPILOT_API_KEYS.
  Use `--provider copilot` for the GitHub Copilot provider bridge.
  Use `deepseek` or `--provider deepseek` to keep Codex/Super and route through a local Responses-to-DeepSeek adapter. Supply `--api-key`, DEEPSEEK_API_KEY, or DEEPSEEK_API_KEYS.
  Use `gemini` or `--provider gemini` to route Codex through Gemini with `--api-key`, GEMINI_API_KEY, GEMINI_API_KEYS, GOOGLE_API_KEY, or GOOGLE_API_KEYS.
  Google Gemini OAuth profile routing is unsupported and disabled. Existing OAuth profiles remain readable for migration diagnostics but cannot launch.
  Use `--provider gemini` or positional `gemini` with a Gemini API key for the Gemini provider bridge.
  Use `--provider kiro --profile <name>` with an imported Kiro profile for the application-level Codex-to-Kiro ACP bridge.
  Add `--cli agy` to launch Antigravity CLI with `--dangerously-skip-permissions`. Antigravity owns its keyring auth and currently cannot use Prodex account rotation. Override the binary with PRODEX_AGY_BIN.
  Local mode defaults to a 16k context window; use `--context-window` and `--auto-compact-token-limit` if your server is configured larger.
  --sub-agent explicitly enables sub-agents; --no-sub-agent explicitly disables them.
  --sub-agent-provider, --sub-agent-model, --sub-agent-model-reasoning-effort, --sub-agent-url, and --sub-agent-max-concurrency require --sub-agent.
  Sub-agent provider names use canonical ProviderId values and default to openai; model ids are arbitrary nonempty strings.
  Sub-agent reasoning efforts are none, minimal, low, medium, high, xhigh, max, or ultra.
  Maximum active sub-agents defaults to 4; presets are 4, 8, 16, and 32, with custom values from 1 through 64.
  Additional Codex args are appended unchanged after Prodex's generated options.
  The expose URL is an ephemeral full-Super bearer capability. Anyone with the complete URL can control the configured workspace session; this is not OAuth or multi-user authentication. Use `--no-tunnel` or select Local only for loopback access.
""")
    output = output.replace("Usage: prodex ", "Usage: " + executable + " ")
    return output^


def super_expose_help(executable: String) -> String:
    var output = String("""Usage: prodex __super-expose [OPTIONS] [MODE] [CODEX_ARG]...

Arguments:
  [MODE]          MCP surface to expose. Exec mode exposes only the direct OS exec tool [default: full] [possible values: full, exec]
  [CODEX_ARG]...  Arguments passed through to `codex` after Prodex's generated options

Options:
      --listen <ADDR>
          Loopback address for the local MCP endpoint [default: 127.0.0.1:0]
      --no-tunnel
          Keep the endpoint local. This is the default and remains accepted for 0.429.x compatibility
      --tunnel
          Public tunnel compatibility flag. The lean 0.430 expose surface is local-only
      --openai-tunnel-id <ID>
          Pre-created OpenAI Secure MCP Tunnel id. Supplying it enables the official tunnel client
      --name <NAME>
          Optional display name for this workspace endpoint
  -p, --profile <NAME>
          Starting profile for the run. If omitted, prodex uses the active profile
      --auto-rotate
          Allow eligible pre-commit rotation. This is the default behavior
      --no-auto-rotate
          Keep the selected profile fixed and fail instead of rotating
      --auto-redeem
          Allow Prodex to redeem one earned reset credit automatically when all configured OpenAI/Codex profiles are weekly-exhausted
      --skip-quota-check
          Skip the preflight quota gate before launching codex
      --full-access
          Compatibility flag. Super already starts Codex with launch-time full access
      --dry-run
          Print resolved launch diagnostics without starting Codex
      --base-url <URL>
          Override the upstream ChatGPT base URL used for quota preflight and the runtime proxy
      --no-proxy
          Disable system and environment proxy settings for upstream OpenAI/quota HTTP requests
      --presidio
          Enable Presidio request-body and WebSocket text redaction without prompting. Unsupported by native Kiro and Antigravity CLIs
      --no-presidio
          Disable Presidio redaction and skip the interactive opt-in prompt
      --sub-agent
          Enable Codex sub-agent support for this Super launch
      --no-sub-agent
          Disable Codex sub-agent support for this Super launch
      --sub-agent-provider <PROVIDER>
          Provider used by sub-agents. Detail flags require explicit sub-agent
      --sub-agent-model <MODEL>
          Model used by sub-agents. Any nonempty model id is accepted
      --sub-agent-model-reasoning-effort <EFFORT>
          Reasoning effort used by the sub-agent model
      --sub-agent-url <URL>
          Local HTTP(S) endpoint used by sub-agents
      --sub-agent-max-concurrency <VALUE>
          Maximum number of child sub-agent processes active at once (1-64)
      --tool <TOOL>
          Add an optional tool to the default Super tool set
      --require-tool <TOOL>
          Require an optional tool; launch fails before the TUI if it is missing or invalid
      --url <URL>
          Route Codex directly to a local OpenAI-compatible /v1 endpoint
      --provider <PROVIDER>
          External provider preset to use through Codex/Super
      --cli <CLI>
          Compatibility native CLI. Prodex 0.430 retains Antigravity (agy) only [possible values: agy]
      --api-key <KEY>
          API key for --provider. Prefer the provider-specific environment variable for shells/history
      --model <MODEL>
          Model id to use with Codex, --url, or --provider [alias: --local-model]
      --context-window <TOKENS>
          Context window advertised to Codex when using --url or --provider [alias: --local-context-window]
      --auto-compact-token-limit <TOKENS>
          Auto-compact threshold advertised to Codex when using --url or --provider [alias: --local-auto-compact-token-limit]
      --web-search <MODE>
          Override Codex hosted web search mode: disabled, cached, indexed, or live [possible values: disabled, cached, indexed, live]
      --rollout-budget-tokens <TOKENS>
          Enable Codex rollout token-budget reminders with this total token limit
      --rollout-budget-reminders <TOKENS>
          Remaining-token thresholds for rollout budget reminders. Defaults to 75%,50%,25% of the limit
      --rollout-budget-sampling-weight <WEIGHT>
          Sampling token weight used by Codex rollout budget accounting
      --rollout-budget-prefill-weight <WEIGHT>
          Prefill token weight used by Codex rollout budget accounting
      --current-time-reminder
          Enable Codex current-time reminders
      --current-time-reminder-interval <REQUESTS>
          Model-request interval for Codex current-time reminders
      --current-time-clock-source <SOURCE>
          Clock source for Codex current-time reminders [possible values: system, external]
      --respect-system-proxy
          Enable Codex auth clients to respect the OS system proxy when upstream Codex supports it
      --no-respect-system-proxy
          Disable Codex auth system-proxy routing even when the profile config enables it
  -h, --help
          Print help
""")
    return output.replace("Usage: prodex ", "Usage: " + executable + " ")
