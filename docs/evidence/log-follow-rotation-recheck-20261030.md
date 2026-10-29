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

These focused passes do not resolve the full-suite failure. The missing marker
was not reproduced or traced, no code was changed for log following, and the
full-suite result remains an unqualified intermittent gap pending reproduction.
