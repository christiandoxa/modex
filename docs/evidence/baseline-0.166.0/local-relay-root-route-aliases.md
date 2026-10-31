# Local relay root route aliases (Prodex 0.166.0)

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

## Remaining route gaps

For the tested CONNECT model request, the release sends authority-form while
Modex's shared outbound transport sends origin-form. Both connect only to the
configured loopback upstream; this method-format difference remains open.

The Messages route is covered separately in `local-relay-messages-routes.md`.
Both processes returned 404 for the tested `/embeddings` and `/v1/embeddings`
requests.

This evidence does not establish behavior for other release targets or full
provider parity; the six-release denominator is unchanged.
