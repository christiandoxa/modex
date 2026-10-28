# Session state-filename guard against Prodex 0.439.2

The pinned 0.439.2 session-list path loads application state from `state.json`
and its `state.json.last-good` recovery file, using `state.json.lock`; atomic
writes use a `state.json.*.tmp` sibling. Profile lifecycle and import journals
also require recovery semantics. Modex does not yet implement that locking or
recovery and continues to reject these names before reading sessions.

The earlier guard rejected every name starting with `state.json`, including
unrelated user files. In isolated homes, the old Modex build rejected
`state.json.backup` and `state.json.scratch`; the checksum-verified 0.439.2 and
separately pinned 0.439.5 releases listed the session and preserved the files.
The corrected production CLI matches their full normalized JSON output for
those names and `state.last-good.json`, preserving each file. A held synthetic
`state.json.lock`, the real state and last-good names, pending atomic temp and
both profile journal directories still fail closed and retain their contents.

`python3 scripts/ci/run-unittest.py test_session_state_backup_04395.py
test_sessions.py test_session_04395_slice.py` passed 17 tests with synthetic
fixtures and isolated homes. No real credentials, account login, or paid traffic
were used. This does not establish state recovery, race-free concurrent access,
profile ownership, or full session parity. No contract status is promoted.
