# Super Codex probe environment

The active Prodex 0.165.1 Linux oracle is pinned at SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
The Prodex 0.439.2 oracle is pinned at SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
The frozen source commits are `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.
Its `crates/prodex-app/src/codex_binary.rs` validates `codex --version`, then
runs `codex app-server --help`. The shared `probe_codex` helper removes
`CODEX_HOME`, `TEST_CODEX_LOG`, `TEST_CODEX_LOG_APPEND`,
`TEST_CODEX_ARGS_LOG`, `TEST_CODEX_ARGS_LOG_APPEND`, and
`TEST_CODEX_STDIN_LOG` from both subprocess environments.

`tests/test_super_launch_01651.py` runs the real oracle and Modex with an
isolated synthetic Codex executable. The peer records each probe's argv and
environment, then exits 7 for `app-server --help`. Both binaries issue
`--version` followed by `app-server --help`; all six variables are absent in
both probes. They return exit 1 with the same final capability diagnostic,
make no app-server RPC or provider request, and leave no temporary runtime
overlay. The test compares complete stdout and normalized stderr, including
the launch progress fallback before probes.

When provider-key variables are supplied, the 0.165.1 probe keeps
`DEEPSEEK_API_KEY`, `DEEPSEEK_API_KEYS`, and
`PRODEX_RUNTIME_LOCAL_KEYS_JSON` in the Codex probe environment. Modex strips
these variables before its Codex probe. The updated process test supplies
synthetic sentinels and asserts both behaviors; no sentinel appears in output
or diagnostics. The release's six-variable probe cleanup remains unchanged.

The frozen source requires Codex `0.153.2` or newer in
`crates/prodex-app/src/codex_binary.rs`. It parses stdout plus stderr through
`crates/prodex-mojo-core/src/codex_auth_headers.rs`, whose lexer is in
`mojo/prodex_core/codex_auth_headers.mojo`. Modex now rejects synthetic
`0.153.1` before app-server help and accepts exact-minimum `0.153.2` from
stderr with a case-insensitive Codex label and trailing punctuation. The
noninitial `+` forms `0.+153.2` and `0.153.+2` are accepted like Rust's unsigned
integer parser. A version probe that exits 7 also matches Prodex's status,
path, and install guidance. These cases run under a mode-0700 temp directory
nested below a private temp root, covering diagnostic path normalization.
Modex now matches the frozen fallback progress and provider panel before
version, capability, and bounded-capture errors. The single-key message now
uses “API-key rotation is skipped and quota preflight stays disabled.” Both
`crates/prodex-app/src/app_commands/runtime_launch/providers_mode.rs` sources
use this exact text. Multi-key output keeps “API-key rotation is enabled across
N keys; quota preflight stays disabled.”
`test_deepseek_provider_panel_key_counts_match_both_releases` compares both
messages across 0.165.1, 0.439.2, and Modex using synthetic one-key and two-key
inputs, then forces a Codex capability-probe failure before provider I/O. It
also prints the child-start fallback only after capability and hook-trust
preflight succeeds. Full output, exit status, probe arguments,
legacy instrumentation-variable sanitization, no-provider-request behavior,
and overlay cleanup are compared against 0.165.1. The same progress cases
compare against historical 0.439.2.

The focused process run passed three methods:

```sh
PYTHONPATH=tests rtk python3 -m unittest \
  test_super_launch_01651.ActiveSuperLaunchTests.test_probe_failure_and_environment_match_01651 \
  test_super_launch_01651.ActiveSuperLaunchTests.test_deepseek_provider_panel_key_counts_match_both_releases \
  test_super_launch.SuperLaunchTests.test_launch_progress_and_probe_errors_match_historical_release
```

`rtk make build` passes with existing unused-variable warnings. The production
import audit passes for 71 Mojo files. The test census passes with 50 native
test sources and 140 Python modules. `git diff --check` passes. The full suite
was not run.

The redirected provider panel also matches `PRODEX_TERM_COLUMNS=50` and `120`.
PTY comparisons cover text fallback with `TERM=dumb` and
`PRODEX_TUI_STRICT=true`, but the test PTY has no controlling-terminal size;
those checks do not qualify natural TTY width or render the interactive panel.
`tests/test_terminal_dimensions.py` now creates a controlling 24x42 PTY. Both
the 0.165.1 and 0.439.2 oracles render a 42-column fallback panel;
Modex renders 110 columns. The test records this expected mismatch and confirms
no upstream/provider request or overlay remains. `mojo build
probes/gaps/terminal.mojo` directly fails because Mojo 1.2.0's `std.os` exports
neither `openpty` nor `terminal_size`. Both pinned Prodex sources obtain Unix
dimensions by opening `/dev/tty` and running `stty size`; the project rules
prohibit that helper and new native bindings. Natural TTY width therefore
remains an explicit parity gap.
Hosted Fast CI run `40788779491` failed when the old normalizer assumed the
fixture was directly under `/tmp`; the shared normalizer now covers nested
private roots and the 0.439.2 regression suite checks the same path layout.

Oversized synthetic `--version` and `app-server --help` output also produce
the same path-wrapped capture diagnostics in both binaries. The executable
and upstream are synthetic; no account, real credential, or provider traffic
is used. Redirected and selected TTY fallback text is qualified; controlling
TTY width without `PRODEX_TERM_COLUMNS`, interactive TTY panel rendering,
wrapper/hash qualification, other malformed version inputs, full
startup/storage/security behavior, other targets, and broader Super parity
remain unverified.

## Codex executable selection

The pinned `crates/prodex-app/src/codex_binary.rs` keeps an explicitly set
`PRODEX_CODEX_BIN` spelling, resolves relative paths against the working
directory and bare command names through `PATH`, and selects the first
canonical `codex` in `PATH` when the variable is unset. Default discovery
skips Prodex wrappers and six legacy bundled Codex hashes. Validation resolves
symlinks before checking the executable, while the later child command uses
the selected path spelling.

Modex now resolves the same tested forms using Mojo stdlib path, mode and SHA
helpers. Version and capability probes use the canonical executable path as
`argv[0]`. Hook preflight and final launch execute that canonical path while
preserving the selected spelling as `argv[0]` for native ELF Codex processes.
For shebang scripts, the interpreter instead sees the executed script path:
the oracle keeps the selected spelling for preflight/final execution while
Modex uses the canonical path. `tests/codex_argv_child.mojo` is a native
synthetic ELF that records the raw argument vector, including
`argv[0]`, and serves the hook-trust RPC. `tests/test_super_launch_01651.py`
compares those arguments against the checksum-pinned oracle across a relative
path, relative symlink, configured bare command, default PATH discovery,
relative PATH entry and shim skip. It also compares full redirected
stdout/stderr, exit code, no-request behavior and overlay cleanup through the
actual compiled Modex CLI. Synthetic Codex controls also cover a missing
executable.
The selected launch cases reach the final child, which exits 7 before making
any provider request. The missing case matches the release diagnostic and
starts no Codex or provider peer.

A real shebang-script capture now matches the reference: both binaries pass
the canonical path to version and capability probes, then expose the selected
relative path, symlink or PATH candidate to the preflight and final script
interpreter. The native ELF fixture also checks raw `argv[0]`, including an
empty PATH entry, and records PIDs that the harness checks are reaped.

These controls expose an existing storage difference: 0.165.1 creates profile,
housekeeping and session lock files during launch and even on the missing
binary path; Modex does not implement those lock lifecycles. Both remove the
temporary launch overlay and preserve the synthetic session. This slice does
not claim matching storage mutations. The selected executable path is not
pinned: replacement or symlink retargeting between probe and spawn remains
possible because Mojo 1.2 exposes no
file-descriptor-based spawn. The six legacy hashes
and wrapper markers are ported from the pinned source, but the test suite does
not run an actual legacy Codex binary. This qualifies only the selected Linux
x86-64 cases; other release targets and full Super startup remain open.

Reproduce with:

```sh
make build
make unit-build
python3 scripts/ci/run-unittest.py test_super_launch_01651.py
```

Fast and Full CI run this module as a 0.165.1 historical comparison. This verifies selected Linux x86-64 startup probes
and version cases only. Other release targets and broader Super parity remain
unverified.
