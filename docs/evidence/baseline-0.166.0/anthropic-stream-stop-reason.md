# Anthropic stream stop-reason handling (Prodex 0.166.0)

The pinned reference is official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In `anthropic_messages_sse_reader.rs`, Prodex maps `stop_reason` through
`anthropic_stream_finish_reason` and passes its optional result to
`RuntimeDeepSeekSseState.observe_chat_chunk`. The shared state calls
`observe_finish` only when that value is present. An absent, null, or
non-string `stop_reason` therefore leaves tool arguments open until
`message_stop`, which performs final validation and completion.

Modex previously validated and completed every tool call at `message_delta`,
including when `stop_reason` was absent or non-string. A streamed call with a
partial JSON argument before that event and the remaining fragment after it
made Prodex complete successfully while Modex emitted `response.failed` and
then an argument delta. Modex now validates and completes tools at
`message_delta` only when `stop_reason` is a string. The string control keeps
its existing completion order.

`tests/test_anthropic_stream_01660.py::AnthropicStream01660Tests.test_tool_completion_waits_for_string_stop_reason`
compares both real processes over a synthetic loopback Anthropic Messages
provider. It covers missing, null, numeric, and string stop reasons, plus
malformed arguments first rejected at `message_stop`. The last case includes a
trailing argument frame and confirms it is ignored after the response fails.
The test uses a synthetic API key and isolated temporary HOME, config, and
storage. No real credentials or external provider traffic are used.

On 2026-10-31, the focused method passed against the checksum-verified oracle.
The complete `test_anthropic_stream_01660` module also passed: 3 tests in
15.569 seconds. `make build` and `make ci-dependencies` passed; the production
import audit found only standard-library and internal imports across 73 Mojo
files.

Reproduce from the Modex worktree after `make build`. Replace the oracle path
with the verified official 0.166.0 Linux x86-64 binary:

```sh
MODEX_WORKSPACE="$PWD" \
PRODEX_ORACLE_SOURCE="/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu" \
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
ip link set lo up
ip -o link show | awk 'END { exit NR != 1 }'
ip route show default | awk 'END { exit NR != 0 }'
ip -6 route show default | awk 'END { exit NR != 0 }'
cd /mnt/tests
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
  PATH=/usr/local/bin:/usr/bin:/usr/sbin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
  MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE=/tmp/oracle \
  PYTHONPATH=/mnt/tests python3 -m unittest -v test_anthropic_stream_01660
NS
```

This qualifies the tested stop-reason transition on Linux x86-64 only. Other
Anthropic stream orders, DeepSeek behavior, and the remaining five baseline
targets are not qualified by this comparison.
