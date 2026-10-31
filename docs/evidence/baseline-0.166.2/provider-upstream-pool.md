# Bounded upstream connection reuse

The new `LoopbackHTTPConnectionPool` retains at most one idle upstream socket
per runtime. A reusable socket is keyed by the configured numeric loopback
endpoint, credential scope, and authentication scheme (`Authorization: Bearer`
or `x-api-key`). Fully consumed, self-delimited buffered and
passthrough responses may return their socket to the pool. Translated SSE
responses stay outside the pool because the event reader can stop before the
HTTP framing is fully consumed. Concurrent pool misses open their own socket;
the pool lock is not held during connection or response I/O, and failed
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

`tests/test_provider_upstream_pool_01662.py` runs fourteen synthetic loopback checks
in the rootless Bubblewrap network namespace. Its preflight verifies the
namespace contains only loopback, has no IPv4 or IPv6 default route, and uses a
private tmpfs. The cases cover a canonical loopback alias redirect and rejected
cross-port redirect, path-varying reuse, buffered `/v1/responses` reuse and
final error draining, Bearer and `x-api-key` 401 retry behavior, native
`DeepSeekExchange` redirect handling with `x-api-key` followed by reuse in the
passthrough Messages route, same-credential Bearer/`x-api-key` reuse isolation,
concurrent requests with an in-flight warm socket, close-delimited and
truncated chunked responses without replay, downstream SSE cancellation,
stale idle peer discard, and shutdown of the final idle pooled socket. The
`x-api-key` 401 same-scope case uses duplicate identical key entries to exercise
reuse after the 401; the separate rotated-key case verifies scope separation.

`rtk make build` exited successfully with Mojo 1.2.0. The isolated strict test
runner passed all fourteen tests in 4.979 seconds against Modex and the checksum-
verified Prodex 0.166.2 Linux oracle where comparison was applicable. Synthetic
credentials and local listeners only were used. This validates selected Linux
x86-64 pool behavior; it does not establish full provider parity, six-target
parity, or upstream resource/security equivalence.
