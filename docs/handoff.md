# Checkpoint 2: verified native token limits and CLI fixes

Starting main and origin/main were clean/equal at
`f5973a27c64c33f9f17eabbec160822e0f95595a`. Sol reviewed the exact worker
patches and applied focused no-commit cherry-picks: log help
`0862e19f5d076a2055df9cf97a9850cfce6afb0f`, gateway switch diagnostics
`0624a066220819cb7ee2c8b8e1905e6f22ac61b2`, quota ASCII validation
`211cc940f92e55fdcb60d720d0bc37ceba7d99f0`, and, after its worktree was clean
and deliverable reviewed, session delimiter diagnostics
`4c8d9b2014f62f9bdd2767919e2358dba0a2099b`. The user supplied these workers
as Luna/MAX; this checkpoint spawned no new workers. Main integration, tests,
commit and push remain Sol-owned. Admission worker G's
`bf80ee85d871191804b46355ac52fb9108a68c15` is not integrated: its arbitrary
128-header cap intentionally differs from the pinned baseline and requires
separate consideration. Its isolated worktree remains intact.

Nine source files were verified byte-for-byte against pinned Git objects.
The requested non-2xx quota projection would diverge: the reference only
projects after successful Responses dispatch. Six live synthetic production
cases now compare 401/403/429/503, non-2xx SSE and a provider error inside a
200 SSE stream, checking quota semantics and exactly one upstream POST.
Native quota extraction now matches the reference's HTAB/visible-ASCII
validation. Bounded error tests cover chunk framing, nominated hop-header
removal and sanitized oversized-body failure. Non-2xx SSE buffering versus
reference streaming remains a recorded timing/size gap.

Sol's production fallback connects `--context-window` and
`--auto-compact-token-limit`, including their local aliases, through native
Super launch. Nine live comparisons cover zero/one fallback, clamping,
plus/leading-zero values and UInt64 maximum. The first provisional catalog
rewrite failed five live subcases; it was removed. The pinned exact-value
lookup accepts TOML strings only, so numeric budgets reach Codex while the
catalog retains its original defaults. No failed run is counted as passing.

The corrected focused run passed all 10 Python methods in 40.777 seconds.
The final serial `rtk proxy make build unit test` exited 0: all 44 native
unit executables completed, all 328 Python methods passed in 551.394 seconds,
with no skips, and the 407 recovery-policy differential vectors still passed.
The dependency/import/link review found no new application dependency, native
binding, Python production code, generator or runtime delegation. Explicit
paths and credential-shaped diff review passed before the checkpoint commit. Evidence:
`docs/evidence/checkpoint2-reference.json`,
`docs/evidence/checkpoint2-tests.txt`, and
`docs/evidence/checkpoint2-dependencies.txt`.

No complete contract/platform status changed. All six release qualifications
remain BLOCKED; the JavaScript SDK, broad security/storage/lifecycle behavior,
worker lanes and unconnected production recovery remain in the denominator.
Next runtime work is already implemented and under isolated validation at
`/tmp/modex-sol-error-sse-20261026`: bounded non-2xx SSE passthrough, early
chunk delivery, downstream-reset cleanup and stream-header ASCII validation.
Its original production regression failed before the change and focused
checks now pass; integrate only after pinned-release comparison and review.
Preserve isolated worker boundaries and verified commit/push cadence.

# Previous checkpoint: native Super

Target: Prodex 0.439.1 at `81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`.
The reference repository remains unchanged. Sixteen relevant snapshot files were
compared byte-for-byte with pinned Git objects; the 0.439.0-to-0.439.1 delta
is 463 files, 8,026 additions and 26,066 deletions. Worker-lane isolation,
nonblocking bounded admission, separate compaction capacity, targeted affinity
release, progress-aware recovery/backoff, tunnel-client 0.0.18 and Kiro CLI
2.34.0 were source-traced. Evidence: `docs/evidence/native-super-reference.json`.

The existing tracked and untracked work was preserved and backed up outside
the repository in `/tmp/modex-parity-20261026-initial`. This checkpoint integrates
its process capture, Super argv validation and Chat Completions relay work.

The production CLI now admits a narrow native Super launch: DeepSeek with an
explicit model/API key/numeric-loopback base URL, `--no-presidio`,
`--no-sub-agent`, and a simple `exec` invocation. `PRODEX_CODEX_BIN` must be an
absolute path; the shared Codex home must be empty and owned/private, and
existing account/config state is rejected before children/network traffic.
For example, with isolated private `PRODEX_HOME` and
`PRODEX_SHARED_CODEX_HOME` and an explicitly selected Codex executable:

```text
modex super --provider deepseek --api-key <key> --base-url http://127.0.0.1:PORT/v1 --model deepseek-chat --no-presidio --no-sub-agent exec -- <prompt>
```

`super_launch.mojo` creates a private temporary overlay, links session/history
storage, writes the native selected/bundled DeepSeek model catalog and default
budgets, probes Codex, performs the native hook-trust handshake and starts the
same native Modex executable as a supervised relay, launches Codex with an
explicit environment and returns its exit status. Relay readiness is bounded;
normal/error paths kill and reap the direct relay/app-server/client children.
The idle relay exits on parent-channel EOF. Unknown Codex-created overlay
files are retained with their location reported, preserving data until their
storage lifecycle is implemented. Shared session targets survive cleanup.
The native relay handles buffered/streamed Responses and binary/query-preserving
Chat Completions passthrough; successful SSE uses bounded reads without an
aggregate cap, while error/non-SSE responses remain bounded.

The pre-existing closed-stdin probe is fixed: hook requests use the official
stdlib socketpair/send(MSG_NOSIGNAL) wrappers. A living peer that closes stdin
now produces an RPC error and is reaped; Modex does not die with SIGPIPE.
Tests cover that exact race, legacy hook bypass, client exit 7, relay failure,
parent-channel closure, state preservation and credential containment.

Two implementation workers ran concurrently through the required official
launcher with disjoint provider and recovery files. Its configuration had no
model/effort override; both child banners reported `gpt-6.1-sol` and reasoning
effort `none`, rather than the requested Luna/MAX. Worker A implemented native
passthrough/auth/header/streaming checks. Worker B implemented native recovery
policy and tests. The primary owns integration, combined testing, docs,
review, commit and push. Worker stdout/stderr were captured separately under
`/tmp/modex-worker-{a,b}-20261026.{stdout,stderr}`; raw logs stay outside the
repository because they contain launcher/account metadata.

`runtime_recovery.mojo` ports the immediate/5/10/20/40/60-second schedule,
saturating counters/deadlines and owned persistent thread/goal policy. An
accepted control RPC increments attempt accounting; it is not actual goal
progress. Only a changed real-progress revision or root session resets retry
state, and each new failure starts its own cooldown. Native tests and 407
pinned Mojo wire-policy differential vectors exercise the policy. This module
is still unconnected to the production event monitor, owned control transport,
affinity release and recovery mutation dispatcher. There is no live recovery
or bounded-worker-lane PASS.

Focused production Super tests passed against synthetic external Codex/provider
peers, including live differential observations of the verified 0.439.1 release.
These replace the external integration targets, never Modex itself. The final
combined `rtk proxy make test` exited 0: the pinned build/native unit phase and all
321 Python methods passed in 518.690 seconds for Python discovery, with no
skips. Output and raw-log digest: `docs/evidence/native-super-tests.txt`. The
intermediate run had two `ldd` harness errors because the primary rebuilt the binary
during filesystem-isolation tests; the final run used a fixed artifact.
No passing claim relies on that failed run. No complete contract or new release
platform obligation is marked PASS. All six release qualifications are BLOCKED.

Next: reconcile locked existing state and private file modes, implement
additional model/config options and Smart Context, preserve all Codex shared
storage and frontend companion lifecycle, then replace the serial relay with isolated
bounded lanes/nonblocking admission and connect owned recovery transport and
real progress observations. TLS/DNS/WS, account rotation, process-tree signals,
older host OS/CPU support and the other five targets remain gaps. The current
clean-home launch is a development slice, not complete Super parity.

# Previous checkpoint (historical)

The active target is Prodex 0.439.1 at
`81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`. Its tag, Cargo version, release
manifest, GitHub asset digests and Linux oracle checksum are verified. The
immutable source snapshot and executable live outside the product graph in
`~/.cache/modex/`. Evidence:
`docs/evidence/baseline-0.439.1/reference-verification.json`.

The current inventory has 71 contracts and 426 platform obligations, remains
incomplete and includes all six release targets and the JavaScript SDK.
Eleven newly separated obligations cover worker-lane capacity, nonblocking
admission, local-pressure isolation, compaction capacity, progress-aware
recovery/backoff/session ownership/diagnostics, tunnel-client 0.0.18, Kiro CLI
2.34.0 and exact-commit release gates. None of these new obligations is PASS.
Older 0.439.0 captures retain their original commit/checksum. Shared help,
session CLI and malformed-Zstandard captures, plus Super hooks/app-server
argv fixtures, were executed again against the verified 0.439.1 artifact.

Sol implemented actual `super`/`s`/help routing and selected source-traced
argument validation, direct-child timed wait and native startup stdio spawn
with an explicit environment. The CLI still rejects Super startup before
filesystem, child or network side effects: secure temporary overlays, Smart
Context and live launch supervision are unfinished. Luna B completed native
hook JSON-RPC transport with 12-second per-RPC deadlines, a 16 MiB stdout-line
bound, stderr suppression and direct-child cleanup. It also corrected TOML
model-value projection and recaptured 54 argv/14 hook scenarios against the
new oracle. These transport components remain connected to real process test
drivers, not a successful production Super launcher.

Luna A removed the aggregate 4 MiB streaming HTTP-body cap while retaining
bounded read chunks and SSE line/event/JSON-accumulation guards. Buffered/error
bodies remain capped. It implemented DeepSeek request/token rate-limit header
projection on both buffered and streamed relay responses, integrated with Sol
in `runtime_local_rewrite.mojo`. A proposed chat-only POST retry was rejected
after source review: the baseline gates its first-event prefetch to native
Messages, which this relay does not support. No unsupported retry/replay was
retained. Output/final-response/conversation memory still scales with output.
The relay itself remains outside successful CLI startup.

The spawner accepted explicit `gpt-6.1-sol`/MAX and two `gpt-6-luna`/MAX
configurations. Runtime agent metadata exposes task status, not independently
verifiable model/effort identity. All workers produced native code and ran
checks. File ownership was coordinated; Sol corrected an overlapping relay
edit before the final combined run. Only Sol may stage, commit and push shared
`main`.

Final combined verification: `rtk proxy make test` exited 0; `make build`,
the full native unit phase and all 301 Python tests passed (493.468 seconds
for Python discovery). Exact output:
`docs/evidence/checkpoint-04391-tests.txt`. The previous 300-test run's 17 old
fixture identity failures were fixed by actual 0.439.1 recapture before this
full passing rerun. Scoped worker reruns passed 56 provider/HTTP/relay cases,
14 hook/RPC cases and selected production Super comparisons against 0.439.1.
Dependency/link inspection is in
`docs/evidence/checkpoint-04391-dependencies.txt`: no new application library,
native declaration, implementation helper or Python production dependency.
The final diff and changed fixtures passed credential-pattern review; all
release metadata JSON parses and manifest checksums match.

Next implementation priorities remain real secure overlay/Smart Context
preparation and launch integration, then the new worker-admission and native
recovery obligations. Startup descriptor swapping is restricted to a parent
with no concurrent I/O. Descendant cleanup/signals, secure durable storage,
TLS/DNS, general backpressure and non-host targets remain visible gaps.

The following milestones describe historical progress before this checkpoint;
their original test counts and baseline references are not current totals.

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

Validation: `rtk make test` (16 Mojo unit programs, test-only
JSON/Zstandard/text/log/TOML/SHA-256/HTTP/SSE drivers, and 178 Python methods PASS;
no skips). Final endpoint-edge and absolute-executable-path changes have
focused reruns in `docs/evidence/inspection-policy-tests.txt`. This includes
712 policy-oracle comparisons, 500 deterministic generated JSON values,
malformed UTF-8/syntax/boundary vectors and numeric/local session times,
future recurring rules through 2100, transition-second boundaries and
explicit/invalid POSIX TZ strings. Additional capability validation:
`python3 tests/probe_capabilities.py` (3 positive programs PASS,
4 expected public-API gaps reproduced). `python3 tests/session_mismatches.py`
retains 3 FAIL cases and 3 unapproved differences for baseline panics.
Actual compiler diagnostics and commands are in `docs/evidence/capabilities/`.

The later standalone chat-decoding addition passes `rtk make unit` (17 native
programs) and 27 focused provider Python methods, including 8 new chat tests.
There are 186 distinct verified Python methods across the prior full run and
this focused run; no full 186-method run is claimed. Evidence:
`docs/evidence/provider-chat-tests.txt`.

The frozen help inventory now contains 35 routes and 326 option mentions,
including four hidden commands and both Super exposure/short aliases. Capture
command: `python3 tests/capture_cli.py`; all help routes exit 0 with empty stderr
and no state mutations. Help mentions still require source validation for
registered flags, hidden flags, defaults, precedence and passthrough.
Root `--help`, `-h` and bare `help` are now connected, including ignored
trailing arguments after help flags and custom executable names in Usage.
Their release comparisons check isolated homes and no created paths.
Current/info/status help and diagnostics now match fixed and 384 seeded
argument-order comparisons, with no filesystem mutations. Status interval
validation retains the frozen 1..=60 range and error precedence. Their runtime
backends still fail explicitly as unimplemented; other command help routes
remain unfinished. Evidence: `docs/evidence/inspection-policy-tests.txt`,
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
the log test modules.

Policy-backed log directories now load through a native TOML 1.1 parser.
The loader validates all baseline policy section types, proxy settings and
secret-backend dependencies before resolving the log directory; invalid policy
falls back silently as in the release. Tests cover path/env precedence, empty
overrides, whitespace preservation, signed/unsigned integer boundaries,
negative zero and year-zero dates. Malformed string-continuation carriage
returns and truncated datetimes fall back without crashing. The parser passes
218 typed-value fixtures and 494 invalid
fixtures from a pinned independent TOML 1.1 corpus. An additional 712 wrapped
policy files match actual release output and directory selection: 226 use the
configured directory and 486 use TMPDIR. Evidence:
`docs/evidence/policy-unicode-tests.txt` and `docs/evidence/policy-corpus.json`.

Binary-text classification now uses exact Unicode 17 Alphabetic/Number data:
844 merged intervals covering 149,106 scalars. Native and independent checks
cover all 1,112,064 valid Unicode scalars, and production tests retain Deseret
and property-edge tool output. The table is static Mojo data, re-derived by a
test-only native audit; no build/runtime generator is used. The earlier
Deseret and policy-directory failures now have matching observations in
`docs/evidence/log-mismatches.json`.

Log timestamp parsing and rendering now has 732 exact official-release
comparisons across runtime/transcript events and JSON/plain snapshots. The
native formatter covers RFC3339 and custom offset forms, signed and expanded
years, variable fields, Unicode whitespace, fractional milliseconds, invalid
input preservation, UTC date-range boundaries and DST changes. Historical
subminute offsets round as in the release, including leap-second normalization.
Evidence: `docs/evidence/log-timestamps-tests.txt` and
`docs/evidence/log-timestamps-link.txt`.

File-based `log upstream` now follows processed payloads after an initial
latest-event snapshot. The native follower retains at most 32 descriptors,
reads at most 1 MiB per poll, caps pending data at 1 MiB and checks complete
lossy-UTF8 line sizes against 2 MiB. Split lines/scalars, truncation, replacement,
two-second path discovery, descriptor pressure and oversized-line recovery are
covered by native and actual release process tests. Inspection errors retain
the release's exit code and cause formatting. Without explicit disk recording,
broker/direct-source registries still fail explicitly; terminal views also fail.
Evidence: `docs/evidence/upstream-follow-tests.txt` and
`docs/evidence/upstream-follow-link.txt`.

Detached general `log` / `log stream` now emits ordered startup snapshots and
follows runtime/session events, including operational details and every
session-metadata projection. Adjacent duplicate transcript events are suppressed
within each file-read batch, while later batches retain repeated events. Runtime
paths refresh every two seconds and session paths every ten seconds. Their
shared 32-file budget reserves 16 entries per source and fills unused slots by
full-precision modification time and path. An isolated Linux process test
compares the exact 16/16 retained descriptor paths with the release under
`RLIMIT_NOFILE=48` before writing synthetic events. Operational tests cover the
frozen event catalog, detail order, clipping/control handling, scalar number
normalization and URL display cases. Decimal conversion and notation match the
observed default release behavior across 382 generated finite floats and 27
raw numeric boundary cases. Evidence: `docs/evidence/log-stream-tests.txt`
and `docs/evidence/log-stream-link.txt`.

Explicit disk recording now bypasses live registry discovery for detached
`log`, `log stream` and `log upstream`, including registries present at startup
or appearing during follow. The shared predicate preserves the frozen
Unicode trimming and ASCII case rules for `1`, `true`, `yes` and `on`.
Actual release comparisons cover JSON/plain output and unchanged registry
contents/directory inventory. Disabled/absent recording retains the explicit
unsupported live-source guard. Evidence: `docs/evidence/log-foundations-tests.txt`.

Native SHA-256 and a bounded loopback HTTP/1 GET client are implemented and
tested as standalone foundations. SHA vectors include padding boundaries,
incremental binary input, repeat digests and message-length overflow rejection;
file hashing uses 64 KiB reads and a 512 MiB default cap. The HTTP client uses
only the pinned stdlib's existing POSIX socket wrappers, with nonblocking
I/O, absolute deadlines, validated requests and bounded response framing.
Both drivers run in test filesystems without implementation helpers. Neither
module is connected to the CLI yet, and no production cryptography readiness,
general HTTP equivalence or non-host capability is claimed. Dependency/link
evidence: `docs/evidence/log-foundations-link.txt`.

`tests/capture_log_live.py` retains eight actual Modex/release mismatches in
`docs/evidence/log-live-mismatch.json`. The oracle's authenticated direct/broker
snapshots, cursor reset and rejected-identity behavior are characterized; Modex
still exits explicitly without connecting. This harness keeps host PID/network
namespaces because the attempted user/mount namespace prevented inspection of
the host identity holder. Its synthetic HOME/cwd/ports are isolated, but it is
not clean-runtime evidence. Registry loading must acquire the release's
compatible `.json.lock` and preserve recovery/legacy effects; the pinned stdlib
still lacks those facilities. The reference also executes candidate binaries
with `--version`, which conflicts with the prohibition on product calls to
Prodex. Do not bypass locking or add a helper to connect the foundations.

The release emits credential-like values unchanged from stream_payload source
and text. Modex masks those values in both JSON and plain output. Exact startup
and append fixtures are retained as an additional UNAPPROVED_SAFE_DIFFERENCE in
`docs/evidence/log-stream-mismatch.json`; they do not count as parity PASS.

This remains an incomplete log contract. Broker feeds and
terminal views remain unimplemented. Existing insecure application roots still fail instead of
receiving baseline permission repair. Remaining event selection and projection
combinations need further verification. Three Unicode-whitespace inputs expose
credentials in the release while Modex masks them; a fourth preserves spacing
differently. These four unapproved safe differences and two matching regressions
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

Next work: resolve compatible registry locking/recovery and private capability
reads before connecting live broker/direct-source acquisition. Preserve the
candidate-version-probe conflict. Continue independent command/config slices,
URL/parser/failure coverage and policy recursion/resource verification while
those capabilities remain unavailable; terminal views also remain unfinished.
Native incremental provider SSE framing and JSON assembly are implemented as
standalone foundations. Parallel GPT-6 Luna workers completed build/test
integration, boundary regressions and a clean-runtime check. Framing preserves
the frozen data-field rules, CR/LF suffix handling, strict UTF-8 and independent
4 MiB line/event limits; JSON assembly preserves joined/separate/accumulated
precedence, exact accumulation diagnostics and Unicode-trimmed `[DONE]`.
The test driver stops before malformed/oversized trailing input after `[DONE]`.
Root review also fixed a dropped event at a final CR-only separator; native
and process regressions cover it. All 19 focused SSE Python methods pass.
These are frozen-source tests, not official-release provider observations or
a connected product path. Provider-event translation, completion/error
envelopes and HTTP/TLS/proxy/cancellation/backpressure integration remain next
work. Evidence: `docs/evidence/provider-sse-tests.txt` and
`docs/evidence/provider-sse-link.txt`. No complete contract or additional
platform obligation is counted PASS.

Chat-compatible provider chunk helpers now select the first choice, decode
choice metadata/text/tool deltas and classify embedded errors in native Mojo.
The implementations reuse the JSON decoder and preserve frozen typed-field
and presence-based fallback rules. These remain standalone foundations;
stateful translation has subsequently been implemented as described below.
Original chunk evidence and limits:
`docs/evidence/provider-chat-tests.txt` and
`tests/fixtures/provider-chat/README.md`.

The recovered chat-stream work now combines SSE bytes, JSON assembly and
stateful DeepSeek response events in native Mojo. Three parallel GPT-6 Luna
workers implemented stream regressions, tool-item/RTK shaping and an
official-release capture/replay harness; root reviewed and integrated their
changes. Usage conversion, request/provider metadata merge, text/reasoning
completion, tool ordering, failure idempotence and synthetic malformed input
are covered at the standalone component boundary. Root corrected a random
UUID test that treated hex `a`/`b` as ASCII punctuation and added zero/max
timestamp vectors. UUID layout also matches RFC 9562 Appendix A.6.

The actual release generates UUIDv7 fallback tool IDs. The apparent conflict
with deterministic provider-core ID helpers is resolved by
`RuntimeDeepSeekToolCall::default`, which sets a fresh `Some(CallId::new())`
before those fallback helpers are consulted. Two independently captured
release UUIDs prove their changing bytes. The comparer validates canonical
UUIDv7, count and within-stream identity before allowing that specific field
to vary; all other output bytes remain compared. No incomplete component,
successful assertion or oracle-only observation increases the parity count.

The provider modules are not connected to CLI execution. Next integration
requires request/auth/config handling, HTTP/TLS/proxies, conversation history
persistence, bounded transport/backpressure/cancellation and first-event retry.
The test-only synthetic Codex child records real release HTTP/SSE behavior but
does not complete app-server; outer Super exit 1 remains explicit. This is not
a Super command parity result. Keep the incomplete inventory at 60 coarse
contracts/360 platform obligations, with 1 Linux obligation and 0 complete
cross-platform contracts PASS. Validation and dependency evidence for this
checkpoint: `docs/evidence/provider-chat-stream-tests.txt` and
`docs/evidence/provider-chat-stream-link.txt`.

Checkpoint validation: `rtk make test` exits 0 with 25 native Mojo unit
programs and 194 Python methods PASS, no skips. Final unified-diff section,
ASCII/Unicode whitespace and literal `/dev/null` path regressions were then
rebuilt and run through native item/stream tests and all 35 focused provider
Python methods, all PASS. The fresh official-release capture exits 1 because
two oracle responses are unavailable: 39 available responses match exact
bytes and one matches after the proven UUIDv7 field normalization. No other
captured response mismatch remains; unavailable captures do not count PASS.

The capture catalog also preserves two unavailable official-release responses:
non-object first choices and null tool entries reach the synthetic upstream,
but Super exits before producing SSE with its hook-trust preflight channel
error. These are explicit observation gaps. Native unit failure behavior for
these shapes is not a parity PASS, and no expected response is fabricated.

Native DeepSeek request preparation now composes Responses input/history
translation, adjacency/thinking rules, function/custom/MCP/namespace tools,
strict schema normalization, request parameters and metadata. The active
runtime computes pending messages/metadata before a simple-request conformance
pass can replace only the upstream body. The implementation and tests retain
that distinction, including raw `messages` precedence and the native body's
`text.format`/`stream_options` omissions. Passed history is an explicit input;
the live conversation store and lookup remain unfinished.

The user now requires GPT-6.1 Sol at MAX effort for primary implementation
and GPT-6 Luna at MAX effort for parallel implementation. This is recorded in
`AGENTS.md`. An explicitly configured Sol MAX lead implemented combo-model
handling, staged metadata limits and shared tool normalization; two explicitly
configured Luna MAX workers wrote preparation fixes and the capture/test
harness. Root integrated their disjoint files and ran the combined build.
The workers performed code changes, builds and tests, including MCP config
selection, strict tool handling, call-ID preservation and request preparation.

The new request modules remain outside CLI dispatch. Next work is native
provider transport/request routing, including the separately observed Anthropic
web-search route, credential/config handling, persistent conversation lookup
and cancellation/backpressure. The original full parity goal remains active;
the incomplete inventory and all six release targets are unchanged. See
`docs/evidence/provider-request-tests.txt`,
`docs/evidence/provider-request-link.txt` and
`tests/fixtures/provider-requests/README.md` for this component's evidence and
its local HTTP rejections with hidden detailed diagnostics. The synthetic
child's later hook-trust failure also occurs after successful responses and
does not explain the generic HTTP 502 by itself.

Request checkpoint validation: `rtk make build unit` exits 0 with 30 native
programs PASS. The final parse-context change also has a rebuilt native
integration test PASS. All 43 focused provider Python methods pass without
skips, including a real clean-filesystem/network request-driver test.
The fresh 27-case request capture contains 20 exact prepared-chat-body byte
matches, six generic local HTTP rejections with hidden detailed diagnostics,
and one separate Anthropic web-search route observation. The latter route
and incomplete outer Super process are not provider-command parity.

Native provider transport now joins request preparation, provider header/auth
filtering, real HTTP POST and incremental DeepSeek SSE translation. The Sol
MAX lead wrote the exchange, native driver and header regressions. Two Luna
MAX workers wrote the owning socket stream, shared socket helpers and real
TCP/process harnesses. File ownership stayed disjoint; workers built and
tested actual native code. Root reviewed the combined paths, added the build
targets, tightened test-environment isolation and recorded the remaining gaps.
The stream preserves duplicate response headers and returns partial chunk
payloads before the chunk, response or zero terminator has finished. It has
setup/request and body-idle deadlines and closes on explicit cancellation,
drop, malformed/truncated input, timeout or translated `[DONE]`.

The integration retains prepared body, pending messages and response metadata
separately. Tests replay stored checksum-pinned upstream request/SSE captures
through actual sockets; the filtering and framing regressions are separately
source-derived, not new official-release full-header captures. The native
driver also runs in a bubblewrap filesystem with only its executable,
platform/official Mojo libraries and synthetic data, sharing the host network
only for its synthetic loopback upstream. Python serves that peer outside
the namespace and supplies no product implementation.

The provider exchange remains outside CLI dispatch and accepts only numeric
IPv4 127/8 or compressed IPv6 `::1`. Its 4 MiB total decoded-body cap is a
known gap from the frozen reader's per-frame limits on arbitrarily long SSE.
Buffered success JSON translation, Anthropic web-search routing/adaptation,
credential/config discovery, conversation persistence, TLS/DNS/proxies,
redirects/pooling, retry/rotation, complete downstream backpressure and
non-host execution remain unfinished. Cancellation between reads closes the
socket; interrupting an in-progress synchronous read relies on its idle
deadline. No whole provider/transport contract or new platform obligation is
counted PASS. Evidence: `docs/evidence/provider-transport-tests.txt` and
`docs/evidence/provider-transport-link.txt`.

Transport checkpoint validation: `rtk make test` exits 0 with 31 native Mojo
unit programs and 235 Python methods PASS, no skips. Source/dependency and
unchanged-denominator checks pass. The product CLI binary hash is unchanged.

Next work is native provider request/response execution through the real
runtime entry point while preserving continuation ownership,
first-event retry and the unresolved platform/capability obligations. Keep
the original full goal active and the incomplete inventory at 60 coarse
contracts/360 platform obligations, with 0 complete contracts and 1 Linux
obligation PASS.

Buffered DeepSeek success JSON now uses that same real POST exchange. A Luna
MAX worker authored the mapper/native tests/driver and another Luna MAX worker
captured deterministic application/json observations from the checksum-pinned
release. The Sol MAX lead traced and corrected active conformance/fallback
differences, typed UUIDv7 IDs, namespace/RTK behavior, metadata omission and
malformed-argument diagnostics; he added native assistant-history extraction.
This work used an isolated worktree with disjoint file ownership. Root copied
the reviewed files, wired buffered response dispatch, and retained conversation
messages separately from request preparation and translated Responses output.

The mapper preserves the release's structural acceptance of ordinary tool
argument strings, including some malformed literal/escape spellings. Strict
diagnostics apply when that structural scan rejects or tool-search arguments
would produce invalid output JSON. This observable distinction has retained
oracle fixtures; no execution or broad validation readiness is claimed.
Failed translations and blank response IDs produce no completed conversation
result. The result is still in memory; no persistence or live continuation
lookup is connected. Fallback response ID/time remain explicit caller inputs,
as in the SSE component; production clock/UUID generation at CLI dispatch is
still required. HTTP translation failures currently raise through the native
driver, not the release's full HTTP 502 rendering path.

Buffered component evidence: `docs/evidence/provider-buffered-tests.txt`,
`docs/evidence/provider-buffered-link.txt`, and
`tests/fixtures/provider-buffered/README.md`. All prior platform and transport
gaps, route/Anthropic web-search adaptation, rate-limit response headers,
retry/rotation, conversation persistence and CLI integration remain in scope.
Buffered validation: four pinned native builds and the buffered/header native
programs PASS; all 72 focused provider Python methods PASS, no skips. Seventeen
buffered oracle cases produce 15 exact body-byte matches and two narrowly
canonical-UUIDv7-normalized matches through real POST. Both SSE and buffered
restricted-filesystem tests ran. The whole 235-method repository run belongs
to the previous streaming checkpoint; it was not repeated here. Large-output
conformance fallback and complete parser/resource/error equivalence remain
unverified. No complete contract or new platform obligation is counted PASS.

The native loopback listener, scoped in-memory conversation cache and internal
local-rewrite relay are implemented together. Sol MAX wrote CLI/runtime
composition and native argument/namespace checks; Luna MAX workers wrote the
listener, borrowed-peer cancellation and process/oracle harnesses. Root
integrated the source, implemented retention and fixed connect errno capture
before peer probes, plus empty-history/body-conformance distinctions. Reset
cancellation and valid request `SHUT_WR` have separate real socket checks.

The frozen gateway is a different entry path from Super local rewrite: it
sets `force_runtime_proxy=true`, which excludes the latter path. Captured
DeepSeek startup either reports no available profile or no compatible proxy.
The public CLI now matches those observed outputs, exits and zero-upstream
behavior; it does not expose a successful DeepSeek gateway extension. Native
relay operation is exercised only through `tests/local_rewrite_driver.mojo`.
The internal driver covers exact buffered/streamed bodies, scoped continuations,
unknown versus known-empty history, reset/half-close handling and clean runtime.

Gateway startup side effects still FAIL: real runtime/profile lifecycle locks
and housekeeping artifacts are missing. The exact baseline/current observations
are retained in `docs/evidence/gateway-mismatch.json`; no dummy artifacts are
created. `tests/capture_gateway_mismatches.py` exits 1 for that retained mismatch.
Standard tests verify both output compatibility and the documented remaining
filesystem failure. They do not label the whole gateway contract PASS.
The output cases use private `0600` Codex config. An additional `0664` probe
is retained in `docs/evidence/gateway-permissions-mismatch.json`: the release
reaches its factory error while Modex rejects group write access. This remains
an unapproved safe difference and is not hidden by the private input cases.

The baseline conversation store is in memory. The native cache scopes by the
frozen session-header/metadata/body precedence and UTF-8-length prefixes, keeps
256 entries per scope/2048 total under logical 64 MiB accounting, and preserves
sequence saturation and latest tool-history selection. Serde layout weights
are inferred from source, not verified artifact resource boundaries. It has
one serial owner, without the baseline shared Mutex/worker concurrency.

The incoming native request limit is 64 MiB; larger positive u64 baseline
configuration values remain unsupported. Arbitrary-length SSE still differs
because of the earlier total 4 MiB cap. Graceful FIN cancellation, signals,
first-event retry, full backpressure/admission/concurrency, route/provider
coverage, TLS/DNS/proxies and non-host execution remain unfinished. Fallback
clock/UUID timing is not yet exact for delayed buffered responses.

Next active-path work: Super's `force_runtime_proxy=false` and Smart Context
enable local rewrite, but overlays and Codex app-server hook trust must finish
before the real child launch. The preflight sends `initialize`, `hooks/list`,
optional `config/batchWrite` and another `hooks/list` within a 12-second RPC
deadline. The test-only synthetic child currently fails that handshake. Do
not bypass it or claim a completed Super command from provider observations.
Redirected process I/O, deadlines/descendant cleanup and prior capability gaps
remain necessary. Evidence: `docs/evidence/runtime-local-tests.txt` and
`docs/evidence/runtime-local-link.txt`. No complete contract or additional
platform obligation is counted PASS; all six targets and the full goal remain.

The internal driver currently uses the no-local-file-access namespace context.
Actual Super integration must select the appropriate context, including the
unscoped cache for allowed local-file access, rather than inferring it from
the test driver. The native store already supports unscoped and scoped keys.

Checkpoint validation: `rtk make test` exits 0 with 34 native Mojo programs
and 275 Python methods PASS, no skips. Final empty-history corrections then
have four rebuilt native drivers/programs, native preparation/cache checks,
72 focused provider tests, 11 relay tests and five gateway output/retained-
difference tests PASS. Strict gateway mismatch/permission capture commands
each exit 1 for their explicitly retained failures. The source/dependency
audit matches all 58 Mojo paths. The denominator remains 60 contracts and
360 platform obligations; GATEWAY is now FAIL instead of NOT_STARTED, with
0 complete contract PASS and 1 Linux platform obligation PASS.

The parser now preserves the frozen independent limits: 80 active
array/inline-table levels and 80 segments per local key path. Forty-five
additional policy comparisons cover exact boundaries, large keys/strings,
malformed tails and admitted semantic table trees up to 80-by-80 levels.
Other resource boundaries remain unverified. General policy/config
application outside log-directory selection is still unfinished.
Stateful paths still fail explicitly. Future recurring timezone rules and
POSIX TZ strings are implemented; their earlier evidence is
`docs/evidence/recurring-time-tests.txt`.
Startup effects still differ. Details and the baseline
panic are in `docs/known-gaps.md`; no session contract is PASS.

The pinned stdlib's public and bundled internal source has now been inspected
for file/process/terminal prerequisites. It supplies basic pipes and direct
child management. The bundled posix_spawnp wrapper now proves complete explicit
child environments without changing the parent's environment. The new native
module requires an absolute executable path, owns string storage through the
spawn call and returns the official Process owner. Native/isolated-runtime
checks cover long, empty and Unicode arguments, omitted inherited variables,
NUL/malformed inputs and exact nonzero exit status. It is not connected to the
CLI; spawn file-actions/attributes, redirected I/O, deadlines and descendant
cleanup remain unfinished. Terminal raw mode/size, permission repair, durable
sync and atomic rename wrappers remain unavailable. The private fcntl ABI experiment is excluded from product
evidence and does not establish baseline-compatible locking. Details:
`docs/evidence/stdlib-internals-audit.md`. No dependency exception was added.

Endpoint rendering now handles tested special-scheme IPv4 radix/abbreviated
forms, IPv6 literals and embedded IPv4 tails, empty explicit ports, relative
file paths and dot segments after empty path segments. Query/userinfo secret
omission remains covered. The WHATWG-derived address validators are native
Mojo; complete domain/IDNA and URL-parser equivalence remain unverified.
Evidence: `docs/evidence/inspection-policy-tests.txt` and
`docs/evidence/inspection-policy-link.txt`.

Use GPT-6 Luna agents in parallel for independent implementation, validation
and review; file ownership must stay disjoint. This user preference is also
recorded in `AGENTS.md`.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.
