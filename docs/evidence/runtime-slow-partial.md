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
headers under default and one-worker settings, 127/128/129- and 136-client
partial-header floods, a 130-client overflow completion and keep-alive reuse,
sixteen incomplete bodies, client half-close, an incomplete header followed by
EOF, 1,024- and 2,048-byte
declared bodies truncated after one byte, a zero-length body, a valid header
split across five sends, and the declared body limit. It first requires the
two frozen releases to agree. Modex must match their response timing for the
existing eight-header and sixteen-body pools, plus the exact truncated-body
status and body, header-EOF close, zero-length-body status, fragmented-header
status, and body-limit status.

At the earlier one-slot checkpoint, the 127/128-client case was an explicit
allowed gap: both releases served before release, while Modex could serve
before or after release. The expanded queue controls below supersede that
checkpoint for the tested 127/128/129-client counts.

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

On 2026-10-29, the expanded nine-test process matrix passed against Modex at
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

The earlier focused matrix also measured parked-header admission with 127 and
128 held partial requests. At 127, both releases and Modex served the healthy
request before release. At 128, both releases served it in about 2 ms, while
that Modex candidate waited through the 1,000 ms hold. This one-slot candidate
observation is retained as history; the updated bounded queue behavior and its
current flood limit are recorded below.

## Bounded overflow queue controls

On 2026-10-29, the accept loop replaced its single overflow socket with a
round-robin list capped at `max(2, worker_count)`, where worker count is capped
at eight. It gives each queued connection the existing 512-byte header-capture
turn, promotes queued sockets into freed parked slots, and retains completed
keep-alive connections in the overflow list when the parked set is full and
queue capacity remains. Excess clients stay in the kernel listen backlog.

The production `super exec` flood controls use isolated homes, synthetic
credentials, ephemeral loopback listeners, and a loopback-only synthetic
upstream. In one recorded run, Prodex 0.165.1, Prodex 0.439.2, and Modex each
served the healthy request before release for 129 and 132 partial headers:

| Partial headers | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
| ---: | ---: | ---: | ---: |
| 129 | 200 in 2 ms | 200 in 2 ms | 200 in 3 ms |
| 132 | 200 in 2 ms | 200 in 2 ms | 200 in 3 ms |
| 136 | 200 in 2 ms | 200 in 2 ms | no response before release; 200 after 1,001 ms |

The 136-client control records a current finite-cap mismatch. Its assertion
requires eventual 200 from every product and does not require Modex to miss the
1,000 ms window. Larger floods and full admission fairness remain unqualified.

The 130-client control completes one parked request to free a slot, completes
the promoted overflow request, reuses that same keep-alive connection for a
second request, and then checks a separate healthy connection. All four
requests returned 200 and reached the synthetic upstream in all three
products. The recorded elapsed time was 5 ms for Prodex 0.165.1, 6 ms for
Prodex 0.439.2, and 57 ms for Modex. The parent-EOF test also exits cleanly
after 137 partial clients and observes every peer closed.

The rebuilt Modex candidate used Mojo 1.2.0 (`2016d0cd`),
`-O3 --target-cpu=x86-64-v3 -I src`, from worktree base
`20ede2c2708f469ec67a709570845313281e2405`; its SHA-256 was
`2e865f940d9f5c7485e2d32b4ac8572aea4799313b92270f65d76e6b880b7579`.
All 14 tests in `test_runtime_slow_partial.py` passed against both checksum-
pinned releases and this candidate in 50.836 seconds. The separate parent-EOF
test passed one test in 0.126 seconds. `git diff --check` and Python syntax
compilation passed. This evidence covers only these Linux x86-64 process cases;
all six release targets, wider floods, and full runtime/security parity remain
unqualified.

## Configured relay worker count

On 2026-10-30, Modex began honoring `PRODEX_RUNTIME_PROXY_WORKER_COUNT` for
local-relay workers. With the variable unset, the existing Modex default is
unchanged: `min(8, Mojo parallelism)`. A positive configured value can reduce
the active pool, subject to that default and the eight-worker safety cap.

Real-process comparisons against Prodex 0.165.1 and 0.439.2 verified counts
one and two in two places. The incomplete-body test held that many workers
reading unfinished bodies; in all three products a healthy request waited
until a blocker was cancelled, then completed with 200. A synthetic upstream
barrier observed no overlap at count one and overlap at count two in both
releases and Modex. Default incomplete-body and provider-overlap controls
also passed against both pinned releases and Modex.

The startup test also compared empty, whitespace-only, malformed, and zero
values across both releases and Modex. Each exited with the same diagnostic,
before any synthetic Codex probe or upstream request, and left no managed
profile behind.

The production candidate was built with Mojo 1.2.0 (`2016d0cd`),
`-O3 --target-cpu=x86-64-v3 -I src`, from base
`00fa4f13da48cfe342ba1e02f6ceaeadf3927222`; `build/modex` SHA-256 was
`9a8fd599f3f8b8674e17d55c6860f4c9cffe8b2c69d461a356eb9dbf6b1c22f8`.
All 15 tests in `test_runtime_slow_partial.py` passed in 59.123 seconds; all
3 `test_local_rewrite_admission.py` tests passed in 3.254 seconds. The
configured provider-barrier test passed against each pinned release, as did
the default provider-overlap control. The four-value startup test passed for
all three products. The 71-file production import audit and the 50-native /
140-Python test census passed.

Reproduce the focused checks with:

```sh
PYTHONPATH=tests python3 -m unittest -v test_runtime_slow_partial
PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_worker_count_controls_parallel_provider_stalls
PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_worker_count_controls_parallel_provider_stalls
env -u PRODEX_RUNTIME_PROXY_WORKER_COUNT PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_two_codex_requests_overlap_at_the_provider
env -u PRODEX_RUNTIME_PROXY_WORKER_COUNT PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_two_codex_requests_overlap_at_the_provider
PYTHONPATH=tests python3 -m unittest -v test_super_launch.SuperLaunchTests.test_invalid_runtime_proxy_worker_count_fails_before_codex_or_upstream
```

The cap remains a known limit: Prodex accepts configured worker counts up to
64, while Modex cannot scale above eight or above its existing default. The
policy-file `runtime_proxy.worker_count` setting is not connected to this
pool. Modex's default also remains `min(8, Mojo parallelism)`, while the
releases document CPU parallelism clamped to 4–12; only the default process
controls above were checked on this Linux x86-64 host. All six release
targets, larger worker counts, policy-file tuning, and full runtime parity
remain unqualified.
