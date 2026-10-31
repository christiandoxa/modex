# Empty-profile `current` inspection slice

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The pinned Prodex 0.166.0 Linux x86-64 oracle prints the `Active Profile` panel
with `Status: No active profile.` when the configured app root does not exist.
The same process also creates `profile-lifecycle.json.lock` and
`update-check.lock`; runtime-housekeeping files may appear asynchronously.
Modex matches the observed panel, exit code, and stderr for that absent-root
case, but deliberately omits all of those state and lock side effects.

The source trace is `crates/prodex-app/src/profile_commands/manage.rs`,
`handle_current_profile`, at Prodex commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. It acquires the profile lifecycle
lock, loads and recovers state, repairs missing active references, and renders
the no-active status when the resulting state has no active profile. The
standalone lock-family constraint is recorded in
`lifecycle-lock-stdlib-gap.md`.

Modex reaches this result only when `app_root_is_absent()` verifies that the
final app-root entry is absent under an existing directory owned by the current
user with its owner-write bit set. An existing root or dangling root symlink
stays fail-closed, and the test also covers a non-owner-writable parent. The
guard checks owner and mode bits only; ACL denial and read-only mounts can still
make the baseline fail where Modex renders the empty-state panel. Those cases
are not tested here.

`tests/test_current_empty_profile_01660.py` pins the oracle digest, runs both
executables with synthetic HOME and an isolated Bubblewrap namespace, checks a
custom `argv0`, and records baseline and Modex filesystem effects. The existing
profile state fixture contains only synthetic text and remains byte-identical.
No credentials, provider calls, or user data are used.

This covers one absent-state branch of `current`; it does not implement profile
recovery, populated profile inspection, lifecycle locking, Guardian behavior,
or any of the other five release targets. It does not promote full
`PROFILE-CURRENT` parity.
