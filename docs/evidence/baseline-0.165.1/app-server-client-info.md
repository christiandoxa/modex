# App-server hook-trust client identity

Prodex 0.165.1 declares package version `0.165.1` in `Cargo.toml`; its
`crates/prodex-app/src/runtime_tools/hook_trust.rs` initializes the app-server
client with `env!("CARGO_PKG_VERSION")`. The verified Linux oracle has SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.

Before the fix, an isolated synthetic Codex launch through the production
Modex CLI emitted `clientInfo.version="0.439.2"`; the same launch through the
0.165.1 oracle emitted `"0.165.1"`. After the fix,
`python3 tests/test_app_server_rpc_01651.py` compares those complete
`clientInfo` objects through both production entrypoints and passes.

The test uses isolated homes and a synthetic Codex child. Its one provider
request per process terminates at a synthetic loopback server; no external
provider traffic or real credentials are used. The historical
`tests/fixtures/super_hooks/historical-0.439.2.json` remains unchanged, and its
test-only driver rewrites only this request field to `0.439.2` to retain that
fixture's provenance. This verifies the initialize identity field only. The
other five release targets and broader app-server behavior remain unqualified.
