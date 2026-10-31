# Lifecycle lock interface gap

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

This is a Linux-only lock-family characterization for the pinned Prodex 0.166.0
reference at `9f69e1835808f478f59f12a3ae3fa88027d896a4`. It is not a Modex
parity claim.

In the pinned source, `crates/prodex-app/src/profile_commands/import_export/lifecycle.rs`
acquires the profile lifecycle lock through the runtime store using
`profile-lifecycle.json`. `crates/prodex-app/src/runtime_store/io.rs` derives
`profile-lifecycle.json.lock`, opens it with create/read/write and no truncate,
then calls `FileExt::lock_exclusive`. `crates/prodex-app/src/runtime_core_shared.rs`
keeps the open file in the RAII lock and unlocks it on drop. The pinned
`fs2` dependency is 0.4.3: its Unix implementation calls `flock(fd, LOCK_EX)`
(except Solaris, where it emulates that contract with `fcntl`); its Windows
implementation uses an exclusive `LockFileEx` range over the full file.

Mojo 1.2.0 (2016d0cd) exposes `std.sys._libc.fcntl` as a variadic wrapper whose
optional arguments are `Intable`. The full pinned standard-library source also
defines descriptor and status-flag commands, including `F_GETFD`, `F_SETFD`,
`F_GETFL`, and `F_SETFL`; it exposes no `flock` function, `F_SETLK`/`F_SETLKW`
or `LOCK_EX`/`LOCK_NB` constants, typed `struct flock` record, or `LockFileEx`
API. A hand-declared record and platform ABI constants would not be a typed
standard-library interface, and Linux POSIX record locks still do not
interoperate with `flock`.

Run the standalone synthetic check with:

```sh
python3 tests/manual_lifecycle_lock_interop_01660.py
```

The test starts a process holding exclusive `flock` on a temporary
`profile-lifecycle.json.lock`. A second nonblocking `flock` is blocked, while a
second nonblocking POSIX record lock (`fcntl.lockf`) succeeds on that same file.
The test uses only Python's standard library, has bounded readiness and child
process waits, isolated temporary `HOME` and `TMPDIR`, and cleans up the owner
even on failure. It runs only on Linux; it does not call Modex or Prodex and
characterizes the lock families on this host's local `/tmp` filesystem. It does
not qualify network filesystems or other release targets.

Observed on 2026-10-30: the manual test passed. The same-family exclusive
`flock` contender was blocked; the POSIX record-lock contender acquired the
file while the owner still held `flock`.

Therefore the exposed Mojo 1.2.0 API does not provide a safe interoperable
profile lifecycle lock on Linux. On Windows, the upstream lock uses
`LockFileEx`, which is also absent from the audited standard library. Keep
lifecycle operations fail-closed until Mojo provides a compatible whole-file
lock API or the project constraints change to permit the required native
bindings. This finding covers the lock prerequisite only, not lifecycle parity.
