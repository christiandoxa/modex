# Invalid UTF-8 in JSON session files

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Prodex 0.166.0 at `9f69e1835808f478f59f12a3ae3fa88027d896a4` reads `.json`
session files through `crates/prodex-session-store/src/session_file.rs::read_session_file_to_string`.
`String::from_utf8` reports the file path, first invalid byte, and invalid
sequence length; a truncated final sequence reports its starting byte as
incomplete. The `.jsonl` reader uses `read_line` and reports
`stream did not contain valid UTF-8` without an offset.

Modex previously exposed Mojo's generic conversion error for `.json` files:
`Cannot construct a String from invalid UTF-8 data`. The production reader now
scans bytes only after Mojo rejects the file and reproduces the release
diagnostic. It does not include file contents or alter path validation. JSONL
diagnostics remain unchanged.
For a filename containing terminal controls, the release emits the controls
in the error path; Modex escapes them to avoid introducing a terminal-control
regression. This is an intentional security difference, not parity.

`tests/test_session_outputs_01660.py` compares the pinned oracle and production
Modex in private user, mount, and network namespaces. Fixtures use temporary
HOME/workspace directories and synthetic data. Cases cover invalid leading
bytes, malformed continuation bytes with one and two valid prefix bytes,
overlong E0, surrogate ED, out-of-range F4, truncated EOF sequences, and valid
Unicode. Each invalid case checks both `.json` and `.jsonl`; output checks
ensure file contents are not echoed and session files are unchanged.

The targeted active session output class passed 18 test methods on Linux
x86-64. This validates selected session output and invalid UTF-8 behavior only;
it does not establish full session or cross-platform parity.

Reproduce after building Modex with Mojo 1.2.0:

```sh
MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 -m unittest discover -s tests -p test_session_outputs_01660.py -v
```
