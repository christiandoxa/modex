# Anthropic custom tool-call input mapping (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0 source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; verified Linux x86-64 oracle
SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The Anthropic Messages validation path previously admitted only
`function_call` and `function_call_output` items, even though the shared
DeepSeek request mapper and release accept `custom_tool_call` and
`custom_tool_call_output`. The release maps the custom call to an Anthropic
`tool_use` block whose input wraps the JSON-encoded custom input, then maps its
output to a `tool_result` block. Modex now lets those two types reach the
shared mapper; that mapper still validates the call ID, name, and output.

`tests/test_anthropic_custom_tool_calls_01660.py` compares the real 0.166.0 and
Modex processes through synthetic loopback providers in automatic and forced
Anthropic modes. It checks the translated request body for a custom call pair
and an ordinary function-call control. Missing custom IDs or names, missing
custom output, and an unknown typed item still fail before provider I/O with
the same response as the reference.

The pinned source trace is
`crates/prodex-app/src/runtime_launch/proxy_startup/provider_bridge/tests/request.rs:279-318`
(`deepseek_request_conformance_translates_custom_and_shell_call_items`), which
records the release's custom call/output pair and the mapped tool-call
arguments. `crates/prodex-provider-core/src/deepseek_bridge/request_messages.rs:33-52`
routes Responses array items through shared validation and mapping.
`crates/prodex-provider-core/src/translators/anthropic/messages_tests.rs:75-120`
shows the downstream Anthropic `tool_use` and `tool_result` shapes for the
ordinary function-call control.

## Checks

- `make build` passed with Mojo 1.2.0.
- `make ci-dependencies` passed; all 72 production Mojo files use only
  standard-library and internal imports.
- In the isolated namespace below, the new test plus
  `test_anthropic_missing_message_content_01660.py` and
  `test_provider_shapes_01660.py` passed 10 tests in 47.096 seconds.

## Reproduction

Build Modex, then run the focused test in a private user, mount, and network
namespace. The test uses a synthetic client, a synthetic API key, temporary
home and state, and a loopback provider; it does not contact a real provider.
Mount the workspace and oracle read-only, and use the checksum-verified oracle
path.

```sh
MODEX_WORKSPACE="$PWD" \
PRODEX_ORACLE_SOURCE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
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
mount -t sysfs -o nosuid,nodev,noexec sysfs /sys
ip link set lo up
test -z "$(ip -4 route show default)"
test -z "$(ip -6 route show default)"
test "$(find /sys/class/net -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)" = lo
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(stat -c %a /tmp)" = 700
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
  PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
  MODEX_BINARY=/mnt/build/modex PRODEX_ORACLE=/tmp/oracle \
  PYTHONPATH=/mnt/tests python3 scripts/ci/run-unittest.py \
  test_anthropic_custom_tool_calls_01660.py \
  test_anthropic_missing_message_content_01660.py \
  test_provider_shapes_01660.py
NS
```

This qualifies the tested Anthropic custom-tool pair and validation controls on
Linux x86-64 only. Broader Anthropic and six-target parity remain unqualified.
