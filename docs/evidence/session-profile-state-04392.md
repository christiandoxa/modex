# Read-only profile bindings for session listing

Prodex 0.165.1 (`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`)
and 0.439.2 (`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`)
were compared with the production Modex binary built from worktree `b2f0a70`
(`b6da0f8c214afec91ba8352f45822f946aa178668d6ca534ab31000b489c94b4`).
All fixtures use synthetic state and session files in isolated homes; no
credentials or provider traffic are involved.

The production `session list` path reads a valid `state.json` primary without
repairing it, attaches matching `session_profile_bindings`, and applies the
profile filter. The read rejects non-regular, unowned, world-accessible, and
oversized primary files. It compares the opened descriptor and link count with
the path before and after the read. Existing lock and last-good files do not
block a valid primary, and the test verifies that Modex leaves the primary,
backup, lock marker, session file, and file set unchanged.

Binding processing uses a hash index for profile membership and the final
occurrence of each binding key, matching JSON/Serde last-key behavior. One
timestamp is shared by both binding maps. Response bindings are validated but
not retained for the session report. Session bindings keep the same sorted
2,048-entry retention order; a hash index then attaches retained profiles to
session reports.

`tests/test_session_profile_04392.py` compares both releases for profile
filters, retention, conflict and identity behavior, duplicate keys, the
2,048-entry tie cutoff, 16,384 profiles and response bindings, 2,048
session reports, and stable hard-linked state primaries. The initial
checkpoint's 12-test run passed.
The 16,384-entry and 2,048-report cases complete against both references. The
broader session Python suite passes all 68 tests, and native `test_sessions`
passes. The dependency audit reports 71 standard-library-only production Mojo
files; the test census reports 50 native tests and 125 Python modules with one
owner each.

The release recovers an invalid primary from a valid `.last-good` file and
rewrites the primary; Modex fails closed and leaves both files untouched.
Both releases and the current Modex production path treat a dangling
`state.json` symlink as absent during read-only session listing. Modex uses
Mojo 1.2.0's `std.os.path.exists`, which follows the link only to check target
existence; the absent case never enters the state reader. A live symlink still
reaches the unchanged reader and is rejected by its `lstat` regular-file
check, without reading or changing the synthetic external target. A concurrent
replacement is not a general race-freedom claim: the standard-library reader
still has no `O_NOFOLLOW` or interprocess exclusion. A pre-existing lock or
last-good marker alongside a dangling link remains fail-closed. The releases
accept a world-readable state primary; Modex rejects it. A private primary with a
pre-existing hard-link alias is accepted by both releases and Modex; the
process test verifies that Modex preserves both paths and the link count. The
reader compares link counts during its descriptor/path checks but does not
reject a stable, multiply linked primary. These selected security differences
are not parity claims. A live symlink is rejected by both tested release
binaries and by Modex.

This read path does not implement cross-process locking or recovery. The
observed descriptor and metadata checks do not exclude concurrent writers or
prove general race freedom. A selected atomic-replacement stress case never
returned mixed profile data, but broader mutation and security behavior remain
unverified. Invalid or unsafe state stays fail-closed in Modex. See
`tests/test_session_profile_04392.py` and
`docs/evidence/baseline-0.165.1/session-profile-filter.md` for the production
vectors and earlier recovery comparison.

## Dangling primary follow-up

The 0.439.2 source trace is `crates/prodex-app/src/app_state.rs`,
`AppStateIoExt::load_with_recovery`: it checks `state_file.exists()` and treats
a broken symlink as absent when no last-good file exists. The updated Modex
path uses Mojo 1.2.0's `std.os.path.exists` for the same marker check. Both
pinned binaries and Modex now treat dangling state symlinks as absent and
continue rejecting live symlinks; synthetic external targets remain unchanged.
Lock and last-good markers still fail closed beside a dangling link.

All 17 tests across `test_session_profile_04392.py` and
`test_session_state_backup_04395.py` passed on the follow-up worktree. This
does not establish general TOCTOU safety, cross-process state locking or
recovery parity.
