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
`RLIMIT_NOFILE=48`. The general detached stream now follows both runtime and
session files with operational event projection and all per-record transcript
events. Its combined descriptor selection matches the release's exact 16/16
paths in a tied-mtime fixture under the same cap; path discovery and adjacent
transcript duplicate behavior are covered by actual process comparisons.
URL display and JSON number normalization have additional corpus coverage;
complete URL/parser equivalence is still unverified. Live broker/direct sources
and terminal views remain unfinished. When explicit runtime disk recording is
enabled, file following skips live registry discovery as in the release.
Otherwise a live-source registry still fails explicitly; unsupported terminal
paths also fail. Further follow
failure/race cases and non-host platforms remain unverified. Evidence:
`docs/evidence/upstream-follow-tests.txt`.

Live-source admission also requires the frozen registry store's exclusive
`.json.lock`, backup recovery and legacy-artifact handling before reading a
registry. The pinned stdlib exposes no compatible file-lock wrapper or the
durable replacement/permission operations required by recovery. Reading an
unlocked registry would weaken the storage contract, so it remains unsupported.
The reference process identity resolver also runs candidate executables with
`--version`; invoking Prodex from Modex is prohibited. SHA-present and
version-only identity cases still need a compliant admission design and exact
behavioral verification. Source: `runtime_broker/registry/store.rs`,
`runtime_store/io.rs`, `runtime_broker/registry/process.rs` and
`app_commands/log_live.rs` under the frozen `crates/prodex-app/src/`.

`tests/capture_log_live.py` characterizes the actual oracle with synthetic
loopback snapshots and validates the capability header, cursor advance/reset,
gap markers and rejected identities. All eight current Modex comparisons are
FAIL in `docs/evidence/log-live-mismatch.json`, including rejection cases where
Modex exits while the release keeps following. The harness uses isolated HOME,
working directories and ports in the host PID/network namespaces: its attempted
bubblewrap isolation could not inspect the host identity holder's executable.
This is limited test evidence, not clean-runtime or live-source parity.

Native SHA-256 and loopback HTTP foundations now have standalone tests; they
are not connected to CLI broker acquisition. SHA known-answer and independent
hashlib checks do not establish production cryptography readiness. The HTTP
client has additional bounded framing limits and rejects unsupported protocol
features; exact equivalence to reqwest tolerance and non-host platforms is
unverified. See `docs/evidence/log-foundations-tests.txt` and
`docs/evidence/log-foundations-link.txt`.

Native provider SSE framing and JSON assembly now have bounded, incremental
tests, including fragmented UTF-8, exact size limits, malformed input and
`[DONE]` termination. The test driver also runs without Python, Node, Rust or
Prodex in its filesystem/network namespace. These are frozen-source
regressions, not observations against the official release. Provider execution
does not call the modules yet; translation, completion/error envelopes,
HTTP/TLS/proxies, backpressure and cancellation remain unfinished. Evidence:
`docs/evidence/provider-sse-tests.txt` and `docs/evidence/provider-sse-link.txt`.

Chat-compatible choice/error decoding now feeds a native stateful DeepSeek
response-stream translator. It accumulates text/reasoning/tool deltas, emits
completion/failure envelopes, projects usage/metadata and shapes tool items.
Synthetic loopback fixtures run through the checksum-verified official
release's Super adapter and are replayed through the native component. Missing
tool IDs require UUIDv7; the runtime initializes them before the deterministic
provider-core fallback can apply. Two independent release captures prove the
varying UUID bytes; comparison preserves all other bytes and validates stable
UUIDv7 identity within each stream.

These remain standalone modules outside the product CLI. The test-only
synthetic Codex client replaces the external integration target, never Modex;
its outer Super process exits 1 because it does not implement app-server.
Adapter response comparisons do not establish Super command parity. Provider
route selection, auth/config, conversation storage/lookup, first-event retry,
HTTP/TLS/proxies, cancellation/backpressure and full resource/error equivalence
remain unfinished. UUID generation uses the official file API to read
`/dev/urandom` and is only exercised on Linux. Non-host behavior is unverified.
See `docs/evidence/provider-chat-stream-tests.txt`,
`docs/evidence/provider-chat-stream-link.txt` and
`tests/fixtures/provider-stream/README.md`.

Two seeded malformed-shape captures (`choices: [7]` and `tool_calls: [null]`)
do not yield official-release SSE. Super exits with `Codex hook-trust preflight
initialize failed: channel is empty and sending half is closed`. The catalog
retains upstream bytes and observed stderr without an expected response. These
cases establish an oracle observation gap, not successful provider equivalence;
the native component's defined failure behavior is only source-derived.

DeepSeek request preparation is now implemented as another standalone native
component. It translates messages/history, tools and parameters and retains
the pending response metadata separately from the prepared upstream body.
The active release first validates/translates the runtime request, then may
replace only its body with the native provider-core conformance result for a
simple request. This preserves observable differences such as omitted
`text.format` and `stream_options` in that body while pending messages retain
JSON guidance. Native tests trace that pass instead of assuming pending
messages equal upstream `messages`.

Synthetic official-release captures exercise the prepared chat body and
request metadata. The web-search fixture instead reaches the Anthropic
Messages route and is kept separate; that adaptation is not implemented here.
Several malformed requests receive the proxy's generic HTTP 502 without an
upstream request. The frozen HTTP dispatcher deliberately hides the detailed
translation error; no exact translator diagnostic is claimed from that body.
The synthetic child's later hook-trust error also occurs on successful
captures and is a separate harness limit. Isolated native tests verify
source-derived errors. Credential/config setup, conversation lookup/storage,
provider transport and CLI dispatch remain unfinished. Evidence:
`docs/evidence/provider-request-tests.txt`,
`docs/evidence/provider-request-link.txt` and
`tests/fixtures/provider-requests/README.md`.

The native DeepSeek exchange now joins preparation, source-derived provider
header/auth filtering, a real HTTP POST socket and incremental response SSE.
It preserves duplicate response headers and separate pending messages/metadata,
returns body bytes for HTTP errors, and closes on completion, cancellation,
drop or error. Socket tests exercise partial HTTP chunk delivery before EOF,
malformed/truncated framing and setup/idle deadlines. Stored release request
and SSE observations are replayed through that native socket path; no new
full-header oracle capture or whole-process provider parity is claimed.

This remains a component outside CLI execution. Only numeric IPv4 127/8 and
compressed IPv6 `::1` are admitted. Total decoded response data is capped at
4 MiB, whereas the frozen SSE reader can consume longer streams under its
per-frame limits. Route selection and
Anthropic web-search adaptation, TLS/DNS/proxies/redirects/pooling,
retry/rotation, persistent conversation state, general HTTP parser tolerance,
downstream backpressure and non-host behavior remain unfinished. Closing is
explicit between synchronous reads; interrupting an in-progress read relies
on its idle deadline. Evidence: `docs/evidence/provider-transport-tests.txt`
and `docs/evidence/provider-transport-link.txt`.

Buffered chat success JSON now goes through the same real POST exchange. The
native mapper handles text/tool outputs, usage, metadata, typed fallback IDs
and the frozen malformed-argument distinction between structural acceptance
and strict diagnostic parsing. A malformed literal/escape inside an ordinary
function-call argument string can remain a string in the release; a raw
tool-search argument must form valid output JSON. Captured examples document
that behavior without treating it as execution or validation readiness.
Missing call IDs use UUIDv7; explicit empty IDs remain present. Response ID
and time fallback are supplied by the component caller; production runtime
generation still needs wiring at the CLI path.

The exchange exposes pending plus normalized assistant messages only for
nonfailed translated responses with a nonblank response ID. No persistent
conversation store has been connected. Exact buffered captures and real
socket regressions are in `tests/fixtures/provider-buffered/cases.json`,
`docs/evidence/provider-buffered-tests.txt` and
`docs/evidence/provider-buffered-link.txt`. Large-output conformance fallback, complete parser/resource/error
equivalence, rate-limit response headers, provider route selection and all
previously listed transport/CLI/platform gaps remain unfinished.

The native listener and internal local-rewrite relay now serve real synthetic
HTTP requests through the existing provider exchange. They remain outside the
active Super launch path. The frozen gateway forces a different proxy path;
the two captured DeepSeek configurations fail at profile/proxy preparation.
Modex preserves those observed output/exit/upstream failures rather than
exposing a successful DeepSeek gateway extension. Gateway help and ten parse
cases also have captured output checks. Remaining argument combinations and
all operational gateway providers/configurations are unfinished.

Both startup cases still omit real runtime/profile lifecycle locks and
housekeeping side effects. `docs/evidence/gateway-mismatch.json` records exact
baseline and Modex deltas with overall FAIL. The tests assert that this
reproducible mismatch remains documented; passing those assertions does not
establish gateway parity. No placeholder lock files are created.

The private `0600` fixture is not the whole permission contract. A separate
synthetic `0664` Codex config reaches the release's no-proxy failure, while
Modex refuses the group-writable file. This stricter guard remains an
unapproved safe difference in `docs/evidence/gateway-permissions-mismatch.json`;
reproduce with `python3 tests/capture_gateway_permissions.py` (exit 1).

Conversation state is a scoped in-memory cache, not disk persistence. The
native implementation preserves 256 entries per scope, 2048 globally, logical
64 MiB retention, sequence saturation, replacement and latest tool-history
selection. Logical Serde type weights are source-inferred; actual artifact
memory-eviction boundaries and non-host layouts are unverified. The serial
relay owns one cache; shared Mutex/concurrent behavior remains unfinished.
Known empty histories are retained separately from unknown response IDs, so
the frozen body-only conformance pass receives the correct existence fact.

The relay supports bounded request capture, incremental response writes,
buffered/streamed scoped continuation and upstream cleanup on downstream
reset. Valid request half-close remains supported. Graceful full FIN cannot
be distinguished from request half-close by the current peek-only watcher;
immediate cancellation in that case remains unverified. Requests are serial;
worker/admission concurrency, complete first-event retry/backpressure,
graceful signals, limits above the incoming 64 MiB cap and the existing total
SSE 4 MiB cap remain gaps. Fallback ID/time generation timing is also unverified.

The real Super path requires Smart Context, overlays and Codex app-server
hook trust (`initialize`, `hooks/list`, optional `config/batchWrite`, then
`hooks/list`, with a 12-second RPC deadline). Existing synthetic captures do
not complete that preflight. No bypass or successful launch stub is added.
Process stdio/deadline/descendant primitives and other recorded capability
gaps still block that integration. See `docs/evidence/runtime-local-tests.txt`
and `docs/evidence/runtime-local-link.txt`.

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
log-directory selection is unfinished. The frozen parser's independent limits
of 80 active array/inline-table levels and 80 segments per local key path now
match production comparisons, including semantic table trees up to 80-by-80
levels. Other resource boundaries remain unverified.

Three frozen-release log fixtures expose a quoted credential beside Unicode
whitespace. Modex masks the complete value and preserves the original spacing;
a fourth fixture differs only in retained spacing. Proposed handling: retain
complete masking and whitespace preservation, with compatibility approval
still pending. These are four `UNAPPROVED_SAFE_DIFFERENCE` observations, not
parity passes. The actual outputs and two resolved regression cases are retained
in `docs/evidence/log-mismatches.json`; reproduce with
`python3 tests/capture_log_mismatches.py`.

The release also prints synthetic bearer/API key values unchanged from
stream_payload source and text, at startup and during follow. Modex masks both
fields. This additional unapproved safe difference is retained with exact
JSON/plain inputs and outputs in `docs/evidence/log-stream-mismatch.json`;
reproduce with `python3 tests/capture_log_stream_mismatch.py`. It is not parity
PASS. General stream evidence is in `docs/evidence/log-stream-tests.txt`.

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
