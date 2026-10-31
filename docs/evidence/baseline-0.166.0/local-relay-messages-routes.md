# DeepSeek local relay Messages routes (Prodex 0.166.0)

The reference is official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; the Linux x86-64 oracle SHA-256
is `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.
The route planner in `mojo/prodex_core/runtime_proxy_request.mojo` maps exact
`/messages` and `/v1/messages` paths to the same Messages route after excluding
the query from route selection.

The checksum-verified oracle and Modex were exercised as real Super processes
with synthetic loopback provider fixtures. Both aliases route to the configured
Anthropic endpoint path (for a `/v1` base URL, `/anthropic/v1/messages`), and
the client query is dropped. POST, GET, HEAD, and PUT methods were accepted;
body-bearing requests retained their exact bodies, the empty GET and HEAD had
no upstream `Content-Length`, and the upstream status and body passed back to
the caller. Additional comparisons covered a malformed body with a synthetic
422 response and a chunked SSE response.

Modex dispatches the new alias after the shared request-target validation and
local bearer-token check. It sends to the prevalidated numeric-loopback
Anthropic address, replaces caller `x-api-key` and `anthropic-version` headers
with the configured provider key and fixed `2023-06-01` version, and removes
incoming Authorization and Cookie headers. The provider response ID remains
bound to the selected credential; a subsequent Responses continuation using
that buffered or streaming Anthropic ID returns 503 before a second provider
dispatch, matching the oracle comparison. A retryable synthetic 401 on the
first configured key was retried with the second key before any response was
sent; the request body was unchanged, and the successful response ID retained
its continuation binding. Concurrent requests using two synthetic provider
keys continued to use only those configured keys. Like the release, Modex may
retry a buffered 5xx response with another key; a provider that performed work
before failing may therefore process the request more than once.

The oracle has an observed credential-forwarding difference: it forwards
caller Cookie, `x-api-key`, and `anthropic-version` values on the Messages route.
Modex intentionally does not reproduce that behavior. The secure behavior is
covered directly by the Modex process test, which also verifies that an invalid
local bearer token gets 401 without reaching the provider.

Validation used the verified oracle, synthetic-only keys and response bodies,
temporary HOME/config/storage, a private bubblewrap network namespace with
loopback-only reachability, and read-only workspace/binary/oracle mounts.
`test_deepseek_messages_route_01660.py` passed all 8 tests. The production build
passed with Mojo 1.2.0, `make ci-dependencies` confirmed all 74 production Mojo
files use only standard-library or internal imports, and `git diff --check`
passed. These observations establish this Linux x86-64 route slice only; they
do not change the six-release or six-target parity denominator.
