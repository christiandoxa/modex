# Upstream log rotation full-suite recheck (2026-10-30)

The full-suite log from `b9b52d5` at
`/tmp/modex-full-b9b52d5-20261030.log` (lines 1296–1311) records
`test_log_upstream_follow.LogUpstreamFollowTests.test_truncation_and_rotation_reopen_followed_file`
failing in JSON mode. After truncation and path rotation, the five-second wait
for `after-rotation` expired with empty stdout and stderr.

On a clean worktree at `2d1217d`, the production build was run and the focused
test was run four times sequentially under quiet conditions. The initial run
and all three repeats passed, each in about 13 seconds. The test covers both
JSON and plain output modes and compares Modex with the pinned 0.439.2 process.

Reproduce one focused run with:

```sh
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests rtk python3 -m unittest -v \
  test_log_upstream_follow.LogUpstreamFollowTests.test_truncation_and_rotation_reopen_followed_file
```

The frozen 0.439.2 `log_follow.rs::inspect_followed_log_metadata` clears the
open file and identity when a followed path is missing. If that path reappears
before the next path reconciliation, `prepare_followed_log_file` opens it
without resetting the previous offset because no file is held. Modex's
`collect_new_followed_lines` does the same. An isolated process probe with a
500 ms gap between rename and replacement observed both pinned Linux releases
and Modex skip the replacement's initial marker, then emit a subsequent append.
This makes the original test's separate rename and creation operations a
plausible race, but does not prove that the full-suite timeout had that cause.

The existing rotation regression now writes the replacement first, links the
old inode to the rotated name, and atomically replaces the tracked path. This
keeps the old file available while ensuring no missing-path interval, so it
tests an inode change without relying on when a follower polls. The missing-path
behavior above remains a separate observed limitation, not a full parity claim.
The full suite still needs a rerun on the corrected revision.

The missing-path probe is not an automated assertion: a sleep alone cannot
guarantee the follower polled during the gap, especially under load. The
atomic-replacement regression is retained in the automated suite.
