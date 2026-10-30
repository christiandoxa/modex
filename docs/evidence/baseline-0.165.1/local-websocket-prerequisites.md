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

No end-to-end runtime WebSocket implementation is added. Modex's `src/main.mojo` exposes
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

## Local rewrite WebSocket fallback (2026-10-30)

The production local rewrite now rejects a valid `Connection: Upgrade` plus
`Upgrade: websocket` request after parsing its headers, before reading a
declared HTTP body. A stalled peer cannot retain a request worker with an
irrelevant body. Invalid request targets and unsupported `Expect` values keep
their earlier 400 and 417 errors. A checksum-pinned process test sends only
the header block with `Content-Length: 100`; 0.165.1, 0.439.2, and Modex return
complete responses without any body bytes or upstream request. It compares
status, normalized response headers except generated `Date`, and the complete
body.

The process comparison also covers conflicting `Content-Length: 0` and
`Content-Length: 100`. For a valid target with `Connection: Upgrade` and
`Upgrade: websocket`, Modex now returns the same 426 fallback as both releases
before reading a body. The response closes the connection, so a pipelined
second request cannot be reused
and is not forwarded to the provider. A synthetic Authorization header does
not appear in response or diagnostics. Invalid targets still take precedence
with 400, and unsupported `Expect` still takes precedence with 417. An `h2c`
upgrade retains the 502 error and does not reach the provider.

For `Upgrade: websocket` without `Connection: Upgrade`, Modex returns the same
426 classification as both releases. It now follows TinyHTTP's body-capture
order: when the first `Content-Length` is 1–1,024, `Expect` is absent, and
transfer encoding is absent, the body is read before the fallback. A complete
body then gets 426; a truncated body that ends at EOF gets no response. Empty
bodies, `Connection: Upgrade`, chunked requests, `Expect` requests, and fixed
bodies over 1,024 bytes still reach the fallback before body capture. These
cases are covered against the checksum-pinned 0.165.1 and 0.439.2 processes
and Modex by
`test_websocket_body_capture_order_matches_both_releases` in
`tests/test_local_rewrite_04392_oracle.py`.

One deliberate fail-closed difference remains for ambiguous framing: with no
`Connection: Upgrade`, a positive first length followed by a smaller duplicate
length and a truncated body makes both releases close without a response;
Modex returns 426 before reading. It sends no upstream request. For a
zero-first conflicting length, the three products return 426. Invalid-target
400, unsupported-`Expect` 417, and non-WebSocket `h2c` 502 precedence remain
covered. With a fragmented non-ambiguous upgrade followed by a valid pipelined
request, both releases return 426 then dispatch the second request for 200;
Modex returns 426 and closes without an upstream request. The local fallback
also differs on this connection-reuse behavior.

A low-load production control holds a one-byte no-Connection WebSocket body
partial while a preconnected idle client receives a valid 200; completing the
body then returns 426. Neither client is evicted in this control. It does not
qualify saturated-pool behavior, so the known admission and saturation gaps
remain open. This evidence qualifies Linux x86-64 only; all six release
targets remain in the parity denominator. It does not implement the separate
profile-backed runtime-proxy WebSocket path or WSS.

This only secures the local rewrite fallback. It does not implement the
separate profile-backed runtime-proxy WebSocket path or WSS; those remain
unimplemented and are not counted as parity.

## Runtime-broker prerequisite recheck (2026-10-30)

This recheck used official Mojo 1.2.0 (`2016d0cd`) and Prodex 0.165.1 source
commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`. It changes no production
code and establishes no Modex WebSocket parity.

The baseline startup chain is production-owned: `RuntimeProxyStartupFactory`
selects a profile and calls `ensure_runtime_rotation_proxy_endpoint`
(`crates/prodex-app/src/app_commands/runtime_launch.rs:366-443`). The endpoint
spawns the current executable as `__runtime-broker`, writes its private pipe
bootstrap, waits for a compatible broker and readiness, and activates the
selected profile (`crates/prodex-app/src/runtime_broker/spawn.rs:288-317,
335-478`). The version 1 bootstrap is capped at 64 KiB and carries profile,
upstream, instance, and admin-token fields
(`crates/prodex-runtime-broker/src/process.rs:7-11,343-410`). The broker
loads application state, starts the profile-backed proxy, publishes its
registry/capability, waits for active requests and leases, then removes its
instance-scoped artifacts (`crates/prodex-app/src/app_commands/broker.rs:22-79`).

WebSocket credentials are selected from that profile when the first message
needs an upstream connection: `connect_runtime_proxy_upstream_websocket`
calls `runtime_profile_usage_auth` for the selected profile
(`crates/prodex-app/src/runtime_proxy/websocket.rs:79-107`,
`crates/prodex-app/src/runtime_persistence/auth.rs:77-114,155-166`). The
separate connector resolves host names, applies timeouts and may establish an
HTTP proxy tunnel before WebSocket/TLS
(`crates/prodex-app/src/runtime_proxy/websocket/connect.rs:3-23,25-69`;
`crates/prodex-app/src/runtime_proxy/websocket.rs:493-505` calls
`client_tls_with_config`).
Profile/runtime state uses cross-process exclusive file locks through `fs2`
(`crates/prodex-app/src/runtime_store/io.rs:35-67,81-92`; workspace
`Cargo.toml:83`). The production WebSocket path also depends on `tungstenite`
and `rustls` (`Cargo.toml:137-139,155`; `crates/prodex-app/Cargo.toml:108`).
The pinned `std/sys/_libc.mojo:305-323` has an internal variadic `fcntl`
wrapper and descriptor-flag constants, but no file-lock record or lock API.

The pinned compiler probes reproduced these exact limits:

| Probe | Result |
| --- | --- |
| `mojo run probes/gaps/network_platform.mojo` | `16 53`; creates and closes one internal UDP socket, sends no packet |
| `mojo build probes/gaps/network.mojo` | Fails: `std.net` has no `TcpListener`, `TcpStream`, or `TlsStream` |
| `mojo build probes/gaps/dns.mojo` | Fails: `std.net` has no `getaddrinfo` or `getnameinfo` |
| `mojo build probes/gaps/crypto.mojo` | Fails: `std.hash` has no `SHA256`; `std.random` has no `secure_random_bytes` |
| `mojo build probes/gaps/filesystem.mojo` | Fails: `std.os` has no `chmod`, `flock`, `fsync`, or `rename` |

`mojo build --target-triple TARGET --emit=llvm -o /tmp/network-TARGET.ll
probes/gaps/network_platform.mojo` compiles for Linux x86-64/ARM64 and macOS
x86-64/ARM64. Both Windows targets fail because the official internal POSIX
socket layer has no `SockaddrIn` witness. LLVM emission proves only compilation,
not target linking or runtime behavior. The successful local probe proves only
raw socket creation; it does not supply a public TCP stream, DNS, TLS,
certificate validation, WebSocket client, or HTTP proxy implementation.

Those missing standard-library facilities leave substantial implementation
work for a profile-backed WSS message path under the project rules. Adding Rust/WebSocket/TLS dependencies, calling
OpenSSL or another executable, or declaring new native bindings is forbidden.
Manually modeling the platform `flock` ABI would also exceed the audited Mojo
API and would leave target-specific locking unverified. No viable complete
production path was established by this recheck. A local 101 handshake or a
bootstrap parser alone would not establish broker lifecycle, selected-profile
auth, or an upstream WSS message path, so no production slice was added.

The bootstrap/process files at 0.165.1 and 0.439.2 are byte-identical. The
0.165.1 WebSocket dispatch/session files still exist at 0.439.2, but the
dispatch and session source differs and must retain separate release-targeted
evidence. The 0.165.1 reference-only WebSocket suite was rerun with six tests
passing using isolated synthetic profiles and loopback peers. This remains
baseline characterization only.
