# Local relay admission under saturation

The 0.165.1 release and 0.439.2 both use vendored TinyHTTP's accept thread.
For every accepted socket, it creates a `ClientConnection` and submits a task
to `TaskPool`. `TaskPool::spawn` starts another thread whenever no thread is
waiting; it has no fixed connection or queue cap. At both source commits,
`TaskPool` sets `MIN_THREADS` to 4 and lets excess idle threads exit after five
seconds. Source was read from Prodex commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` for 0.165.1 and
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` for 0.439.2. The reference
repository was not modified.

Modex keeps at most 128 parked sockets and `max(2, worker_count)` overflow
sockets, then leaves later connections in the kernel accept backlog. When a
parked slot is needed, it closes the oldest socket with no request bytes. That
bounded policy can close a preconnected idle client. Skipping one idle socket
would only move the eviction boundary, and preserving every new idle socket
could let them occupy every slot. No bounded selection rule matching TinyHTTP's
unbounded task creation was established, so this remains a documented parity
gap.

## Production-process comparison

Tests launched the Modex Super CLI and both pinned Prodex binaries as real
processes. The fake Codex created loopback clients with synthetic requests and
an isolated temporary home. No real credentials or provider traffic were
used. Release binary checksums were 0.165.1
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
0.439.2
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

The probe walks the launched product's `/proc` process tree from its supervisor
and excludes the synthetic Codex process. Before sending the healthy request,
the seven-blocker case waits for the product tree's aggregate FD count to rise
by 143 from its pre-client baseline. The incomplete requests do not open
upstream sockets at that point, but the FD count does not identify each client
socket. The probe checks whether both healthy requests finished immediately
before it closes held clients. This counts Modex's relay child as well as its
supervisor; the releases keep their TinyHTTP task pool in the main process. RSS
is the sum of per-process `VmRSS` and can double-count shared pages. CPU uses
process `utime` and `stime`; the host exposes 10 ms ticks, so reported `0.000`
values mean below one observed tick, not proven zero work. Resource values below
are single 1-second samples, not resource qualifications.

The focused run on Linux x86-64 passed three tests in 34.400 seconds. It
compared these admission cases against both releases and Modex:

| Case | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
|---|---|---|---|
| One preconnected idle socket plus 136 partial headers | HTTP 200; one upstream POST | HTTP 200; one upstream POST | Socket closed; `RemoteDisconnected`; zero upstream POSTs |
| One preconnected idle socket plus 136 new idle sockets | HTTP 200; one upstream POST | HTTP 200; one upstream POST | Socket closed; `RemoteDisconnected`; zero upstream POSTs |
| Seven incomplete-body blocker requests, 136 partial headers, then a healthy keep-alive client | Two HTTP 200 responses before held clients close | Two HTTP 200 responses before held clients close | No response before held clients close; then two HTTP 200 responses |
| Full completed keep-alive pool followed by a new request | New request succeeds; oldest stays open | New request succeeds; oldest stays open | New request succeeds; oldest is evicted |
| Oldest socket has a partial request when admission runs | Partial and overflow requests succeed | Partial and overflow requests succeed | Partial and overflow requests succeed; partial socket stays open |

Process-tree samples for the three backlog cases (RSS delta in KiB, FD delta,
CPU seconds over one second):

| Case | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
|---|---:|---:|---:|
| Preconnected plus partial headers | `+2,124`, `+408`, `0.000` | `+2,192`, `+272`, `0.000` | `+400`, `+135`, `0.320` |
| Preconnected plus idle clients | `+2,200`, `+408`, `0.000` | `+1,896`, `+272`, `0.000` | `+52`, `+127`, `0.030` |
| Seven blockers plus partial-header backlog | `+5,300`, `+432`, `0.000` | `+4,484`, `+288`, `0.010` | `+588`, `+143`, `0.290` |

The Modex FD check allows 40 non-client descriptors beyond the synthetic
clients and blockers; observed deltas were 127–143. Release descriptors are
reported for comparison only. These are Linux-specific observations under
one local run and do not establish cross-platform resource bounds or full
admission parity.

Reproduce after `make build` with:

```sh
PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_admission_eviction_compares_preconnected_idle_and_keepalive_sockets \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_saturated_idle_pool_evicts_oldest_connection_to_admit_new_client \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_saturated_pool_preserves_oldest_partial_request_during_admission
```

The 2 MiB request-head boundary, parent EOF, idle deadlines, large-header
capture while saturated, active parsed-head accounting, and other release
targets were not measured by this run. Existing standalone tests do not qualify
their behavior when combined with this backlog. The uncommitted aggregate
budget prototype remains unqualified.
