# Numeric loopback HTTP default port

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; the Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

For a synthetic provider listening on loopback port 80, Prodex accepts an
omitted port, explicit `:80`, and an empty port, then sends a Host header
without `:80`. Modex previously rejected omitted and empty ports, and included
`:80` for the explicit form. The production DeepSeek relay now selects port
80 for these forms and emits the default-port Host header. Numeric loopback
validation still rejects hostnames and non-loopback addresses.

`tests/manual_default_port_01660.py` compares real Prodex and Modex processes
with synthetic provider credentials for four IPv4 and three IPv6 URL forms. It requires a
private user, mount, and network namespace, private `/tmp`, isolated HOME, and
no default route before it binds port 80. The command below creates a private
network namespace before the fixture binds. The native Gateway unit also checks port selection and
Host authority formatting without opening a socket.

The real-process test remains manual: the existing bubblewrap launcher drops
the capability needed to bind port 80, and an attempted nested user namespace
was denied. The test is not counted as an automated CI pass. Run it in a clean
checkout after `make build`, with the Python interpreter and pinned oracle
available outside host `/tmp`:

```sh
ORACLE_SOURCE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
unshare -Urnm /bin/sh -s <<'NS'
set -eu
mount --make-rprivate /
mount --bind "$PWD" /mnt
mount -o remount,bind,ro /mnt
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp
mkdir -m 700 /tmp/home /tmp/work
ip link set lo up
test "$(ip -o link show | wc -l)" -eq 1
test -z "$(ip -4 route show default)"
test -z "$(ip -6 route show default)"
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/sbin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 MODEX_REAL_CODEX_NETNS=1 \
  MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE="$ORACLE_SOURCE" PYTHONPATH=/mnt/tests \
  python3 tests/manual_default_port_01660.py -v
NS
```

The manual process comparison passed for all seven forms in 4.081 seconds. The
production build, full native `make unit` at
`7834b9284531833cd16a1349c80bd64062ffa89b`, and the dependency audit passed.
The existing loopback GET and stream suites
passed 52 tests; the active URL and session-history modules passed 12 tests. A
fragmented-response helper control also passed against 0.166.0 after the test
harness change. These checks cover Linux x86-64 and do not establish general
provider parity or qualification on the other five release targets.
