# DeepSeek provider request and stream shape matrix

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

The streaming response matrix covers metadata with empty choices, multiple
choices, a non-string text delta, reasoning followed by text, finish without
content, missing choices, and usage arriving after finish. Each process makes
one request per case and returns HTTP 200 with a completed Responses stream.
Event JSON matches after normalizing only generated numeric text item IDs.
Upstream IDs, event order, sequence numbers, response metadata, output text,
and usage remain directly compared.

The focused two-method process test and the existing 0.166.0 build pass on
Linux x86-64. This is selected request and response-shape evidence only; it
does not establish full provider parity or qualify the other five release
targets.

## Reproduction

From the Modex workspace, set `PRODEX_ORACLE` to the checksum-verified official
0.166.0 Linux x86-64 binary and `MOJO_LIBRARY_DIR` to the installed Mojo
runtime library directory. The wrapper mounts the workspace, oracle, and Mojo
runtime read-only, uses a private tmpfs for test state, and allows only
loopback networking. The test also creates distinct temporary HOME and state
directories for each product process.

```sh
export MODEX_WORKSPACE="$PWD"
export PRODEX_ORACLE="/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu"
export MOJO_LIBRARY_DIR="/path/to/mojo/lib"
unshare -Urnm /bin/sh -s <<'NS'
set -eu
mount --make-rprivate /
mount -t sysfs -o nosuid,nodev,noexec sysfs /sys
mount -t tmpfs -o mode=0700 tmpfs /tmp
mkdir -m 700 /tmp/home /tmp/work /tmp/workspace
: > /tmp/oracle
mount --bind "$MODEX_WORKSPACE" /tmp/workspace
mount -o remount,bind,ro /tmp/workspace
mount --bind "$PRODEX_ORACLE" /tmp/oracle
mount -o remount,bind,ro /tmp/oracle
mount --bind "$MOJO_LIBRARY_DIR" "$MOJO_LIBRARY_DIR"
mount -o remount,bind,ro "$MOJO_LIBRARY_DIR"
ip link set lo up
[ "$(ip -o link show | wc -l)" -eq 1 ]
[ -z "$(ip route show default)" ]
[ -z "$(ip -6 route show default)" ]
cd /tmp/workspace
export HOME=/tmp/home TMPDIR=/tmp/work PYTHONDONTWRITEBYTECODE=1
export PRODEX_ORACLE=/tmp/oracle MODEX_BINARY=/tmp/workspace/build/modex
python3 scripts/ci/run-unittest.py test_provider_shapes_01660.py
NS
```
