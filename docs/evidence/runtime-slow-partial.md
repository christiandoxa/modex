# Eight-client slow-partial process observation

This is focused Linux process evidence for a known runtime mismatch. It does not
establish full runtime parity or change the six-target denominator.

The test runs each binary through its real isolated `super exec` relay. A fake
Codex client opens eight TCP connections and sends an incomplete `POST
/v1/responses` header on each, then sends a complete healthy ninth request. The
partial clients stay open for 1,000 ms. The test records whether it receives the
healthy HTTP status before closing them, then verifies the final status. Each
run used isolated HOME, XDG directories, Prodex state, shared Codex home and
workspace, a synthetic provider key, and a loopback-only synthetic upstream.
Exactly one complete request reached the upstream in each run.

| Process | Worker setting | Healthy status before partial close | Final status | Elapsed from healthy send |
| --- | --- | ---: | ---: | ---: |
| Prodex 0.165.1 | default | 200 | 200 | 2 ms |
| Modex candidate | default | no response | 200 | 1,009 ms |
| Prodex 0.165.1 | `PRODEX_RUNTIME_PROXY_WORKER_COUNT=1` | 200 | 200 | 2 ms |
| Modex candidate | `PRODEX_RUNTIME_PROXY_WORKER_COUNT=1` | no response | 200 | 1,008 ms |
| Prodex 0.439.2 | default | 200 | 200 | 2 ms |
| Modex candidate | default | no response | 200 | 1,008 ms |
| Prodex 0.439.2 | `PRODEX_RUNTIME_PROXY_WORKER_COUNT=1` | 200 | 200 | 2 ms |
| Modex candidate | `PRODEX_RUNTIME_PROXY_WORKER_COUNT=1` | no response | 200 | 1,008 ms |

The measured Modex candidate was supplied with `MODEX_BINARY` from the isolated
runtime-concurrency prototype worktree. Oracle SHA-256 pins are checked by the test:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

Reproduce against a built candidate with:

```sh
MODEX_BINARY=/path/to/build/modex \
PRODEX_ORACLE_01651=/path/to/prodex-0.165.1 \
PRODEX_ORACLE_04392=/path/to/prodex-0.439.2 \
python3 scripts/ci/run-unittest.py test_runtime_slow_partial.py
```

The earlier candidate observation is retained above as a reproducible gap. The
current regression requires Modex to match both releases and answer during the
hold for the tested header case.

## Frozen source trace and expanded controls

The compared sources are Prodex 0.165.1 commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Both relay versions start their
configured local-rewrite worker count in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite/background_workers.rs`.
Each worker waits for a complete request from TinyHTTP before it captures the
body. TinyHTTP accepts sockets separately and runs each `ClientConnection` in
its `TaskPool`; the pool starts four parser threads and adds threads when all
are busy. The pool source blob is identical in both releases. Its request-line
and header reader waits for CRLF and builds a `Request` only after the blank
line. An incomplete header therefore occupies a parser task, not a relay
worker.

After headers complete, requests with a `Content-Length` above 1,024 bytes
defer body reads to the relay worker. The 2,048-byte partial-body control fills
the worker pool. A healthy request waits until client half-close makes body
capture return an error and releases a worker. Both releases return 502 for the
truncated body and then serve the healthy request with 200. Their default
request-body limit is 64 MiB; `RuntimeLocalRewriteRequest::capture` rejects a
larger declared length before reading the body. The 67,108,865-byte control
returns 413 without upstream traffic.

`tests/test_runtime_slow_partial.py` runs the real isolated Super process
against both checksum-pinned releases and Modex. It covers eight incomplete
headers under default and one-worker settings, sixteen incomplete bodies,
client half-close, an incomplete header followed by EOF, 1,024- and 2,048-byte
declared bodies truncated after one byte, a zero-length body, a valid header
split across five sends, and the declared body limit. It first requires the
two frozen releases to agree. Modex must match their response timing for the
incomplete header and body pools, exact truncated-body status and body,
header-EOF close, zero-length-body status, fragmented-header status, and
body-limit status.

Request-head boundaries and large-header limits remain covered by
`test_local_rewrite_01651_oracle.py` and
`test_local_rewrite_04392_oracle.py`; see
`docs/evidence/baseline-0.165.1/local-relay-http.md`. These tests use isolated
state, synthetic credentials, ephemeral loopback ports, and a synthetic
upstream. They do not qualify other release targets or full HTTP parity.

Reproduce the complete focused matrix with:

```sh
MODEX_BINARY=/path/to/build/modex \
PRODEX_ORACLE_01651=/path/to/prodex-0.165.1 \
PRODEX_ORACLE_04392=/path/to/prodex-0.439.2 \
python3 scripts/ci/run-unittest.py test_runtime_slow_partial.py
```

On 2026-10-29, the expanded eight-test process matrix passed against Modex at
`/tmp/modex-truncated-body-eof-build/modex`, built with Mojo 1.2.0
(`2016d0cd`), `-O3 --target-cpu=x86-64-v3 -I src`, from base revision
`30901e73c3dd1a3503fc7f39c6e2ff08994e9fe9`. Its SHA-256 was
`14bb3ff9e53261961c1b15a737feb765878240655acf8dbd4ed4aa4b61c9df5a`.
Both pinned releases and Modex returned 502 with body `upstream request failed`
for a complete head declaring 2,048 bytes, one body byte, then client half-close;
all three closed without a response for an incomplete head. Additional raw
controls against both releases confirmed the TinyHTTP 1,024-byte boundary:
fixed-length body EOF at 1,024 bytes closes without a response, while 1,025
bytes yields that 502. `Expect: 100-continue` and chunk-data EOF also yield that
502. A WebSocket upgrade or invalid target with a 1,025-byte body is rejected
from the head with 426 or 400 respectively, before the body arrives; at 1,024
bytes all three wait for the body. Chunked WebSocket heads receive 426 before
the body arrives. These controls use synthetic loopback traffic and reach no
upstream.

The complete focused 0.165.1 relay oracle suite passed 19 tests, the 0.439.2
suite passed 11 tests, and the loopback/local-rewrite/relay stream suites passed
51 tests. This confirms only the tested Linux request cases; the other release
targets and full runtime parity remain unqualified. The earlier candidate
observation remains historical evidence of the original mismatch.

## Production request-head capture controls

The added controls use the real isolated `super exec` process path. They send
synthetic requests to the relay over loopback, use a synthetic provider
upstream, and verify its request count and provider authorization. Requested
head size is the byte offset of the final `\r\n\r\n`; padding is split among
fields no longer than 60 KiB each.

| Case | Prodex 0.165.1 | Prodex 0.439.2 | Modex candidate |
| --- | ---: | ---: | ---: |
| Complete 80 KiB head, one send | 200 | 200 | 200 |
| Exact 2 MiB head, sent in 512-byte fragments | 200 | 200 | 200 |
| 2 MiB + 1 byte complete head | 200 | 200 | 502, no upstream request |

For the fragmented 2 MiB case, the fake Codex client opens a second healthy
request after sending the first 512 bytes of the large head. All three
processes answer that request with 200 in 8 ms, before the large head is
complete. The large head completes in about 1.0–1.1 seconds and also returns
200, with two total upstream requests. This exercises the 512-byte capture
passes without a 100 ms pause on each pass. The 80 KiB complete request is
answered in 108 ms by Modex and 3 ms by each release in the recorded run.

The 2 MiB + 1 byte result is an existing production request-head limit gap:
both releases dispatch it, while Modex rejects it before upstream dispatch.
This remains recorded in `docs/handoff.md` and
`docs/evidence/baseline-0.165.1/local-relay-http.md`.

On 2026-10-29, all seven tests in `test_runtime_slow_partial.py` passed against
both checksum-pinned releases and a Modex build from commit
`30901e73c3dd1a3503fc7f39c6e2ff08994e9fe9`. The build used Mojo 1.2.0
(`2016d0cd`), `-O3 --target-cpu=x86-64-v3 -I src`; its SHA-256 was
`21f1064fa4af4c424ae220c3db69b54bfb31c69ab6588acb51cd851e9c4c5ea1`. The
suite took 29 seconds. This Linux x86-64 process evidence covers only these
request sizes and cases; it does not establish full HTTP or release parity.
