# Session profile filtering

## Production trace

The frozen 0.165.1 `session` command calls
`load_session_reports(..., profile, ...)`. The report collector reads each
session, looks up `state.session_profile_bindings[report.id]`, attaches its
`profile_name`, then applies the profile filter.

State loading calls `AppState::load`, which first reads a valid primary state
file. If that read or parse fails, `load_json_file_with_backup` acquires
`state.json.lock`, reloads under that lock, and may restore the primary from
the `.last-good` file. Modex currently rejects state files because its pinned
Mojo stdlib does not provide the interprocess file lock and recovery behavior
needed to read or repair this state safely.

## Reproduction

`tests/test_session_report_01651.py::test_profile_filter_remains_fail_closed_while_state_recovery_is_unavailable`
runs both production executables in separate bubblewrap sandboxes with a
synthetic session and valid profile binding. It uses no credentials.

- 0.165.1 exits 0 and returns the session with `"profile": "main"`.
- Modex exits 1 with `Error: locked state loading and recovery are not implemented`.
- Both leave the synthetic `state.json` bytes unchanged.
- The reference creates `profile-lifecycle.json.lock`,
  `runtime-housekeeping.last-run`, `runtime-housekeeping.lock`,
  `state.json.lock` and `update-check.lock`. Modex creates no files. These are
  observed startup side effects; neither executable changes session data.

The mismatch remains open. Do not count this fixture as parity. Implementing
the path requires compatible bounded regular-file reads, interprocess locking,
backup recovery and atomic repair. Keep the state path fail-closed until Mojo
1.2 stdlib support can meet those requirements without a native binding. All
six release targets remain in the denominator.
