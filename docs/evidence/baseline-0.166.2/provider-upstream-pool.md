# Bounded upstream connection reuse

The new `LoopbackHTTPConnectionPool` retains at most one idle upstream socket
per runtime. A reusable socket is keyed by the configured numeric loopback
endpoint, credential scope, and authentication scheme (`Authorization: Bearer`
or `x-api-key`). Fully consumed, self-delimited buffered and passthrough
responses may return their socket to the pool. For ordinary translated
Responses SSE, `[DONE]` ends provider-event parsing. After the downstream
terminal chunk has been sent, Modex attempts a nonblocking HTTP framing drain
and returns the socket to the pool only if the persistent, self-delimited
response completes within the already buffered bytes and a 64 KiB additional
body / 128 KiB additional wire budget. It does not parse or forward bytes after
`[DONE]`. If framing is incomplete, close-delimited, malformed, cancelled, or
over budget, Modex closes the socket without waiting or replaying the request.
Native Messages SSE remains unpooled. Concurrent pool misses open their own
socket; the pool lock is not held during connection or response I/O, and failed
requests are not replayed.

The configured idle timeout, capped at 30 seconds, is a lazy reuse cutoff, not
an enforced socket lifetime. An expired idle socket is discarded on the next
checkout. A peer may also close an idle socket before checkout; the next
checkout detects EOF and discards it.
There is no background expiry worker, so an idle descriptor may remain open
until checkout, replacement/eviction, or runtime shutdown. The stale-peer
regression covers close-before-checkout; it does not remove the race where a
peer closes immediately after the checkout probe. A request that encounters
that race fails without replay.

`tests/test_provider_upstream_pool_01662.py` runs seventeen synthetic loopback checks
in the rootless Bubblewrap network namespace. Its preflight verifies the
namespace contains only loopback, has no IPv4 or IPv6 default route, and uses a
private tmpfs. The cases cover a canonical loopback alias redirect and rejected
cross-port redirect, path-varying reuse, buffered `/v1/responses` reuse and
final error draining, chunked translated SSE framing reuse after `[DONE]`,
nonblocking rejection of delayed chunk framing, rejection of a single over-64-KiB
SSE chunk with `[DONE]` in its first 8 KiB, suppression of post-`[DONE]` events,
Bearer and `x-api-key` 401 retry behavior, native
`DeepSeekExchange` redirect handling with `x-api-key` followed by reuse in the
passthrough Messages route, same-credential Bearer/`x-api-key` reuse isolation,
concurrent requests with an in-flight warm socket, close-delimited and
truncated chunked responses without replay, downstream SSE cancellation,
stale idle peer discard, and shutdown of the final idle pooled socket. The
`x-api-key` 401 same-scope case uses duplicate identical key entries to exercise
reuse after the 401; the separate rotated-key case verifies scope separation.
The delayed-trailer case uses a synthetic RawPeer control request sent only after
the client consumes the downstream terminal chunk. Modex must close the upstream
socket before the peer releases the missing terminator; a bounded five-second
wait is only a deadlock guard. Security-relevant controls verify cross-port
redirect rejection, credential and authentication-scheme pool isolation, no
replay after truncation or cancellation, and that untrusted event data after
`[DONE]` is not forwarded downstream.

`rtk make build` exited successfully with Mojo 1.2.0. The isolated strict test
runner passed all seventeen tests in 6.344 seconds against Modex and the checksum-
verified Prodex 0.166.2 Linux oracle where comparison was applicable. Synthetic
credentials and local listeners only were used. This validates selected Linux
x86-64 pool behavior; it does not establish full provider parity, six-target
parity, or upstream resource/security equivalence. The separate active provider
shape, passthrough, and framing suites passed 32 tests after the SSE reuse
change; two historical local-relay checks also confirmed prompt completion and
upstream cancellation for unfinished streams.
