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

## Remaining route gaps

A separate active-process inventory observed that Prodex accepts `/messages`
and `/v1/messages`, forwarding both to the synthetic `/anthropic/v1/messages`
upstream, and returns its built-in catalog for `/models` and `/v1/models`.
Modex still returns 404 for those four paths. Both processes returned 404 for
the tested `/embeddings` and `/v1/embeddings` requests. The tested unavailable
model path also has different 404 bodies: Prodex reports `model_not_found`,
while Modex reports `unsupported_provider_route`. These paths require separate
handlers and are not part of this alias fix.

This evidence does not establish behavior for other release targets or full
provider parity; the six-release denominator is unchanged.
