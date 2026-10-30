# Anthropic search query stream fragments (Prodex 0.166.0)

At pinned source `9f69e1835808f478f59f12a3ae3fa88027d896a4`, the reader in
`crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs`
initializes web-search input from a nonempty object and appends every
`input_json_delta.partial_json`, including deltas after `content_block_stop`.
The provider translator in
`crates/prodex-provider-core/src/translators/anthropic/messages/web_search.rs`
passes accumulated input to `mojo/prodex_core/anthropic_request.mojo`'s
`anthropic_request_write_web_search_input_queries`, which uses
`anthropic_request_object_field`. That scanner requires the complete input to
begin with `{` and end with `}`. It scans fields from the first object and can
return its query before inspecting trailing objects. This explains why a
complete start object followed by a complete delta object preserves the start
query, while a truncated suffix or trailing whitespace yields `queries: []`.
Multiple complete objects select the first object's query. A malformed suffix
ending in `}` also selects the first query because the scanner returns before
reading the suffix. The protocol validity of these multi-object sequences is
unqualified.

Modex now keeps appending deltas. It uses the existing strict JSON parser for a
single object; if parsing fails, it applies the same outer-brace bound, finds
the first complete object with a byte scan that respects quoted strings and
escapes, and strictly parses that object before projecting queries. The scan
runs only after whole-input parsing fails, stores no extra input copy, and
cannot exceed the existing 4 MiB provider body and SSE accumulation limits.
Start input is retained only when it is a nonempty object, matching the pinned
reader. The existing state-machine behavior and response request routing are
unchanged.

`tests/manual_anthropic_stream_01660.py` compares real Prodex and Modex
processes through the synthetic loopback provider. Its 22 cases cover empty
start with complete and split fragments; same and different start/delta
queries; split, truncated, and consecutive delta objects; absent, null, and
non-string start queries; string, array, and null start inputs; nested braces
inside strings; malformed suffixes; leading, trailing, and internal
whitespace; and deltas after `content_block_stop`. Every case compares the
translated request and full normalized response events.

This is a manual-only test because it requires its own network and mount
namespace; it is excluded from normal CI discovery. Before each oracle launch,
the test requires an absolute `PRODEX_ORACLE` path whose bytes match SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`. It also
requires a user-owned private tmpfs at `/tmp`, private `HOME` and `TMPDIR`, a
namespace-local sysfs view containing only `lo`, loopback enabled, and empty
IPv4/IPv6 default-route tables. The synthetic provider uses a synthetic key
and loopback only. No account login or outbound network is used. Coverage is
limited to these stream inputs and the tested request route/body; broader
Anthropic parity remains open.

On 2026-10-30, the focused process test passed all 22 cases in 31.484 seconds.
Each oracle launch verified the pinned SHA at
`/home/doxa/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu`.
The `test_provider_chat_reader` and `test_provider_chat_stream` Mojo unit
programs also passed after the change.

Reproduce from the Modex worktree after building `build/modex`:

```sh
timeout 180s unshare -Urnm sh -c 'mount --bind "$PWD" /mnt && mount -t tmpfs -o mode=1777 tmpfs /tmp && mount -t sysfs -o nosuid,nodev,noexec sysfs /sys && ip link set lo up && mkdir -m 700 /tmp/home /tmp/work && cd /mnt && exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/home/doxa/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE=/home/doxa/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu PYTHONPATH=tests python3 tests/manual_anthropic_stream_01660.py -v'
```
