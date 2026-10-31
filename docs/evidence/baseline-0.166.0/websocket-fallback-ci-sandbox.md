# Active 0.166.0 WebSocket fallback CI sandbox

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The Fast and Full CI scripts schedule
`LocalRewriteWebSocketFallback01660Tests.test_pipeline_reuses_only_complete_client_framing`
through `scripts/ci/run_websocket_fallback_01660.py`. The test compares the
real Modex and checksum-verified Prodex 0.166.0 processes over synthetic loopback
connections. It covers complete fixed-length and zero-length
WebSocket fallback requests, fragmented requests, a pipelined follow-up, an
unauthorized follow-up, ambiguous framing, and a truncated body.

The wrapper runs the strict Python test runner in bubblewrap with all
namespaces unshared, a private 1777 tmpfs at `/tmp`, private 0700 HOME and XDG
directories, and a cleared environment. It exposes only the required test
environment variables. The root filesystem is read-only. Any required input
under host `/tmp` is restored at its original path with a read-only bind after
the private tmpfs is mounted.

The manual test preflight requires a rootless user namespace, private tmpfs
`/tmp`, and a network namespace with only loopback and no default IPv4 or IPv6
route. It checks that workspace, Modex, oracle, Python executable and prefix,
Python import paths, and an optional Mojo toolchain are covered by read-only
mounts. It rejects `/tmp` itself as a runtime search path and fails if an input
overlaps the writable scratch directory.

`tests/test_ci_websocket_fallback_sandbox.py` also probes synthetic inputs in
both layouts. One puts the workspace, Modex marker, oracle marker, Python venv
and prefix, and toolchain under host `/tmp`; the other puts workspace and
markers outside `/tmp`. Both verify read-only access. The `/tmp` probe checks
that the host environment sentinel does not cross the boundary and that the
network namespace has only loopback with no default route. Negative checks
reject unbound `/tmp` paths and any mount target that overlaps writable
scratch.

Local validation on Linux x86-64:

- Mojo 1.2.0 production build passed.
- The dedicated CI module passed all three tests, including the real oracle
  comparison.
- The real comparison also passed from a clean worktree outside `/tmp` while
  the Modex build and active oracle were under `/tmp`.
- `bash -n scripts/ci/run-fast.sh scripts/ci/run-full.sh` passed.
- `bash scripts/ci/validate-workflows.sh` passed with actionlint 1.7.12.
- `python3 scripts/ci/check-test-census.py` found one owner for all 50 native
  test sources and 182 Python test modules.

Hosted Fast CI run [41120572378](https://github.com/christiandoxa/modex/actions/runs/41120572378)
on `37c78129280c4c5666a5a1562b2f28201e9e127c` passed all three sandbox tests.
It also passed the 115-test active lane, but the overall run failed closed for
missing historical 0.439.2 and 0.439.5 oracles. These observations do not
qualify the full CI run, later commits, or other release targets.

The active oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.
