# Runtime WebSocket interrupt oracle observations (2026-10-30)

These are checksum-pinned Prodex process observations using synthetic profile
data and loopback-only upstream peers. They do not exercise Modex and are not
Modex parity evidence.

| Release | Pinned source | Linux x86-64 oracle SHA-256 |
| --- | --- | --- |
| Prodex 0.165.1 | `10ae15b5d1806302b60f051e4e6fec788044f4c2` | `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` |
| Prodex 0.439.2 | `72b77478a5198fc5da6b4d2253137f9cdbf43be9` | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` |

The fixture creates a private profile directory, private auth and state files,
a fresh quota snapshot, isolated `HOME`/`PRODEX_HOME`/runtime logs, synthetic
tokens, and ephemeral loopback ports. No account login or provider request is
used. Runtime log recording is directed to the isolated temporary directory.

## Prodex 0.165.1

Two local Responses WebSockets each create an active response on their own
synthetic upstream connection. A `response.interrupt` sent on the first local
socket but naming the second response closes the submitting local and upstream
sockets with EOF and no WebSocket frame. The response owner's upstream socket
receives no bytes, and the listener receives no third upstream connection. The
broker remains alive. A same-session interrupt is forwarded as the exact text
frame on its owning upstream socket; the synthetic acknowledgement and
completion frames are each forwarded once to the local client.

The pinned implementation is in
`crates/prodex-app/src/runtime_proxy/websocket/response_tracking/control.rs`:
it checks that the interrupted ID belongs to the active connection before
sending on that connection's existing upstream socket.

The complete oracle module passed six tests. The focused interrupt test passed
three additional fresh-process runs:

```sh
PRODEX_ORACLE_01651=/home/doxa/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu \
  python3 -m unittest discover -s tests -p 'test_runtime_proxy_websocket_01651_oracle.py' -k interrupt_is_forwarded -v
```

## Prodex 0.439.2

The same synthetic cross-session setup leaves the local submitter and both
upstream sockets without readable data for a 500 ms wait on each socket; the
broker remains alive and no third upstream connection appears. After the fake
upstream completes the submitter's active response, the local client receives
that completion. The queued foreign interrupt is then forwarded unchanged on
the submitter's existing upstream connection. The other response owner's
upstream socket remains unreadable; no new connection is opened. One diagnostic
capture also observed an empty Ping frame (opcode 9) before the completion.

The 0.439.2 runtime-proxy source has no Responses `response.interrupt` handler
or owned-socket interrupt check. Its
`crates/prodex-app/src/runtime_proxy/websocket/read_loop.rs` reads the next
local text after the current text-message flow returns, matching the delayed
forwarding observed here. The separate test passed three fresh-process runs:

```sh
PRODEX_ORACLE_04392=/home/doxa/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
  python3 -m unittest discover -s tests -p 'test_runtime_proxy_websocket_04392_oracle.py' -v
```

These release-specific behaviors are not interchangeable. The 0.439.2 result
does not change the 0.165.1 expectation or establish Modex behavior. The
profile-backed WebSocket production path remains unimplemented; the current
Mojo standard-library constraints lack the DNS/TLS transport needed for the
production WSS path. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.
