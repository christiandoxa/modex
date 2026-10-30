# Bodyless SSE connection header

The active reference is Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

For the tested DeepSeek passthrough route, the reference writes both
`Transfer-Encoding: chunked` and `Connection: close` on empty HTTP 204 and
304 event-stream responses. Modex previously omitted the connection header.
The production response writer now includes it for this bodyless chunked case.
Despite that header, a raw-socket comparison observed both processes accept a
second request on the same connection and return its 200 response. Modex keeps
that existing reuse behavior. JSON 204/304 and event-stream 205 controls also
match the tested reference framing.

The pinned upstream `crates/prodex-app/src/runtime_proxy/response_forwarding/streaming_writer.rs`
emits the close and chunked headers and terminal chunk for streaming replies.
The related dispatch paths reach this writer for the tested SSE responses.

The production build, four active passthrough tests and production dependency
audit passed. Tests used synthetic credentials and peers, isolated temporary
state, and a private loopback-only network namespace. This evidence covers
the tested Linux x86-64 HTTP route, not physical connection closure, all
response shapes, other transports, or other release targets.
