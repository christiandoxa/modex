# Profile state access against Prodex 0.165.1

The verified Prodex 0.165.1 Linux binary and source are pinned at
`10ae15b5d1806302b60f051e4e6fec788044f4c2`. Prodex 0.439.2 is the active
comparison release. Both release binaries were checked by SHA-256 in
`tests/test_profile_state_01651.py`.

`profile list` is not a lock-free read in either release. In the 0.165.1
source, `crates/prodex-app/src/profile_commands/manage.rs::handle_list_profiles`
acquires the profile-lifecycle lock, loads and recovers profile state, and
repairs a missing active profile. The loader at
`crates/prodex-app/src/profile_commands/import_export/import/lifecycle_support.rs`
calls `AppState::load_and_repair`; state repair and save use the separate
`state.json.lock` in `crates/prodex-app/src/runtime_store/io.rs`. The lifecycle
lock is `profile-lifecycle.json.lock`. The profile read may therefore rewrite
state, and a valid-looking file can still be in use by another Prodex process.

The pinned Mojo 1.2.0 (2016d0cd) audit records that `std.os` exposes no
`flock`, `fsync`, `chmod`/`fchmod`, or atomic rename/replace operation. The
internal `fcntl` wrapper does not provide a supported file-lock protocol.
The compile probe and source audit are preserved in
`docs/evidence/capabilities/run.json` and
`docs/evidence/stdlib-internals-audit.md`. A directory or marker-file lock
would not coordinate with the release's `flock` users. Plain reads would race
with writes or recovery, and plain writes cannot preserve the release's
atomic-recovery contract.

The new real-process test uses owner-only temporary HOME and workspace paths,
synthetic profile state, and a synthetic auth marker. With an active profile,
both verified releases list it without exposing the marker, preserve the
primary state and auth bytes, and create these persistent files:

```text
home/.prodex/profile-lifecycle.json.lock
home/.prodex/runtime-housekeeping.last-run
home/.prodex/runtime-housekeeping.lock
home/.prodex/state.json.lock
home/.prodex/update-check.lock
```

When `active_profile` is absent, both releases repair it to `main`; Modex
returns its existing unsupported-command error before reading or changing the
synthetic state. Modex creates no lock files and does not expose the auth
marker. This reproduces the stateful mismatch; it does not count as
profile-list parity. The same tests also compare stateless profile help and
parser routes against 0.165.1 and verify that they create no files.

Validation on Linux x86-64 with Mojo 1.2.0:

```text
make build BUILD_DIR=/tmp/modex-profile-state-build
MODEX_BINARY=/tmp/modex-profile-state-build/modex PYTHONPATH=tests \
  python3 -m unittest test_profile_state_01651 -v
```

All three focused process tests pass. Profile-state listing and mutations remain
unsupported until compatible locking, permission, atomic replacement, and
recovery primitives are available in the permitted standard library. No
credentials, provider traffic, account login, native bindings, or product
dependencies were used. The existing 12-method 0.439.2 profile CLI suite also
passes. The production import audit passes for all 71 Mojo files; the test
census passes with 50 native test sources and 141 Python modules.
