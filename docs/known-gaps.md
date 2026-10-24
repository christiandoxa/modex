# Verified gaps

The goal remains complete behavioral and feature parity with all six Prodex
0.439.0 release targets. Current tests establish narrow local facts, not that
goal. `docs/parity.json` records the initial inventory and platform obligations.

Session machine-output tests cover populated and archived plain JSON/JSONL,
metadata precedence, timestamp ordering, Unicode whitespace and query behavior,
parent filtering, limits, exact JSON formatting, ID/resume command output, and
symlink exclusion. The product rejects existing state rather than reading
without the required lock/recovery. Remaining unverified Unicode combinations,
interactive terminal output, profile bindings and startup lifecycle/housekeeping
effects remain unfinished.

Detached plain text output matches 71 printable-ASCII scenarios, including
tables, empty panels, wrapping, width overrides and exact trailing whitespace.
`PRODEX_TERM_COLUMNS` and the 110-column fallback are implemented; `/dev/tty`
dimension discovery is not. Widths above `Int.MAX` fail explicitly.
See `docs/evidence/session-text-tests.txt`.

The renderer now uses [Unicode 17 width data](https://www.unicode.org/Public/17.0.0/ucd/EastAsianWidth.txt)
and the frozen width rules. Tests check all 1,112,064 Unicode scalars and the
auxiliary property tables, plus actual production output for 3,026 official
emoji sequences, 960 generated mixed-script strings, property boundaries and
wrapped paths. Scalar clipping and wrapping match the release, including cuts
inside emoji. All 3,905 Kirat vowel sequences of lengths one through five
also match production oracle output. Other sequence combinations remain
unverified. Width measurement uses constant auxiliary state over UTF-8
slices. Linux RSS samples cover five large-input patterns, and production
checks cover a 1,100,000-byte mixed title and the exact 64 MiB line boundary
plus one-byte overflow. Whole-command peak memory and other platforms remain
unverified. Evidence: `docs/evidence/unicode-width-tests.txt`,
`docs/evidence/text-memory-tests.txt` and `docs/evidence/text-memory.json`.

The release's scalar planners reject U+17D8's three-cell width and panic when
truncating or wrapping it. Modex renders these cases. Proposed handling:
retain rendering and resolve the compatibility difference separately. Both
exact reproductions are in `docs/evidence/session-mismatches.json`, marked
`UNAPPROVED_SAFE_DIFFERENCE`; they are not parity PASS cases.

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
Root `--help`, `-h`, bare `help`, ignored help-flag tails and custom executable
Usage now match isolated release checks. Remaining help routes and command
execution are unfinished. Evidence: `docs/evidence/unicode-width-tests.txt`.

Detached `log last` is connected for transcript/upstream/token snapshots with
JSON and plain output. The suite covers 75 log CLI argv cases, bounded tails,
mtime ties, numeric validation, strict base64, redaction, context/tool/protocol
events, payload rendering and 128 KiB decompressed-payload boundaries.
File-based upstream following is connected for detached JSON/plain output,
including bounded incremental reads, partial lines, rotation/truncation and
two-second file discovery. Process tests cover more than 32 runtime files and
`RLIMIT_NOFILE=48`. The general `stream` mode, live broker/direct sources and
terminal views remain unfinished. Upstream following fails explicitly when a
live-source registry or unsupported terminal path is present. Further follow
failure/race cases and non-host platforms remain unverified. Evidence:
`docs/evidence/upstream-follow-tests.txt`.
Native policy loading and directory resolution now match tested release paths,
schema errors and fallback behavior, including 712 wrapped corpus inputs.
Binary-text classification uses exact Unicode 17 Alphabetic/Number data;
the retained U+10400 Deseret fixture now matches. Existing root permission
repair is still unsupported. Log timestamps now have 732 exact release
comparisons covering custom/RFC formats, Unicode whitespace, signed years,
fractional and leap seconds, range boundaries, DST and historical offset
rounding. Unexercised timestamp/projection combinations and non-host platforms
remain unverified. Evidence: `docs/evidence/log-timestamps-tests.txt`.
Evidence: `docs/evidence/log-tests.txt`, `docs/evidence/log-link.txt` and
`docs/evidence/policy-unicode-tests.txt`. General policy application beyond
log-directory selection is unfinished; parser resource/recursion behavior
beyond the tested 128-level limit remains unverified.

Three frozen-release log fixtures expose a quoted credential beside Unicode
whitespace. Modex masks the complete value and preserves the original spacing;
a fourth fixture differs only in retained spacing. Proposed handling: retain
complete masking and whitespace preservation, with compatibility approval
still pending. These are four `UNAPPROVED_SAFE_DIFFERENCE` observations, not
parity passes. The actual outputs and two resolved regression cases are retained
in `docs/evidence/log-mismatches.json`; reproduce with
`python3 tests/capture_log_mismatches.py`.

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
The stronger bundled-source audit is in
`docs/evidence/stdlib-internals-audit.md`; its limited positive stdout-capture
probe does not establish redirected process supervision or raw terminal I/O.

The baseline release's npm smoke path actively stages and imports a JavaScript
gateway SDK, despite the checked-in package being private and the exact version
currently missing from npm. Native JavaScript import compatibility conflicts
with the Mojo-only/no-adapter policy. That obligation remains BLOCKED; see
`docs/packaging-audit.json`. Its historical admin endpoint documentation does
not by itself establish active gateway server routes.
