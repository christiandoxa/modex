# DeepSeek HTTP base URL backslash paths (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The active local-rewrite URL builder is
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_transport/urls.rs::runtime_local_rewrite_upstream_url`.
Its request path passes the assembled URL to reqwest in
`local_rewrite_transport.rs`. The real 0.166.0 process accepts a backslash as
an HTTP path separator: a synthetic request using
`http://127.0.0.1:<port>\v1` reached `/v1/chat/completions`; the same base on
the Anthropic Messages path reached `/v1/anthropic/v1/messages`.

Modex previously searched only for `/` after the scheme and treated this
valid path separator as part of the host/port. The shared local-rewrite URL
parser now splits at the first `/` or `\` after `http://`. The existing
credential-free, HTTP-only and numeric-loopback checks still validate the
authority before a connection is made. Caller credentials, query strings,
fragments, controls, and malformed or encoded host delimiters remain rejected.

`test_provider_base_url_scheme_01660.py` compares the real oracle and Modex
through synthetic loopback providers for Chat and Anthropic Messages. It also
compares strict-tools routing through `PRODEX_DEEPSEEK_BETA_BASE_URL` with a
`\beta` path: both processes sent the Chat request to
`/beta/chat/completions`. Non-loopback and credential-bearing backslash forms
fail before provider I/O. `test_gateway_cli` covers the native URL parser,
including non-loopback, `@`, query, fragment, `%5c`, and malformed escape
controls. The active process comparisons ran in a private bubblewrap network
namespace with isolated HOME and temporary state, read-only
worktree/oracle/binary, and loopback-only provider fixtures. No real
credentials or external traffic were used.

Validation passed with Mojo 1.2.0 on Linux x86-64. This qualifies only the
tested HTTP URL path form and does not establish other target or full relay
parity.
