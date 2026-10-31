# Local relay root route aliases (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The pinned route planner in
`mojo/prodex_core/runtime_proxy_request.mojo::prodex_runtime_provider_route_plan_v1`
accepts exact `/responses`, `/responses/compact`, and `/chat/completions`
paths alongside their `/v1` forms. It excludes query strings for route
selection. The active process accepts all three aliases; Modex previously
returned 404 for them.

The production local rewrite now adds `/v1` only to those exact root paths,
after request-target validation and local client-token authentication. Query
bytes remain intact. The existing `/v1` routes and all other paths retain their
prior handling. Responses aliases continue through the same continuation
ownership guard, and the compact alias uses the existing local compact
fallback.

Synthetic process comparisons cover POST and GET on `/responses` and
`/chat/completions`, query forwarding, `/responses/compact` query and GET
controls, trailing-slash and tenant-prefix rejection, malformed duplicate
slashes, invalid client tokens, and an owned continuation follow-up. Both
products reject the malformed path with 400. Modex retains its stricter local
client authentication: an invalid token gets 401 with no provider request;
Prodex accepts it. Both products block the tested owned follow-up with 503
before a second provider dispatch. This preserves the existing security
boundaries while matching only the accepted route aliases.

Validation used the checksum-verified Linux x86-64 oracle, synthetic local
provider fixtures and credentials, and bubblewrap with a private loopback-only
network namespace, private temporary storage, isolated HOME, and read-only
workspace, binary, and oracle mounts. No live provider traffic or personal
data was used.

- `make BUILD_DIR=/tmp/modex-relay-cycle-build build` passed with Mojo 1.2.0.
- `test_provider_passthrough_01660.py` and `test_local_compact_gap_01660.py`
  passed: 14 tests in 28.321 seconds.
- A separate isolated HEAD probe matched upstream methods, paths, and bodies
  for root and `/v1` Responses/Chat routes. Its synthetic upstream returned an
  empty HEAD response, so both products returned 502 for Responses and 200 for
  Chat; this is method-routing evidence, not full HEAD response parity.
- `make ci-dependencies` passed; all 74 production Mojo files use only
  standard-library or internal imports.
- `git diff --check` passed.

This evidence covers the listed DeepSeek local-relay routes on Linux x86-64.

## DeepSeek model catalog routes

The pinned route planner also accepts `/models`, `/v1/models`, and their
single-model forms. The provider bridge handles GET locally with a three-row
catalog (`deepseek-v4-pro`, `deepseek-flash`, `deepseek-v4-flash`); aliases
such as `auto`, `pro`, and `flash` resolve to their canonical model row, and
unknown IDs return `model_not_found`. Query strings do not affect route
selection. Other methods, including POST and HEAD, go to the configured
provider path; root and `/v1` paths resolve against the same configured base
path.

Modex now returns that catalog from the native local relay and supports the
same single-model lookups. POST bodies, query bytes, upstream method and
error responses use the existing bounded passthrough transport. The separate
Super launch catalog is not reused because it is launch-model-dependent and
has a different Codex schema. Modex keeps its local client-token guard: an
invalid token gets 401 without provider dispatch, while the pinned Prodex
oracle serves the catalog. This stricter authentication difference remains.

`test_provider_passthrough_01660.py` compares both paths and the complete
catalog with production processes over synthetic loopback. Its POST and HEAD
fixtures verify forwarded methods, provider authorization, query/body
preservation, 429/503 propagation, and HEAD's empty response body. The test
also compares valid alias/canonical model rows, missing-ID error JSON, and the
invalid-token control. All test state, HOME, and credentials are synthetic;
no provider traffic or personal data is used.

- `make BUILD_DIR=/tmp/modex-models-route-build build` passed with Mojo 1.2.0.
- `test_provider_passthrough_01660.py` passed: 12 tests in 25.469 seconds
  inside the `run_websocket_fallback_01660.py` bubblewrap helper, with private
  `/tmp`, read-only worktree/build/oracle inputs, loopback only, and no default
  route.
- The model-route test in `test_local_rewrite.py` also passed in that private
  loopback sandbox. Its wider run had one failure in the existing empty-port
  strict-beta URL case. A separate clean `fa2d525` worktree and build reproduced
  the same failure for `http://127.0.0.1:/beta`, confirming it predates this
  slice.
- `make ci-dependencies` passed: all 74 production Mojo files use only
  standard-library or internal imports.

## CONNECT request-target and tunnel boundary

The pinned `local_rewrite_deepseek_send.rs` passes the inbound method and
configured upstream URL to `local_rewrite_transport.rs`, which calls
`reqwest`'s request builder. For CONNECT, Prodex therefore sends the upstream
authority as the request target. Modex's shared `_stream_request` previously
used the configured origin-form path for every method.

The shared Modex request builder now uses the already validated upstream
authority with its explicit port as the target for the exact `CONNECT`
method, while the `Host` header keeps its existing default-port formatting.
Native Mojo checks cover IPv4 and IPv6 port 80. Synthetic 418 process
comparisons confirm the same authority-form target at the loopback
upstream for `/models`, `/v1/chat/completions`, `/v1/messages`, and
`/v1/responses`; both products return the fixture's status and body. An invalid
local token on the Modex model route still returns 401 before provider
dispatch.

CONNECT tunnel responses remain unsupported. A synthetic 200 response on the
model route becomes a bodyless 200 in Prodex, while Modex returns 502 before
reading a CONNECT tunnel body. A raw synthetic 200 with no Content-Length or
Transfer-Encoding and immediate tunnel bytes confirms that Modex closes the
upstream socket, returns 502, and forwards none of those bytes. A synthetic
Codex client captures the complete downstream response through EOF; the 502
body matches its Content-Length, and the tunnel sentinel is absent from the
entire wire. On the
translated Responses route both products return 502 for the framed 200 control,
with Modex failing closed at the transport boundary. A synthetic 101 upgrade
also returns 502 in Modex. The relay does not attach an upgraded socket or
enable bidirectional tunneling. Authority-form matching is limited to the
numeric loopback URL that passed the existing validation and connection
checks.

`test_provider_passthrough_01660.py` covers these route and response cases
with real processes, a synthetic provider, isolated homes, read-only binary
and workspace mounts, and bubblewrap network isolation with loopback only.
This qualifies the selected Linux x86-64 request-target and fail-closed cases,
not successful CONNECT tunneling or other release targets.

- `make build` passed with Mojo 1.2.0.
- `make unit UNIT_BUILD_PROGRAMS=test_provider_deepseek_transport UNIT_RUNS=test_provider_deepseek_transport`
  passed the native IPv4 and IPv6 default-port request checks.
- `test_provider_passthrough_01660.py` passed all 15 tests in 31.008 seconds
  inside bubblewrap with a private `/tmp`, isolated HOME, read-only workspace,
  binary and oracle, and loopback-only networking.
- `make ci-dependencies` passed: all 74 Mojo files use only standard-library
  or internal imports; `git diff --check` passed.

## Remaining route gaps

The Messages route is covered separately in `local-relay-messages-routes.md`.
Both processes returned 404 for the tested `/embeddings` and `/v1/embeddings`
requests.

This evidence does not establish behavior for other release targets or full
provider parity; the six-release denominator is unchanged.
