# Invalid UTF-8 session path differential

Run with the pinned Mojo 1.2.0 build and verified Linux oracles:

```sh
python3 scripts/ci/run-unittest.py test_session_invalid_utf8_04392.py
```

The real-process tests give each binary a fresh synthetic home and workspace.
Fixtures include invalid filename bytes `0x80`, `0xff`, and `0xc3 0x28` in the
session root, a dated session directory, and `archived_sessions`. They also put
valid sessions under recursive directory names `0x80 0x7a`, `0xff 0x61`, and
the nested components `0xc3 0x28` / `0xff`. The same-ID, same-time reports
exercise path-based ordering. A replacement-character query checks those paths.
The fixture also includes an invalid app-root entry and symlinks to a session
file and directory. Its app root also contains raw name
`state.json.\x80.tmp`, which must not be treated as an ASCII state temporary
file; the harness verifies the entry remains present after listing.

All processes run under `bwrap` with cleared environments, private `HOME`, and
an unshared network namespace. The harness uses no credentials or provider
traffic.

| Binary | SHA-256 | Result |
| --- | --- | --- |
| Prodex 0.165.1 | `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` | Invalid leaf names are ignored; valid sessions under invalid directory names are listed. |
| Prodex 0.439.2 | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` | Same JSON, path display, ordering, replacement-character queries, and symlink exclusion as 0.165.1. |
| Modex (isolated session build) | `1149129e4ef8c54bcf66f98c5d3da1827768aadb4ce826bbab336d03a2f0ab28` | Matches both releases, including the invalid state temporary name. |

After normalizing only each temporary fixture root, JSON output matches both
releases. Invalid path bytes display as U+FFFD, matching Rust `Path::display()`.
For reports tied by timestamp and ID, paths under `0xff 0x61` sort before
`0x80 0x7a` after replacement; both releases and Modex use that order. Query
`�` returns the same four session IDs, and query `�(` returns only the session
under that directory. Both symlink entries are excluded by the existing
`lstat` checks. The focused runner passed 2 tests.

Invalid names in `PRODEX_HOME` do not bypass the existing lock and journal
guards: valid `state.json.lock` and `profile-lifecycle-journal` still fail
closed when the raw invalid state temporary name is present. With only
`state.json.\x80.tmp`, all three binaries list the same sessions and leave the
entry untouched. The valid ASCII name `state.json.123.456.0.tmp` still
triggers Modex's fail-closed guard.

## Implementation trace

Mojo 1.2.0 `std.os.listdir` returns `List[String]` and builds each name from
raw `readdir().d_name` bytes through `StringSlice(unsafe_from_utf8=...)`
(`std/os/os.mojo:135-163,216-234`). There is no separate public byte-preserving
directory API. Both frozen source trees route `session list` through
`load_session_reports` in `crates/prodex-app/src/app_commands/session.rs`,
which loads `AppState` and collects reports from the shared Codex root. The
real-process controls establish that invalid app-root names are ignored.
Modex's state marker scan now validates each name with
`String(from_utf8=name.as_bytes())` and skips invalid names before comparing
ASCII lock, journal, and temporary-file names. This avoids matching a lossy
replacement character between `state.json.` and `.tmp`. Session-tree scanning
still validates regular-file names before `endswith`, traverses directories
with raw names, joins paths bytewise, and renders reports with
`String(from_utf8_lossy=path.as_bytes())`. No native binding or dependency was
added.

Validation on the isolated Linux x86-64 worktree: `rtk make build` passed;
`test_session_invalid_utf8_04392.py` passed 2 tests against both pinned
release binaries; `test_session_profile_04392.py` passed 12 tests;
`test_session_state_backup_04395.py` passed 2 guard tests; and the production
import audit passed for all 71 Mojo files. `git diff --check` passed. The full
repository suite and other release targets were not run.
