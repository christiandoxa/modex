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

### Bootstrap and profile-auth trace

At the 0.165.1 source pin, `RuntimeProxyStartupFactory::start` in
`app_commands/runtime_launch.rs` resolves the selected profile before deciding
whether to start a fixed direct proxy or call
`ensure_runtime_rotation_proxy_endpoint`. That endpoint checks/reuses a
compatible broker registry, or generates separate broker-instance and admin
tokens and calls `spawn_runtime_broker_process`. The child command is the
current executable with the private `__runtime-broker` argument. Its stdin
bootstrap is version 1, has a 64 KiB maximum, rejects unknown fields, and
carries the selected profile name, upstream base URL, proxy flags, broker key,
instance ID, admin token, and optional listen address. The secret wrapper
redacts debug output, limits secret size to 4 KiB, and zeroizes the serialized
buffer. The broker reads that bootstrap, loads the real application state,
starts the runtime-rotation proxy against `current_profile`, publishes
instance-scoped registry/capability metadata, then waits for active requests
and profile leases before idle shutdown.

WebSocket profile credentials are selected later. The incoming handshake path
supports the Responses and realtime routes and may return its local 101
response without opening an upstream connection. On a message, the session
calls `runtime_profile_usage_auth`; this resolves the selected profile's
`codex_home`, loads its `auth.json` through the secret-store file backend, and
caches/revalidates access token plus account ID. The upstream WebSocket
handshake adds `Authorization: Bearer <access_token>` and
`chatgpt-account-id` when available, forwards allowed request metadata and
profile-scoped cookies, then resolves/connects to the upstream URL. Thus the
local 101 characterization is not evidence of selected-profile auth or
upstream WebSocket operation.

The bootstrap/process and WebSocket paths are materially unchanged between
0.165.1 source commit `10ae15b5d1806302b60f051e4e6fec788044f4c2` and the
frozen 0.439.2 source commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; the compared broker and process
files are byte-identical. The WebSocket dispatch and session implementation
also remain in both releases.

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

The reference process also accepts 16 simultaneous idle Responses WebSockets.
With an incomplete text-frame header held on the first connection, masked
ping frames on two other connections receive their matching pongs, and no
connection reaches the synthetic upstream. This is a bounded control for idle
parking and partial-frame isolation, not a measurement of the eviction limit,
message admission, interruption, or Modex behavior.
Another reference-only control sends a masked binary message: the broker
returns an `invalid_request_error` with status 400 in a text frame, keeps the
connection usable for ping/pong, and makes no upstream connection.

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

The later Mojo 1.2.0 standard-library source audit and compile/platform probes
are recorded in `docs/evidence/mojo-1.2.0-network-tls-dns.md`.

## Connected-slice feasibility check (2026-10-29)

The 0.165.1 process characterization was rerun: all three tests passed for
local 101, missing-key 400, and unsupported-path 404. This uses a pinned
Prodex process, not Modex. `mojo build probes/gaps/network.mojo` was also run
with Mojo 1.2.0 (`2016d0cd`) and fails because the official `std.net` package
does not export `TcpListener`, `TcpStream`, or `TlsStream`.

No connected implementation slice is added. Modex's `src/main.mojo` exposes
`__modex-local-rewrite` but no runtime-broker command. The production Super
path in `src/modex/super_launch.mojo` intentionally creates an isolated
DeepSeek API-key home, sets `supports_websockets=false`, and launches only the
local-rewrite relay; `_clean_home` rejects existing managed profile state.
Adding just the private bootstrap reader or a listener that sends 101 would
not supply the selected-profile `auth.json` lookup or message-to-upstream
transport, leaving a client upgraded onto a dead connection. Reusing raw
POSIX sockets would also introduce a Linux/POSIX-only route without the
standard-library TLS, DNS, or HTTP CONNECT support required by the production
WSS path. A small test of either unconnected helper would not prove production
behavior and is not counted as parity.

The first useful connected milestone must include profile selection in the
real Super launch, versioned bounded bootstrap over the private child pipe,
broker ownership/readiness/shutdown, selected-profile auth loading, and a
separate runtime-proxy listener whose session can complete at least one
upstream WebSocket message. It then needs checksum-pinned process tests with a
synthetic profile and local-only WSS peer; currently the official Mojo
standard-library transport surface prevents that end-to-end milestone under
the no-new-bindings/no-third-party rules. WSS, frame handling, admission,
continuation ownership, recovery, and non-host platform behavior remain
unimplemented.
