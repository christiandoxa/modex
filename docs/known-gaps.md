# Verified gaps

The goal remains complete behavioral and feature parity with all six Prodex
0.439.0 release targets. Current tests establish narrow local facts, not that
goal. `docs/parity.json` records the initial inventory and platform obligations.

Session machine-output tests cover populated and archived plain JSON/JSONL,
metadata precedence, timestamp ordering, Unicode whitespace and query behavior,
parent filtering, limits, exact JSON formatting, ID/resume command output, and
symlink exclusion. The product rejects existing state rather than reading
without the required lock/recovery. Remaining Unicode/control text output,
interactive terminal output, profile bindings and startup lifecycle/housekeeping
effects remain unfinished.

Detached plain text output matches 71 printable-ASCII scenarios, including
tables, empty panels, wrapping, width overrides and exact trailing whitespace.
`PRODEX_TERM_COLUMNS` and the 110-column fallback are implemented; `/dev/tty`
dimension discovery is not. Widths above `Int.MAX` fail explicitly.
See `docs/evidence/session-text-tests.txt`.

The renderer also supports tested Latin, Greek, Cyrillic, CJK, kana and Hangul
ranges plus combining accents and soft hyphens. It measures cells rather than
UTF-8 bytes and preserves codepoint boundaries. Wide ranges follow the
[Unicode 16 width data](https://www.unicode.org/Public/16.0.0/ucd/EastAsianWidth.txt);
zero-width behavior is checked against the release. The 239 current raw-output
scenarios cover these ranges, but other scripts, emoji sequences and remaining
control cells still fail explicitly. Full Unicode rendering remains unfinished.
Evidence: `docs/evidence/session-unicode-tests.txt`.

Dictionary-free compressed rollouts now pass native decoder interoperability
and production-command comparisons. Coverage includes entropy table reuse,
repeat offsets, frame checksums, concatenated/skippable frames, line boundaries
and the decoded 64 MiB line limit. The implementation uses a 128 MiB window
bound, matching the tested release boundary. Compression encoding and stateful
metadata repair remain unfinished. Evidence: `docs/evidence/zstd-tests.txt`.

A retained synthetic Huffman mutation has unused bits after its required
symbols. [RFC 8878 section 4.2.2](https://www.rfc-editor.org/rfc/rfc8878.html#section-4.2.2)
requires exact bit consumption. The frozen release accepts the compressed
stream and later reports invalid UTF-8; Modex reports compressed-data
corruption first. Proposed handling: retain exact-consumption validation and
approve the difference separately. This remains an unapproved difference,
not parity. The binary reproducer and both errors are in
`docs/evidence/baseline/session-zstd-errors.json`.

The release also accepts an empty frame whose declared decoded size is
134217729 bytes. Modex rejects its oversized window. This malformed-frame
difference is retained beside the Huffman case, with the exact input bytes;
keeping size/window validation is proposed and remains unapproved.

Session help and argument-error output match 271 captured frozen-release
cases and 152 seeded generated comparisons, including suggestions, short-flag
clusters, literal boundaries, help routing and ordered conflicts. This does
not establish complete CLI coverage. Other commands and remaining combinations
are unverified. Valid session resume execution still fails explicitly as
unimplemented. Valid-command startup mutations are outside these output
claims. Evidence: `docs/evidence/session-arguments-tests.txt`.

Numeric and file-modification timestamps now match the release in UTC,
Asia/Jakarta, America/New_York and Europe/London for the tested dates, including
daylight offsets, negative epochs, expanded years and Chrono's range limits.
The Mojo implementation parses OS TZif files using standard file APIs.
References: [TZif format](https://www.rfc-editor.org/rfc/rfc9636.html) and
[Chrono 0.4.44 date limits](https://docs.rs/chrono/0.4.44/chrono/naive/struct.NaiveDate.html).
Recurring TZif footer rules now handle future dates, northern/southern seasons,
half-hour daylight changes, Julian/ordinal/month-week dates and signed extended
transition times. Explicit POSIX TZ strings use the release's narrower syntax;
invalid values fall back to UTC as observed in the official artifact. Sources:
[POSIX TZ grammar](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html)
and [glibc timezone documentation](https://sourceware.org/glibc/manual/latest/html_node/Proleptic-TZ.html).
The current differential suite checks dates through 2100 and exact transition
seconds in six named zones.

Leap-second TZif v1-v3 files now pass 324 additional release comparisons using
synthetic fixtures. They cover positive/negative corrections, exact transition
seconds, 64-bit timestamps, file-mtime fallback and future rules. Invalid
records, inconsistent footers and unsupported v4 files fall back to UTC. The
frozen reader's permissive indicator handling is reproduced. Other timezone
file edge cases remain unverified, and this host has no installed `right/`
leap-zone directory. Evidence: `docs/evidence/leap-timezone-tests.txt`.

`python3 tests/session_mismatches.py` records both executables' output, exit
status and new files. The output-focused tests explicitly exclude those
side-effect failures from their claims. No session contract is PASS.

The official baseline panics with exit 101 when a valid JSONL session contains
a subsequent valid non-object JSON value such as `[]` or `null`.
`crates/prodex-session-store/src/report.rs::apply_session_value` calls an
object-only Mojo planner with `expect`. Modex safely ignores those follow-up
values. This is an unapproved safe behavioral difference, preserved in mismatch
evidence, and not counted as parity. Proposed resolution: approve the safe
behavior and separately fix the baseline; neither action has been assumed.

Platform and foundation gaps are in `docs/capabilities.json`. No TLS,
cryptography, native Windows, Intel macOS, process-tree, locking, or clean
distribution claim is implied by the current Linux probes.

The baseline release's npm smoke path actively stages and imports a JavaScript
gateway SDK, despite the checked-in package being private and the exact version
currently missing from npm. Native JavaScript import compatibility conflicts
with the Mojo-only/no-adapter policy. That obligation remains BLOCKED; see
`docs/packaging-audit.json`. Its historical admin endpoint documentation does
not by itself establish active gateway server routes.
