# Local relay overflow admission

On 2026-10-29, the local rewrite relay was changed to scan its single accepted
overflow connection with the same 512-byte request-header capture turn as
parked clients. When that connection cannot be admitted or dispatched, the
event loop keeps it and waits briefly before retrying; it does not accept a
second socket over it. Parent-channel EOF remains checked on each loop pass.

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
`test_local_rewrite_01651_oracle.py` also pass. The complete historical
0.165.1 relay oracle suite passed 19 tests, the 0.439.2 relay oracle suite
passed 11 tests, and `test_runtime_slow_partial.py` passed 11 tests. `make
build`, the local relay driver build, and `git diff --check` passed. All tests
use synthetic credentials, loopback peers, and temporary state.

The admission bound remains 128 parked connections plus one accepted overflow
connection, with a 128-entry listen backlog. Further clients wait in that
kernel backlog. Prodex 0.439.2's TinyHTTP task pool creates more parser threads
when all are busy and has no hard request-queue limit, so this finite Modex
policy does not reproduce its unbounded admission behavior. It prevents loss
of the retained overflow client and serves it when capacity opens; broader
flood capacity and wait-time parity remain open. This Linux x86-64 evidence
does not qualify the other release targets or full runtime parity.

Reproduce the focused checks from the repository root with:

```sh
make build
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/local_rewrite_driver.mojo \
  -o build/tests/local_rewrite_driver
PYTHONPATH=tests python3 -m unittest -v test_local_rewrite_admission
PYTHONPATH=tests MODEX_LOCAL_REWRITE_DRIVER=build/tests/local_rewrite_driver \
  python3 -m unittest -v test_local_rewrite_01651_oracle
PYTHONPATH=tests MODEX_LOCAL_REWRITE_DRIVER=build/tests/local_rewrite_driver \
  python3 -m unittest -v test_local_rewrite_04392_oracle
PYTHONPATH=tests python3 -m unittest -v test_runtime_slow_partial
```
