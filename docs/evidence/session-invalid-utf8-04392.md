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
file and directory.

All processes run under `bwrap` with cleared environments, private `HOME`, and
an unshared network namespace. The harness uses no credentials or provider
traffic.

| Binary | SHA-256 | Result |
| --- | --- | --- |
| Prodex 0.165.1 | `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` | Invalid leaf names are ignored; valid sessions under invalid directory names are listed. |
| Prodex 0.439.2 | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` | Same JSON, path display, ordering, replacement-character queries, and symlink exclusion as 0.165.1. |
| Modex (isolated worker build) | `db0693d99d8da2bf519b2bdecbb7c03af6d2157684796a1cde30e47a3f474679` | Matches both releases for these session-entry cases. |

After normalizing only each temporary fixture root, JSON output matches both
releases. Invalid path bytes display as U+FFFD, matching Rust `Path::display()`.
For reports tied by timestamp and ID, paths under `0xff 0x61` sort before
`0x80 0x7a` after replacement; both releases and Modex use that order. Query
`�` returns the same four session IDs, and query `�(` returns only the session
under that directory. Both symlink entries are excluded by the existing
`lstat` checks. The focused runner passed 2 tests.

Invalid names in `PRODEX_HOME` do not bypass the existing lock and journal
guards. Valid `state.json.lock` and `profile-lifecycle-journal` still fail
closed when an unrelated invalid name is present. One intentional behavior
difference remains: both frozen releases list sessions when the app root
contains raw name `state.json.\x80.tmp`, while Modex rejects it as an atomic
state temporary file. Modex preserves that guard by checking the ASCII prefix
and suffix after lossy conversion. This fail-closed difference is not a parity
pass.

## Implementation trace

Mojo 1.2.0 `std.os.listdir` returns `List[String]` and builds each name from
raw `readdir().d_name` bytes through `StringSlice(unsafe_from_utf8=...)`
(`std/os/os.mojo:135-163,216-234`). There is no separate public byte-preserving
directory API. Modex checks each entry's type first, validates regular-file
names with `String(from_utf8=name.as_bytes())` inside `try`/`except`, and skips
invalid file names before calling `endswith`. Directories recurse with their
raw names. Path joining checks the final slash bytewise, so a directory name
that ends in an invalid continuation byte remains traversable. File I/O keeps
the raw path; report paths use `String(from_utf8_lossy=path.as_bytes())`,
matching the tested `Path::display()` output and path-query behavior. No native
binding or dependency was added.
