# Local relay WebSocket fallback connection reuse

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The pinned source identifies `Upgrade: websocket` in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_request.rs`
and returns the 426 HTTPS fallback in
`local_rewrite_pipeline_websocket.rs`. The active process accepts another HTTP
request on that connection after the fallback when the first request has
complete, unambiguous fixed-length framing and does not request a protocol
switch with `Connection: Upgrade`.

`tests/manual_local_rewrite_websocket_fallback_01660.py::LocalRewriteWebSocketFallback01660Tests.test_pipeline_reuses_only_complete_client_framing`
compares the production Modex relay with the checksum-pinned oracle. Contiguous
and fragmented requests with a positive fixed body and with `Content-Length: 0`
receive 426 followed by 200 in both products. The second authorized request
reaches only the synthetic loopback provider, including when the first request
explicitly sends `Connection: keep-alive`. Modex checks authorization again for
the second request: an invalid token gets 401 without provider dispatch, while
the 0.166.0 baseline accepts it. Keep the Modex authorization check; this is a
security-preserving baseline difference.

Conflicting duplicate Content-Length, Content-Length plus Transfer-Encoding,
and malformed Content-Length controls remain fail-closed in Modex. The oracle
returns 426 and then processes the pipelined request for these ambiguous heads;
Modex returns 426 and closes before dispatch. A truncated fixed-length WebSocket
body produces no response in either product. These ambiguous and unauthenticated
controls are not counted as parity.

The production relay still rejects WebSocket transport with 426. This change
only preserves HTTP/1.x connection reuse after a fully captured request; it does
not add WebSocket transport. The existing fallback response smoke test sends
`Connection: close` because its raw exchange helper reads through socket EOF;
the active comparison above covers persistent reuse. Evidence covers the tested
Linux x86-64 cases only.
The historical 0.439.2 oracle was unavailable during validation, and other
release targets remain unqualified.

## CI sandbox execution (2026-10-31)

Fast and Full CI now schedule this active 0.166.0 comparison through
`scripts/ci/run_websocket_fallback_01660.py`. Both CI scripts run
`tests/test_ci_websocket_fallback_sandbox.py`; its real-oracle case launches
the comparison in bubblewrap with a private tmpfs `/tmp`, isolated networking,
and a cleared environment. CI does not exclude this regression from either
lane.

The runner restores required host inputs below `/tmp` at their original paths
with explicit read-only binds after mounting the private tmpfs. It supports
both `/tmp` and non-`/tmp` input layouts. The dedicated sandbox tests exercise
these layouts and reject inputs overlapping writable scratch. Local evidence
and scope limits are recorded in
`docs/evidence/baseline-0.166.0/websocket-fallback-ci-sandbox.md`. Hosted Fast
CI run `41120572378` passed the sandbox comparison on its recorded commit;
the overall run failed closed on missing historical oracles. Evidence remains
limited to Linux x86-64.

## Historical manual validation (2026-10-30)

At the time of this run, the probe was manual-only and excluded from automatic
test discovery and the Fast/Full CI lists. Its namespace preflight required a
rootless user/mount/network namespace, private tmpfs `/tmp`, loopback as the
only interface, and no default route. The old setup did not preserve required
inputs below host `/tmp`; it required them outside `/tmp` and failed closed if
they were hidden. Direct host invocation failed at the namespace preflight
before either product started. This old reproduction no longer describes the
current CI runner.

The historical reproduction after `make build` was:

```sh
unshare -Urnm /bin/sh -c '
  set -eu
  mount --make-rprivate /
  mount --bind "$PWD" /mnt
  mount -o remount,bind,ro /mnt
  mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp
  ip link set lo up
  mkdir -m 700 /tmp/home /tmp/work
  cd /mnt
  exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/sbin:/usr/bin:/bin \
    LANG=C.UTF-8 NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
    MODEX_REAL_CODEX_NETNS=1 MODEX_BINARY=/mnt/build/modex \
    PRODEX_ORACLE="$PRODEX_ORACLE" PYTHONPATH=tests \
    "$PYTHON" -m unittest -v \
    manual_local_rewrite_websocket_fallback_01660.LocalRewriteWebSocketFallback01660Tests.test_pipeline_reuses_only_complete_client_framing
'
```

This historical command required `PRODEX_ORACLE` to name the checksum-verified
0.166.0 oracle and `PYTHON` to name the host interpreter before execution.

The historical manual validation passed on Linux x86-64: one active-oracle
comparison test in 5.107 seconds. Direct host invocation failed before
comparison. The 21 CI-oracle-routing tests passed after the probe was removed
from the active lists. These results describe the 2026-10-30 setup; they do not
describe current CI routing or qualify other targets.
