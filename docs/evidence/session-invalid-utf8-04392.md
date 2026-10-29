# Invalid UTF-8 session filename differential

Run with the pinned Mojo 1.2.0 build and verified Linux oracles:

```sh
python3 scripts/ci/run-unittest.py test_session_invalid_utf8_04392.py
```

The real-process test makes a fresh synthetic home and workspace for each
binary. Each home contains the same valid session fixture and an empty session
entry named with raw bytes `b"\x80.jsonl"`. The test runs under `bwrap` with a
cleared environment, private `HOME`, and an unshared network namespace. It uses
no credentials or provider traffic.

| Binary | SHA-256 | Result |
| --- | --- | --- |
| Prodex 0.165.1 | `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` | Exit 0; lists the valid fixture session and ignores the invalid name. |
| Prodex 0.439.2 | `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e` | Exit 0; lists the valid fixture session and ignores the invalid name. |
| Modex (`build/modex`) | `3d11224d63818078f00d714e7b7814da6b39a8d454ae00f341a770bd729f76d1` | Exit 132; aborts with `String span starts on0 which is not a codepoint boundary.` |

The focused unittest completed with `Ran 1 test ... OK`. It passes only when
the expected difference remains observable; this is a recorded parity gap, not
a parity pass. A filename beginning with byte `0xff` did not reproduce this
failure on the same build; byte `0x80` is the reproducible case.

## Source trace and limitation

Modex enumerates session files in `src/modex/sessions.mojo` through
`std.os.listdir`. In the pinned Mojo 1.2.0 source,
`std.os.listdir` returns `List[String]`; its Linux iterator calls `readdir`,
wraps each raw `d_name` with `StringSlice(unsafe_from_utf8=...)`, then appends a
`String` (`std/os/os.mojo:135-163,216-234`). The assertion is reported from
`std/collections/string/string_span.mojo:397` while Modex filters the name.
`std.pathlib.Path.listdir` delegates to the same function.

The standard library source contains no separate public byte-preserving
directory iterator. Its only `opendir`/`readdir` implementation is the
`std.os` iterator; `std.sys._libc` has no directory-enumeration binding. Reading
raw names in Modex would require a new native binding, which this project
forbids. Leave this Linux filesystem edge as an explicit gap until an allowed
stdlib API can preserve arbitrary filename bytes.
