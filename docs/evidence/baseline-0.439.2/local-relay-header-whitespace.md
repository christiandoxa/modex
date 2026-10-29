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
| Duplicate equal `Content-Length` | 200 | 200 | 502 `gateway request capture failed` | Releases dispatch; Modex does not |
| Conflicting `Content-Length` and `Transfer-Encoding` | Connection closes without response | Same | 502 | No request |
| Raw UTF-8 whitespace at header boundaries | Connection closes without response | Same | 400 | No request |

The duplicate and conflicting framing cases remain explicit differences, not
parity passes. Raw UTF-8 whitespace is not accepted by TinyHTTP's ASCII line
reader; Modex's different 400 response remains unqualified. Embedded-control,
conflicting-framing, and raw-UTF-8 cases avoid upstream dispatch. Both releases
dispatch the duplicate-length control while Modex rejects it.

The focused three-method process suite passed:

```text
PYTHONPATH=tests python3 -m unittest -v test_loopback_header_whitespace
Ran 3 tests in 24.442s
OK
```

The CI runner also passed:
`python3 scripts/ci/run-unittest.py test_loopback_header_whitespace.py`.

The 28-test `test_loopback_server` suite passed. The test census reports 50
native sources and 140 Python modules with one discovery owner. The new module
runs in the `focused-python-active-cross-release` groups in `run-fast.sh` and
`run-full.sh`, after both pinned oracles are acquired. `make ci-dependencies`
audited 71 production Mojo files and found only standard-library and internal
imports. `git diff --check` passed. This qualifies selected Linux x86-64
behavior only; it does not reduce the six-target denominator or establish full
parity.
