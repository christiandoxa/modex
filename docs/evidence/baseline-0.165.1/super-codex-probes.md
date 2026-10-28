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
both probes. They return exit 1 with the same normalized diagnostic, make no
app-server RPC or provider request, and leave no temporary runtime overlay.
The Codex executable and upstream are synthetic; no account, real credential,
or provider traffic is used.

Reproduce with:

```sh
python3 scripts/ci/run-unittest.py test_super_launch_01651.py
```

Fast and Full CI run this module in the active 0.165.1 reference lane before
historical oracle routing. This verifies the selected Linux x86-64 probe
failure and environment boundary only. The Codex semantic-version parser,
wrapper/hash checks, full launch/storage/security behavior, other release
targets, and broader Super parity remain unverified.
