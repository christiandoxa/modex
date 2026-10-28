# App-server invalid UTF-8 error

The verified 0.165.1 Linux oracle has SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
At the pinned source, `crates/prodex-app/src/runtime_tools/hook_trust.rs`
reads stdout with `BufRead::lines()` and wraps line decoding errors as
`Codex hook-trust preflight stdout failed: ...`.

When a synthetic app-server writes one invalid UTF-8 byte after receiving
`initialize`, the oracle reports `Error: Codex hook-trust preflight stdout
failed: stream did not contain valid UTF-8`. Production Modex now reports the
same final line. Before the fix, Modex included `initialize failed` in this
error. Both processes exit 1, send one `initialize`, write no stdout, make no
upstream request, and remove temporary overlays. The comparison is in
`python3 tests/test_app_server_rpc_01651.py`. The same comparison covers
invalid UTF-8 during the later `hooks/list` phase.

The test also sends a valid `雪` response with its UTF-8 bytes split across two
writes, preceded by malformed JSON and an unmatched response ID. Both the
0.165.1 oracle and Modex continue through hook verification and the synthetic
loopback request successfully. A checksum-verified 0.439.2 historical oracle
(`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`) emits
the same invalid-UTF-8 error in both phases and passes the split/noise control.
This historical observation does not extend the active target claim.

The test uses isolated homes and a synthetic Codex child. No real credentials
or external provider traffic are used. This qualifies invalid app-server
stdout bytes only on Linux x86-64; other release targets and broader transport
behavior remain unverified.
