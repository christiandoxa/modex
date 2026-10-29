# Identical repeated Expect handling

The source trace uses Prodex 0.165.1 at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and the frozen Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. In both
`vendor/tiny_http/src/request.rs`, `new_request` selects the first `Expect`
field with `headers.iter().find`. The process tests verify the pinned Linux
binary hashes: 0.165.1 is
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`, and
0.439.2 is
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

Before this change, both releases answered repeated identical
`Expect: 100-continue` with one interim 100, then returned 200 after one
synthetic upstream request. Modex returned 417 before reading the body or
dispatching. The production TinyHTTP-compatible parser now accepts only
repeated identical `100-continue` values. It still rejects mixed values in
either order. The shared parser remains strict by default.

| Raw request | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
| --- | --- | --- | --- |
| Two identical `100-continue` fields | One 100, then 200; one upstream request | Same | Same |
| `100-continue` then `100-wait` | One 100, then 200; one upstream request | Same | 417; no interim or upstream request |
| `100-wait` then `100-continue` | 417; no upstream request | Same | Same |
| Invalid target, duplicate `100-continue`, nonzero length | 400; no interim or dispatch; client socket stays open | Same | 400; no interim or dispatch; client socket closes |
| Repeated `100-continue` with a valid chunk body plus `Content-Length` and `Transfer-Encoding` | 100, then 200; one upstream request | Same | 502; no interim or upstream request |

Mixed expectations stay fail-closed in Modex even when the first value is the
valid `100-continue` token. Both releases ignore later expectation fields after
the first, so that remains a documented compatibility difference. Modex also
continues to reject ambiguous framing before body parsing; the releases dispatch
the valid chunked body in that control. The client close after invalid-target
rejection preserves the unread-body boundary. None of these stricter behaviors
is counted as full parity.

The focused tests use only synthetic credentials, Codex, and loopback provider
traffic. On Linux x86-64, `rtk make build` and the focused parser/process run
passed all 32 tests in 27.369 seconds. The native `test_loopback_server` suite
passed all 30 tests. The production import audit passed for 71 Mojo files; no
dependency changed. Other compiler targets and the remaining relay/security
surface are unverified; all six baseline release targets remain in the
denominator.

Reproduce the process and parser controls from the Modex repository root:

```sh
rtk make build
rtk mojo build -O3 --target-cpu=x86-64-v3 -I src tests/loopback_server_driver.mojo -o build/tests/loopback_server_driver
PRODEX_ORACLE_01651="$HOME/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu" \
PRODEX_ORACLE_04392="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests rtk python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed \
  test_loopback_server
```
