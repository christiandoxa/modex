# Buffered provider metadata passthrough

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`tests/test_provider_passthrough_01660.py` compares that oracle with the built
Modex binary on buffered Chat Completions and Responses passthrough. It uses
loopback-only synthetic upstream fixtures, temporary HOME/config/storage, and a
synthetic API key. The fixture's cached update version is 0.166.0. No user
credentials or provider traffic are used.

Five response turn-state values cover visible ASCII, horizontal tab, an invalid
high byte, an invalid `0xff` byte, and UTF-8 `é`. Both routes retain the first
two values and omit the other three. The comparison also checks the binary
response body byte-for-byte, removes a Connection-nominated hop header, keeps
the request ID, forwards the synthetic inbound turn state, strips internal
namespace metadata, and sends exactly one provider POST per request.

Reproduce after building with the pinned Mojo toolchain. Set `PRODEX_ORACLE` to
the verified 0.166.0 Linux binary (generic path placeholder shown below):

```sh
PRODEX_ORACLE=/path/to/verified/prodex-x86_64-unknown-linux-gnu \
unshare -Urnm sh -c '
set -eu
mount --make-rprivate /
mkdir -p /mnt
mount --bind "$PWD" /mnt
mount -t tmpfs -o mode=0700 tmpfs /tmp
ip link set lo up
mkdir -m 700 /tmp/home /tmp/work
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=dumb NO_COLOR=1 MODEX_BINARY=/mnt/build/modex \
  PRODEX_ORACLE="$PRODEX_ORACLE" \
  python3 scripts/ci/run-unittest.py test_provider_passthrough_01660.py
'
```

This runs in private user, mount and network namespaces. `/tmp` is a private
tmpfs, the network namespace has only loopback enabled, and the test receives
a clean environment and temporary HOME/config/storage.

On 2026-10-30 this wrapped strict run passed: 1 test in 1.236 seconds. The
same private namespace wrapper passed 25 focused active methods, including the
manual fragmented-tool-stream comparison, in 13.160 seconds. Active callers of
the shared process fixture explicitly seed version metadata as 0.166.0; its
historical default remains unchanged. This is buffered metadata evidence for
these two routes only. It does not qualify streaming metadata, other response
headers, other platforms, or full parity.
