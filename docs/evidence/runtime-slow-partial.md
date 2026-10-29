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

The assertions require both releases to answer before the partial clients close
under both worker settings. The candidate must eventually answer after release;
the observed delay matches the one-second hold. This records a mismatch only.
