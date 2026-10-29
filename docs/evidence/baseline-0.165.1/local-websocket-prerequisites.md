# Local WebSocket transport prerequisites against 0.165.1

The source trace is pinned to Prodex `10ae15b5d1806302b60f051e4e6fec788044f4c2`.
It distinguishes the local rewrite adapter from the separate runtime-proxy
WebSocket path.

## Local rewrite adapter

`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_pipeline_websocket.rs`
returns HTTP 426 with `provider adapter requires HTTPS Responses transport
fallback` when the local rewrite sees a WebSocket upgrade. Modex returns the
same fallback from `serve_local_rewrite`. Keep this route's 426 behavior; it is
not evidence that the separate WebSocket transport is implemented.

## Runtime-proxy path

`crates/prodex-app/src/runtime_proxy/dispatch.rs` detects WebSocket upgrades and
routes them separately from HTTP requests. Its dispatch path can park a
handshake without holding an inference permit. In
`crates/prodex-app/src/runtime_proxy/dispatch/websocket.rs`, Prodex checks the
supported path and `Sec-WebSocket-Key`, builds the 101 response, hands the
connection to `Request::upgrade`, and wraps the raw socket in a server-side
WebSocket.

When the session pool is enabled, `runtime_proxy/websocket/parking.rs` owns the
socket, captured handshake, connection control, and session state together.
The bounded idle pool can evict parked sockets. Fixed handshake workers and
nonblocking socket polling separate idle connection ownership from message
work. A complete text message acquires request admission before provider I/O;
`runtime_proxy/websocket/read_loop.rs` handles text, control frames, close, and
the baseline's binary-message rejection.

`runtime_proxy/websocket.rs` constructs the upstream handshake with profile
credentials and forwarded request metadata. The `websocket/connect.rs` path
resolves upstream addresses, applies connect and I/O timeouts, supports
Happy-Eyeballs address attempts, and can establish an HTTP proxy CONNECT
tunnel before the upstream WebSocket handshake. The session path also carries
interrupt, continuation, response-tracking, and unauthorized-recovery state.

## Modex constraints and next step

Modex has no production WebSocket upgrade, socket handoff, or frame relay.
Its local rewrite listener currently handles bounded HTTP requests over raw
numeric-loopback sockets and uses the 426 fallback for WebSocket requests. It
does not provide a WSS client, DNS resolver, HTTP proxy CONNECT, idle WebSocket
pool, message-level admission, or equivalent interrupt and recovery handling.

The next implementation slice is the raw HTTP upgrade and socket handoff in
the existing listener, followed by a bounded frame relay and explicit idle
connection ownership. The 0.165.1 path has independent handshake capacity,
message admission, and connection-owned interruption behavior; a basic frame
copy alone would not establish parity. WSS, DNS, and HTTP proxy CONNECT remain
significant constraints under the project's Mojo-stdlib-only and no-new-binding
rules. Their availability must be proven against the pinned Mojo toolchain
before claiming support. The full behavior remains unimplemented and
unverified on all six release targets.
