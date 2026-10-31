# Anthropic parent-EOF cancellation after a stream failure

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

## Original combined case is characterization-only

At Modex snapshot `b04873c96f55db20151e2c284144824ec470c3aa`,
`test_parent_eof_cancels_failed_open_stream_with_truncated_pipeline_body`
placed an invalid UTF-8 comment and later SSE frames after `response.failed`.
Its chunked provider fixture did not hold the upstream connection open. The
`held` record meant the synthetic Codex client had read `response.failed`; it
did not prove that the response or Modex parent remained alive. In the full
1,195-test run, the Modex parent returned `0` before SIGTERM, while the client
recorded `IncompleteRead`. The test therefore did not establish cancellation.
Its full-suite log had SHA-256
`b9b4342a09a5ca931cb5d4380fc6c3f9b9a4a2d32a53d70bf1c0a7374e625a18`.

Modex's `_exec` starts the synthetic Codex child, waits for it to exit, then
waits for the relay and returns the child's exit status. When the test client
reads the ended response and exits normally, that path can stop the relay and
return before the test sends SIGTERM. This is a fixture timing gap; it does not
show that parent-EOF cancellation failed. A focused rerun of the exact
`b04873c` test passed in 1.071 seconds, consistent with its prior standalone
passes. The invalid-UTF-8 suffix remains covered by
`test_invalid_utf8_after_response_failed_records_release_open_body`.

The current worktree keeps active and historical combined cases as separate
tests. The active case is
`test_anthropic_parent_shutdown_01660.AnthropicParentShutdown01660Tests.test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized`;
the historical case is
`test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized`.
Both tests restore the invalid comment and later SSE frames, send 1,024 bytes of the
declared 1 MiB pipeline body, and leave the client write side open. They assert
the held `response.failed` body, pipeline shape, parent exit within five
seconds, and no surviving direct children. When SIGTERM is sent, it requires a
`-SIGTERM` exit; when no signal is sent, it requires status 0 and classifies
that as a clean exit without cancellation. The active test compares Modex with
checksum-verified Prodex 0.166.0; the historical test compares Modex with
0.165.1/0.439.2. In one isolated observation all four parents were alive at
the held marker and received SIGTERM. The full-suite `b04873c` observation
still records Modex returning 0 before SIGTERM. These cases characterize both
outcomes; they do not qualify cancellation. Focused active and historical
checks passed in an isolated network namespace with the three verified oracle
hashes listed below.

### Reproduce the original snapshot

This focused command uses the unmodified `b04873c` checkout, its built binary,
the checksum-pinned historical oracles, a private `/tmp`, and a new user,
mount, and network namespace. The test creates synthetic HOME, config, state,
and work directories and sends traffic only to loopback.

Replace `/path/to/` placeholders with verified local paths before running.

```sh
task_scratch="$(mktemp -d "$HOME/.cache/modex/parent-eof.XXXXXX")"
trap 'rm -rf -- "$task_scratch"' EXIT
mkdir -p "$task_scratch/workspace/b04873c" "$task_scratch/oracle"
touch "$task_scratch/oracle/01651" "$task_scratch/oracle/04392"
TASK_SCRATCH="$task_scratch" unshare --user --map-root-user --mount --net --fork /bin/bash -s <<'SH'
set -eu
mount --make-rprivate /
mount --bind /path/to/modex-snapshot-b04873c "$TASK_SCRATCH/workspace/b04873c"
mount --bind /path/to/prodex-0.165.1/prodex-x86_64-unknown-linux-gnu "$TASK_SCRATCH/oracle/01651"
mount --bind /path/to/prodex-0.439.2/prodex-x86_64-unknown-linux-gnu "$TASK_SCRATCH/oracle/04392"
mount -o remount,bind,ro "$TASK_SCRATCH/oracle/01651"
mount -o remount,bind,ro "$TASK_SCRATCH/oracle/04392"
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp
mkdir -m 0700 /tmp/modex-test-home
ip link set lo up
test -z "$(ip -4 route show default)"
test -z "$(ip -6 route show default)"
sha256sum "$TASK_SCRATCH/oracle/01651" "$TASK_SCRATCH/oracle/04392"
cd "$TASK_SCRATCH/workspace/b04873c/tests"
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 HOME=/tmp/modex-test-home TMPDIR=/tmp \
  PYTHONDONTWRITEBYTECODE=1 \
  MODEX_BINARY="$TASK_SCRATCH/workspace/b04873c/build/modex" \
  PRODEX_ORACLE_01651="$TASK_SCRATCH/oracle/01651" \
  PRODEX_ORACLE_04392="$TASK_SCRATCH/oracle/04392" \
  python3 -m unittest -v \
    test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_cancels_failed_open_stream_with_truncated_pipeline_body
SH
```

The checked oracle hashes are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
for 0.165.1 and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
for 0.439.2. A standalone pass does not resolve the full-suite observation.

## Deterministic cancellation slice

The active test
`test_anthropic_parent_shutdown_01660.AnthropicParentShutdown01660Tests.test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body`
compares 0.166.0 with Modex. The historical test
`test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body`
compares 0.165.1/0.439.2 with Modex. Each
stops the upstream SSE body immediately after `response.failed` and keeps the
synthetic provider connection open. Its hold timeout is 30 seconds for this
fixture only; the shared server default remains 3 seconds. The synthetic
client writes a complete pipeline head plus 1,024 bytes of a declared 1 MiB
body, then keeps its write side open.

Before SIGTERM, the test asserts the parent is alive. It then requires an
actual `-SIGTERM` parent exit, an upstream disconnect before the hold timeout,
an incomplete downstream read, and no direct children alive after two
seconds. Cleanup uses pidfds opened only for children listed under that
synthetic launcher; it does not signal a process group or reuse numeric PIDs.
The active module requires only the official Prodex 0.166.0 oracle; historical
comparison remains in the shared historical module. Their manifest-pinned
oracle SHA-256 values are
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`,
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`, and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`,
respectively. The active checksum is checked inside this test; historical
class setup does not require the active oracle.

The body-only and truncated-head held-open tests passed in a private tmpfs
`/tmp` under a user/mount/network namespace with no default route. Both tests
use isolated synthetic state and the loopback upstream. The cancellation test
passed ten consecutive repetitions. This qualifies only the held-open
`response.failed` slice; it does not qualify the original invalid-UTF-8-tail
plus parent-EOF combination or a full-suite run.

A separate forced four-second delay before reading the held marker once left a
direct child of the 0.166.0 launcher alive at the existing two-second check;
the fixture killed that captured child through its pidfd. Its role was not
captured. Five subsequent active-oracle repetitions with the same delay had
no surviving children. Keep the two-second child assertion and treat this
single timing observation as unresolved; it does not establish a release
mismatch.

Reproduce the current tests from `tests/` in the same isolated namespace:

```sh
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 HOME=/tmp/modex-test-home TMPDIR=/tmp \
  MODEX_BINARY=/path/to/modex \
  PRODEX_ORACLE=/path/to/0.166.0/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE_01651=/path/to/0.165.1/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE_04392=/path/to/0.439.2/prodex-x86_64-unknown-linux-gnu \
  python3 -m unittest -v \
    test_anthropic_parent_shutdown_01660.AnthropicParentShutdown01660Tests.test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized \
    test_anthropic_parent_shutdown_01660.AnthropicParentShutdown01660Tests.test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body \
    test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized \
    test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body \
    test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_parent_eof_with_truncated_pipeline_head_closes_cleanly \
    test_anthropic_stream_optional_metadata_shared.AnthropicOptionalMetadataSharedTests.test_invalid_utf8_after_response_failed_records_release_open_body
```
