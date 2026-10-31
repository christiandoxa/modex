# Provider stream edge ordering (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0, source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## DeepSeek stream metadata

`tests/test_provider_shapes_01660.py::ProviderShapes01660Tests.test_chat_stream_metadata_tool_order_and_error_match_active_release`
compares real 0.166.0 and Modex processes through a synthetic loopback
provider. Three stream chunks cover refusal and citation metadata, usage and
logprobs; tool calls arriving at indexes 2 then 0; and an embedded provider
error. The test checks request routing, synthetic authorization, response
metadata, output order, error code/message, a generated response-ID shape, and
a positive runtime timestamp.

For the failed response, comparison normalizes only `response.id` and the
event's top-level `created_at`, after separately checking their shape. All
other event fields remain exact. Successful metadata and tool-order event
sequences are compared without normalization.

## Anthropic stream ordering

`tests/test_anthropic_stream_01660.py` compares only the verified 0.166.0
oracle and Modex. The synthetic fixtures cover overlapping search and result
blocks, starting a search while another result block is open, duplicate search
IDs, and partial failures before `message_start`, after a result block, and
after `message_delta`. It also checks environment-only `anthropic` mode,
TOML-only `anthropic` mode, and TOML precedence over environment
`openai_chat`.

All tested stream events match after normalizing only generated response or
message IDs and `created_at`. Provider request JSON comparison ignores object
member order only: it rejects duplicate keys and preserves every value, type,
and array order. In the two interleaved-block fixtures, the raw request bytes
differ because one Modex object serializes its members in a different order;
the parsed request structures are equal, with no duplicate keys. No production
change was justified by this difference.

These fixtures use synthetic input, synthetic keys and loopback providers.
They do not establish general Anthropic stream parity, transport behavior,
other platforms, or full release parity.

## Checks

- `rtk make build` passed with Mojo 1.2.0 before the test-only changes.
- `python3 -m unittest -v test_anthropic_stream_01660
  test_provider_shapes_01660` passed 6 tests in 13.611 seconds against active
  Prodex and Modex in an isolated namespace.
- The Anthropic comparison used no historical oracle. It ran in private user,
  mount, and network namespaces with a read-only worktree and oracle, a private
  `/tmp`, isolated `HOME`, and loopback only with no default routes.
- `make ci-dependencies` passed; these changes add only Python test and
  Markdown evidence files.

Reproduce after building `build/modex`. Replace the oracle path with the
checksum-verified 0.166.0 binary:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu \
unshare -Urnm sh -c '
set -eu
mount --make-rprivate /
mount --bind "$PWD" /mnt
mount -o remount,ro,bind /mnt
mount -t tmpfs -o mode=0700 tmpfs /tmp
mkdir -m 700 -p /tmp/oracle /tmp/home /tmp/work /tmp/reference
touch /tmp/oracle/prodex
mount --bind "$PRODEX_ORACLE" /tmp/oracle/prodex
mount -o remount,ro,bind /tmp/oracle/prodex
mount -t sysfs -o nosuid,nodev,noexec sysfs /sys
ip link set lo up
[ -z "$(ip -4 route show default)" ]
[ -z "$(ip -6 route show default)" ]
[ "$(find /sys/class/net -mindepth 1 -maxdepth 1 -printf "%f\n" | sort)" = lo ]
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
  PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
  MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE=/tmp/oracle/prodex \
  MODEX_REFERENCE_CACHE=/tmp/reference PYTHONPATH=tests \
  python3 -m unittest -v test_anthropic_stream_01660 test_provider_shapes_01660
'
```
