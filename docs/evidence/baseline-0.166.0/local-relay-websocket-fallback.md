# Local relay WebSocket fallback connection reuse

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

This is a manual namespace regression and is excluded from automatic test
discovery and the fast/full CI lists. Its preflight verifies a rootless
user/mount/network namespace, a private tmpfs `/tmp`, loopback as the only
interface, and no default route. Direct host invocation fails before the
comparison. The test checks that the mounted workspace, Modex binary, oracle,
and Python remain visible outside private `/tmp`. Bind the workspace before
replacing `/tmp`. The Python executable and oracle must be available outside
host `/tmp`; preserving those paths from host `/tmp` has not been implemented,
so the test fails closed if either is hidden.

Reproduce after `make build` with:

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

Export `PRODEX_ORACLE` as the checksum-verified 0.166.0 oracle path and `PYTHON`
as a host interpreter path before running. The active automated lane does not
run this namespace comparison.

Manual validation passed on Linux x86-64: one active-oracle comparison test in
5.107 seconds. Direct host invocation failed at the namespace preflight before
starting either product. The 21 CI-oracle-routing tests passed after removing
the manual probe from the active lists. This does not qualify other targets.
