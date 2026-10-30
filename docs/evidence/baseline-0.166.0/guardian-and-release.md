# Prodex 0.166.0 Guardian and release reference checks

The official tag resolves to `9f69e1835808f478f59f12a3ae3fa88027d896a4`.
The following checks were run in an isolated checkout of that commit, with a
synthetic HOME and local fixture endpoints. They characterize Prodex; they do
not exercise Modex's missing profile-backed runtime path.

- `CARGO_NET_OFFLINE=true PRODEX_MOJO_REQUIRED=1 PRODEX_MOJO_VERSION=1.2.0 cargo test --locked -q -p prodex-app --lib runtime_proxy_guardian -- --test-threads=1`: six tests passed and one TLS test was ignored.
- `node scripts/compat/guardian-tls-smoke.mjs`: the separately enabled TLS test passed through a local TLS/CONNECT fixture. It observed three handshakes and verified that the reviewer used its parent's `__oailb` cookie after the shared cookie changed.
- `node --test --test-name-pattern='release sync preserves local-only tags' scripts/npm/release-run.test.mjs`: one test passed with a temporary local Git remote and `fetch.pruneTags=true`.

The successful Cargo runs were offline. The first, unsuccessful attempt had an
isolated HOME without the installed Rust toolchain metadata and attempted a
Rust toolchain metadata request; no account login or paid provider traffic
was used. The checked-out Prodex files remained unmodified; ignored build
artifacts were written in that isolated checkout.

The existing Modex `test_websocket_upgrade_returns_the_https_fallback_response`
passed against its real local-rewrite driver: three synthetic upgrade cases
returned 426 without an upstream request. Modex does not yet implement the
profile broker, Guardian pin and cookie handling, upstream WebSocket reuse, or
release-metadata synchronization. These behaviors remain unverified gaps on
all six targets.
