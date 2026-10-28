# App-server closed-stdin error

The verified 0.165.1 Linux oracle has SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
Its `crates/prodex-app/src/runtime_tools/hook_trust.rs` writes each JSON-RPC
request with `stdin.write_all`; when the Codex child closes stdin after
`initialize`, the oracle reports `Error: Broken pipe (os error 32)`.

Before the fix, Modex reported `Error: Codex hook-trust preflight hooks/list
failed: request write failed` for the same synthetic process. Now only EPIPE
maps to the observed message and the standard-library errno; `MSG_NOSIGNAL` remains in use, and
other write errors retain their existing handling.

`python3 tests/test_app_server_rpc_01651.py` compares the last error line from
both production entrypoints. The isolated synthetic Codex peer closes stdin
after the initialize request. Both processes exit 1, send no later RPC, and
make zero upstream requests. Full stderr remains different because Modex does
not emit the oracle's launch progress lines. No external provider traffic or
real credentials are used. This qualifies the closed-stdin error only; broader
transport behavior and the other five release targets remain unqualified.
The numeric errno text is verified only on Linux x86-64; macOS and Windows
behavior remains unverified.
