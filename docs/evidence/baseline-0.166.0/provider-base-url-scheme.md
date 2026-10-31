# DeepSeek base URL scheme casing (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The reference is official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The checksum-verified Linux
x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Source trace and mismatch

In the pinned source, `crates/prodex-app/src/runtime_deepseek_config.rs`
validates the configured upstream with `reqwest::Url::parse` and accepts parsed
schemes `http` and `https`. This accepts valid case variants such as `HTTP://`.
The production DeepSeek route then reaches
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_transport/urls.rs::runtime_deepseek_upstream_url`.

Modex's production route starts at
`src/modex/runtime_local_rewrite.mojo::local_rewrite_upstream`. Its manual
loopback URL check previously required the literal lowercase prefix
`http://`, so it rejected a valid `HTTP://127.0.0.1:<port>/v1` before any
upstream request. The check now folds the scheme case while retaining the
numeric-loopback, HTTP-only, credential-free, query-free, and fragment-free
guards.

## Isolated process comparison

`tests/test_provider_base_url_scheme_01660.py` runs both products through the
production DeepSeek local rewrite using a synthetic client shim, a synthetic
provider API key, and a loopback HTTP server. With `HTTP://` as the base URL,
both processes issue one POST to `/v1/chat/completions`; the authorization
header is `Bearer synthetic-provider-key`, and the translated request bodies
match exactly. Before the fix, Prodex completed the request while Modex exited
before sending a request with `this Modex gateway requires a credential-free
numeric loopback HTTP upstream URL`.

On 2026-10-31, the checksum-verified oracle comparison and the existing four
0.166.0 provider shape comparisons passed together: 5 tests in 6.464 seconds.
The native `test_gateway_cli` check also passed, including rejections for HTTPS,
non-loopback hosts, userinfo, queries, and fragments.
The run used a private user, mount, and network namespace; read-only workspace,
oracle, and Mojo runtime mounts; a private mode-700 tmpfs at `/tmp`; isolated
HOME and TMPDIR; loopback only; and no default routes. The test does not launch
real Codex or contact an external provider.

This evidence covers scheme casing for one numeric-loopback DeepSeek route on
Linux x86-64. It does not qualify TLS or other release targets.

## Spaces in loopback upstream paths

The production Super path now percent-encodes ASCII spaces in the path portion
of numeric-loopback HTTP base URLs. The 0.166.0 process sends `hello%20world`
for `hello world`; previously Modex rejected the launch before contacting its
synthetic provider. The active process comparison also covers spaces at path
segment boundaries, UTF-8, and already encoded `%20`. Both the Chat Completions
and Anthropic Messages routes were compared. The native URL checks
retain rejection of whitespace in the authority and C0/DEL bytes, credentials,
non-loopback destinations and HTTPS. This only qualifies the tested HTTP
loopback route; it does not establish provider transport or TLS parity.

## Reproduction

After `make build`, set `PRODEX_ORACLE_SOURCE` to the verified 0.166.0 binary
and `MOJO_LIBRARY_DIR` to the installed Mojo runtime library directory:

```sh
MODEX_WORKSPACE="$PWD" \
PRODEX_ORACLE_SOURCE="/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu" \
MOJO_LIBRARY_DIR="/path/to/mojo/lib" \
unshare -Urnm /bin/sh -s <<'NS'
set -eu
mount --make-rprivate /
mount --bind "$MODEX_WORKSPACE" /mnt
mount -o remount,bind,ro /mnt
mount -t tmpfs -o mode=0700 tmpfs /tmp
mkdir -m 700 /tmp/home /tmp/work
: > /tmp/oracle
mount --bind "$PRODEX_ORACLE_SOURCE" /tmp/oracle
mount -o remount,bind,ro /tmp/oracle
mount --bind "$MOJO_LIBRARY_DIR" "$MOJO_LIBRARY_DIR"
mount -o remount,bind,ro "$MOJO_LIBRARY_DIR"
ip link set lo up
ip -o link show | awk 'END { exit NR != 1 }'
ip route show default | awk 'END { exit NR != 0 }'
ip -6 route show default | awk 'END { exit NR != 0 }'
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
  PATH=/usr/local/bin:/usr/bin:/usr/sbin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
  PRODEX_ORACLE=/tmp/oracle MODEX_BINARY=/mnt/build/modex PYTHONPATH=tests \
  python3 scripts/ci/run-unittest.py \
    test_provider_base_url_scheme_01660.py test_provider_shapes_01660.py
NS
```
