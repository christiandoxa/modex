# DeepSeek provider request and stream shape matrix

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0, commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`tests/test_provider_shapes_01660.py` runs the real Prodex and Modex processes
through the existing temporary-home process harness. Both use the same
synthetic loopback provider and synthetic client authorization. The isolated
run uses a private network namespace with only loopback available, separate
temporary HOME/state directories, and no external provider traffic.

The Responses request matrix sends eight cases through the production local
rewrite route: empty input, mixed role messages, typed text input, function
output continuation, optional sampling/token/logprob/stop/user fields, JSON
schema degradation, local and provider metadata, and a named function tool.
All requests reach the provider once; upstream route, synthetic authorization,
HTTP status, and exact translated request bodies match between the oracle and
Modex. The response comparison also confirms that the `local_tag` and
provider-specific `trace` metadata survive into the final response metadata.
The local metadata additionally sets `deepseek.finish_reason` to an object with
a synthetic `local_tag`, while the provider reply supplies the string
`"stop"`. Both final responses retain the request's tag object, matching the
release's request-metadata merge in
`mojo/prodex_core/deepseek_message_metadata.mojo::ds_merge_metadata` and
Modex's production `deepseek_buffered_response` metadata merge. This covers one
local-over-provider collision only.

The streaming response matrix covers metadata with empty choices, multiple
choices, a non-string text delta, reasoning followed by text, finish without
content, missing choices, and usage arriving after finish. Each process makes
one request per case and returns HTTP 200 with a completed Responses stream.
Event JSON matches after normalizing only generated numeric text item IDs.
Upstream IDs, event order, sequence numbers, response metadata, output text,
and usage remain directly compared.

The active process test also compares these model cases: direct `flash`,
explicit `deepseek-flash`, explicit `deepseek-v4-flash`, `combo:flash,pro`
retrying after a structured 404 or 429, and empty `combo:,,,` / `combo:`
inputs. The active oracle and Modex send the same provider model IDs and bodies.
Direct `flash` resolves to `deepseek-flash`; the explicit compatibility ID
stays `deepseek-v4-flash`. Both retryable combo errors proceed from
`deepseek-flash` to `deepseek-v4-pro`; empty combos are sent literally and do
not retry. The 0.439.2 expectations in the historical cross-release tests stay
separate and are not used as active evidence.
A separately run checksum-verified 0.165.1 control also matched Modex on direct
`flash`, the two combo retry cases, and `combo:,,,`; it remains a historical
control. No 0.439.2 oracle was run for this evidence.

The focused three-method process test and the existing 0.166.0 build pass on
Linux x86-64. This is selected request and response-shape evidence only; it
does not establish full provider parity or qualify the other five release
targets.

## Reproduction

Run `make build` first. From the Modex workspace, set `PRODEX_ORACLE_SOURCE`
to the checksum-verified official 0.166.0 Linux x86-64 binary and
`MOJO_LIBRARY_DIR` to the installed Mojo runtime library directory. Both paths
must be outside `/tmp`. The test verifies the oracle digest. Bind the workspace
before replacing `/tmp`, since a workspace can itself live there.
The wrapper runs with a cleared environment, read-only workspace/oracle/runtime
mounts, private mode-700 tmpfs, synthetic HOME/TMPDIR, loopback only, and no
default routes. The process harness creates distinct temporary state for each
binary and uses a synthetic loopback provider and API key.

```sh
MODEX_WORKSPACE="$PWD" \
PRODEX_ORACLE_SOURCE="/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu" \
MOJO_LIBRARY_DIR="/path/to/mojo/lib" \
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
mount --bind "$MOJO_LIBRARY_DIR" "$MOJO_LIBRARY_DIR"
mount -o remount,bind,ro "$MOJO_LIBRARY_DIR"
ip link set lo up
ip -o link show | awk 'END { exit NR != 1 }'
ip -o link show lo >/dev/null
ip route show default | awk 'END { exit NR != 0 }'
ip -6 route show default | awk 'END { exit NR != 0 }'
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(stat -c %a /tmp)" = 700
test "$(stat -c %u /tmp)" = "$(id -u)"
cd /mnt
exec env -i HOME=/tmp/home TMPDIR=/tmp/work \
    PATH=/usr/local/bin:/usr/bin:/usr/sbin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    TERM=dumb NO_COLOR=1 PYTHONDONTWRITEBYTECODE=1 \
    PRODEX_ORACLE=/tmp/oracle MODEX_BINARY=/mnt/build/modex \
    python3 scripts/ci/run-unittest.py test_provider_shapes_01660.py
NS
```
