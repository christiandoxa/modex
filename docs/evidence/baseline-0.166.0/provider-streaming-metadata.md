# Streaming provider metadata passthrough

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The pinned `crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_response_dispatch.rs`
passes upstream text headers through
`runtime_forward_text_response_headers`; the helper in
`crates/prodex-runtime-proxy/src/response_forwarding.rs` drops hop-by-hop and
Connection-nominated headers. Its caller omits values that are not accepted by
`HeaderValue::to_str()`.

Modex reaches `src/modex/runtime_local_rewrite.mojo::_passthrough_response`
from its Chat Completions and native Messages paths. The shared writer applies
`_response_headers`, then sends SSE chunks without changing the body.

`tests/test_provider_passthrough_01660.py::ProviderBufferedMetadata01660Tests.test_streamed_passthrough_metadata_matches_active_release`
compares real Prodex and Modex Super processes through synthetic loopback
upstreams. It covers `/v1/chat/completions` and `/v1/messages`, with response
turn-state values containing ASCII, horizontal tab, `0x80`, `0xff`, and `é`.
Both products return HTTP 200, preserve the two ASCII/HTAB values, omit the
three non-ASCII values, retain `x-request-id`, and pass each chunked SSE body
byte-for-byte. Each of the ten route/value requests causes exactly one
synthetic upstream POST. The test does not compare the generated `Date` header.

Validation used the checksum-verified oracle, synthetic credentials and
loopback-only upstreams in a private network namespace. `HOME`, temporary
storage, configuration, and process environments were isolated. The focused
test passed on Linux x86-64 with Mojo 1.2.0.

This qualifies only the tested metadata values on these two streaming routes.
Other headers, response shapes, providers and release targets remain
unqualified.
