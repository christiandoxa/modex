# Local relay header whitespace against pinned TinyHTTP releases

The production Super relay now trims ASCII space and bytes `0x09`–`0x0D` at
header-line and header-value boundaries only in TinyHTTP compatibility mode.
The shared parser stays strict by default. The outbound request builder still
rejects control bytes before network I/O.

The source trace uses Prodex 0.165.1 at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Both `vendor/tiny_http/src/client.rs`
implementations convert request lines to `AsciiString` before calling
`trim()` on each header line. Both `vendor/tiny_http/src/common.rs` versions
split each line once at `:` and call `trim()` on the value before converting it
to `AsciiString`. Thus non-ASCII bytes are rejected before trimming. The
real-process tests also verify the pinned Linux binaries against their recorded
SHA-256 values.

`tests/test_loopback_header_whitespace.py` sends raw requests through each
release and Modex to a synthetic loopback upstream:

| Case | Prodex 0.165.1 | Prodex 0.439.2 | Modex | Upstream |
| --- | --- | --- | --- | --- |
| ASCII whitespace around header line/value and `Content-Length` | 200 | 200 | 200 | One request; trimmed value is `value` |
| Valid CRLF starts another header | 200 | 200 | 200 | One request; `x-injected: yes` preserved |
| Embedded VT, FF, bare CR or bare LF in a value | 502 `upstream request failed` | Same | Same | No request |
| Equal duplicate `Content-Length`, including trimmed boundary whitespace | 200 | 200 | 200 | One request; duplicates collapse and outbound length is normalized |
| Equal duplicate zero lengths on an unsupported route | 404 | 404 | 404 | No request |
| Different numeric text (`0N` then `N`) or values (`N` then `N+1`) | 200 | 200 | 502 `gateway request capture failed` | Releases dispatch using the first length; Modex does not |
| Duplicate equal `Content-Length` plus `Transfer-Encoding`, or duplicate `Transfer-Encoding`, with a valid chunk body | 200 | 200 | 502 `gateway request capture failed` | Releases dispatch; Modex does not |
| Raw UTF-8 bytes at header-name or value boundaries | No response; `RemoteDisconnected` | Same | Same after fix; pre-fix Modex returned 400 | No request |

For `Expect: 100-continue\x00bad` with `Content-Length: 0`, and unsupported
`Expect: 100-wait` with duplicate `Content-Length: 0` fields, both releases
and Modex return `417 Expectation Failed`, send no interim `100`, return an
empty body, close the client connection, and make no upstream request. The raw
response heads match after removing the dynamic `Date` field:

```text
HTTP/1.1 417 Expectation Failed\r\n
Server: tiny-http (Rust)\r\n
Content-Length: 0\r\n\r\n
```

Both controls run against both checksum-pinned releases and Modex in
`test_duplicate_expect_and_framing_rejections_remain_fail_closed`; the former
Modex-only 400 and 502 expectations were stale.

Only lexically identical duplicate lengths after TinyHTTP-compatible trimming
are collapsed. Numeric variants and conflicting framing stay fail-closed in
Modex even though the releases dispatch numeric variants using the first
length. With valid chunked bodies, both releases also dispatch ambiguous
`Content-Length`/`Transfer-Encoding` and duplicate `Transfer-Encoding` fields;
Modex returns 502 before upstream dispatch. This remains a deliberate
fail-closed difference, not a parity pass. An earlier conflict probe used a
decimal instead of hexadecimal chunk size, so its no-response observation did
not establish behavior for valid chunked framing. Raw UTF-8 bytes are rejected
by TinyHTTP's ASCII line reader; Modex now closes without sending its previous
400 response. Embedded-control, mismatched-length, and conflicting-framing
cases avoid upstream dispatch in Modex.

The source trace uses Prodex 0.165.1 at
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. In both
`vendor/tiny_http/src/client.rs` versions, `read_next_line` converts each
completed line to `AsciiString` before trimming. A non-ASCII line returns a
read error; `ClientConnection::next` drops that error without writing a
response. Modex's TinyHTTP-compatible path now closes on the same parser
error, before provider dispatch.

`test_non_ascii_header_bytes_close_without_response_like_releases` checks
non-ASCII bytes in header names and values across both checksum-pinned releases
and Modex. It also splits the value bytes across request writes and tests a
client half-close after the complete request. Each control observes
`RemoteDisconnected`, an empty response head, exit 0, and no upstream request.
`test_non_ascii_header_after_valid_pipelined_request_gets_no_response`
confirms the valid first request receives one 200 and reaches the upstream
once; the following invalid request gets no response and is not dispatched.
The process helper's secondary socket-state sample is not asserted after its
HTTP reader has already observed EOF.

The focused six-test process suite passed in 36.007 seconds:

```text
PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" rtk python3 -m unittest -v test_loopback_header_whitespace
Ran 6 tests in 48.404s
OK
```

The 29-test `test_loopback_server` suite also passed. The module runs in the
`focused-python-active-cross-release` groups in `run-fast.sh` and `run-full.sh`,
after both pinned oracles are acquired. The 0.439.2 tests resolve only
`PRODEX_ORACLE_04392` or the pinned cache path; they do not fall back to the
generic `PRODEX_ORACLE`. A focused rerun set that generic variable to the
0.165.1 binary and kept the explicit 0.439.2 path; checksum and behavior checks
still passed. The production import audit and `git diff --check` pass. This
qualifies selected Linux x86-64 behavior only; it does not reduce the
six-target denominator or establish full parity.

Reproduce the Expect control on both releases and Modex with:

```sh
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests rtk python3 -m unittest \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_duplicate_expect_and_framing_rejections_remain_fail_closed \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_duplicate_expect_and_framing_rejections_remain_fail_closed
```
