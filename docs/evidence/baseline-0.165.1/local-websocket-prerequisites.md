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

The release starts this runtime proxy through its private
`prodex __runtime-broker` process contract. `crates/prodex-app/src/app_commands/broker.rs`
reads the versioned bootstrap and starts the profile-backed proxy;
`crates/prodex-runtime-broker/src/process.rs` defines the bounded bootstrap
and secret handling. The broader runtime-launch path in
`crates/prodex-app/src/app_commands/runtime_launch.rs` selects the profile and
chooses a direct proxy or broker. Auto-rotate requests use
`crates/prodex-app/src/runtime_broker/spawn.rs` to start or reuse the broker;
`crates/prodex-app/src/app_commands/child_process.rs` injects its endpoint into
the managed child. Super uses this broker path when profile rotation is enabled;
Gateway shares runtime-launch setup but starts a direct proxy.

`tests/test_runtime_proxy_websocket_01651_oracle.py` exercises the checksum-
pinned Linux binary as a real process with an isolated temporary home, a
synthetic OpenAI profile/token, an ephemeral loopback listener, and a local
synthetic upstream that accepts no connection. On
`GET /backend-api/prodex/responses`, a valid RFC 6455 handshake receives
`101 Switching Protocols` with the expected `Sec-WebSocket-Accept`; an absent
key gets 400, and an unsupported route gets 404 before key validation. The
valid handshake does not connect to the upstream: provider profile auth and
upstream transport begin only when a WebSocket message is handled. These are
reference characterization checks only; they do not exercise or qualify
Modex. Run them with:

```sh
python3 -m unittest tests/test_runtime_proxy_websocket_01651_oracle.py -v
```

The harness verifies the official Linux binary SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` before
starting it. It uses synthetic credentials and makes no external requests.

## Modex constraints and next step

Modex's only production Super network path is the DeepSeek local rewrite.
`src/modex/super_launch.mojo` configures that provider with
`supports_websockets=false`, and `src/modex/runtime_local_rewrite.mojo` returns
the same 426 as the release. That path must remain unchanged. Modex does not
have the release's profile-backed runtime broker bootstrap integrated in its
Super launch path. A raw relay attached to the local rewrite listener, or an
uncalled private worker, would not implement the separate runtime-proxy
contract.

The pinned Mojo 1.2.0 compiler rejects `probes/gaps/network.mojo` because
`std.net` exports none of `TcpListener`, `TcpStream`, or `TlsStream`. The
existing raw socket wrappers are POSIX-specific; there is no standard-library
DNS resolver or WSS client available under the current no-new-bindings rule.
The baseline's message path depends on selected-profile credentials, admission,
bounded session parking, interruption/recovery, DNS, optional HTTP proxy
CONNECT, and TLS. A loopback-only `ws://` tunnel would not exercise those
production semantics and is not counted as parity.

The next viable implementation path is the real runtime-launch-owned broker
bootstrap, profile/auth selection, and lifecycle, followed by the locally
accepted WebSocket handshake and bounded session path. WSS/DNS/proxy support
and all security, resource, and interruption behavior remain visible gaps
until their required implementation path exists. The full behavior remains
unimplemented and unverified on all six release targets.
