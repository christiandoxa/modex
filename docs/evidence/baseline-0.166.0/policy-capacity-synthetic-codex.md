# Policy-capacity HTTP 503 through the active Super process

This check covers Modex's connected `super --provider deepseek` API-key route
with one synthetic key. It does not verify Prodex's separate profile-backed
Responses proxy or claim profile Guardian/policy parity.

The pinned reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its verified Linux x86-64 binary
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In the release source, `crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs`
classifies non-2xx API-key responses and retries credentials only when another
attempt is available.
`crates/prodex-app/src/runtime_launch/proxy_startup/provider_bridge_error_policy.rs`
calls the shared provider-error classifier.
`crates/prodex-provider-core/src/errors.rs` keeps the HTTP status candidate alongside structured body codes, and
`mojo/prodex_core/provider_error.mojo` classifies HTTP 503 as transient. With
one available key the local API-key route therefore forwards the 503; this
route's status-based retry behavior is distinct from the profile-backed policy
capacity behavior described in the 0.166.0 release notes.

`tests/test_provider_policy_codex_01660.py` runs the official release and the
compiled Modex executable through their production Super launchers. A
synthetic Codex HTTP client completes the hook-trust handshake and sends one
request to the local relay; the synthetic loopback provider returns
`policy_capacity_unavailable` with HTTP 503. Both processes return that exact
status and body to the client, perform one upstream POST, use the active
`prodex-hook-trust` client version, leave no profile overlay entries, and do not
print the synthetic provider key. The Codex client in this test is a fixture,
not the real Codex binary.

`make build` and the four focused active-baseline tests passed on Linux
x86-64. The process differential ran in a rootless user, mount and network
namespace with a private temporary filesystem, loopback only, and no default
routes:

```sh
make build
MODEX_WORKSPACE="$PWD" \
PRODEX_ORACLE="/path/to/verified/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu" \
unshare -Urnm /bin/sh -s <<'NS'
set -eu
mount --make-rprivate /
mount -t tmpfs -o mode=1777 tmpfs /tmp
ip link set lo up
ip -o link show | awk 'END { exit NR != 1 }'
ip route show default | awk 'END { exit NR != 0 }'
ip -6 route show default | awk 'END { exit NR != 0 }'
mkdir -m 700 /tmp/home /tmp/work
cd "$MODEX_WORKSPACE"
exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  MODEX_BINARY="$MODEX_WORKSPACE/build/modex" \
  PRODEX_ORACLE="$PRODEX_ORACLE" PYTHONPATH=tests \
  python3 scripts/ci/run-unittest.py \
    test_policy_capacity_01660.py test_provider_policy_codex_01660.py
NS
```

This characterizes one Linux x86-64 API-key Super route only. It does not
implement or qualify the profile-backed HTTP 503 policy, profile rotation,
Guardian affinity, or the other five release targets.
