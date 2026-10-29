# Super Codex probe environment

The active Prodex 0.165.1 Linux oracle is pinned at SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
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
version, capability, and bounded-capture errors. It also prints the child-start
fallback only after capability and hook-trust preflight succeeds. Full output,
exit status, probe arguments, environment sanitization, no-provider-request
behavior, and overlay cleanup are compared against 0.165.1. The same progress
cases compare against historical 0.439.2.
The redirected provider panel also matches `PRODEX_TERM_COLUMNS=50` and `120`.
PTY comparisons cover the text fallback with `TERM=dumb` and
`PRODEX_TUI_STRICT=true`; they do not render or qualify the interactive panel.
Hosted Fast CI run `40788779491` failed when the old normalizer assumed the
fixture was directly under `/tmp`; the shared normalizer now covers nested
private roots and the 0.439.2 regression suite checks the same path layout.

Oversized synthetic `--version` and `app-server --help` output also produce
the same path-wrapped capture diagnostics in both binaries. The executable
and upstream are synthetic; no account, real credential, or provider traffic
is used. Redirected and selected TTY fallback text is qualified; interactive
TTY panel rendering, wrapper/hash qualification, other malformed version
inputs, full startup/storage/security behavior, other targets, and broader
Super parity remain unverified.

Reproduce with:

```sh
python3 scripts/ci/run-unittest.py test_super_launch_01651.py
```

Fast and Full CI run this module in the active 0.165.1 reference lane before
historical oracle routing. This verifies selected Linux x86-64 startup probes
and version cases only. Other release targets and broader Super parity remain
unverified.
