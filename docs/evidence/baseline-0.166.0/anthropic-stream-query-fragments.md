# Anthropic search query stream fragments (Prodex 0.166.0)

The pinned source at `9f69e1835808f478f59f12a3ae3fa88027d896a4` accumulates
`input_json_delta` fragments for `server_tool_use` web search in
`crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs`.
The translator in
`crates/prodex-provider-core/src/translators/anthropic/messages/web_search.rs`
projects the accumulated input into the Responses search item.

`tests/manual_anthropic_stream_01660.py` compares real Prodex and Modex processes
through the synthetic loopback provider. Empty start input followed by a single
valid JSON delta, and the same JSON split over two deltas, produce the same
completed search query in both processes. A fixture with a complete query in
the start block followed by the same full JSON in a delta reproduces a
mismatch: Prodex keeps `queries: ["release"]`; Modex appends the delta to the
start JSON, then emits `queries: []` when the combined text cannot be parsed.
The same complete query appears in both start and delta input; protocol
validity of this duplicate-input sequence is unqualified. It is recorded as a
characterization, not a parity pass or a production behavior change.

This is a manual-only test because it requires its own network and mount
namespace; it is excluded from normal CI discovery. The process test checks the
exact oracle SHA before each oracle launch, requires
a private user-owned tmpfs at `/tmp`, a namespace-local sysfs view containing
only `lo`, loopback enabled, and empty IPv4/IPv6 default-route tables. It uses
private temporary HOME/TMPDIR directories plus a temporary config/state tree,
a synthetic provider key, and only a loopback provider. `PRODEX_ORACLE` may
name any absolute path whose bytes match the pinned SHA-256. No account login or
outbound network is used. Scope is limited to the tested request route/body and
these search query frames; broader Anthropic stream parity remains open.

On 2026-10-30, the focused manual test passed one method covering all three
cases in 4.272 seconds. Each oracle launch verified SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735` at the
configured absolute path, using `/tmp/prodex-01660` as a symlink to verify
alternate-path support.

Reproduce from the Modex worktree after building `build/modex`:

```sh
timeout 180s unshare -Urnm sh -c 'mount --bind "$PWD" /mnt && mount -t tmpfs -o mode=1777 tmpfs /tmp && mount -t sysfs -o nosuid,nodev,noexec sysfs /sys && ip link set lo up && mkdir -m 700 /tmp/home /tmp/work && ln -s /home/doxa/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu /tmp/prodex-01660 && cd /mnt && exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/home/doxa/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE=/tmp/prodex-01660 PYTHONPATH=tests python3 tests/manual_anthropic_stream_01660.py'
```
