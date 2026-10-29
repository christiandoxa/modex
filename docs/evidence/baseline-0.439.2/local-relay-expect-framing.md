# Local relay Expect and framing precedence

The TinyHTTP source for Prodex 0.165.1 at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and pinned 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` handles `Expect` after selecting
the first `Transfer-Encoding` and `Content-Length` headers in
`vendor/tiny_http/src/request.rs::new_request`. An unsupported expectation
returns `RequestCreationError::ExpectationFailed` before body-reader setup.
`vendor/tiny_http/src/client.rs` converts it to `ReadError::ExpectationFailed`
and writes an empty `417 Expectation Failed` response before closing the
connection. Both source snapshots were inspected outside the Modex repository
and left unchanged.

Modex previously raised duplicate or invalid framing errors while parsing the
head, before it checked a deferred unsupported `Expect`. The production relay
uses `defer_expectation_errors=True`; its parser now retains the first framing
error until after expectation validation. A rejected expectation therefore
returns 417 before body parsing, interim 100, or provider dispatch. Strict
shared-parser calls keep their existing behavior.

The real-process tests compare checksum-verified Prodex 0.165.1 and 0.439.2
with the production Modex Super relay and synthetic loopback providers:

- `Expect: 100-wait` with conflicting `Content-Length`/`Transfer-Encoding`,
  duplicate `Transfer-Encoding`, malformed `Content-Length`, or unsupported
  transfer encoding returns 417 with no interim 100, an empty body, a closed
  socket, and no upstream request on all three processes.
- The fragmented, half-closed conflicting-framing request has the same 417
  result. A valid request pipelined behind a rejected expectation receives no
  response; the 417 closes the socket first, and no request reaches upstream.
- A single valid `Expect: 100-continue` control remains 100 then 200 with one
  upstream request on all three processes.
- A valid `100-continue` request with ambiguous framing remains fail-closed in
  Modex: the releases send 100 and dispatch the valid chunked body, while Modex
  sends no interim response and returns 502 without dispatch. This remains a
  deliberate security behavior gap.
- With a valid hexadecimal chunk body and no expectation, both releases also
  dispatch `Content-Length` plus `Transfer-Encoding` and duplicate
  `Transfer-Encoding` requests. Modex returns 502 before dispatch. This is not
  counted as a parity pass.

The last control corrects an earlier malformed fixture: it encoded the chunk
size as decimal rather than hexadecimal. That fixture did not establish the
releases' behavior for valid ambiguous framing.

The tests run in the active CI paths. `test_local_rewrite_04392_oracle.py` and
`test_loopback_header_whitespace.py` resolve Prodex 0.439.2 from
`PRODEX_ORACLE_04392` or its checksum-pinned cache location. They never fall
back to generic `PRODEX_ORACLE`. The focused rerun deliberately set generic
`PRODEX_ORACLE` to the 0.165.1 binary while keeping the explicit 0.439.2 path;
both checksum and behavior checks passed.

Validation on Linux x86-64:

```text
rtk make build — passed
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/loopback_server_driver.mojo -o build/tests/loopback_server_driver — passed
3 focused release/framing tests — passed in 30.783s
test_loopback_header_whitespace — 6 passed in 36.007s
test_loopback_server — 29 passed in 2.282s
scripts/ci/check-product-dependencies.py — 71 Mojo files audited
git diff --check — passed
```

Reproduce the release/framing matrix with a deliberate stale generic-oracle
control:

```sh
PRODEX_ORACLE_04392="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu" \
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests rtk python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_duplicate_expect_and_framing_rejections_remain_fail_closed \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_duplicate_expect_and_framing_rejections_remain_fail_closed \
  test_loopback_header_whitespace.LoopbackHeaderWhitespaceTests.test_ambiguous_framing_release_dispatch_remains_modex_fail_closed
```

These controls qualify selected Linux x86-64 request behavior only. The
ambiguous-framing security difference remains visible; unsupported targets,
broader security behavior, and all six baseline release targets remain open.
