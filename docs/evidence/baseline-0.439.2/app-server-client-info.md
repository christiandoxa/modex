# Hook-trust client identity

The frozen 0.439.2 source at `crates/prodex-app/src/runtime_tools/hook_trust.rs`
uses `CARGO_PKG_VERSION` in the app-server initialize request. The frozen root
`Cargo.toml` sets that version to `0.439.2`. Modex now sends that version from
its production hook-trust session.

`tests/test_app_server_rpc_04392.py` launches the verified Linux release and
Modex with a synthetic Codex peer and loopback provider, and compares the
captured initialize client identity. Both report `prodex-hook-trust` and
`0.439.2`. The replay driver no longer rewrites the identity before sending
it. The separate 0.165.1 comparison records that release's different version.

This is one Linux behavior comparison, not full Super parity or evidence for
the other five release targets.
