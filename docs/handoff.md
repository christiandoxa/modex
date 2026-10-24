# Current work

The destination repository began empty. The frozen tag and official Linux
release checksum have been verified. Reference source and the oracle are kept
outside the Modex source and build graph, under `~/.cache/modex/`.

The current bootstrap implements product version output, including ignored
trailing arguments after exact leading `--version` and `-V` flags. Twelve
isolated official-release cases pass with no state mutations and the narrow
documented identity mapping. Evidence: `docs/evidence/version-arguments-tests.txt`.
A clean filesystem/network namespace contains only Modex and the
platform/official Mojo runtime libraries; version output works without Python,
Node, Rust, or Prodex. Native JSON decoding and development `session list` /
`session current` machine-output paths are connected to the production binary.
The inventory contains 60 coarse contracts and 360
platform obligations; 1 Linux obligation passes, and 0 complete cross-platform
contracts pass. Inventory expansion remains necessary; no parity percentage is
valid.

Validation: `make test` (4 Mojo unit programs, test-only JSON/Zstandard/text/log drivers, and 93
Python black-box/runtime tests PASS, including 500 deterministic generated
JSON values plus malformed UTF-8/syntax/boundary vectors and numeric/local
session time comparisons, including future recurring rules through 2100,
transition-second boundaries, and explicit/invalid POSIX TZ strings),
`python3 tests/probe_capabilities.py` (3 positive programs PASS,
4 expected public-API gaps reproduced). `python3 tests/session_mismatches.py`
retains 3 FAIL cases and 3 unapproved differences for baseline panics.
Actual compiler diagnostics and commands are in `docs/evidence/capabilities/`.

The frozen help inventory now contains 35 routes and 326 option mentions,
including four hidden commands and both Super exposure/short aliases. Capture
command: `python3 tests/capture_cli.py`; all help routes exit 0 with empty stderr
and no state mutations. Help mentions still require source validation for
registered flags, hidden flags, defaults, precedence and passthrough.
Root `--help`, `-h` and bare `help` are now connected, including ignored
trailing arguments after help flags and custom executable names in Usage.
Their release comparisons check isolated homes and no created paths.
Other command help routes remain unfinished. Evidence:
`docs/evidence/unicode-width-tests.txt` and `tests/test_root_help.py`.

Detached `log last` now selects transcript, upstream-payload and token-usage
snapshots through native Mojo. The connected path covers context/message/tool/
protocol/status projections, credential redaction, bounded file tails,
millisecond session ordering and runtime path ties, strict base64 and numeric
fields, binary labels and bounded in-memory Zstandard payload decoding.
Plain snapshots render metadata, source labels, wrapped payloads and throughput;
JSON preserves envelope order and null request IDs. Log help and diagnostics
have 75 frozen-release argv comparisons, including short-help clusters and
error precedence. Shared JSON serialization sorts object keys and retains the
last duplicate value. No external implementation dependency was added.
Evidence: `docs/evidence/log-tests.txt`, `docs/evidence/log-link.txt` and the
eight `tests/test_log*.py` modules.

This remains an incomplete log contract. Policy-backed directories are
rejected unless `PRODEX_RUNTIME_LOG_DIR` supplies the location; live stream,
upstream-follow and terminal views remain unimplemented. Binary-text
classification currently uses common Unicode ranges and loses a Deseret
tool-output event. Existing insecure application roots still fail instead of
receiving baseline permission repair. Timestamp layouts and remaining log
combinations need further verification. Three Unicode-whitespace inputs expose
credentials in the release while Modex masks them; a fourth preserves spacing
differently. These four unapproved safe differences and two concrete failures
are retained by `python3 tests/capture_log_mismatches.py` in
`docs/evidence/log-mismatches.json`; none is parity PASS.

Session help and argument diagnostics now match 271 captured official-release
cases and 152 seeded generated comparisons. Coverage includes suggestions,
short-flag clusters, literal `--` boundaries, nested/root help routing,
ordered multi-flag conflicts, missing/duplicate/value-error precedence,
stdout/stderr and exit codes. Captured help/error paths also check that no
paths are created. Valid-command startup mutations remain outside the output
claims. Suggestion scoring follows the frozen clap_builder 4.6.7/strsim 0.11.1
Jaro behavior, implemented independently in Mojo. Parsing preserves a raw cwd;
execution resolves it, so help/error paths do not need cwd discovery.
Reproduce with `python3 tests/capture_session_cli.py` and
`python3 -m unittest discover -s tests -p test_session_cli.py`.
Evidence: `docs/evidence/baseline/session-cli.json` and
`docs/evidence/session-arguments-tests.txt`. Other commands and remaining CLI
combinations are unverified; valid resume execution remains unfinished.

Detached plain session text output now matches 71 official-release scenarios:
table columns, truncation and full-ID details, optional cells, multiple rows,
list/current filters, empty panels, long-token wrapping, widths 1 through 300,
and valid/invalid `PRODEX_TERM_COLUMNS` overrides. `COLUMNS` is ignored as in
the release. Tests compare raw bytes in identical disposable homes.
The initial slice covers printable ASCII; terminal dimensions and the
interactive view remain unimplemented. Evidence:
`docs/evidence/session-text-tests.txt`. The text mismatch reproducer now records
matching output separately from the remaining startup side-effect differences.

Plain rendering now uses Unicode 17 character and string-width rules,
including other scripts, emoji presentation/modifiers/ZWJ sequences, script
ligatures and control cells. Independent data checks cover all 1,112,064
Unicode scalars and the auxiliary property tables. Production comparisons
cover 3,026 official emoji sequences, 960 seeded mixed-script strings,
property-range boundaries, truncation, padding, full IDs and path wrapping.
The release's scalar cuts and scalar wrapping are preserved even when they
split an emoji sequence; cell measurement uses combined string widths.
Width checks now walk UTF-8 slices with constant auxiliary state. Tifinagh
joiner parity and backward Kirat folding avoid scalar and decomposition lists.
Linux RSS checks cover ASCII, mixed Unicode, Tifinagh, Kirat and emoji tags;
fresh harnesses prevent inherited Python memory from masking regressions.
The old implementation fails the same memory regression check. Output also
matches the oracle for a 1,100,000-byte mixed title, the exact 64 MiB JSONL
line boundary and its one-byte overflow, and all 3,905 Kirat vowel sequences
of lengths one through five. RSS observations support the source-level bound;
they do not establish a whole-command or cross-platform memory guarantee.
Evidence: `docs/evidence/unicode-width-tests.txt`; the earlier 239 scenarios
are retained in `docs/evidence/session-unicode-tests.txt`. The bounded-width
checks and before/after samples are in `docs/evidence/text-memory-tests.txt`
and `docs/evidence/text-memory.json`.

The release panics with exit 101 when U+17D8 (a three-cell Khmer glyph) reaches
its scalar truncation or wrapping planner, which rejects widths above two.
Modex renders these inputs. Exact inputs and both observations are retained
by `tests/session_mismatches.py` as two unapproved differences, not parity.

Session inspection now decodes dictionary-free Zstandard rollouts in native
Mojo, including raw/RLE/compressed blocks, FSE/Huffman tables and reuse,
repeat offsets, checksums, concatenated/skippable frames and bounded streaming.
Independent vectors come from Python's test-only standard `compression.zstd`;
the production binary never calls it. Full command checks cover list/current,
filters and machine output, records crossing frames/blocks, decoded line-size
limits and 25 frozen-release diagnostic cases. Error/read ordering around
8192 decoded bytes is reproduced, including early rejection of non-session
metadata. Evidence: `docs/evidence/zstd-tests.txt` and
`docs/evidence/baseline/session-zstd-errors.json`.

One noncanonical Huffman input is accepted by the release despite unused
entropy bits prohibited by RFC 8878 section 4.2.2. Modex rejects it before the
release's subsequent UTF-8 error. The exact synthetic input and both observed
errors are retained as an unapproved difference. A second retained difference
is an empty frame declaring 134217729 decoded bytes: the release accepts it,
while Modex rejects the oversized window. No parity PASS is claimed.

The active release staging/smoke path imports the JavaScript gateway SDK.
Its module-import compatibility is BLOCKED by the Mojo-only/no-adapter policy,
not removed from scope. `docs/packaging-audit.json` preserves conflicting
source/publishing/README evidence.

TZif v1-v3 leap-second tables now participate in timezone transition lookup
without changing the POSIX seconds displayed in session timestamps. There are
324 official-release comparisons covering positive/negative/mixed corrections,
exact transition seconds, 64-bit times, file-mtime fallback, future rules,
invalid records, indicator pairs and inconsistent footers. Invalid files and
unsupported TZif v4 fall back to UTC as in the frozen reader. Native tests
also cover correction overflow. The fixtures are synthetic; this host has no
installed `right/` leap-zone directory. Evidence:
`docs/evidence/leap-timezone-tests.txt` and `tests/test_timezone_files.py`.

Next work: replace common-range log binary-text classification with complete
Unicode alphanumeric data, implement native TOML policy loading and runtime
log-directory resolution, then complete log live views and remaining commands.
Stateful paths still fail explicitly. Future recurring timezone rules and
POSIX TZ strings are implemented; their earlier evidence is
`docs/evidence/recurring-time-tests.txt`.
Startup effects still differ. Details and the baseline
panic are in `docs/known-gaps.md`; no session contract is PASS.

The pinned stdlib's public and bundled internal source has now been inspected
for file/process/terminal prerequisites. It supplies basic pipes and direct
child management, but no spawn file-actions/attributes, separate child
environment, terminal raw mode/size, permission repair, durable sync or atomic
rename wrapper. The private fcntl ABI experiment is excluded from product
evidence and does not establish baseline-compatible locking. Details:
`docs/evidence/stdlib-internals-audit.md`. No dependency exception was added.

Use GPT-6 Luna agents in parallel for independent implementation, validation
and review; file ownership must stay disjoint. This user preference is also
recorded in `AGENTS.md`.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.
