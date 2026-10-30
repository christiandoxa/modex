# DeepSeek local compact fallback

The active reference is Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`tests/test_local_compact_gap_01660.py` compares the production route with the
oracle using the synthetic Codex client and loopback-only provider fixture. It
checks compact summary bodies and headers, zero upstream requests, empty and
invalid JSON, message/tool/generic content, whitespace behavior, non-object
items, recent-item retention, UTF-8 snippet truncation, the 24 KiB summary cap,
an 8 MiB whitespace-padded model, 20,000 input items, 96 nested arrays, query
and GET handling, and an unsupported neighboring path.

The test ran with a private user, mount and network namespace, an isolated
temporary HOME and `/tmp`, and read-only bindings for the worktree, oracle, and
Mojo runtime libraries. It has no real credentials and observed no upstream
traffic.

The invalid-token control exposes a security-preserving baseline mismatch:
the 0.166.0 oracle accepts `Bearer synthetic-invalid-token` on the compact
route and returns 200, while Modex rejects it with 401 in its shared request
reader before compact dispatch. Keep the Modex client-token check; this result
is not parity for that control.

This evidence covers the tested Linux x86-64 route inputs only. It does not
qualify all JSON shapes, other release targets, remote compact behavior, or
full provider parity.
