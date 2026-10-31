# Guarded `--experimental-json` Super argument

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The checksum-pinned official Codex 0.166.0 Linux x86-64 binary is
`b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8`.
Its direct `codex exec --help` documents `--json` as JSONL event output but
does not list `--experimental-json`. A direct parser-only invocation using
`exec --json --experimental-json` reports that `--json` cannot be used multiple
times, confirming that the experimental spelling is a hidden alias for the
same output option. The probe uses only `--help` and the duplicate-flag parser
error; it does not run a model turn or exercise emitted JSON events.

In the isolated synthetic-client comparison, Prodex 0.166.0 forwards
`--experimental-json` unchanged and exits with the synthetic Codex client's
status 7. Modex rejects the same launch before starting a child. The existing
`--json` control reaches the same synthetic client through Modex. Neither run
made a provider request, and both left no managed overlay behind.

On 2026-10-30 UTC, `tests/manual_super_experimental_json_01660.py -v` passed one
test in a rootless user, mount, and network namespace using the pinned Linux
binaries and current Modex build.

The candidate remains guarded because this launcher currently injects
`--dangerously-bypass-approvals-and-sandbox` when it starts Codex. This note
does not authorize enabling another invocation through that path. The fake
Codex child records arguments and exits; the real Codex binary is used only
for direct help and parser diagnostics. Actual JSONL event output, launch
security behavior, other targets, and general Super parity remain unverified.

## Reproduce

Build Modex first. Then run this manual characterization in a rootless user,
mount, and network namespace with private temporary storage, loopback only,
and no default route:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu \
CODEX_BINARY=/path/to/codex-0.166.0/codex-x86_64-unknown-linux-musl \
unshare -Urnm sh -eu -c '
  mount --make-rprivate / &&
  mount -t tmpfs -o mode=1777 tmpfs /tmp &&
  ip link set lo up &&
  mkdir -m 700 /tmp/home /tmp/work /tmp/config /tmp/cache /tmp/data &&
  exec env -i \
    HOME=/tmp/home TMPDIR=/tmp/work TMP=/tmp/work TEMP=/tmp/work \
    XDG_CONFIG_HOME=/tmp/config XDG_CACHE_HOME=/tmp/cache XDG_DATA_HOME=/tmp/data \
    PATH=/usr/sbin:/usr/bin:/sbin:/bin TERM=dumb NO_COLOR=1 \
    MODEX_BINARY="$PWD/build/modex" \
    PRODEX_ORACLE="$PRODEX_ORACLE" CODEX_BINARY="$CODEX_BINARY" \
    python3 tests/manual_super_experimental_json_01660.py -v
'
```

The harness checks the Linux namespace and private `/tmp` before invoking any
binary. It verifies both release artifact digests, probes Codex help and the
duplicate-option error directly, then compares the pinned Prodex release and
the built Modex binary with the synthetic client from `test_super_launch.py`.
