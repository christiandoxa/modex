# Local relay status reason phrases

The pinned baseline is Prodex 0.165.1 at
`10ae15b5d1806302b60f051e4e6fec788044f4c2`.

## Source trace

`local_rewrite_response_dispatch.rs` passes the upstream numeric status to the
passthrough response handler. The buffered path passes it to
`build_runtime_proxy_response_from_parts` as `tiny_http::StatusCode`; the
streaming path also retains the numeric status in `RuntimeStreamingResponse`.
The frozen workspace patches TinyHTTP 0.12.0 from
`vendor/tiny_http/src/common.rs`. Its `StatusCode::default_reason_phrase`
contains 56 explicit phrases for final statuses 200–599 and returns `Unknown`
for other final statuses. `vendor/tiny_http/src/response.rs` writes that phrase
into the HTTP status line.

Modex's shared `LoopbackHTTPConnection` writer formats both buffered and
streaming response heads through `_response_head`, which calls `_reason`; the
runtime relay reaches it through `respond` and `start_stream`.
Before this change, `_reason` omitted several pinned phrases, returned
`Unprocessable Content` for 422, and used `Response` as its fallback. The
writer rejects status codes below 200, so informational 1xx responses are not
part of this final-response mapping.

`_reason` now matches all 56 explicit final-status phrases from the pinned
table, including `Partial Content` for 206 and `Unprocessable Entity` for 422;
unmapped final statuses return `Unknown`.

## Verification

The synthetic peer sends each selected upstream status through the real Super
local-rewrite route. The production oracle matrix checks exact status and reason,
body and response headers, the unchanged upstream request, and exactly one
upstream POST. Controls match Prodex 0.165.1 for 200/OK, 204/No Content,
206/Partial Content, 302/Found, 404/Not Found, 418/Unknown, 422/Unprocessable
Entity and 500/Internal Server Error. The same selected cases also match the
hash-verified historical Prodex 0.439.2 Linux binary
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`; these
historical observations do not establish current-target parity.

A native shared-writer test directly checks 206, 418 and 422. A source-table
comparison checked every final status from 200 through 599 against the pinned
TinyHTTP source; there were no phrase differences.

Focused checks passed:

- `python3 -m unittest -v tests.test_local_rewrite_01651_oracle`
- `python3 -m unittest -v tests.test_loopback_server`
- `python3 -m unittest -v tests.test_local_rewrite`
- `python3 -m unittest -v tests.test_provider_deepseek_transport`
- `PYTHONPATH=tests python3 -m unittest -v tests.test_provider_passthrough`

The existing HEAD 204/304 SSE wire expectation remains unchanged: Prodex sends
the terminal chunk and Modex does not. The request header-cap gap also remains.
No full contract or release-target qualification is claimed.
