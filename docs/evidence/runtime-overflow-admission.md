# Local relay overflow admission

The initial 2026-10-29 implementation scanned one accepted overflow
connection with the same 512-byte request-header capture turn as parked
clients. That one-slot behavior is historical. The follow-up bounded queue
below replaces it and is the current implementation. Parent-channel EOF remains
checked on each loop pass.

The regression uses the actual `serve_local_rewrite` entry point through the
Mojo test driver and an isolated loopback upstream. It holds all worker slots
on incomplete request bodies, fills the 128 parked slots with incomplete
headers, and then sends two complete overflow requests. Both clients receive
200 after one body-held worker is closed. Neither received a response before
the worker was released (`response_before_release = false`). A separate run
closes the parent channel while an overflow client is retained; the relay exits
within the 3-second bound and closes the overflow sockets without an upstream
request.

A separate check left workers free and held 128 partial headers. The healthy
request completed with HTTP 200 in 4.1 ms, before the partial clients were
released; the test enforces a 750 ms ceiling.

The idle-eviction, oldest-partial-request, and ready-client-churn controls in
`test_local_rewrite_01651_oracle.py` also pass. At the initial one-slot
checkpoint, the historical 0.165.1 relay oracle suite passed 19 tests, the
0.439.2 relay oracle suite passed 11 tests, and `test_runtime_slow_partial.py`
passed 11 tests. `make build`, the local relay driver build, and
`git diff --check` passed. All tests
use synthetic credentials, loopback peers, and temporary state.

The initial admission bound was 128 parked connections plus one accepted
overflow connection. The follow-up raises queued overflow capacity to
`max(2, worker_count)`, where `worker_count` honors the positive
`PRODEX_RUNTIME_PROXY_WORKER_COUNT` environment value but cannot exceed
Modex's default or eight. The 128-entry listen backlog remains; further
clients wait there. Configured counts one and two were compared with both
releases for incomplete-body and provider-barrier behavior; the default
controls also pass. Higher counts and policy-file tuning remain gaps; see
`docs/evidence/runtime-slow-partial.md`.
Prodex 0.439.2's TinyHTTP task pool creates more parser threads when all are
busy and has no hard request-queue limit, so this finite Modex policy does not
reproduce its unbounded admission behavior. Larger floods and full wait-time
parity remain open. This Linux x86-64 evidence does not qualify other release
targets or full runtime parity.

## Bounded-queue follow-up

The current overflow list receives a 512-byte header-capture turn per loop and
promotes queued sockets into newly freed parked slots. Completed keep-alive
connections also enter this bounded list when the parked set is full and
capacity remains. If the overflow list is full, completed connections still
close; the cap and its scheduling tradeoffs remain explicit.

The latest production checks cover the 129-, 132-, and 136-client floods, a
130-client promoted-overflow completion and keep-alive reuse, and parent EOF
with 137 held clients. The 14-test slow-partial matrix and separate parent-EOF
shutdown test passed against the checksum-pinned releases and the rebuilt
Modex candidate. Measurements and exact build evidence are in
`docs/evidence/runtime-slow-partial.md`.

Reproduce the focused checks from the repository root with:

```sh
make build
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/local_rewrite_driver.mojo \
  -o build/tests/local_rewrite_driver
PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_admission
PYTHONPATH=tests MODEX_LOCAL_REWRITE_DRIVER="$PWD/build/tests/local_rewrite_driver" \
  python3 -m unittest -v test_local_rewrite_01651_oracle
PYTHONPATH=tests MODEX_LOCAL_REWRITE_DRIVER="$PWD/build/tests/local_rewrite_driver" \
  python3 -m unittest -v test_local_rewrite_04392_oracle
PYTHONPATH=tests python3 -m unittest -v test_runtime_slow_partial
```

`MODEX_LOCAL_REWRITE_DRIVER` must be absolute because these tests run the relay
from isolated temporary working directories.

## Uncommitted aggregate-budget experiment (2026-10-30)

An isolated candidate based on Modex 23c5a22 adds a 4 MiB pending-connection
budget, capture reserve, and parsed-head charges. It is in
`/tmp/modex-relay-gap-23c5a22-20261030` on branch
`codex/relay-admission-gap-23c5a22-20261030`; its code base is `23c5a22`, five
commits behind `origin/main` at `63bb015`. The provider-only commits on
`origin/main` were not integrated into this experiment, and the candidate
product changes remain uncommitted.

The new production-process comparison uses 136 partial request heads, seven
body-blocked requests, an 8-worker environment setting, then a healthy
keep-alive client. With the healthy socket opened **after** the partial heads
settle, the 0.165.1 and 0.439.2 oracles and Modex each completed two requests
on that socket. Observed first/second response times were 1/1 ms, 1/1 ms, and
6/92 ms, respectively. The fixture uses a 400 ms settle period and samples
resources for 2 seconds. The comparison command is:

```sh
make build
PYTHONPATH=tests python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_admission_stress_compares_both_pinned_releases_and_modex
```

This passing ordering does not establish admission parity. In the other
ordering, the same healthy socket is opened before the partial-header flood
and sends its request after the 400 ms settle period. Both pinned releases
answer it and reuse the socket. The candidate closes it with
`RemoteDisconnected`; no upstream request is recorded. This occurred in
repeated 136-head, seven-blocker runs. A smaller sweep passed at 127 partial
heads but failed at 128 or 129 in several runs; a later 128-head replay passed
once, so the boundary observation is timing-sensitive. The candidate's
`_evict_oldest_idle_connection` can close an accepted socket with no request
bytes when the parked set is full, which explains the preconnected-client
failure. The current test fixture creates the healthy socket after the flood;
to reproduce the failed ordering, move the two `healthy = socket.create_connection`
and `healthy.settimeout` lines in the fake Codex `admission_stress` branch to
before its blocker and partial-client loops, then run the same unittest command.

The fake Codex script samples `/proc/<ppid>` for resource deltas. That PID is
not the Modex process for this launch path: the candidate reported zero RSS and
FD deltas and 0.010 CPU seconds over 2 seconds in the final run while its relay
served requests. Therefore the test's candidate CPU, RSS, and FD figures are
invalid and cannot be compared with the oracle figures (which showed
4.4–5.3 MiB RSS, 286–429 FDs, and 0.000 sampled CPU seconds). The CPU sample
also has 10 ms clock-tick resolution. No resource-bound claim follows from this
run.

This candidate remains unqualified. In addition to resolving or explicitly
accepting the preconnected idle-socket gap, a process-correct resource probe,
parent-EOF controls, large request-head limits, and repeated production
comparisons are still required. Do not treat the successful late-arrival case
as improved parity.
