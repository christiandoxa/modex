# Prodex 0.166.2 session-list state recovery

The active reference is the checksum-pinned Prodex 0.166.2 Linux x86-64
binary, SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`, from
source commit `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`.

`tests/test_session_state_recovery_01662.py` compares `session list --json
--profile main` with a synthetic valid session, an owner-only `state.json`
containing invalid JSON, and a valid owner-only `state.json.last-good` that
binds the session to `main`. Prodex exits successfully, returns the bound
session, restores the primary state from the backup, and normalizes both state
files. Modex exits 1 with `locked state loading and recovery are not
implemented`; it leaves both fixture files byte-for-byte unchanged. This is a
reproducible mismatch capture, not a parity pass.

Modex retains the fail-closed guard because this recovery reads profile
ownership and repairs persistent state. Prodex uses an exclusive `flock` on
`state.json.lock` before recovery. Mojo 1.2.0 does not expose a compatible
standard-library lock API; its POSIX record-lock wrapper does not interoperate
with Linux `flock`. Reading the backup without the matching lock could race a
lifecycle update and select stale ownership. Keep the guard until an
interoperable lock and recovery path can be implemented within the project
constraints. Lock-interface details are in
`../baseline-0.166.0/lifecycle-lock-stdlib-gap.md`.

Verified on 2026-10-31 with:

```sh
python3 scripts/ci/run-unittest.py test_session_state_recovery_01662.py
```

The test is included in the active Fast and Full CI lanes. It uses isolated
temporary homes and synthetic profile state only; it does not inspect or
modify user data.
