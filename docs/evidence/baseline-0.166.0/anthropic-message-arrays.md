# Anthropic Messages array grouping (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; verified Linux x86-64 oracle
SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The frozen source trace is
`mojo/prodex_core/anthropic_chat_request.mojo::anthropic_chat_write_body`,
which writes the translated system and message arrays, and
`mojo/prodex_core/anthropic_chat_messages.mojo::anthropic_chat_write_messages`
and `anthropic_chat_write_message_group`, which merge adjacent same-role
messages and preserve ordered content blocks. System and developer messages
are joined with two newlines.

Modex reaches the same production path through
`src/modex/provider_deepseek_transport.mojo` and
`src/modex/provider_anthropic_messages.mojo::deepseek_anthropic_messages_body`
and `_messages`. The active process regression is added to the existing
`tests/test_anthropic_missing_message_content_01660.py`, which is already in
the active 0.166.0 CI lane.

The accepted request combines adjacent user and assistant messages, separate
system and developer messages, and `input_text` plus `output_text` content
parts. Both real processes send one request to `/anthropic/v1/messages` with
the same decoded translated JSON body, synthetic provider key, and no bearer
authorization. Their buffered Responses JSON matches after ignoring only the
per-process `created_at` value. The same test runs in automatic and forced
Anthropic modes.

A second production comparison confirms mixed text and image input is rejected
with the same 502 body before either process sends an upstream request. This is
a fail-closed control, not image support. The fixtures use only synthetic text,
an example-domain image URL, and a synthetic provider key.

## Checks

- `make build` passed with Mojo 1.2.0 (2016d0cd).
- `make ci-dependencies` passed; all 73 production Mojo files use only
  standard-library and internal imports.
- The two new active process tests passed in 4.977 seconds. The run used the
  verified 0.166.0 oracle and a read-only workspace, oracle, and Modex binary.
  A private tmpfs held isolated temporary HOME and state. The network namespace
  had only loopback up and no IPv4 or IPv6 default route.

This slice adds active-release coverage for selected message-array shapes; it
does not promote a parity status or qualify the other five release targets.
Other Anthropic input shapes and broader provider parity remain open.

## Reproduction

Build Modex and set `MODEX_WORKSPACE`, `MODEX_BINARY_SOURCE`, and
`PRODEX_ORACLE_SOURCE` to the workspace, built binary, and checksum-verified
0.166.0 Linux x86-64 oracle. Keep the build and oracle outside `/tmp`; the
namespace replaces `/tmp` with a private tmpfs.

```sh
MODEX_WORKSPACE="/path/to/modex" \
MODEX_BINARY_SOURCE="/path/to/build/modex" \
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
: > /tmp/modex
mount --bind "$MODEX_BINARY_SOURCE" /tmp/modex
mount -o remount,bind,ro /tmp/modex
ip link set lo up
ip -o link show | awk 'END { exit NR != 1 }'
ip -o link show lo >/dev/null
test -z "$(ip -4 route show default)"
test -z "$(ip -6 route show default)"
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(stat -c %a /tmp)" = 700
test "$(stat -c %u /tmp)" = "$(id -u)"
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
  PATH=/usr/local/bin:/usr/bin:/usr/sbin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
  PRODEX_ORACLE=/tmp/oracle MODEX_BINARY=/tmp/modex PYTHONPATH=/mnt/tests \
  python3 -m unittest -v \
  test_anthropic_missing_message_content_01660.AnthropicMissingMessageContent01660Tests.test_message_arrays_coalesce_roles_and_preserve_text_parts \
  test_anthropic_missing_message_content_01660.AnthropicMissingMessageContent01660Tests.test_rich_anthropic_message_content_is_rejected_before_provider_post
NS
```
