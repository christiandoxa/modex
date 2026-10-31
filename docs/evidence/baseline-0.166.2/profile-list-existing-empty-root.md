# Existing empty profile root

The active reference is Prodex 0.166.2 at source commit
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. The isolated Linux x86-64
oracle has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

`tests/test_profile_list_existing_empty_root_01662.py` creates an empty
`home/.prodex` directory in separate synthetic homes and runs `profile list`
through Bubblewrap with the checksum-pinned oracle and production Modex binary.
Prodex exits 0 and prints the empty-profile panel. It creates
`profile-lifecycle.json.lock` and `update-check.lock`; asynchronous runtime
housekeeping may also create `runtime-housekeeping.lock` and
`runtime-housekeeping.last-run`. Modex exits 1 with its unsupported-command
error and leaves the preexisting directory untouched.

This is a captured mismatch, not profile-list parity. In the pinned source,
`crates/prodex-app/src/profile_commands/manage.rs::handle_list_profiles`
acquires the global profile lifecycle lock, loads state with recovery enabled,
and repairs a missing active profile before printing the empty panel. Startup
also checks update status and schedules housekeeping. The pinned source uses
`File::lock_exclusive`; the tested Linux implementation uses `flock`, and its
Windows implementation uses `LockFileEx`. Mojo 1.2.0 exposes no compatible
standard-library lock API. The existing-root guard therefore remains in place
until a safe lock and recovery path can be implemented within the project
constraints. See
`../baseline-0.166.0/lifecycle-lock-stdlib-gap.md` for the lock-family
characterization.

Verified on 2026-10-31 with:

```sh
make build
python3 scripts/ci/run-unittest.py test_profile_list_existing_empty_root_01662.py
```

The fixture uses no credentials, provider traffic, or external network access.
This Linux x86-64 observation does not qualify the other release targets.
