# Anthropic missing message content

The pinned Prodex 0.166.0 source at
`9f69e1835808f478f59f12a3ae3fa88027d896a4` filters chat messages without
emittable blocks in `mojo/prodex_core/anthropic_chat_messages.mojo`, including
`anthropic_chat_message_has_blocks` and `anthropic_chat_next_emitted`. Modex's
Anthropic preflight previously rejected any input item missing `content`
before translation. It now requires content for explicitly typed messages
while leaving untyped items to the existing translator.

`tests/test_anthropic_missing_message_content_01660.py` compares real Modex
and checksum-verified 0.166.0 processes using isolated synthetic homes and
loopback providers. It covers selected untyped messages with missing, empty,
null and scalar content, mixed function calls and outputs, and typed invalid
input rejected before a provider POST, in automatic and forced Anthropic
modes. The three active tests passed in a user, mount and network namespace
with private `/tmp`, synthetic HOME, loopback enabled and no default routes;
five historical message-array regression tests also passed. An earlier plain
network-namespace attempt was interrupted after reporting failures; their
cause was not captured. These observations cover only those cases on Linux
x86-64; broader input translation and six-platform parity remain open.

To reproduce the isolated active comparison after building Modex, run from
the checkout with the local toolchain and oracle paths adjusted if needed:

Replace `/path/to/` placeholders with verified local paths before running.

```sh
unshare -Urnm sh -c 'mount --bind "$PWD" /mnt && mount -t tmpfs -o mode=1777 tmpfs /tmp && ip link set lo up && mkdir -m 700 /tmp/home /tmp/work && cd /mnt && exec env -i HOME=/tmp/home TMPDIR=/tmp/work PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 TERM=dumb NO_COLOR=1 PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu python3 scripts/ci/run-unittest.py test_anthropic_missing_message_content_01660.py'
```
