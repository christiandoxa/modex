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

`tests/test_runtime_slow_partial.py` now runs the real isolated Super process
against both checksum-pinned releases and Modex. It covers eight incomplete
headers under default and one-worker settings, sixteen incomplete bodies,
client half-close, a valid header split across five sends, and the declared
body limit. It first requires the two frozen releases to agree. For Modex, the
header case requires the release response during the hold; the
body case permits either timing and either no response or 502 on the cancelled
request, while requiring the queued healthy request to finish with 200. The
fragmented-header and body-limit cases require their release status and no
unexpected upstream traffic.

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

On 2026-10-29, the four-test matrix passed against the rebuilt Modex candidate
at `/tmp/modex-admission-build/modex` in 19 seconds. The candidate was built
with Mojo 1.2.0 (`2016d0cd`), `-O3 --target-cpu=x86-64-v3 -I src`, from base
revision `0c251c7def188dd55ba7b64d4a5f0888b9fe3c12` plus the in-progress
admission and head-capture changes in `src/modex/runtime_local_rewrite.mojo`
and `src/modex/loopback_server.mojo`. Its SHA-256 was
`f86d147aac656e9b0cc7aad0d2921efc9d4d842734b3c2a774969dfdff2198a6`. The
matrix ran both pinned release controls and the Modex binary for each
scenario. This confirms the tested candidate's behavior for these scenarios;
it does not qualify the other release targets or establish full runtime
parity. The older prototype result above remains as historical evidence of
the original gap.

An independent candidate run returned 200 during the partial-header hold in
5 ms, matching the release behavior. In the sixteen-partial-body control, the
healthy request waited for cancellation in both, but Modex produced no response
for the half-closed partial request while both releases returned 502. This
truncated-body response remains a reproducible gap.
