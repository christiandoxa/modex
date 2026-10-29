# Session profile filtering

## Production trace

The frozen 0.165.1 `session` command calls
`load_session_reports(..., profile, ...)`. The report collector reads each
session, looks up `state.session_profile_bindings[report.id]`, attaches its
`profile_name`, then applies the profile filter.

State loading calls `AppState::load`, which first reads a valid primary state
file. If that read or parse fails, `load_json_file_with_backup` acquires
`state.json.lock`, reloads under that lock, and may restore the primary from
the `.last-good` file. Modex now reads a valid, private regular primary for
session binding and filtering without repair. It still fails closed if the
primary is invalid or unsafe because matching the release's interprocess lock
and backup recovery behavior is not implemented.

The release's `crates/prodex-app/src/runtime_store/io.rs` reader rejects
symlinks and non-regular files, bounds the file size, and verifies the opened
file still matches the named path. It does not reject a readable state file by
its group/other permission bits. The process controls confirm mode 0644 is
accepted by 0.165.1 when the `.prodex` parent remains mode 0700.

A process control with an owner-owned, single-linked `state.json` at mode 0644
inside the verified mode-0700 `.prodex` directory now returns the same bound
profile report as 0.165.1 without changing the file. Modex still rejects
group/other-writable state and group/other-readable state with a hard-link
alias. Shared write bits stay fail-closed by policy; a readable alias outside
the owner-only app directory would bypass the directory's access control.

## Reproduction

`tests/test_session_report_01651.py` and
`tests/test_session_profile_04392.py` run both production executables in
separate bubblewrap sandboxes with synthetic sessions and profile bindings.
They use no credentials. The active suite also checks 0.439.2, a 16,384-entry
response map, the 2,048-binding cutoff, duplicate keys and high-volume report
lookups.

- 0.165.1 exits 0 and returns the session with `"profile": "main"`.
- For a valid primary, Modex exits 0 with the same profile output and leaves
  the synthetic `state.json` bytes unchanged.
- For an invalid primary with a valid `.last-good`, Prodex recovers the
  primary; Modex exits 1 with `Error: locked state loading and recovery are
  not implemented` and leaves both files unchanged.
- The reference creates `profile-lifecycle.json.lock`,
  `runtime-housekeeping.last-run`, `runtime-housekeeping.lock`,
  `state.json.lock` and `update-check.lock`. Modex creates no files. These are
  observed startup side effects; neither executable changes session data.

Valid-primary profile binding and filtering match the two tested release
binaries for the checked mode and link cases. Recovery and security differences
remain open: Modex rejects group/other-writable state and group/other-readable
state with a hard-link alias, treats dangling symlink primaries as absent, and
does not recover malformed primary state from `.last-good`. The primary-file
metadata checks are observations, not
interprocess locking or proof of race freedom. Do not count these selected
fixtures as full parity. All six release targets remain in the denominator.

## Read-only state permissions

The 0.165.1 process accepts an owner-owned `state.json` at mode 0644 when it is
single-linked inside a mode-0700 `.prodex` directory. Modex now reads the same
binding and returns the same session report without changing the state file.
It retains owner, regular-file, size, descriptor identity, stable-mode, and
link-count checks; group/other-writable files and group/other-readable files
with hard-link aliases remain fail-closed. Shared write bits are denied by
policy, and a readable hard-link alias could expose the inode outside the
protected app directory.

On 2026-10-29, five synthetic session-state test methods passed against both
checksum-verified release binaries: readable single-link state, writable mode
rejection, readable hard-link rejection, live/dangling symlink and private
hardlink controls, and atomic replacement stress. The separate unsafe app-root
guard passed against 0.439.2.
