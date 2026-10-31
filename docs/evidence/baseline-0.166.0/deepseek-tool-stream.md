# DeepSeek streamed function call

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The pinned reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Baseline trace

Prodex dispatches chat-completion SSE chunks through
`crates/prodex-provider-core/src/translators/deepseek/stream.rs`. The
translator validates `data: <json>` framing and delegates chat chunks to the
Mojo stream transform in `response.rs`. Its application stream state records
chunk metadata, including usage, before it checks for a choice; tool deltas
are accumulated and emitted by `deepseek_sse.rs` and
`deepseek_sse/tool_calls.rs`. The finish path completes the function-call item,
and `deepseek_sse/completion.rs` includes the retained usage in
`response.completed`.

Modex's production path is the local rewrite through
`src/modex/runtime_local_rewrite.mojo`,
`src/modex/provider_deepseek_transport.mojo`,
`src/modex/provider_chat_reader.mojo`, and
`src/modex/provider_chat_stream.mojo`. This evidence adds a manual process
comparison only; no production source changed.

## Isolated process comparison

`tests/manual_test_deepseek_tool_stream_01660.py` runs real Prodex and Modex
processes against the same loopback-only synthetic provider. The request uses
a synthetic API key and asks for one `lookup` function call. The stream
fragments `{"query":"synthetic"}` across two argument deltas, finishes the
call, then sends usage in a final chunk with `choices: []`.

Before either product process starts, the test requires `ip -o link` to show
only `lo`, empty IPv4 and IPv6 default-route tables, `/tmp` to be an
owner-owned mode-700 tmpfs, and distinct owner-owned mode-700 HOME and TMPDIR
directories beneath `/tmp`. No real credentials, provider traffic, or account
login are used.

The request body and response status match. The response bodies match
byte-for-byte, including this event order: `response.created`,
`response.output_item.added`, two
`response.function_call_arguments.delta` events,
`response.output_item.done`, and `response.completed`. The two deltas are
`{"query":` and `"synthetic"}`. The completed call carries compact arguments
`{"query":"synthetic"}` and usage `{input_tokens: 3, output_tokens: 4,
total_tokens: 7}`.

This is one Linux x86-64 function-call stream case. It does not establish
broader DeepSeek stream parity or parity on the other five release targets.
The test is manual-only and is not routed through fast or full CI.

## Reproduction

Run from the Modex checkout after building `build/modex`. The script creates a
private user, mount and network namespace, makes the workspace, oracle and
Mojo runtime library read-only, verifies the oracle digest, and asserts that
`lo` is the only interface and both default-route tables are empty. `/tmp` is
a private mode-700 tmpfs, and HOME is a mode-700 directory inside it.

Replace `/path/to/` placeholders with verified local paths before running.

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu \
MOJO_LIBRARY_DIR=/path/to/mojo/lib \
unshare -Urnm /bin/sh -s <<'NS'
set -eu
mount --make-rprivate /
mount --bind "$PWD" /mnt
mount -o remount,bind,ro /mnt
mount --bind "$PRODEX_ORACLE" "$PRODEX_ORACLE"
mount -o remount,bind,ro "$PRODEX_ORACLE"
mount --bind "$MOJO_LIBRARY_DIR" "$MOJO_LIBRARY_DIR"
mount -o remount,bind,ro "$MOJO_LIBRARY_DIR"
mount -t tmpfs -o mode=0700 tmpfs /tmp
mkdir -m 700 /tmp/home /tmp/work
ip link set lo up
[ "$(ip -o link show | wc -l)" -eq 1 ]
ip -o link show lo >/dev/null
[ -z "$(ip route show default)" ]
[ -z "$(ip -6 route show default)" ]
[ "$(stat -f -c %T /tmp)" = tmpfs ]
[ "$(stat -c %a /tmp)" = 700 ]
[ "$(stat -c %u /tmp)" = "$(id -u)" ]
[ "$(stat -c %a /tmp/home)" = 700 ]
[ "$(stat -c %u /tmp/home)" = "$(id -u)" ]
actual_sha="$(sha256sum "$PRODEX_ORACLE" | cut -d ' ' -f1)"
[ "$actual_sha" = 349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735 ]
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/bin:/usr/sbin:/bin \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
    MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE="$PRODEX_ORACLE" \
    python3 scripts/ci/run-unittest.py manual_test_deepseek_tool_stream_01660.py
NS
```

On 2026-10-30 this ran one test and passed. The test itself also hashes the
oracle before starting either process.
