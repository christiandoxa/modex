# Current work: Prodex 0.439.2 parity and CI

Hosted Fast run `40828238106` on `3ad0a8acca97d45326143fdcaffb8c543b32abdb`
failed after the focused build and native checks passed: the official 0.439.2
tag was unavailable. Both CI helper shards passed. Oracle-dependent tests and
artifact consumers did not run; this is not a Fast CI pass.

Repeated real-process invalid-target probes found that the historical 0.165.1
oracle sometimes closes a half-closed request with a missing chunk terminator
within the 500 ms observation window. Its close-state assertion is therefore
unqualified; Modex's close assertion remains. Both pinned releases and Modex
return 400 without an upstream request in the selected malformed-trailer and
missing-terminator controls. The broader connection-lifecycle mismatch remains
open; see `docs/evidence/baseline-0.165.1/local-relay-http.md`.

The frozen active reference is officially released Prodex 0.439.2 at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Prodex 0.165.1 and 0.439.1
observations retain historical provenance; 0.439.1 is regression-only. CI
routes active oracle checks to 0.439.2 and keeps all six release targets in the
parity denominator. The 76-contract inventory and complete production parity
remain unfinished, with all six release qualifications BLOCKED.

Gateway help parsing now matches tested active 0.439.2 and historical 0.165.1
short-cluster and attached-value cases, including Clap's usage variation after
switches and attached versus split values. Synthetic API-key text stays out of
output. The production build, native parser program and focused process checks
pass; this covers CLI parsing only. Evidence:
`docs/evidence/baseline-0.165.1/cli-observations.md`.

After integrating the Super argument, bounded large-header and image-start
changes, the production build and four native checks passed. Sixteen focused
image, header and Super process tests passed, including comparisons against
both pinned releases; the
shared stream and CI-routing run passed 17, and two further process tests
reproduced the documented image-stop collisions. The production import audit
covered 71 Mojo files and the census covered 50 native sources and 128 Python
modules. An earlier broad relay run had two close-state assertion failures;
they remain recorded below. These checks do not establish full parity.

Production hook-trust initialization now reports client version 0.439.2. The
production build, its real-process comparison, native hook-trust test,
dependency audit and data-plane rerun passed. The combined RPC run exposed
three reproducible state/lock-file mismatches in the imported
`test_super_launch` suite. An isolated identity/RPC/replay rerun passed 21
tests. No full-suite PASS or parity promotion is claimed. The standalone
`test_app_server_rpc_04392.py` and cross-release streaming checks are in the
active CI path; the streaming test also requires the pinned historical 0.165.1
oracle.

The 0.439.2 local relay now emits the terminal chunk for HTTP/1.0 HEAD
204/304 event-stream responses, as observed from the Linux release. The
launch controls compare output and separately record missing Modex runtime
lock and housekeeping files. The tested relative, symlink and PATH Codex
launches now match both releases' shebang and native argument behavior. The
selected path is not pinned against replacement between probe and launch.
These observations do not qualify Super or the other release targets.
The local relay now captures non-WebSocket upgraded request bodies through EOF,
matching selected 0.165.1 and 0.439.2 controls while retaining its byte cap and
timeout. This does not implement h2c or HTTP/2. See
`docs/evidence/baseline-0.165.1/local-relay-http.md`.
After integrating the EOF, session-name and beta-host changes, the production
build and four native checks passed. Seven focused process tests passed against
the pinned releases, followed by the five-second malformed-stream control;
nine CI routing and cleanliness checks passed. The preceding relay run passed
70 local parser/relay tests and 17 release-oracle tests; after preserving the
non-deferred parser behavior, both upgrade-oracle tests and the bounded-capture
controls were rerun. The import audit covers 71 Mojo files and the census covers
50 native sources and 127 Python modules. These checks do not establish full
parity or qualify the other targets.
The rebuilt production path passed 36 launch and RPC tests, followed by
focused real-process checks for both releases, including empty and relative
PATH entries. The native spawn check retains absolute-only defaults.

Non-strict DeepSeek beta URL preflight now rejects selected malformed hosts
before launch, including fullwidth characters that map to forbidden host
characters. Complete UTS #46 normalization, TOML precedence and public beta
transport remain gaps; see `docs/evidence/deepseek-strict-tools-04392.md`.

Session listing skips tested invalid UTF-8 leaf names, traverses invalid-byte
directories, and matches both releases' displayed paths, ordering, queries
and symlink exclusions. The app-root marker scan also ignores malformed
`state.json.\x80.tmp` names, matching both releases while retaining valid lock,
journal and ASCII temporary-file guards. Real-process comparisons are in
`docs/evidence/session-invalid-utf8-04392.md`.

Session listing now reads a valid private `state.json` primary without
repairing it, attaches profile bindings, and applies profile filters. Indexed
binding processing matches last-key and 2,048-entry retention behavior; a
16,384-entry response-map stress case and 2,048-session report case match both
0.165.1 and 0.439.2. All 68 focused Python session tests and native
`test_sessions` pass; the dependency audit and test census pass. Modex still
does not lock or recover state: an
invalid primary with a valid `.last-good` remains fail-closed, world-readable
state and dangling symlinks are rejected, while the releases accept those
cases as readable or absent. A live symlink is rejected by the tested
releases. Descriptor checks are not interprocess exclusion. Details and exact
artifacts are in `docs/evidence/session-profile-state-04392.md`.

Both releases and Modex also accept a stable private state file with a
hard-link alias. The process regression verifies that Modex leaves the file,
alias, link count and directory contents unchanged; the earlier single-link
claim in the evidence was incorrect.

Bound empty profile names now remain distinct from absent bindings: JSON emits
`""` for the former and `null` for the latter, matching both releases and
`--profile ""` filtering. Identifier, duplicate-key and retention probes are
recorded in `docs/evidence/session-profile-identifiers-04392.md`.

Empty and whitespace-only sub-agent model arguments now produce the selected
pre- and post-positional diagnostics of both releases. Post-positional state
creation remains different; see `docs/evidence/super-subagent-model-validation.md`.

The guarded DeepSeek Super launch now forwards selected Codex `exec` output
flags and `--skip-git-repo-check`, including the literal `--` boundary. Exact
launch argv matches both releases in synthetic-child comparisons. Config,
sandbox and other unverified flags remain guarded; see
`docs/evidence/baseline-0.165.1/super-exec-output-flags.md`.

The combined production build and four focused native checks passed. The
sub-agent model and session profile process suites passed 14 tests against
both releases, and CI routing, workflow, cleanliness and reference helpers
passed 50 tests. The dependency audit covers 71 Mojo files; the test census
covers 50 native sources and 127 Python modules. These Linux checks do not
establish full parity.

After integration, the production build and four native session, Super and
provider checks passed. The focused profile, invalid-path, historical session
and state-guard suite passed 29 tests, and nine shared stream/concurrency
tests passed. The CI helper/routing suite passed 11 tests; the dependency audit
and 126-module census passed. These do not establish full parity.

Selected Anthropic message metadata, text/input and thinking deltas, unknown
string delta types, and unmatched block stops now match both releases in
real-process stream comparisons. Selected missing, null, and numeric delta
types now match the release failure diagnostic and event sequence; active
search and open result blocks follow the observed ignore precedence. Selected
closed-result text and post-failure continuation sequences now match both
releases, including malformed follow-up frames and terminal markers. A real
process probe with an invalid UTF-8 comment after `response.failed` records a
separate mismatch: both releases leave the downstream chunked body open for
the five-second client timeout, while Modex closes it with the same events.
Most other malformed stream shapes and
after-failure UTF-8 positions remain unverified. The focused shared-stream
suite passed 12 tests; the production dependency audit and test census passed.
See `docs/evidence/anthropic-stream-optional-metadata-shared.md`.
The integrated stream, model, session and historical mixed-tool suites passed
40 tests; the worker's separate text and historical stream suite passed 28.
After the continuation follow-up, the production build and five native checks
passed, as did 29 integrated stream, mixed-tool and model tests. The worker's
final stream and historical characterization run passed 39 tests.
The overlapping-result control covers 128 open indexes; no aggregate cap
limits retained per-stream search and tool state. See
`docs/evidence/anthropic-stream-optional-metadata-shared.md`.

After integrating the empty-profile and stream-order follow-ups, the production
build and four native checks passed. The combined stream suite passed 51 tests;
session, state and concurrency checks passed 32; CI helper/routing checks
passed 11. The dependency audit covers 71 Mojo files and the census covers 126
Python modules. These are focused Linux checks, not full parity.

The combined production build, three native provider/parser checks, nine
cross-release stream and concurrency tests, and eleven CI helper/routing
tests passed locally. The dependency audit covered 71 Mojo files and the
test census covered 125 Python modules; this is not a full parity result.

The combined production and native builds passed. Seven cross-release tests,
34 session regression tests, and 11 CI routing and helper tests passed after
integration; the worker also passed 62 session tests and 31 stream tests.
The dependency audit covers 71 Mojo files and the census covers 124 Python
modules. These checks do not establish full parity or non-Linux support.

After integrating these changes, the production and focused driver builds
passed, followed by 84 provider, relay, launch and hook-identity tests, including
production comparisons against the verified 0.439.2 release. The historical
0.165.1 relay/RPC controls passed
19 tests before the beta-host follow-up. The CI routing and reference helpers
passed 39 tests; the 71-file dependency audit and 122-module census passed.
The full suite and non-Linux targets were not rerun for this integration.

Hosted Fast CI run `40823584604` on `aa377d6` passed the production build and
native suite, then failed at the missing required 0.439.2 tag. Oracle
comparisons and artifact publication did not run.

Hosted Fast CI run `40822073508` on `5c0803b` passed the production build and
native suite, then failed at the missing required 0.439.2 tag. Oracle
comparisons and artifact publication did not run.

Hosted Fast CI run `40820069692` on `795ad94` passed both helper shards and
the production build and native suite, then failed at the missing required
0.439.2 tag. Oracle comparisons and artifact publication did not run. Run
`40819640597` was canceled after the newer push.

Hosted Fast CI run `40817443892` on `7a15fbe` passed both helper shards and
stopped before build because the required 0.439.2 tag was absent; artifact
consumption was skipped. Fast CI now runs the independent build and native
checks before that required oracle gate, while retaining the gate before
reference-dependent tests and artifact publication. See `docs/ci-lessons.md`.

Hosted Fast CI run `40816136528` on `87e57c3` passed both helper shards but
failed before build at the missing required 0.439.2 tag; artifact consumption
was skipped. No hosted product checks or parity gate ran.

Hosted Fast CI run `40814263090` on `a33ce8b` failed before build because the
required 0.439.2 tag was absent; both helper shards passed and the artifact
consumer was skipped. No hosted product checks or parity gate ran.

Hosted Fast CI run `40812724678` on `b2f0a70` failed because the required
0.439.2 tag and release were unavailable; both helper shards passed, the
producer stopped before build, and the artifact consumer was skipped. See
`docs/ci-lessons.md`.

Hosted Fast CI run `40809617468` on `46b8ba8` failed in two independent checks.
Helper shard 0 used a stale `focused-python` label, and the same stale label in
`test_ci_build_input_cleanliness.py` would fail later in the producer suite.
Both assertions now match `focused-python-active`; focused checks and both
helper shards pass locally. The producer still fails closed at the required
0.439.2 tag check and skips artifact consumption. No hosted success or
current-oracle revalidation is claimed. See `docs/ci-lessons.md`.

Hosted Fast CI run `40805095414` failed on three 0.165.1 reference-only
WebSocket handshake timeouts. The same three tests passed locally, including
with single-CPU affinity; the hosted cause remains unresolved. No hosted CI
success is claimed.

The notes below retain their original release-specific evidence and CI results.
They do not become current-target proof when the active baseline changes.

## Historical implementation and validation record

Hosted Fast CI run `40801262569` failed in the relay suite because its strict
mixed-tools test still expected rejection after mixed Anthropic tools were
enabled. With a rebuilt relay driver, the updated test verifies the Anthropic
route and strict schema, and a 0.165.1 production comparison matches the
forwarded request and response. This does not claim that hosted CI passed.
An isolated exact-commit `make test` on `028d9cd` ran 748 Python tests and the
native checks; it failed only that same stale strict mixed-tools assertion.
The corrected relay and loopback suites pass 45 tests with rebuilt drivers;
the full suite has not yet been rerun at the corrected commit.

The Anthropic Messages adapter now supports selected mixed function and web
search requests and buffered or streamed replies against 0.165.1. Buffered
content is capped at the reference's 65,536 blocks; tests cover the boundary,
text ordering and reused search IDs; buffered comparisons cover 3, 64 and
1,024 search pairs with a function call. The stream parser now matches selected mixed function and
multiple web-search uses with overlapping result blocks, reversed result stops,
duplicate IDs, pending results at `message_stop`, and fragmented queries. A
64-search synthetic stream also matches the pinned process. Query text that is
missing, malformed, or non-string maps to an empty query list without being
reflected; function argument validation remains strict. Broader text/search
interleavings and an aggregate stream search-count limit remain open. See
`docs/evidence/baseline-0.165.1/anthropic-mixed-tools.md` and
`docs/evidence/baseline-0.165.1/anthropic-stream.md`.

Hosted Fast CI run `40796304229` passed both helper shards, the active 0.165.1
and focused relay checks, then failed on the unavailable required historical
0.439.2 tag; the artifact consumer was skipped. An isolated local `make test`
run completed 728 Python tests and the native checks successfully. The checkout
changed during that run, so it is not evidence for an exact final commit.

Hosted Fast CI run `40794762417` passed both helper shards, the build, active
0.165.1 checks and relay checks, then failed because the mandatory historical
0.439.2 tag was unavailable. Its artifact consumer was skipped. No hosted CI
success is claimed for that run.

The local relay supports tested sequential and pipelined HTTP/1.1 keep-alive
requests, honors `Connection: close`, and parks up to 128 idle sockets so a
second client can run. Pipelined requests are parsed and dispatched in order;
responses remain serial. The parked queue is FIFO; when full, admission closes
the oldest idle socket to make room, after ready sockets are dispatched. If no
socket is safe to evict, one accepted overflow connection is retained until
admission is safe. Parked sockets have no idle expiry. A partial request on a
reused socket blocks other clients until the request completes or that socket
closes; parent EOF is checked between requests and does not interrupt an
in-progress read. The separate runtime-proxy WebSocket transport remains
unimplemented; the local rewrite adapter's 426 fallback matches its tested
release behavior. See `docs/evidence/baseline-0.165.1/local-relay-http.md` and
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

A new read-only characterization test launches the checksum-pinned 0.165.1
`__runtime-broker` with an isolated synthetic profile and a local-only upstream.
It confirms that the supported Responses path returns a local 101 handshake
without upstream I/O, rejects a missing WebSocket key with 400, and rejects an
unsupported path with 404. It is reference evidence only, not a Modex parity
test. Modex's only production Super network route remains the DeepSeek local
rewrite, which must keep its matching 426. No general profile-backed runtime
broker bootstrap is integrated in Modex Super. Mojo 1.2.0 exposes no public
`std.net` TCP/TLS stream types, so a `ws://` helper alone would not connect the actual
profile-authenticated WSS path or qualify its session, admission, interruption,
and recovery behavior. See
`tests/test_runtime_proxy_websocket_01651_oracle.py` and
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

Validation on Linux x86-64: `rtk make build` and the native local-rewrite and
loopback driver build passed. The focused 0.165.1 oracle module passed 14 tests
before the final pipeline controls were added. The expanded pipeline matrix
passed with oversized-body and HEAD SSE half-close cases. The direct
local-rewrite and shared loopback suites passed 45 tests. The production import
audit passed for 71 Mojo files. All six release targets and broader security
behavior remain unqualified.

The pinned HEAD SSE pipeline control also passes with and without
`shutdown(SHUT_WR)`: both binaries dispatch both requests. Prodex emits a
terminal zero chunk after its HEAD SSE response; Modex suppresses it, so that
wire mismatch remains. Modex's upstream reader treats HEAD as bodyless, so this
real-path control does not reach `write_chunk` with nonempty data. Existing
native reset tests still pass; no disconnect behavior change was justified.

Buffered local-relay responses now retain a valid HTTP/1.0 request version,
including selected malformed-header and fragment-target errors. A version
token before an invalid suffix also selects the matching final status-line
version; absent/invalid versions keep HTTP/1.1. The real-path regression
matches 16 selected response and streaming controls against historical 0.439.2,
with 0.439.1 controls. Default Server/Date headers, non-token method
admission, and HEAD event-stream terminal chunks remain an explicit gap. SSE
streaming stays incremental and uses HTTP/1.1 response framing.

The official Linux binary and
manifest were checked against SHA256SUMS and the GitHub asset digests; see
`docs/evidence/baseline-0.165.1/reference-verification.json`.

The session-report regression suite now also runs against the verified
0.165.1 Linux binary. It covers selected listing, filters, metadata, ordering,
timestamps and timezones; one safe handling test exercises Modex alone and is
not a parity claim. Session state locking and non-host targets remain gaps.
The new `session list --profile main` process comparison reproduces the state
gap: 0.165.1 returns the bound synthetic session, while Modex exits 1 with
`locked state loading and recovery are not implemented`. The release loads
valid state directly, but locks and repairs from `.last-good` when primary
state parsing fails; Modex keeps failing closed because its stdlib cannot yet
match that recovery contract. The test confirms the state JSON stays unchanged.
See `docs/evidence/baseline-0.165.1/session-profile-filter.md`.

The existing bounded logging suite now also runs in an isolated active-0.165.1
lane. All 36 selected log snapshot, payload, redaction, runtime parsing,
transcript, text and timestamp checks passed against the verified Linux
binary; historical 0.439.2 comparisons remain separate. This does not verify
live-source registry locking/recovery, terminal rendering or non-host targets.
See `docs/evidence/baseline-0.165.1/log-01651-tests.md`.

The production Super Codex version and app-server help probes now run with
`CODEX_HOME` and the five `TEST_CODEX_*` logging variables removed. A synthetic
peer comparison against the active 0.165.1 Linux oracle verifies both probe
arguments, the selected capability-failure diagnostic, no RPC/provider start,
and overlay cleanup. The version check now enforces the frozen `0.153.2`
minimum: a synthetic `0.153.1` stops before app-server help, while exact-minimum
`0.153.2` from stderr and components with leading `+` are accepted. A version
probe exit 7 also preserves the oracle's path/status/guidance diagnostic. The
tests use a private nested temp directory; oversized version/help capture
errors still match. Modex now matches the selected fallback progress lines,
provider panel, and child-start line on complete redirected stdout/stderr
comparisons against 0.165.1 and historical 0.439.2, with synthetic child and
no provider requests. Active 0.165.1 also matches redirected provider-panel
wrapping at columns 50 and 120, plus text fallback output on a PTY with
`TERM=dumb` or `PRODEX_TUI_STRICT=true`. Interactive TTY panel rendering
remains unfinished. A controlling 24x42 PTY now reproduces the natural-width
mismatch against both 0.165.1 and 0.439.2: the oracles render 42 columns while
Modex uses its 110-column fallback. The test asserts this known mismatch and
checks that no provider request or overlay remains. The direct Mojo 1.2.0
compile probe confirms that `std.os` lacks both `openpty` and `terminal_size`;
the pinned Prodex sources use `/dev/tty` plus `stty size`, which project rules
prohibit. Natural TTY width remains a parity gap. See
`tests/test_terminal_dimensions.py` and
`docs/evidence/terminal-dimensions-gap.txt`.
Other malformed version inputs, remaining startup/security behavior, and other
targets remain gaps. Hosted Fast CI run
`40788779491` exposed a diagnostic normalizer that assumed the fixture was
directly under `/tmp`; it now handles nested private temp roots. Both the
0.165.1 and 0.439.2 production-oracle tests cover that layout. See
`docs/evidence/baseline-0.165.1/super-codex-probes.md`.

Codex binary selection now follows the pinned 0.165.1 source for tested
`PRODEX_CODEX_BIN` relative paths and command names, default and relative PATH
entries, symlink targets, Prodex shim skipping and missing executables. The
resolved canonical path reaches version and capability probes with its path in
`argv[0]`; hook preflight and final launch preserve the selected invocation
spelling in `argv[0]` while executing that canonical path. A native Mojo ELF
Codex fixture records the raw argument vector, and the active-oracle suite
compares it across six selection modes. The suite also compares full
output/status, zero provider requests, and temporary-overlay cleanup. The
process-spawn unit checks an explicit custom `argv[0]`.
The pinned shebang-script test separately captures interpreter-visible
`sys.argv[0]`: probes use the canonical path in both binaries, while Prodex
preflight/final execution exposes relative, symlink, or PATH-selected spellings
and Modex exposes the canonical script path. Linux uses the executable
pathname for shebang scripts. The 0.439.2 six-mode comparison records this
gap; default and relative `PATH` launch modes match. Native fixture records
also carry PIDs so the active launch test checks their cleanup. See
`docs/evidence/baseline-0.439.2/super-codex-path-selection.md`.
Missing-path diagnostics match exactly and start no Codex process. The release
still creates session, profile and housekeeping locks that Modex does not, so
full storage side-effect parity remains open. Modex retains the canonical
pathname across probes and launch, which avoids symlink retargeting after
resolution. Path resolution does not pin the executable file: replacement of
that canonical file between probe and spawn remains possible with the current
pathname-based stdlib spawn.
Legacy-hash rejection is source-derived; no real legacy Codex binary was run.
See `docs/evidence/baseline-0.165.1/super-codex-probes.md`.

The pinned 0.439.2 Codex probe also enforces the `0.153.2` minimum. Its real
oracle comparison now covers below-minimum rejection, exact-minimum acceptance
from stderr, leading-plus components, version-probe exit 7, and oversized
`--version`/`app-server --help` diagnostics under a private nested temp
directory. Selected fallback progress output matches in `tests/test_super_launch.py`
and `tests/test_super_probe_diagnostic_04392.py`. The same test records the
baseline-only profile, broker, housekeeping, session-maintenance, and proxy-lease
artifacts explicitly; interactive TTY rendering remains unverified. These Linux
x86-64 synthetic cases do not establish broader Super parity. See
`docs/evidence/baseline-0.439.2/super-codex-minimum-version.md` and
`docs/evidence/baseline-0.439.2/super-codex-probe-output-limit.md` and
`docs/evidence/baseline-0.439.2/super-launch-progress-controls.md`.

The local relay now matches selected 0.165.1 `Expect: 100-continue` ordering,
including unsupported values, declared body limits, HTTP/1.0 interim responses,
WebSocket fallback and a half-closed body. Strict duplicate/framing rejection
remains a difference. See
`docs/evidence/local-expect-tests.txt`.

Pre-positional Super missing-value diagnostics now match the pinned Clap output
for all 27 value-option spellings and aliases, with empty values, dash-prefixed
values, help ordering and historical 0.439.2 controls. After `exec`, the
references still create lock state and report runtime-style errors; Modex
preserves its old exit-1 diagnostics without state mutations. Unsigned parse
errors now also match before the tail for context-window, auto-compact,
rollout-token, rollout-reminder and current-time interval options, including
the local aliases. Tests cover negative, overflow and whitespace errors,
accepted zero/U64-max/+1 values, attached forms and help ordering against both
pinned releases. After `exec`, the negative context-window parse still follows
the existing exit-1 path and state mismatch. Sub-agent concurrency syntax and
range diagnostics now match pre-tail, with accepted bounds, whitespace,
attached values and help ordering checked against both releases. Accepted
whitespace forms normalize to the typed default or decimal value. A real
0.165.1 dry run reports the custom/default concurrency, but Modex stops at its
Super startup guard before a sub-agent consumer; both pre-tail runs leave no
files. After `exec`, Modex now accepts those whitespace forms and reaches its
unimplemented startup guard. Selected invalid post-tail diagnostics match both
releases; reference lock creation remains different. See
`docs/evidence/baseline-0.165.1/super-cli-missing-values.md` and
`docs/evidence/baseline-0.165.1/super-sub-agent-concurrency.md`.

The Super model override now matches the tested 0.165.1 app-server argument
for a literal TAB, with quote, backslash, Unicode and injection controls. The
reference emits several other raw controls in invalid single-line TOML; Modex
retains parseable escapes for them. See
`docs/evidence/baseline-0.165.1/super-model-toml-tab.md`.

The local response writer now matches the pinned TinyHTTP final-status reason
table. Production controls cover 200, 204, 206, 302, 404, 418, 422 and 500
against 0.165.1 and historical 0.439.2. The HEAD 204/304 terminal-chunk and
large-header gaps remain. See
`docs/evidence/baseline-0.165.1/local-relay-status-reasons.md`.

The local relay now forwards tested HTTP methods on both supported routes,
including extension methods. GET JSON and SSE responses and selected HEAD
framing match 0.165.1, including the terminal chunk for HEAD 204/304 event
streams. Modex still suppresses the release's terminal chunk for HEAD 200
event streams. Large request heads now match
selected 65,535/65,536/65,537-byte boundaries, 128 KiB fields, and 1 MiB
aggregate/token cases against 0.165.1 and 0.439.2. The relay is bounded at
1 MiB, while both releases accept 1 MiB + 1; this mismatch remains open. Other
callers retain 64 KiB request-head and direct-stream defaults. Concurrency,
WebSocket transport and broader security behavior remain open. See
`docs/evidence/baseline-0.165.1/local-relay-http.md`.

The large-header validation run passed four focused 0.165.1/0.439.2 process
tests, the shared-parser 64 KiB boundary and direct 70 KiB stream rejection.
An earlier 111-test broad run had 109 passes and two existing 0.165.1
close-state assertion failures for invalid-target malformed-trailer and
missing-chunk-terminator requests. Three separate reruns of each control
matched the existing assertions (oracle leaves the socket open; Modex closes
it). Preserve the broad-run failures; this is not a full-suite PASS. Final
`make build`, three focused native driver builds, the 71-file production
import audit, Python syntax compilation and `git diff --check` passed.

Production Super hook-trust initialization now identifies itself as 0.165.1,
matching the verified Linux oracle through isolated synthetic Codex launches.
The 0.439.2 fixture and source provenance remain intact for the historical
protocol regression. This covers `clientInfo` only; see
`docs/evidence/baseline-0.165.1/app-server-client-info.md`.

When the synthetic Codex app-server closes stdin after `initialize`, production
Modex now reports the same `Broken pipe (os error 32)` text as the 0.165.1
oracle, without changing SIGPIPE handling or attempting an upstream request.
Full redirected stderr now matches the oracle, including launch progress and
provider fallback messages. Interactive TTY progress rendering and broader
transport cases remain unverified. The numeric errno text is verified only on
Linux x86-64; macOS and Windows behavior remains unverified. See
`docs/evidence/baseline-0.165.1/app-server-broken-pipe.md`.

When the synthetic app-server closes stdout immediately after `initialize`,
production Modex now reports the 0.165.1 oracle's empty-channel error. It sends
one initialize request, makes no upstream request, and removes its temporary
overlay. Partial lines still reach JSON-RPC parsing; timeout, oversized-line,
closed-stdin, and malformed-frame cases retain separate checks. This qualifies
the empty-stdout EOF case only on Linux x86-64; other release targets and
broader transport behavior remain unverified. See
`docs/evidence/baseline-0.165.1/app-server-closed-stdout.md`.

When a synthetic app-server writes invalid UTF-8 to stdout after `initialize`,
production Modex now reports the 0.165.1 oracle's stdout decoding error. It
sends one initialize request and makes no upstream request. The same diagnostic
matches when invalid UTF-8 arrives during `hooks/list`. Valid UTF-8 split across
reads, malformed JSON and an unmatched response ID still pass; the oracle
comparison reaches the synthetic loopback request. A historical 0.439.2
control matches both error phases and the split/noise case. The active
diagnostic mapping is verified only on Linux x86-64; other release targets and
broader transport behavior remain unverified. See
`docs/evidence/baseline-0.165.1/app-server-invalid-utf8.md`.

The `help update` unknown-subcommand diagnostic now preserves the full
argument, including attached values, in three real-process comparisons with
0.165.1 and the historical 0.439.2 control. Update execution remains
unimplemented; see `docs/evidence/baseline-0.165.1/cli-observations.md`.

An oversized declared relay body now returns the 413 `Payload Too Large`
phrase and error body observed in 0.165.1 and historical 0.439.2, without an
upstream request. Concurrency, WebSocket transport and broader HTTP behavior
remain unfinished; see `docs/evidence/baseline-0.165.1/local-relay-http.md`.

Session listing now joins a shared home ending in `/` without introducing an
extra separator. Synthetic list and path-query cases match 0.165.1 and the
historical 0.439.2 control; see `docs/evidence/baseline-0.165.1/session-paths.md`.
State locking and profile filtering remain unfinished.

Invalid Super `--provider` values before the positional Codex tail now match
0.165.1 and historical 0.439.2 CLI diagnostics. After `exec`, the error text
matches but the reference creates lock state that Modex does not; see
`docs/evidence/baseline-0.165.1/super-provider-cli.md`.

Buffered Anthropic function calls now preserve tested text and tool ordering,
stop metadata and a two-turn tool-result history against 0.165.1 synthetic
peers. Unmatched IDs, mixed history and representative array outputs also have
real-process controls. Other message shapes and provider behavior remain
unqualified; see `docs/evidence/baseline-0.165.1/anthropic-buffered.md`.

Gateway Presidio conflict diagnostics now follow tested option order and
parsing precedence. Process cases also check usage after value options without
echoing synthetic API keys. The precedence cases match the historical 0.439.2
control; gateway startup and other combinations remain unverified. See
`docs/evidence/baseline-0.165.1/cli-observations.md`.

`tests/test_cli_01651.py` compares selected root-help forms and leading version
flags through both production executables in isolated homes. Both cases passed
on Linux x86-64 with the verified binary. This does not establish complete CLI
or platform parity. The old integration worktree under `/tmp` was missing at
continuation; the original checkout's unrelated uncommitted changes were
preserved. An earlier checkpoint was `3c31fea`; Fast CI run
[40659458138](https://github.com/christiandoxa/modex/actions/runs/40659458138)
failed and its artifact consumer was skipped. The Linux 0.165.1 oracle attestation now verifies the pinned source commit and
release workflow; other release assets have not been separately attested.

CI scratch cleanup now installs its exit trap before creating the private
subdirectories, with a synthetic partial-setup failure regression. The
historical 0.439.2 oracle is still unavailable to unauthenticated hosted CI;
its required comparisons remain fail-closed. Both independent helper shards
passed in run [40748971666](https://github.com/christiandoxa/modex/actions/runs/40748971666)
on `cfa0dad` before the later push canceled its producer job.

Fast run [40753656126](https://github.com/christiandoxa/modex/actions/runs/40753656126)
on `483bcf1` passed helper shards, build, native units and current-target tests,
then failed on the unavailable required 0.439.2 oracle. Artifact consumption was
skipped; see `docs/ci-lessons.md`.

Fast run [40751613083](https://github.com/christiandoxa/modex/actions/runs/40751613083)
on `12b7392` passed both helper shards, production build, native units and
current-target tests, then failed at the unavailable mandatory 0.439.2 oracle.
The artifact consumer was skipped. See `docs/ci-lessons.md`.

Fast run [40749854285](https://github.com/christiandoxa/modex/actions/runs/40749854285)
on `6d51973` passed both helper shards, production build, native units and
current-target focused tests, then failed acquiring the unavailable mandatory
0.439.2 oracle. The artifact consumer was skipped. See `docs/ci-lessons.md`.

An isolated full local run at `6d51973` executed 583 tests but failed 54
assertions in five historical modules because the temporary parent was initially
mode 0775. A rerun of all five affected modules with a 0700 parent passed 10
methods. The original run remains failed; a clean full run on final main is
still required. See `docs/ci-lessons.md`.

The later `027fc48` full run executed 593 tests but failed two setup checks
and rejected one skip because isolated HOME hid the historical source paths.
The affected modules pass with the explicit pinned sources. A subsequent full
run on `165dd15` passed 605 tests with both historical source paths supplied;
the later `f386c7b` run passed 613 tests, `8f7c3c1` passed 616 tests, and
`fb9617f` passed 622 tests and `da71771` passed 625 tests. All predate the
current head. See `docs/ci-lessons.md`.

The local relay now matches selected 0.165.1 request-target admission, body
limit, `Expect` and WebSocket fallback ordering. It also accepts non-WebSocket
`Upgrade` metadata as ordinary framed HTTP when `Connection` does not name
`Upgrade`; h2c, mixed-case H2C and `example/1` production controls return 200,
forward one POST and strip the hop-by-hop `Upgrade` header. The shared parser
still rejects upgrade headers by default. With `Connection: Upgrade` plus
`Upgrade: h2c`, Prodex returns 200 and forwards a POST after a half-close, while
Modex returns 502 without an upstream request. Keep this fail-closed framing
difference documented; Modex does not implement upgraded streams through EOF.
For chunked requests, the relay now rejects tested nonempty trailers with 502
and no upstream POST, while retaining ordinary chunked bodies, extensions and
empty trailers. Shared-parser trailer support remains enabled by default.
Invalid-target chunked controls return 400 before delayed or truncated bodies.
The reference can leave complete request sockets open where Modex closes them;
connection reuse remains an open lifecycle mismatch.
Large request heads still differ; the relay remains serial and does not
implement WebSockets. See `docs/evidence/baseline-0.165.1/local-relay-http.md`.

The Anthropic text-block start now ignores initial text values like 0.165.1;
nonempty, empty, missing and numeric initial fields match full production event
sequences. Subsequent text deltas remain intact. The historical 0.439.2
comparison was recaptured and now matches; see the Anthropic evidence file.

The Anthropic stream parser also handles tested mixed text and multiple function
calls, including selected interleaving and late-delta cases, matching complete
0.165.1 events in real-process loopback tests. Mixed web-search/function streams
remain unverified. See `docs/evidence/baseline-0.165.1/anthropic-stream.md`.

The production Anthropic stream parser now matches two sequential server-side
search/result pairs followed by text against both 0.165.1 and historical
0.439.2. The provider request path and full normalized event order match in
isolated real-process runs. Mixed server-side search plus user-function calls
remain a concrete gap: `validate_deepseek_anthropic_request` requires exactly
one `web_search_preview`, `_tools` rejects translated function tools instead of
producing Anthropic `input_schema` declarations, and the stream parser constrains
search/result/text ordering and indexes. The shared request validator and
`_validate_anthropic_buffered_response` also require an explicit decision for
buffered mixed responses before the request contract can be widened. See
`docs/evidence/baseline-0.165.1/anthropic-stream.md`.

Serial searches that reuse an ID now match both release binaries. The earliest
matching search receives the first result; a later result for that ID is
accepted without a second completion, and the later search completes at
`message_stop` with no sources. Ordered append, binary block-index lookup and
an earliest-ID index remove cumulative quadratic search scans. Search records
and completed output items still require linear memory, and the upstream SSE
body has no aggregate byte or search-count cap. Long-lived streams remain
unbounded in total retained search/output memory. Interleaved search calls and
results remain unverified. Hosted Fast CI run
[40792087830](https://github.com/christiandoxa/modex/actions/runs/40792087830)
failed before active stream tests because their setup required the 0.439.2
oracle before acquisition. Active stream checks now use only 0.165.1 and Modex;
the repeated-search 0.439.2 comparisons run in a separate historical test after
acquisition. A routing regression verifies active setup with the historical
oracle missing and keeps historical tests after acquisition.

The production Anthropic stream parser now maps a tested function `tool_use`
with split JSON fragments to the same 0.165.1 Responses events. Several invalid
stop sequences remain explicitly different. Streamed Anthropic `image` blocks
are now ignored without returning their source data, matching full normalized
0.165.1 and historical 0.439.2 events. Incoming Responses `input_image` and
buffered image responses remain unsupported and match the tested release
behavior: the former is rejected before provider dispatch, and the latter
returns 502 after the synthetic upstream response. Indexed and missing-index
image start/delta/stop controls also match both releases while preserving text
before and after the block. The 48-test focused provider run passed, followed by
the two additional image-sequence tests and the 71-file import audit. See
`docs/evidence/baseline-0.165.1/anthropic-stream.md` and
`docs/evidence/baseline-0.165.1/anthropic-buffered.md`.

The production Anthropic stream parser now accepts missing or non-string stop
reasons and ignores stop sequences, matching selected 0.165.1 process events.
See `docs/evidence/baseline-0.165.1/anthropic-stream.md`; this is not full
provider or streaming parity. Historical mismatch notes below are superseded
for these tested stop-field cases.

The Linux x86-64 production build, focused native reader, exhaustive Unicode
audit, current-release CLI/session/provider comparisons, dependency audit,
test census, and both independent CI helper shards passed locally. The full native unit suite also passed on the production source at `63a3b17`;
its sanitized local log is `~/.cache/modex/ci-evidence/unit-63a3b17.log`. CI now keeps current and historical oracle paths separate, and a
synthetic orchestration regression verifies that current checks precede an
unavailable historical oracle without hiding the resulting failure.

Fast run [40747049105](https://github.com/christiandoxa/modex/actions/runs/40747049105)
on `d960e54` passed the current-target build, native units and focused CLI and
provider checks, then failed at the mandatory unavailable 0.439.2 historical
oracle; its artifact consumer was skipped. See `docs/ci-lessons.md`.

A current-release session-query regression also fixes 55 Unicode 17 lowercase
mappings absent from Mojo 1.2.0, verified against the pinned UnicodeData and
selected 0.165.1 process cases. See `docs/evidence/baseline-0.165.1/session-query-unicode.md`.

Update help and selected parser diagnostics now match 0.165.1 in isolated
process tests; update execution remains unimplemented. The session-query selector now uses the complete Unicode 17 Cased and
Case_Ignorable properties for contextual sigma. Exhaustive scalar tests and
eight real 0.165.1 process comparisons pass; other lowercase behavior and
session state remain unverified. Selected unknown Anthropic event types are now
ignored as in the 0.165.1 release. No contract status is promoted. Profile list
still fails closed because the release acquires interprocess locks and repairs
state; omitting those steps would race concurrent profile operations.

Next: continue recapturing behavior from 0.165.1. WebSocket transport work
must first establish the profile-backed runtime broker and lifecycle in the
actual Modex Super path; keep the local rewrite 426 unchanged. WSS/DNS remain
stdlib blockers. Retain all six targets and do not promote historical PASS
evidence.

# Historical work: Prodex 0.439.2 parity and CI

The Anthropic stream adapter now completes tested text-only and empty messages
when the model does not invoke web search. Eight full event sequences match
0.439.2 with generated IDs and timestamps normalized. A nonempty initial text
block still fails closed while the release drops its contents; broader stream
orders remain unverified. See `tests/test_anthropic_text_stream_04392.py`.

The production Super relay now honors the tested environment web-search modes:
off rejects search before POST, chat aliases select Chat Completions, and
auto/anthropic select the Messages path for the tested search request. Invalid
values fail before dispatch. Plain requests, raw passthrough and strict beta
interactions have separate controls. TOML precedence and broader route and
transport behavior remain unfinished. See
`docs/evidence/deepseek-web-search-mode-04392.md`.

Selected plain user, assistant, system and developer message arrays now reach
the Anthropic web-search path, with adjacent conversation roles merged and
system text retained. Release comparisons cover Unicode and role transitions;
rich content and message metadata still fail closed. Empty, blank-adjacent and
system-only arrays retain documented differences in
`docs/evidence/anthropic-web-search-04392.md`.

The workflow policy now rejects tested job permission overrides, extra root
permissions and alternate unpinned-action spellings; its narrow YAML lexer is
not a general parser. The dependency audit now checks that the declared source
inventory exactly matches all 71 Mojo files. Both helper-test sets run before
reference acquisition in Fast CI. The hosted oracle is still unavailable.

Combined local validation passed the pinned production build, 16 profile and
root CLI methods, 20 Anthropic/request characterization methods, five mode
methods, 19 local-relay methods, two native provider programs and 15 CI helper
methods. The complete suite was not rerun. The latest SHA with both hosted
Fast and Full passing is `75193427dc06541047195f976c48a404eba3deec` under
the earlier 0.439.5 target; it does not validate this 0.439.2 checkpoint.

Fast CI run [40650044718](https://github.com/christiandoxa/modex/actions/runs/40650044718)
on `cf5c5dd45cd66568d6210bc31d1a024eb6b92379` passed workflow validation,
the 71-file dependency audit and 31 reference-helper tests. It failed before
building because the official 0.439.2 tag and pinned oracle were unavailable;
the artifact consumer was skipped. This run does not validate the product
changes in hosted CI.

Fast run [40657417451](https://github.com/christiandoxa/modex/actions/runs/40657417451)
on `9918b416c66f3a5f25d263c18fe73b956c851d35` passed the 14 new CI policy
and inventory tests, the 71-source audit and 31 reference helpers. It failed
before building on the unavailable 0.439.2 oracle; the consumer was skipped.

Profile group help, seven subcommands' short and long help, help aliases and
missing-subcommand output now match the pinned 0.439.2 process for the tested
forms without changing the isolated HOME. Selected valid option prefixes,
short clusters and parser errors now match too; other combinations remain
unverified. Profile listing and mutations remain unimplemented because the
release creates persistent locks that Modex cannot safely share.
See `docs/evidence/profile-help-04392.md`; no profile contract is promoted.

The previously documented protected two-turn ownership mismatch is no longer
present on the current source: the release and Modex both return 200/503 with
one POST. The new 11-case real-process regression also covers previous ID,
session and turn identities, route changes and failed or invalid responses.
The relay still has a single static endpoint and process-local binding table;
multi-profile ownership and persistence remain unverified. See
`docs/evidence/continuation-ownership-04392.md`.

For the validated single-search Anthropic stream shape, the production relay
now matches complete 0.439.2 event sequences for selected null and string
stop reasons, string stop sequences and a missing `message_delta`. Missing or
non-string stop reasons and non-string stop sequences remain fail-closed
differences. No provider or platform status is promoted.

Session listing now distinguishes actual state files, their locks and atomic
temporary files from unrelated names such as `state.json.backup`. Full JSON
output matches the checksum-verified 0.439.2 release for the tested unrelated
names; 0.439.5 is a separately pinned historical control. The old build
rejected two of those cases. Actual state, its last-good copy, a held state
lock, pending temporary files and profile journals still fail closed without
modifying the fixture. State recovery and locking remain unimplemented. See
`docs/evidence/session-state-filenames-04392.md`.

Cached source verification now accepts a tracked symlink to a directory only
after checking its link bytes against the frozen Git tree; it never follows
that link. Synthetic controls reject changed targets, untracked links and
symlinked tracked parents. The 31 reference-helper tests pass locally. The
released binary is still unavailable to hosted CI, so this does not unblock
the oracle or promote a parity status. Hosted Fast run
[40644048655](https://github.com/christiandoxa/modex/actions/runs/40644048655)
on `fdace0b` passed all 31 helper tests, then failed on the unavailable
0.439.2 oracle before the build; its consumers were skipped.
The same result occurred for Fast run
[40644363845](https://github.com/christiandoxa/modex/actions/runs/40644363845)
on `abf4540`.

An isolated combined build passed all native unit programs and 523 Python
tests on Linux x86-64 using checksum-verified local 0.439.2 and 0.439.5
oracles and pinned source checkouts. That full run preceded the final heartbeat
and Git-configuration hardening; those changes were rebuilt and checked with
the focused native, release-comparison and reference-helper suites. Hosted
validation remains blocked by the unavailable 0.439.2 release binary.

The source helper can now recover a reference snapshot after a successful
official tag lookup returns no refs: it validates the recorded release
evidence, fetches only the pinned source commit, and verifies the checkout
against that commit's Git tree. On 2026-10-28 this recovered the exact
0.439.2 commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9` and historical
0.439.1 commit `81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`; a second 0.439.2
source invocation verified the cache. This is source recovery only. The
checksum-pinned release binaries still have no durable credential-free source,
so the oracle helper fails closed and CI cannot run reference comparisons
until those official bytes are available. Exact commands and results are in
`docs/ci-lessons.md` and `docs/evidence/reference-source-fallback-20261028.json`.
Fast run [40642097976](https://github.com/christiandoxa/modex/actions/runs/40642097976)
on `badf04f` passed all 27 reference-helper tests, then failed while acquiring
the missing oracle before the build or source acquisition. Its artifact
consumers were skipped. It predates the directory-symlink correction above.

The Full run `40625731794` memory-control failure is corrected locally by
disabling transparent huge pages in the isolated test children and verifying
that state at both samples. The original 4-byte-per-unit control, noise
threshold and width bounds are unchanged. All ten focused memory tests pass;
hosted validation remains pending, and THP-enabled allocation behavior is not
qualified. See `docs/ci-lessons.md`.

Fast run `40631003222`, attempt 1, producer job `122627098427`, failed before
building on exact SHA `84e4777e033742d3637bbfe0b8e3cd1d3d1ad668` because the
Prodex 0.439.2 tag is absent; consumer job `122628130127` did not run. The
reference checker now distinguishes an absent tag from a moved tag and a
remote lookup failure, while keeping each case fail-closed. Ten focused
reference tests pass locally. Logs and uploaded evidence are preserved under
`/tmp/modex-ci-40631003222/`.
Fast run `40629714742` on exact SHA `f1b8181` failed the same lookup before
building; its consumer jobs did not run.
The official 0.439.2 and historical 0.439.1 binaries were recovered read-only
from their original successful Prodex Actions artifacts and match the
previously verified release checksums. Those artifacts expire in early
November 2026 and require authentication; CI has no durable credential-free
source yet. See `docs/ci-lessons.md` for run and artifact identities.

Fast CI run `40628355469` on `2b6fe89` failed before building because the
official Prodex 0.439.2 tag and release assets are no longer published at the
recorded repository. The source commit remains retrievable and the previously
verified local oracle still matches its pinned SHA-256. Do not substitute a
different release or treat unavailable assets as a pass. Full CI run
`40625731794` on `865815c` failed a width-memory positive control; see
`docs/ci-lessons.md`. Both failures remain open.

The DeepSeek chat-stream path now prefetches a bounded SSE prefix before
commitment, retaining the idle deadline when lookahead expires. The pinned
0.439.2 release and Modex agree on selected empty-prefix failures, partial
prefixes, EOF, truncated framing, invalid UTF-8 inspection and gated
incremental output with one POST. An empty-prefix 502 does not claim the
session, turn or previous-response binding, so a later request can proceed.
The release may expose either of two
timeout messages; Modex emits the decoding form. Complete retry/rotation,
parallel prefetch admission and native Messages remain open. See
`docs/evidence/deepseek-precommit-04392.md`.

Fast CI now has a reviewed build-artifact handoff and two helper-test shards.
The producer checks clean source before building and packaging; consumers
validate the same commit, run/attempt, target, toolchain and file digests
before execution. Rerunning failed consumers retains the producer attempt.
Local `make ci-fast` still runs the helpers directly. The verified local
handoff used Mojo 1.2.0; hosted validation of this workflow is pending.
The remaining fast suite still runs in the producer, and broad sharding and
timing-based balancing remain open. See `docs/ci.md`.

Fast run `40625573927` passed on exact SHA
`865815c2681e8bf2fef86c57f4b95c7e78214308`; its Full run failed as recorded
above. Neither validates this later workflow change.

Session queries now lowercase selected dotted-I and contextual Greek sigma
cases on the production CLI path. Synthetic session comparisons use the
checksum-verified 0.439.2 release; supplementary 0.439.5 checks retain their
own oracle. The pre-change build failed those cases. This is a partial Unicode
slice: complete Case_Ignorable context, broader session behavior and state
locking remain open. See `docs/evidence/session-query-04392.md`.

Fast run `40620967035` and Full run `40620978240` both passed on exact SHA
`87a011893c99dd467a0d8d6c1330e0189baa58de`. Neither result qualifies this
newer session change.

Strict tools now work through the production Super relay when both
`PRODEX_DEEPSEEK_STRICT_TOOLS` and an explicit numeric-loopback HTTP
`PRODEX_DEEPSEEK_BETA_BASE_URL` are set. The relay validates before launch,
normalizes supported function schemas on the runtime path and sends Responses
requests to the beta route; raw Chat Completions passthrough retains its
original route. Synthetic
release comparisons cover strict=true, unsafe URLs, non-strict public URLs,
web tools and config-only inputs. Existing Codex config remains fail-closed;
TOML settings and public beta TLS/DNS remain open. A source-traced follow-up
now rejects a present invalid beta URL before Codex/provider work even when
strict tools are off, while a valid public URL remains unused for routing.
This closes that environment-only case against 0.439.2 and does not establish
full 0.165.1 behavior. Beta host validation now rejects forbidden raw and
percent-decoded delimiters, malformed percent escapes, invalid decoded UTF-8,
and percent-encoded invalid numeric hosts. Valid encoded Unicode IDNs remain
accepted. Modex now rejects all 13 tested fullwidth mappings to forbidden URL
host characters, including percent-encoded fullwidth `@`, matching 0.439.2.
Other UTS #46 hostname normalization remains unimplemented. A separate
0.165.1 launch with `not-a-url` also fails
before provider I/O with no launch or overlay side effects; the release adds
`relative URL without a base` to stderr while Modex keeps the generic message.
The selected active-release HTTP and URL controls do not qualify the broader
target. See `docs/evidence/deepseek-strict-tools-04392.md`.

Fast CI run `40619037675` passed on exact checkpoint
`863585a1bafb125e7b42f1e51137dc5e7cb5e703`. Its Full run `40619064905`
was still in progress when this note was written. The prior checkpoint's
local 445-test full suite does not itself validate this later strict change.

The user-specified frozen reference is officially released Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The tag, Linux oracle SHA-256,
and an isolated full source checkout were verified. Earlier 0.439.5 material
below is historical and retains its original reference; it does not establish
0.439.2 parity. All 76 contracts, 456 platform obligations, six blocked
release qualifications and incomplete inventory remain unchanged.

A combined isolated build restores the 0.439.2 hook version, DeepSeek model
catalog, flash aliases and low-reasoning mapping. Real synthetic launch and
request comparisons cover the active release and selected separately pinned
0.439.5 controls. An incremental passthrough observer now validates and binds
selected SSE response IDs beyond 4 MiB; live 0.439.2 and supplementary 0.439.5
checks return 200/503 with one upstream POST. Native and 571 deterministic
binding-boundary comparisons cover malformed JSON, duplicate keys, long
numbers, UTF-8 and chunk boundaries. Twenty more whitespace prefixes match
the 0.439.2 release in real two-turn tests with one-byte chunks; the former
helper rejects those prefixes, while the release and new observer bind them.
The NBSP data-prefix behavior also matches the release. Numeric-position counters saturate
at one billion; broader resource and security equivalence remains unverified.

The width-memory harness counts minor faults as events, rather than assuming
4 KiB per fault, and independently checks anonymous RSS and transient VmHWM
positive controls. Seven focused fixture/width checks passed locally; the full
nine-method memory suite passed against the combined build. Five saved samples
from Fast run `40611230270` replay successfully; the revised check also passed
in hosted Fast run `40619037675` on `863585a`. The pre-change Fast run on `68446d6` and Full run
`40610499704` on `3f82f0d` failed their old memory assertion. Fault sensitivity,
resident-page reuse and peaks below prior VmHWM remain limitations.

Selected DeepSeek web-search requests now reach Anthropic Messages through
the production Super relay. Release comparisons cover request path suffixes,
text input, web-search options, buffered search/text output and search/text SSE
ordering, sources, and truncated error streams. Anthropic auth headers override
client-supplied values. This is a selected local-loopback slice: broader input
and tool conversion, Anthropic response semantics, HTTPS/DNS/proxies and
complete error/backpressure behavior remain unqualified. The environment-only
strict route matches selected loopback controls; TOML configuration remains
unsupported. See `docs/evidence/anthropic-web-search-04392.md`. No paid traffic
or real credentials were used. Backslash-containing base paths and exact empty
input now match the pinned route behavior; empty input returns 400 without a
POST. Native Messages headers replace caller auth only on that route, while
DeepSeek and raw passthrough retain their previous forwarding. Native SSE now
ignores the Anthropic `ping` heartbeat, matching the whole normalized stream
from the release; unknown event types still fail closed. It fails closed
unless the tested search/result/text blocks stop in order and end with
`message_stop`. Null or string stop reasons, non-null string stop sequences,
and a missing `message_delta` now match full release event sequences for the
selected controls. Missing or non-string stop reasons and non-string stop
sequences still fail closed while the release completes them.

The older profile-list and artifact-manifest prototypes remain unrelated work
in progress in the original checkout. Their stateful and CI implementations
are excluded; the separate stateless profile-help slice is described above.
Evidence for the combined focused checks is
`docs/evidence/active-baseline-04392-tests.txt`.

# Historical checkpoint: Prodex 0.439.5 parity and CI

Checkpoint `96648d0be537ca1c2dedf8dd3fd75d8e5f910fe7` is verified on
`origin/main`. It follows `1f43496` (untyped content) and `3f82f0d` (embedded
tool calls), with focused production builds and 0.439.5 synthetic loopback
regressions passing for each slice. Fast run `40610911584` is in progress on
`96648d0`; exact-SHA Full run `40610499704` is in progress on `3f82f0d`.
The corresponding earlier Fast runs were cancelled by later pushes. The latest
SHA with both Fast and Full passing remains `7519342`; `78472bb` passed Full
but failed Fast as described below. No newer run is counted as a pass.

Three Luna Max workers were launched for CI memory, continuation observation,
and provider tools; the collaboration API does not expose their effective
model or effort independently. The continuation observer and memory-harness
edits remain uncommitted drafts pending integration and adversarial review.
The pre-existing profile and artifact-manifest prototypes are also preserved
in the workspace. Do not stage or build them accidentally when validating a
checkpoint; use a clean snapshot with explicit intended paths.

The continuation draft comprises `src/modex/runtime_local_rewrite.mojo`, new
`src/modex/runtime_sse_binding_observer.mojo`, and two new
`tests/test_runtime_observer*` files. An isolated build, native observer test,
and oversized-event production comparison passed: release and draft both
returned 200/503 with one upstream POST. The streaming parser still needs
bounded differential testing and production-entrypoint controls for malformed
JSON, duplicate IDs, chunk boundaries, and ordinary events before integration.
The CI draft changes only `tests/test_text_memory.py` and
`tests/width_memory_driver.mojo`; its local five-pattern check passed, but the
synthetic fixture does not yet exercise the full decision logic and its fault
threshold can reject huge-page samples. The provider-parameter worker made no
edits after 165 isolated comparisons found no mismatch; tool-shape tracing is
the next independent production slice.

Fast CI run `40606177561` on `78472bb` failed the new minor-fault positive
control on a host using transparent huge pages. All five width measurements
and anonymous controls passed, but a huge-page fault does not correspond to
one 4 KiB page. The 49 earlier focused tests passed. Exact-SHA Full run
`40606182672` passed all 429 Python tests on a host without huge-page growth in
the controls. Requiring either control to pass would conceal the fault
signal's insensitivity to freed huge-page allocations; do not claim transient
allocation coverage from it. See `docs/ci-lessons.md` and the uploaded run
artifacts for the measurements. The RSS test needs a separately validated
transient-peak measurement or an explicitly narrower scope.

The active mission designates official Prodex 0.439.5 at
`ac9aad08f25d6dc8cda96463ce2045b40f35f510` as the frozen reference,
superseding the earlier 0.439.2 session instruction. The checked-in baseline,
active CI oracle, and hook client version match that target. The remote tag
and the cached source and Linux oracle were reverified for this continuation.
Keep the 0.439.2 role regression and earlier captures as historical evidence;
they do not establish 0.439.5 parity. All six release targets remain in the
incomplete denominator.

Bare DeepSeek tool-role messages in simple requests now select the first
present `call_id`, `tool_call_id`, or `id`, including non-string defaulting.
Previously `call_id` and `id` were ignored. Eight added 0.439.5 loopback
controls cover precedence and the unchanged non-simple path; the regression is
`tests/test_provider_request_tool_role_04395.py`. A clean-snapshot production
build, two native request checks and three focused Python tests passed.
Broader tool behavior remains incomplete.

Simple DeepSeek requests now retain embedded generic-message tool calls. A
paired assistant/tool exchange previously sent the tool output without its
preceding call; 0.439.5 sends both. Selected real-process comparisons cover
typed and untyped messages, malformed entries, ID and argument shapes, roles,
and a non-simple control. The source trace is
`deepseek_raw_put_generic_tool_calls` in `mojo/prodex_core/deepseek.mojo`;
`tests/test_provider_embedded_tool_calls_04395.py` covers 15 production
scenarios. A clean-snapshot production build, two native request checks and
13 focused Python tests passed. Broader tool semantics remain incomplete.

Untyped DeepSeek input items now follow the 0.439.5 content-validation path.
For example, untyped null content previously produced a local 502 and no
upstream POST; the frozen release sends the string `null` and succeeds.
Typed `message` content and `prefix` validation remain enforced. Thirty
synthetic real-process cases cover simple and non-simple routing, scalar,
object and array content, and rejection controls. Broader provider semantics
remain incomplete. The source trace is `deepseek_input_item_validation` in
`mojo/prodex_core/deepseek.mojo`; the regression is
`tests/test_provider_request_untyped_content_04395.py`. In a clean snapshot,
the production build, four native request tests, dependency and workflow
audits, test census, and 12 focused Python tests passed. The older 0.439.2
role comparison remains a historical control. Reobserved two-turn 0.439.5
binding controls pass; the oversized SSE characterization still exposes the
separate unresolved mismatch.

Selected untyped DeepSeek role values now reach the mapper, which converts
unsupported and non-string roles to `user`; explicit `type: message` role
validation remains strict. Synthetic production loopback comparisons use the
checksum-verified 0.439.2 release and its pinned source, with 20 cases across
simple and non-simple request shapes. A clean snapshot passed the production
build, four native request checks, two captured-request tests, the dependency
audit, and the 0.439.2 and existing 0.439.5 loopback regressions. CI acquires
the 0.439.2 oracle and source explicitly. This covers only the tested role
cases, not broader request or provider parity.

The width-memory harness now reads post-exec Linux `/proc` VmHWM with a child
barrier, avoiding the inherited `wait4` peak floor observed with a 96 MiB
Python parent. A 4-byte-per-unit positive control exceeded the unchanged RSS
bound for all five local patterns, including a high-parent-memory run. This
demonstrates coarse sensitivity; hosted stability and smaller allocations are
not yet verified. Exact-SHA Full run `40597916331` on `610236a` failed the
revised check: Tifinagh width growth was 3,342,336 bytes against a 2,392,064
bound, and the 4-byte positive control did not exceed the sample-noise bound
for mixed and Kirat patterns. The other 428 tests passed. The cause remains
under investigation; the uploaded `width-rss.json` contains all samples.
The width source uses scalar counters and string views on this path; seven
local trials and allocator-setting probes did not reproduce input-scaled
growth, but do not explain the hosted spike. A follow-up harness measures
before and after each operation in the same process and records VmHWM,
minor faults and optional memory-map diagnostics. A touched 4-byte-per-unit
control is freed before the second sample. In a clean local snapshot the
control exceeded the unchanged bound for all five patterns, and width growth
was zero; a 96 MiB-parent run also passed. Fast run `40603196899` and Full
run `40603202733` on `0267116` nevertheless failed the width RSS check; the
other 428 Full tests passed. The new diagnostics show Tifinagh width's hosted
increase was mostly file-backed: anonymous RSS grew 4 KiB and minor faults by
one, while total RSS grew around 1.3 MiB. The 4-byte transient control grew
about 2.1 MiB in anonymous RSS and incurred about 514 minor faults. The next
harness checks anonymous-residency and minor-fault growth separately, with a
transient positive control for each. Both passed locally and when replayed on
the two hosted artifacts; the new harness still needs hosted validation. It
can miss allocations that reuse resident pages, and huge pages can change the
relationship between faults and resident bytes.
Full run `40591839335` on `663926f` also failed the earlier Tifinagh check,
measuring 3,125,248 bytes against a 2,658,304-byte bound.

Fast CI run `40597893098` passed on `610236a`. An initial Full dispatch
`40597905649` failed before checkout because the source SHA was abbreviated;
`40597916331` above used the full commit ID.

The profile-list and CI artifact-manifest prototypes remain workspace-only
work in progress. Prodex 0.439.2 normally creates persistent state and
lifecycle lock files and uses exclusive `flock`; the current read-only
profile prototype rejects that normal storage and cannot safely coordinate
with the baseline using the available Mojo standard-library locking APIs.
Its existing `src/main.mojo` prototype connection is not included in the
reviewed production change. Cross-job artifact provenance and sharding remain
incomplete.

Checkpoint `b0463949357c14620083e2558e3f94920c00ca0b` is verified on main;
Fast run `40593578860` passed, but exact-SHA Full run `40593599708` failed
the previous Tifinagh RSS check: 1,384,448 bytes against 507,904 allowed.
The latest SHA with both Fast and Full passing is
`75193427dc06541047195f976c48a404eba3deec`: Fast run `40590594088` and
Full run `40590628143` passed, with 422 Python tests in Full. Full run
`40593339273` also passed for `ee2d672`, whose Fast run was cancelled by the
newer push. The revised harness needs its own hosted validation.

DeepSeek accepts untyped `role: tool` input items like 0.439.5. The simple
adapter preserves or defaults a supplied tool-call ID; the non-simple path
keeps the observed release behavior of omitting it. Eleven synthetic
real-process cases cover missing, empty, invalid and paired IDs plus typed-role
rejection. A clean-snapshot production build, three native request checks,
import audit and 25 focused Python tests passed. Broader provider and tool
semantics remain incomplete.

Single-object `.json` session fallback now trims lines like the frozen
0.439.5 release when the whole file is not valid JSON. JSONL first-record
handling stays unchanged. Oracle controls cover Unicode and ASCII whitespace,
internal string content, malformed lines, BOMs, and multiline fallback. A
clean-snapshot production build, native session check, import audit and 25
focused Python tests passed, including compressed-session cases. This does
not complete session or storage parity.

Session query comparisons expose three Unicode lowercase mismatches: the
release expands dotted capital I and applies contextual final sigma, while
Mojo's simple lowercase mapping does neither. Ordinary query, duplicate-key,
and later-metadata controls match. `tests/test_session_query_04395.py` records
the differences; a full Unicode-casing implementation remains open. Four
focused query/state tests and the production import audit passed in a clean
snapshot. No partial casing fix was connected.

Exact `d9cd6c990912407137bdc64285fb974243f59f64` passed Fast run `40588571260`
and Full run `40588594792` attempt 1; Full ran 422 Python tests. Its
successor `7519342` also passed Fast and Full, as recorded above.

Exact `5e92613dea9e18b1587b6a1d9cde07b8b052a0b2` passed Fast run `40587184826`
and Full run `40587202764` attempt 1; Full ran 421 Python tests. The earlier
Full run `40587024590` on `216d494` failed the Tifinagh RSS threshold; logs
and measurement artifacts were retained and the cause is under investigation.
The later pass does not by itself resolve that failure; see `docs/ci-lessons.md`.

At that historical checkpoint, an unrelated `.prodex/state.json.backup` exposed a session-list gap:
0.439.5 lists the synthetic session, while Modex fails closed with its state
recovery error. Both leave the backup unchanged. The guard remains unchanged
until real locking and recovery semantics can be implemented safely. The
clean-snapshot production build, import audit and characterization test pass;
The later 0.439.2 and historical 0.439.5 correction is recorded at the top of
this handoff; state locking and recovery remain open.

Checkpoint `5e92613dea9e18b1587b6a1d9cde07b8b052a0b2` is verified on main.
Fast CI run `40587184826` and exact-SHA Full CI run `40587202764` passed.
The preceding `ab2a8a7` also passed Fast and Full; the separate `216d494`
Full run failed the RSS check described above.

DeepSeek model selection now falls back to `deepseek-v4-pro` for the tested
numeric, boolean, array, object, null and blank values, and resolves tested
combo aliases after selecting the first component. Previously these model
types were rejected and combo aliases could be sent as `flash` or `pro`.
The frozen 0.439.5 oracle and Modex were compared through 24 synthetic
real-process cases across simple and non-simple requests, with explicit
model controls and one upstream POST each. This is a narrow routing slice,
not complete provider catalog or retry parity. In a clean snapshot, the
production build, three native request tests, import audit and 24 focused
Python tests passed.

Runner checkpoint `216d4941bc46cc4ff469e043b7ae3219bd379b91` was pushed
and verified on main. Its Fast CI run `40586989260` was cancelled by the
newer push; exact-SHA Full run `40587024590` failed the RSS check above.

The strict Python runner now supports deterministic module-level shards and
checks exactly-one ownership of discovered test IDs. Discovery import errors,
duplicate IDs, invalid shard arguments, empty selections, and forbidden skips
fail. In a clean snapshot, 420 discovered tests partitioned 116/161/82/61
across four shards; 31 focused runner/cache/census and oversized-SSE checks
and both shards of a 20-test focused set passed. Fixture-level and class-level
skips fail even when their reason resembles a platform exception. Actual
parallel CI jobs, isolation, immutable
artifact sharing and cross-job completeness verification remain open.

The oversized accepted-SSE continuation mismatch is reproducible with
`tests/test_runtime_binding_04395_slice.py`: 0.439.5 returns 200/503 with one
upstream POST while Modex returns 200/200 with two. The 4 MiB observer limit
is retained; increasing it would raise memory consumption without handling
arbitrarily large events. A safe fix needs bounded incremental validation of
the full SSE/JSON event before committing the identifier. The characterization
test records a gap, not a parity PASS.

The native cache checkpoint `ab2a8a734b1b9a47dfd190e64b6aeaee7e955a7e` was
pushed and verified on main. Its Fast run `40585320926` passed 29 focused
Python tests; exact-SHA Full run `40585335244` passed 403 Python tests.
Exact `a5b727d` passed Full run `40580282085` attempt 1, including 388 Python
tests; `969c828` passed Fast run `40581282383` attempt 1.

The native unit build now compiles 79 programs with bounded parallelism and
executes the same 48 native unit programs. Cached outputs require matching
source/toolchain/target fingerprints, executable checksums and file modes.
Cooperating build, unit and test invocations share a per-build-directory lock;
the lock covers the Python phase of `make test`. A clean snapshot built all
79 programs and reused all 79 on the second unit run. After adding the current
session change, production build and native units passed again, along with 17
focused cache, census, provider and session Python tests. Workflow validation,
the import audit, and cache corruption, invalidation, failed-output, locking,
and child-lock regressions also passed. Cross-job artifact provenance and CI
test sharding remain open.

Session checkpoint `969c828bf842f1b06295828609edc78de0cdbc41` is on main.
Its Fast CI run `40581282383` passed; the earlier `a5b727d` Fast run was
cancelled by the newer push. Exact-SHA Full run `40580282085` passed for
`a5b727d`.

Session listing now accepts the same tested minimal resume metadata as the
frozen release, including legacy missing-type records and the four ID
fallbacks. It still rejects unrelated string record types and blank IDs. The
pinned source predicate is `crates/prodex-session-store/src/session_selector.rs`
and its metadata extraction is `mojo/prodex_core/session_report.mojo`.
An independent clean snapshot passed the production build, two native session
checks, import audit, and 36 focused Python tests, including 0.439.5 oracle
comparisons. A non-object first record remains an explicit mismatch: the
release panics and Modex safely omits the session. Broader session parity is
not established.

DeepSeek checkpoint `a5b727debf707b1cf47a2f2f68c30c24d7f548fd` was pushed
to main. Its Fast CI run `40580249376` was cancelled by the newer push; its
exact-SHA Full CI run `40580282085` passed.

The current DeepSeek request path preserves the resolved default model for
simple requests with an absent or null model. Previously it sent
`deepseek-chat` for an absent model and rejected null; the frozen release sends
`deepseek-v4-pro` for both. Six real-process synthetic loopback comparisons
cover three launch models, null and absent request fields, an explicit model,
and a non-simple request. At checkpoint `a5b727d`, numeric models still
differed; the newer slice above covers selected non-string and blank values.
The source trace is `crates/prodex-app/src/runtime_launch/proxy_startup/`
`local_rewrite_deepseek_send.rs` and `mojo/prodex_core/deepseek.mojo` in the
verified 0.439.5 reference. The regression is
`tests/test_provider_catalog_04395.py`.
In a clean snapshot, the production build, three native request checks, import
audit and 23 focused Python tests passed. The first native gate exposed an
outdated model-null rejection assertion; that assertion was corrected while
keeping numeric and boolean rejection coverage.

Exact commit `62b554cb93c477655581ea93d4f2d78a8b042fc4` passed GitHub Fast CI
run `40570794170` and Full CI run `40570838793`, both attempt 1. Full CI ran
387 Python tests and the capability probes. This engineering validation does
not establish complete parity. The newer DeepSeek change requires its own
exact-commit CI validation.

The separate profile-list prototype remains uncommitted: normal Prodex use
leaves persistent lock files, while Mojo's available standard-library APIs do
not provide compatible cross-process `flock` exclusion. Observing Linux
`/proc/locks` cannot prevent a race. Credential-writing profile prototypes also
remain unconnected because private atomic writes and journaling are unresolved.

The active reference is official Prodex 0.439.5 at
`ac9aad08f25d6dc8cda96463ce2045b40f35f510`. Its separate Linux binary,
manifests, checksums, clean source checkout, and signed GitHub/Sigstore
provenance are recorded in `docs/evidence/baseline-0.439.5/`. Prior
0.439.0–0.439.2 captures retain their original versions and checksums.
Modex still identifies itself as `modex 0.1.0-dev`.

The production DeepSeek path now uses the 0.439.5 Flash catalog and alias,
preserves low reasoning effort on the translated wire, and gives an owned
Codex child a bounded graceful shutdown before direct-child escalation if
the relay fails. The 14 hook-preflight scenarios were recaptured from the
new oracle; the old fixture is preserved. Focused native, synthetic
loopback, process, and real-oracle checks cover these changes. A proposed
quota-duration parser edit was rejected after the original source passed the
same new malformed-input tests; the useful edge checks remain.

Three concurrent worker sessions were launched with `gpt-6-luna` and `max`
as explicit tool arguments: CI/bootstrap, DeepSeek catalog/alias, and
process/low-effort implementation. Their changes were reviewed and tested in
combination. The collaboration status API does not independently expose the
workers' effective model or effort, so that runtime identity is not claimed
as separately verified.

The new fast, scheduled/dispatch full, and separate parity-verdict workflows
are Linux x86-64 only and use pinned actions and an official pinned compiler.
The first local full run passed bootstrap, reference, platform and native
checks but failed the Python suite: an unsafe inherited temporary ancestor
blocked the oracle before provider dispatch, and six historical session cases
depended on path wrapping. Focused fixes pass; see `docs/ci-lessons.md`.
The corrected local fast entrypoint passes production build, native units,
workflow/dependency checks, and 13 focused Python tests. The corrected full
validation subsequently passed on `62b554c`, as recorded above.
Build reuse, sharding, artifact provenance across jobs, and timing remain open.

The fresh two-turn continuation now matches: both return 200/503 and perform
one upstream POST. The relay records accepted response, session and turn
ownership with hashed credential/endpoint identities and validates the selected
identity before dispatch. Fresh controls cover unknown IDs, changed session or
turn state, failed upstream responses, accepted invalid bodies, and both routes.
Bindings remain in memory only; multi-account resolution, persistence, affinity
release, large passthrough SSE identifier observation, and recovery remain open.
The before/after production-path observations and artifact identity are in
`docs/evidence/continuation-0.439.5/verification.json`.
Profile/login finalization, account-replacement and login/quota concurrency,
other provider catalogs, SDK, storage/security and the six release-target
qualifications remain open. The incomplete inventory now contains 76
contracts and 456 platform obligations, with no complete contract PASS.

The first checkpoint `d4a50b3c1822d189aba94d53ce4db24beefa75bd` was normally
pushed and verified on main. Its GitHub Fast run `40564880852` attempt 1 and
manually dispatched Full run `40564952057` attempt 1 both failed their Linux
bootstrap because Ubuntu's Bubblewrap AppArmor profile was not loaded. The
workflow correction `8b15ace3593f6fc808ce23cbf2bbf9f32f6370fc` was pushed;
its GitHub Fast run `40566529600` attempt 1 passed and exact-SHA Full run
`40566557490` failed on the private-umask fixture and width-memory measurement.
An independent local full run of exact `d4a50b3`
passed native checks and 383 of 384 Python tests; one fixture did not account
for the private umask. Both issues were corrected and verified in the
`62b554c` full run above. See `docs/ci-lessons.md`.

# Checkpoint 15: bodyless SSE wire and bounded buffered response paths

The 0.439.2 source oracle remains immutable at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Checkpoint 14
was previously committed on main as `e0a29c502556`; no Prodex source was edited.
The initial existing checkpoint 15 worktree's bodyless SSE framing changes
were preserved and integrated with the separately tested buffered-response fix
(`445cfd7`, isolated worktree). The previous checkpoint 15 full gate passed 367
Python methods with a stable production hash before integration.

The real native Super DeepSeek relay now emits chunked headers for bodyless
204/304 SSE and the same final `0\r\n\r\n` raw wire sequence as the official
release. Two isolated real-Super raw socket checks compare the 204 and 304
headers, final bytes and exactly one provider POST. Buffered 2xx/3xx oversized
responses now take the post-accept provider-processing 502 error, whereas >=400
retains the upstream-send 502. The shared fixed-length reader now enforces the
4 MiB bound even when installed after the upstream header was parsed. Redirect
3xx SSE stays streamed, including tested bodies above 4 MiB with both known
Content-Length and unknown-length chunked framing. The first combined full
gate identified two obsolete native-only expectations of a cap on chunked
307 SSE. Fresh 0.439.2 oracle observations disproved that assumption, so the
old test was replaced with eight oracle/native route/status checks without
further changes to production code. Seven protected live outcome/header/post
cases and 30 other differential oversized/SSE observations also match the
checksum-verified release in their selected scope. No payload replay, extra
POST or credential change was introduced.

Validation: serial `make build`, seven combined focused Python methods, native
units and the full `make test` gate passed 370 Python methods in
843.704s (691.887s Python), no skips. The final
production hash `01ef000f0d4aba56c8a9cc21b8b5688cdfffbf2ce484db20ca9c710306c4c7f8` is stable across all Python-phase samples.
All 67 production sources and imports remain inventoried with no new library,
native binding, implementation helper, interop or generator. Tests used
synthetic isolated config, homes, loopback upstream peers and credentials only.
The historical 0.439.1 policy vectors and current quota-policy checks remain
narrow policy evidence, not connected live recovery.

The protected two-turn continuation still differs: official 200/503 and one
upstream POST versus native 200/200 and two. Account/profile/binding ownership,
active recovery, WebSocket, admission/lanes, storage/lifecycle/security, SDK and
six release-target qualifications remain unfinished. Keep all 71 contract
statuses, 426 platform obligations and six BLOCKED release qualifications;
no full parity or broad transport/security equivalence is claimed. Continue
with source-traced ownership/acquisition/rejection before implementing any
quota handoff; do not emulate failure by rejecting arbitrary continuations.

Evidence: `docs/evidence/checkpoint15-reference.json`, `checkpoint15-before.txt`,
`checkpoint15-tests.txt`, `checkpoint15-dependencies.txt`,
`checkpoint15-protected-probes.json`, `checkpoint15-bodyless-wire.json`,
`checkpoint15-original-gate.txt` (superseded test assumptions retained).

# Checkpoint 14: native buffered framing and current hook initialization

Checkpoint 13 was normally pushed as `67bef94c305bf6e4147fb0297e0a6eee0ccc7697`. Local HEAD,
remote main and clean main worktree were verified before immediate continuation.
The target remains released Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.

The native relay now carries its existing buffered/SSE dispatch choice into the
owned response writer. Buffered bodyless JSON retains Content-Length: 0; SSE
retains omission of that header. Status/body prohibition, header/framing and
size guards, deadlines, socket ownership and no-replay behavior stay intact.
Nine live path/framing vectors per binary cover both 304 routes, oversized
representation lengths, held-open chunked input, JSON/SSE 204 Chat responses and
an ordinary 200 control. All send one POST with authoritative synthetic auth.
The release's separate bodyless SSE Transfer-Encoding: chunked versus native
omission is explicitly retained as a mismatch, not counted as parity PASS.

Hook initialization now advertises the frozen Cargo package version 0.439.2.
Fourteen fresh official-release hook scenarios have zero upstream requests;
their RPC traces differ from the preserved 0.439.1 fixture only in that version.
The actual native/release Super entrypoints also compare exact initialization
parameters, successful synthetic client completion and one provider POST.
Oversized-hook panic/exit behavior and checkpoint 13's rejected tool/metadata
proposals remain unchanged. Existing worker branches and dirty files are intact.
Primary integration remains Sol/MAX; existing Luna/MAX worker provenance is
recorded in checkpoint 13. No new worker session is launched for this slice.

The corrected before-test fails six native cases and no oracle cases. The first
test expectation was too broad for SSE and is preserved separately in evidence.
Validation: serial `make build`, 48 native units, 31 focused Python methods
in 43.006s, then serial `rtk proxy make test`: 364 Python methods in
658.422s, no skips. Current quota policy's 1,600 source comparisons and the
407 historical 0.439.1 recovery vectors pass. The production hash is stable
during Python discovery/linkage/sandbox checks. Seven source call-path files
match immutable Git objects; all 67 production sources/imports remain accounted
for with no new dependency, binding, implementation helper, interop or generator.
No real credentials, paid provider traffic or account login are used.

Fresh protected probes still retain the binding ownership mismatch (release
200/503 and one POST versus native 200/200 and two), oversized-302 diagnostics
and bodyless SSE framing. Account pools, WebSocket, worker lanes, native active
recovery, security/storage/lifecycle, SDK and six-target qualification remain
BLOCKED. All 71 coarse contracts, 426 platform obligations and six blocked
release qualifications remain; no full parity or live recovery progress is claimed.

Evidence: `docs/evidence/checkpoint14-reference.json`, `checkpoint14-tests.txt`,
`checkpoint14-dependencies.txt`, `checkpoint14-before.txt` and
`checkpoint14-protected-probes.json`.

# Checkpoint 13: released Prodex 0.439.2 and native inspection usage

The active target is officially released Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
superseding 0.439.1. The read-only remote tag, official manifests, Linux binary
checksum and all 3,280 cached Git-tree blobs are reverified. All prior checkpoint
evidence keeps its original version/commit. All 71 contracts, 426 six-platform
obligations and six BLOCKED release qualifications remain unchanged.

Main began clean at verified pushed `47a86e1ce5be8d64b7cff0aaba1c37699aae8ae3`. The sole integrator reviewed
the existing parallel worker commits against the new source and release.
Inspection `37c9b74` is connected through actual current/info/status/root-help
dispatch. Its shared prefix removes the leading space for empty argv0; four
new release comparisons fail on checkpoint 12 and pass now. Normal executable
names and the existing fixed/384 seeded diagnostics remain covered, without
state mutations or backend-parity claims.

Quota `59815a4` adds only an explicitly unconnected signal foundation. The parent
replaces old-source/string-only checks with execution of current-pinned Mojo
window/candidate/retry-signal policy plus reviewed Rust gate composition:
1,600 comparisons and four busy/cooling source vectors. Synthetic checks keep
unknown and weekly-only quota distinct from exhaustion and retain auth/context/
runtime/quarantine eligibility. No account pool, HTTP/WS owner I/O suppression,
binding release, original deadline, full-history dispatch or live recovery is
proved. Zero signal grants no admission or replay. Accepted RPC is not progress.

Reject `6c4b21b`: current source and both real CLIs keep the specific duplicate
tool in its later slot. Reject `6d0fc33`: both real CLIs accept 4,200,071 merged
metadata bytes, retaining both synthetic values with one POST. Exclude
`624372c`: text replacement leaves the release's 101 panic versus native exit 1
mismatch for 65,537 hooks. Worker branches and all later dirty work remain intact;
chat-item/chunk proposals are not integrated. Process argv confirms the primary
GPT-6.1 Sol/MAX selection and concurrently existing GPT-6 Luna/MAX children.
Run IDs and exact reviewed commits are in checkpoint13-worker-review.json.

Validation: serial `make build`, all 48 native units, 11 focused Python
methods in 27.853s, then serial `rtk proxy make test`: 362 Python methods in
656.825s, no skips. The 1,600 current-source policy checks and 407 historical
0.439.1 wire-policy vectors pass. The production hash remains fixed throughout
Python discovery/linkage/sandbox checks. The source/import inventory remains
67 files, with no new application dependency, binding, runtime helper, interop,
production generator, real credential, paid traffic or account login.
The first full run failed three provenance assertions. Their historical fixture
bytes remain unchanged; 307 cases now also run against actual 0.439.2. The focused
three-method correction gate passes before the final full rerun.

Fresh 0.439.2 protected probes retain binding ownership (release 200/503 and one
POST versus native 200/200 and two), bodyless Content-Length omission and
oversized-302 diagnostics. SDK, account pools, worker lanes, active recovery,
security/storage/lifecycle and complete six-target qualification remain BLOCKED.
The immediate next production slice is the shared bodyless response-header
writer and hook initialization's still-historical 0.439.1 client version, after
this verified normal main push. Fresh hook captures are required; no release/tag
is published.

Evidence: `docs/evidence/checkpoint13-reference.json`, `checkpoint13-tests.txt`,
`checkpoint13-dependencies.txt`, `checkpoint13-before.txt`,
`checkpoint13-worker-review.json`, `checkpoint13-protected-probes.json` and
`docs/evidence/baseline-0.439.2/`.

# Checkpoint 12: native upstream dot segments

Checkpoint 11 was normally committed and pushed as
`3cacd5b01a64cb514035e54b11b949e5d399bd04`. Local HEAD, independent remote main
and clean worktree were verified before immediate continuation. Its reviewed
worker decisions and source/test integrations remain intact; W/X/Y's files
and all worker worktrees remain untouched.

The owned native resolver now removes literal and percent-encoded whole-dot
segments after raw trailing-slash trimming, backslash conversion and provider
suffix assembly. It preserves empty segments and original escape spelling,
clamps traversal at the authority root, and applies the existing UTF-8/six-ASCII
encoder. The validated numeric loopback address is kept separate from path
normalization; existing scheme/userinfo/query/fragment/control-byte guards are
byte-identical. No import, dependency, helper, native binding or option is added.

The new real Super/release regression covers 23 base paths and both provider
routes, totaling 46 paths/POSTs per binary. All compare exact expected paths,
statuses, authoritative synthetic auth and unchanged Chat query escapes.
Checkpoint 11 fails 20 base-path cases; the three existing escape/ordinary
controls already match. Native assertions cover all three single-dot and nine
double-dot spellings, eleven edge paths, an IPv6 retained-address tuple and
eleven invalid URL boundaries. The checkpoint 10 `/v1\..\other` refusal is resolved
within this admitted subset; it is not a broad URL or transport parity claim.

Validation: `make build`, all 46 native units, 18 focused Python
methods in 90.448 seconds, then serial `rtk proxy make test`: 355 Python
methods in 651.506 seconds, no skips, and 407 pinned recovery-policy vectors.
The full gate took 801.077 seconds. The production artifact
hash remained fixed through Python discovery, linkage/sandbox checks and after
completion. Three URL call-path snapshot files still match pinned Git objects;
locked URL 2.5.8 source/archive checksums retain checkpoint 11 provenance.
All 67 production sources, imports, linkage and isolated synthetic credential
checks remain accounted for. No real credentials, paid provider traffic or
account login were used. No new workers were launched; checkpoint 11 records
actual Sol/none supplemental runs and unverified requested Luna/MAX provenance.

Final live probes retain full binding and adjacent transport mismatches:
release 200/503 with one POST versus native 200/200 with two; 304 header
Content-Length: 0 omission; oversized-302 error text. Profile/credential/binding
identity, ownership/conflict/acquisition/persistence/release and actual recovery/
goal progress remain unfinished. Super history stays unscoped; the internal
driver remains scoped. Idle errors, non-object SSE, large output kernels,
physical cache memory, binary lower-client headers, broad storage/security,
JavaScript SDK and non-host qualification remain gaps. All 71 contracts,
426 platform obligations and six BLOCKED release qualifications are preserved.

Evidence: `docs/evidence/checkpoint12-reference.json`, `checkpoint12-tests.txt`,
`checkpoint12-dependencies.txt` and `checkpoint12-before.txt`.

# Checkpoint 11: reviewed worker integration and bodyless HTTP

Main began clean at verified pushed `85bb5540784ea27263f6abc21812071a7d8065ed`;
fetch and independent ls-remote confirmed origin/main. The sole main owner
reviewed every source and test patch in all four supplied completed commits.

Integrate `ff2d0d1` production arithmetic exactly, retaining decoded-value
weights and excluding its duplicate Python scope model. The pinned UInt128
sum is clamped to 64-bit usize::MAX; repeated nonnegative saturation is equal.
This does not establish physical cache memory or artifact eviction boundaries.
The rejected serialized-weight proposal `27cd318` remains excluded.

Adapt `40114bd0`: check the deadline before consuming buffered input, with
frozen `timed out waiting for <method>` text rather than its channel-timeout
assertion. Keep in-receive timeout handling. Register the new native unit.
Adapt `85e8550a` at the shared LoopbackHTTPStream root: zero effective length
for 204/304 before any cap check. The worker's passthrough-only wrapper leaves
Responses affected and is removed; raw headers and bodyless phase stay intact.
Its test reuses the existing fixture. Six live 304 status/body vectors cover
JSON/SSE declared lengths above 4 MiB and held-open chunked responses on both
routes, with authoritative synthetic auth and one POST each. Previous Modex
failed four of these; bounded native 204/304 and expired-buffer unit also fail
before the fixes and pass after them.

Reject `20b6ae2a`: the frozen private limit constructor permits arbitrary
limits, while production already supplies 4 MiB defaults. Its new restriction
and both tests remain on the unchanged worker branch. All four worktrees remain
untouched. W/X/Y's request-tools, hooks and metadata sources/tests are unchanged.

Validation: `make build`, all 46 native units, 31 focused Python
methods in 24.676 seconds, then serial `rtk proxy make test`: 354 Python
methods in 627.898 seconds, no skips, and 407 pinned policy vectors. The
artifact hash stayed fixed through Python discovery and after completion.
Ten reference snapshot files match pinned Git objects. Locked Hyper 1.12.0
and URL 2.5.8 source files match checksum-verified archives; both remain only
reference evidence. Imports, 67-file source inventory and native linkage add
no dependencies, bindings, helpers, interop, real credentials or paid traffic.

Supplied workers are user-reported Luna/MAX, not independently attested by Git.
Both supplemental official-launcher sessions actually selected gpt-6.1-sol
with effort none; exact parent selection is not exposed. No requested-model
claim replaces actual metadata. Full stdout and hashed separate stderr
provenance are retained; parent verified their source claims and assertions.

Remaining reproducible gaps include 304 downstream Content-Length: 0 omission
and oversized-302 error text (release `provider response could not be processed`
versus native `upstream request failed`, both 502/one POST). The worker probe
records fixture and response details. Full profile/credential/binding ownership,
acquisition/conflict/persistence/release, actual progress/recovery, dot paths,
non-object SSE, idle timeouts, broad transport/storage/security, JavaScript SDK
and non-host qualification remain unfinished. All 71 contracts, 426 obligations
and six BLOCKED release qualifications are retained. Continue next with the
owned native upstream dot-segment normalization slice after this verified push.

Evidence: `docs/evidence/checkpoint11-reference.json`, `checkpoint11-tests.txt`,
`checkpoint11-dependencies.txt`, `checkpoint11-before.txt`,
`checkpoint11-worker-review.txt`, `checkpoint11-worker-bodyless.json`.

# Checkpoint 10: native HTTP path separators

Checkpoint 9 was normally committed and pushed as
`66bd04e0fe78cde28b5631c9a6686df7929f38fe`; clean main and remote main
were verified before immediate continuation. Both reviewed worker proposals
remain excluded, with their source and worktrees unchanged.

The owned native upstream resolver now treats admitted HTTP base-path
backslashes as slash separators using existing `String.replace`. The frozen
URL assembly trims raw trailing slash characters before parsing the resulting
HTTP URL. Preserving that order retains a doubled separator after a trailing
backslash; normalizing before trimming would lose a slash. Percent-encoded
backslashes stay encoded, and existing UTF-8/six-ASCII escaping still applies.
No import, dependency, binding, helper, option or public API is added.

Twelve real Super/release path/route vectors cover single/repeated/trailing
backslashes, mixed backslash/slash endings, encoded backslashes, mixed UTF-8
and braces, Responses and Chat Completions query forwarding. Checkpoint 9
Modex failed ten of those requests; the encoded control already matched.
Both products now match the twelve paths, preserve authoritative synthetic
auth and send one POST per accepted request. Native assertions retain the
existing unsupported-dot guard after separator conversion. This stricter
dot refusal is not a parity PASS; literal/encoded dot normalization, authority
variants outside admitted numeric loopback and broader URL behavior remain
unqualified.

Validation: `make build`, all 45 native units, 16 focused Python methods in
52.553 seconds, then serial `rtk proxy make test`: 351 Python methods in
649.173 seconds, no skips, and 407 pinned recovery-policy vectors.
The full gate took 798.850 seconds; the artifact hash stayed fixed throughout
Python discovery and after completion. Final isolated live probes reproduce the
protected binding mismatch. They also show release 200/one POST with normalized
`/other/chat/completions` for `/v1\..\other`, while Modex exits 1 before any
POST. The dot guard is explicitly an unapproved safe difference, not parity PASS.

Three URL call-path snapshot files again match pinned Git objects. The
archive-verified locked URL 2.5.8 parser hash remains identical to checkpoint 9.
It is reference evidence, never a Modex dependency. All 67 production sources,
imports, linkage, isolated synthetic credential checks and clean runtime checks
remain accounted for. No new workers were launched; checkpoint 9 records
actual supplemental launcher Sol/none and unexposed primary selection details.
Requested primary Sol/MAX and original supplied Luna/MAX are not invented
runtime attestations.

Full binding identity/credential/profile ownership, conflict/acquisition,
persistence/release, recovery and actual progress remain unfinished. The
release 200/503 one-POST versus Modex 200/200 two-POST mismatch is retained.
Super history remains unscoped; the internal driver remains scoped. Idle
failure status/text, large-output kernels, non-object SSE, binary headers,
transport/storage/security, JavaScript SDK and non-host qualification remain
visible. Protected passthrough/SSE sources and tests are untouched. All 71
contracts, 426 platform obligations and six BLOCKED release qualifications
are preserved.

Evidence: `docs/evidence/checkpoint10-reference.json`, `checkpoint10-tests.txt`,
`checkpoint10-dependencies.txt` and `checkpoint10-before.txt` in that directory.

# Checkpoint 9: native ASCII upstream paths and two worker reviews

Main began clean at `21a15fcc9bda09d2c93b2436c8010843044d1bad`, matching
`origin/main`. The sole shared-main owner reviewed exactly the two supplied
completed worker commits against immutable 0.439.1 source and real release
behavior. Both proposals remain excluded, with branches/worktrees intact.

The owned native upstream path encoder now percent-encodes quotes, angle
brackets, backticks and braces using its existing byte loop. Ten real Super
path/route vectors compare Responses and Chat Completions, mixed UTF-8,
existing percent escapes, ordinary punctuation, queries and authoritative
synthetic credentials. Previous Modex failed six of those requests; both
products now match the tested paths with one POST each. No import, application
dependency, native binding or public option is added.

`9d05840` preserves a narrow continuation-reader diagnostic but does not prove
production transport compatibility. Live first-event idle receives release
502/plain error versus Modex 200/failed; after a text delta the observed
release message is `error decoding response body`. The async client's own
read-idle deadline and outer continuation timeout must be traced together;
substitution alone is insufficient. `capture_stream_timeout_mismatch.py`
reproduces both observations with one POST each and expected exit 1.

Reject `d127513`: five frames of 100,000 null annotations complete in both real
products, retaining all 500,000 values. The proposed allowance charges more
than 16 MiB and the existing worker binary fails. It also omits metadata and
snapshot retention and leaves the reader consuming after its cap failure.
A separate 17.5 MB refusal probe times out in the release's synthetic client
while Modex completes. Frozen kernel limits are per operation (ordinary stream
inputs 4 MiB, selected large buffered/tool/history payloads 16 MiB), not the
worker's aggregate state cap. No successful large-refusal parity or total
memory bound is claimed. Parent source/live evidence overrides incomplete
supplemental review conclusions; raw worker binary provenance limits remain.

Validation: `make build`, 45 native units, 15 final focused Python methods
in 44.446 seconds, then serial `rtk proxy make test`: 350 Python methods
in 607.700 seconds, no skips, and 407 pinned recovery-policy vectors.
The full gate took 780.277 seconds; the production artifact hash stayed
fixed during Python discovery and after completion.

Twenty relevant snapshot files match pinned Git objects. The inspected URL
2.5.8 parser matches its checksum-verified locked crate archive; it is reference
evidence only. The source/import inventory still has 67 production Mojo files,
and clean runtime/link plus isolated synthetic credential checks pass.

Requested primary execution is Sol/MAX; exact parent runtime selection is not
independently exposed. Supplied worker Luna/MAX identity is user-provided.
Two supplemental official-launcher reviews actually selected `gpt-6.1-sol`
with effort `none`; the immutable null-model/effort launcher config was not
modified. Their full stdout results and hashed separate stderr provenance
are retained in checkpoint evidence. No Luna/MAX run is invented.

Full binding identity/credential/profile ownership, conflicts, acquisition,
persistence and release remain unfinished. The release 200/503 one-POST
versus Modex 200/200 two-POST mismatch remains. Native Super still uses
unscoped history and the internal driver remains scoped. Non-object SSE,
large-output kernel boundaries, binary headers, transport/storage/security,
production recovery/progress, JavaScript SDK and non-host qualification are
unfinished. Accepted control RPCs are not progress. Protected passthrough/SSE
source files and their tests are untouched. All 71 contracts, 426 platform
obligations and six BLOCKED release qualifications are preserved.

Evidence: `docs/evidence/checkpoint9-reference.json`, `checkpoint9-tests.txt`,
`checkpoint9-dependencies.txt`, `checkpoint9-before.txt`,
`checkpoint9-worker-review.txt`, `checkpoint9-state-review.json` and
`checkpoint9-timeout-mismatch.json` in that directory. The adjacent backslash
separator URL mismatch is the next reachable source-traced slice; general
URL normalization and encoded dot segments remain unqualified.

# Checkpoint 8: native session-header alias fallback

Checkpoint 7 was normally committed and pushed as
`9bd28f82da9151086b1e2b6963cb7c515c403512`; local HEAD, remote main and clean
worktree were verified. Its 45 native units, 347 Python methods and 407 pinned
policy vectors passed before the immediate continuation.

An adjacent pinned-source trace found an inaccurate older native expectation:
a blank `session_id` must not suppress a nonblank `session-id` or `x-session-id`.
The frozen helper trims the first matching header per name and chains aliases
before turn metadata/body fallback. The sole main owner removed the redundant
`found` flag from the shared native resolver. Existing namespace and identity guards
now consume the same corrected selection; no API, import or dependency is added.

Six independent real Super/release vectors pass: two oversized resolved aliases
return exact 503 error JSON/cache/nosniff without provider POSTs; four valid
precedence/all-blank/body/metadata cases each dispatch once. The earlier Modex
sent both rejected requests and falsely rejected a valid alias when later turn
metadata was invalid. Valid session IDs are unique per turn so the release's
acquired ownership cannot confound alias precedence. Native tests also preserve
first-occurrence handling of duplicate header names and scoped namespace lookup.

Validation: `make build`, 45 native units, 29 focused Python methods
in 49.412 seconds, then final serial `rtk proxy make test`: 348
Python methods in 587.096 seconds, no skips, and 407 pinned policy vectors.
The artifact hash stayed fixed throughout Python discovery and sandbox/link
checks. Four immutable reference files matched Git objects; production imports,
67-file source inventory, native linkage and synthetic credential review pass.
No additional workers were launched; checkpoint 6 records actual model provenance.

Full binding ownership/release/persistence and production recovery remain gaps;
this is identifier selection and validation only. The release 200/503 one-POST
versus Modex 200/200 two-POST continuation mismatch remains visible. Non-object
SSE, lower-client binary header retention, broad transport/storage/security,
JavaScript SDK and non-host qualification are unfinished. P/Q source files and
external worktrees are unchanged. All 71 contracts, 426 platform obligations,
capability statuses and six BLOCKED release qualifications are preserved.
Evidence: `docs/evidence/checkpoint8-reference.json`, `checkpoint8-tests.txt`,
`checkpoint8-dependencies.txt` and `checkpoint8-before.txt` in that directory.

# Checkpoint 7: native buffered transport metadata

Checkpoint 6 was normally committed and pushed as
`27d0053cef6fe6e2f50f6bd40e7685662152e399`; `git ls-remote origin refs/heads/main`
matched local HEAD and main was clean before this continuation. Its 45 native
units, 346 Python methods and 407 pinned recovery-policy vectors passed.

The sole main owner immediately continued with the reproduced buffered metadata
gap. The frozen dispatch preserves raw binary headers until the TinyHTTP
constructor, which silently drops non-ASCII values. Modex instead forwarded
UTF-8/replacement bytes from its lossy client header representation. The owned
native relay now applies its existing ASCII/HTAB byte filter to buffered and SSE
passthrough alike; the redundant private selector is removed. No import,
dependency, binding, helper or public option is added.

Before the change, the new live release differential failed only for Modex on
both routes. Ten final vectors cover Chat Completions 201 and Responses 503,
ASCII/HTAB retention, C1/invalid UTF-8/valid UTF-8 omission, retained request IDs,
hop-header removal, exact NUL/non-UTF8 bodies, authoritative synthetic auth,
forwarded inbound turn state and stripped internal namespace metadata. Each
accepted request sends exactly one POST. Native header assertions and the
existing history/redirect/cancellation regressions remain connected.

Validation: `make build`, all 45 native units, 28 focused Python
methods in 48.230 seconds, then final serial `rtk proxy make test`:
347 Python methods in 590.347 seconds, no skips, and 407 pinned policy
vectors. The artifact hash stayed fixed through Python discovery and sandbox/
link checks. Eight source files match immutable pinned Git objects, including
the vendored constructor and its Cargo patch registration. Import/source/link
and synthetic credential review found only the existing official stdlib/runtime.
No extra workers were launched; prior model provenance remains in checkpoint 6.

The lower client still stores header text lossily; general binary header
retention outside this relay remains unqualified. Full binding ownership,
non-object SSE, recovery/progress owners, broad transport/storage/security,
JavaScript SDK and non-host qualification remain unfinished. P/Q's source files
and all other worktrees are untouched. All 71 contracts, 426 platform obligations,
capability statuses and six BLOCKED release qualifications are retained.
Evidence: `docs/evidence/checkpoint7-reference.json`, `checkpoint7-tests.txt`,
`checkpoint7-dependencies.txt` and `checkpoint7-before.txt` in that directory.
Continue from a verified main checkpoint; do not count narrow matches or
accepted control RPCs as complete parity or actual goal progress.

# Checkpoint 6: native Super history context and reviewed workers

Main started clean at `db9a78e0d4649538ccb5967b6dd7fb4a00a5844e`.
Fetch and `git ls-remote origin refs/heads/main` verified that same remote SHA
before the checkpoint commit.
The sole main owner traced and reviewed all six supplied Luna/MAX commits.
Only HTTP client `5a1d105d22d06307f82a9ec9e71b66b00ee08fca` and history
`9fe33a5deec24eba341164f99acaa93df3e1e6f3` were applied with no-commit
cherry-picks; both production sources remain exact. Their tests use isolated
synthetic peers; the history harness reuses existing transport helpers.

The owned reachable production change selects the frozen unscoped conversation
context for Super, while the internal driver's default still uses session scopes.
Both buffered and streamed tool-call follow-ups now preserve history across
different session/turn/namespace metadata, matching actual 0.439.1 Super runs.
The tests deliberately select the history-aware request path with
`safety_identifier`; the simple conformance override can bypass that history.
Each accepted turn sends one POST. No file access, public option or dependency
is added. Native scoped/unscoped checks protect the internal boundary.

Reject reader `5a14f47` plus `0663146`, usage `86b5d08`, and params `725c342`.
The release parses and reserializes JSON before its raw usage kernel; escaped
keys and duplicate priority must be decoded. Parent replay of 3,004 exact-worker
cases found 557 differences from the source-derived production model, plus
malformed/depth/size checks. Sixteen live usage vectors confirm decoded behavior.
Malformed response-format types are rejected before the historical raw fallback:
13 live cases retain strict validation and only the valid text case reaches the
provider. Non-object SSE is not an empty chunk: the pinned metadata kernel
rejects it and its Rust caller panics. Three live probes time out in the synthetic
release client; Modex emits `response.failed`. Both reader proposals remain
excluded. A registered native reader unit and a live ordered-event regression
cover ordinary provider-reported errors without claiming non-object parity.

Full hard-binding ownership remains unfinished. A fresh two-turn probe still
observes release 200/503 with one POST versus Modex 200/200 with two. Source
tracing separates dispatch profile identity, accepted raw credential identity,
response/session/turn binding acquisition, persistence and release from history.
No response-ID-only rejection or fake recovery progress was introduced.

Validation: `make build`, all 45 native units, 70 focused Python methods
in 63.978 seconds, then final serial `rtk proxy make test`: 346 Python
methods in 592.411 seconds, no skips, and 407 pinned recovery-policy vectors.
The artifact hash stayed fixed throughout Python discovery and sandbox/link
checks. Twenty-six reference files match immutable pinned Git objects. Imports,
source inventory and native linkage contain only existing local/official stdlib
dependencies. No real credentials, paid test traffic or account login were used.

The two supplemental reviews used the mandatory official launcher; its defaults
selected `gpt-6.1-sol` with effort `none`, not requested Luna/MAX. Full stdout
reports and separate private stream hashes/paths are retained. The parent
verified their source claims and replayed key probes; integration, tests,
staging, commit and push remain main-owned. Worker worktrees remain clean;
P/Q's `provider_sse_json.mojo` and `provider_chat_stream.mojo` are unchanged.

All 71 contract statuses, 426 obligations, capability statuses and six BLOCKED
release qualifications are retained. Evidence: `docs/evidence/checkpoint6-reference.json`,
`checkpoint6-tests.txt`, `checkpoint6-dependencies.txt`, `checkpoint6-before.txt`,
and `checkpoint6-worker-reviews.txt` in the same directory. The next reproduced
production gap is buffered passthrough's non-ASCII turn-state metadata: the
release drops it while Modex forwards replacement/UTF-8 bytes. Continue after
the normal checkpoint push; broad binding, recovery, transport and platform
qualification remain incomplete.

# Checkpoint 5: verified native UTF-8 upstream paths

Checkpoint 4 was committed and normally pushed as
`591497c8439b5649106d868db9d6a21c2ce495b3`; `git ls-remote origin
refs/heads/main` matched local HEAD and main was clean. Its 44 native units,
337 Python methods and 407 policy vectors passed. H/I are integrated; J and
the separate header cap remain excluded for the reasons below.

Sol continued with another reachable production slice in the owned
`runtime_local_rewrite.mojo`. The frozen HTTP client percent-encodes UTF-8
upstream base-path bytes, while Modex sent raw bytes. Three new Responses
path cases failed against checkpoint 4; an already escaped path matched.
A small native byte loop now encodes non-ASCII bytes with uppercase hex,
preserving existing escapes, combining sequences, trailing-slash handling,
loopback/credential/control validation and request framing bounds. No import,
dependency, binding, public option or implementation helper was added.

The final production regression compares four base paths on both Responses
and Chat Completions through the actual Modex and checksum-pinned 0.439.1
CLIs. All eight path/route vectors match status, exact provider target and
authoritative synthetic credentials, with one upstream POST each. Chat
Completions query forwarding is retained. The `default` model probe already
matched the release, so that provisional change was not implemented. Four
source files were verified against immutable pinned Git objects.

The focused run passed 22 methods in 32.064 seconds. The final serial
`rtk proxy make test` exited 0: all 44 native unit executables, 338 Python
methods in 579.123 seconds, no skips, and 407 pinned recovery-policy vectors.
The production artifact hash stayed fixed throughout Python discovery and
isolation/link checks; no concurrent production rebuild ran. Dependency and
credential-shaped diff review found only existing official stdlib/runtime
libraries and synthetic test peers. Evidence:
`docs/evidence/checkpoint5-reference.json`,
`docs/evidence/checkpoint5-tests.txt`,
`docs/evidence/checkpoint5-dependencies.txt`, and
`docs/evidence/checkpoint5-before.txt`.

Full URL normalization, encoded dot segments, ASCII punctuation, redirects
and non-host behavior remain unqualified. The checkpoint 4 binding mismatch
and unconnected recovery/affinity owners are unchanged. Reader/usage worker
files and the dirty experimental worktree remain untouched. All 71 contract
statuses, 426 platform obligations, capability statuses and six BLOCKED
release qualifications are retained; JavaScript SDK and full feature parity
remain incomplete. Future work must keep actual progress ownership distinct
from accepted control RPCs and preserve the verified main checkpoint cadence.

# Checkpoint 4: verified native DeepSeek boundaries

Checkpoint 3 was committed and normally pushed as
`338626fcd515be7cc33597e8d783062cae63dbdd`. Main started clean and equal to
origin/main. The three supplied Luna/MAX commits were inspected by exact diff,
with production callers and frozen sources traced before integration. Only H
`bc072760c93f86d8090953b911363fab868d7052` and I
`39363c8766e4a013a606fefda82533ac6a369c87` were applied with no-commit
cherry-picks. Their production source changes remain exact; H's Python test
now compares eight selectors through both real CLIs and fails if the oracle
is missing, and new 0.439.1 comparisons supplement I's older fixture evidence.

J `27cd3186c1bfed81c2917aea396ced14f729864e` is rejected. Its
`max(decoded weight, serialized bytes)` changes the frozen retention policy:
the pinned empty-array example weighs 2 bytes for key `é`, while J requires
4; escaped histories also evict sooner. Its relay test asserts that earlier
eviction without invoking the oracle. The physical-memory accounting concern
remains open, rather than counting the incompatible change as parity. The
separate `bf80ee8` header cap is still excluded. Reader/usage ownership and all
external worktrees, including the dirty experimental Sol checkout, are intact.

Sol's owned production slice rejects invalid Responses continuation identity
components before provider dispatch. It reuses the exact existing session
precedence for body, headers and turn metadata, then enforces the pinned
1,024 UTF-8 byte limit and C0/C1 control rejection on resolved response,
session and header turn-state identifiers. Twelve live invalid vectors return
the pinned 503 JSON/cache headers with zero upstream POSTs; five valid
boundary/precedence vectors still reach the provider exactly once. Before the
change all twelve invalid requests reached the provider. H's combo alias and
I's delayed timestamp regressions also failed against the previous checkpoint.

The full serial `rtk proxy make test` exited 0: 44 native unit executables,
337 Python methods in 572.229 seconds, no skips, and all 407 pinned
recovery-policy vectors. The earlier `make build`, three focused native units
and 29-method production/relay run also passed. No concurrent production
rebuild ran beside Python discovery or isolation/link checks; the artifact
hash stayed fixed. Seventeen reference files matched immutable Git objects.
Only existing local modules and official Mojo 1.2.0 stdlib are used. Tests
use isolated homes/config/storage, explicit synthetic environments and
ephemeral loopback peers, with no real credentials or paid provider traffic.

The added independent read-only review used the official launcher, whose
immutable configuration selected `gpt-6.1-sol` with effort `none`; it is not
claimed as Luna/MAX validation. Its complete structured report and the parent
caller-trace correction are retained. Integration, execution checks, staging,
commit and push remain main-owner operations. Evidence:
`docs/evidence/checkpoint4-reference.json`,
`docs/evidence/checkpoint4-tests.txt`,
`docs/evidence/checkpoint4-dependencies.txt`,
`docs/evidence/checkpoint4-before.txt`, and
`docs/evidence/checkpoint4-worker-review.txt`.

Full affinity remains a reproducible mismatch. With two buffered turns using
the same synthetic model/key, the release returns 200 then
503 `bound_continuation_unavailable` with one provider POST; Modex returns
two 200 responses with two POSTs. Reproduce using `observe_turns` in
`tests/test_deepseek_continuation.py`, turns
`[{"model":"deepseek-chat","input":"synthetic first"},
{"model":"deepseek-chat","input":"synthetic next","use_previous":true}]`
and two `buffered_reply(index, created=42)` responses, once for each of
`test_cli.ORACLE` and `test_cli.MODEX`. Exact observations are retained in the
reference evidence. The new guard does not implement binding acquisition,
credential/profile conflict resolution, targeted release or recovery.

All 71 contract statuses, 426 platform obligations, capability statuses and
six BLOCKED release qualifications are retained. The JavaScript SDK remains
BLOCKED; full feature parity and production recovery remain incomplete.
Continue with a verified native production slice or the separately owned
reader/usage workers after their deliverables are available. Preserve the
normal main commit/push cadence and do not count accepted RPCs as progress.

# Checkpoint 3: verified native redirect SSE

Checkpoint 2 was committed and normally pushed as
`1f5a68252c7600c5d09eb1ea99e79eff02ad45e4`. `git ls-remote origin
refs/heads/main` matched that local SHA; main was clean after the push. It
contains all four reviewed Luna source commits, native token-limit overrides,
44 native units and the complete 328-method Python passing run.

Sol continued immediately in `/tmp/modex-sol-error-sse-20261026`, then
integrated only the owned relay and new `tests/test_relay_streams.py`. The
provisional early >=400 SSE change was rejected: live 429 buffering and the
pinned upstream caller establish that such errors are buffered before
response dispatch. This corrects the earlier gap note rather than claiming
an incompatible change as parity.

The reachable runtime fix routes 3xx Responses SSE through a shared native
passthrough writer, preserving raw status/body/quota headers and no replay.
Text stream headers now discard non-ASCII values as `HeaderValue::to_str()`
does in the release. Native tests cover 302/307/308 on both routes, successful
Chat SSE, early chunks, downstream-reset cleanup, Connection filtering and
retained 4 MiB truncation. A live 307 through the actual Super CLI compares a
64 KiB prefix before EOF against the pinned release. The tested 3xx responses
have no Location header; redirect-following behavior is unqualified. The same
tests failed before the change (five failing assertions and three timeouts).

Seven source files were verified against immutable pinned Git objects.
Buffered >=400 errors retain the pinned 4 MiB cap. Streamed redirects retain
an additional 4 MiB Modex guard, so larger-redirect parity is still a visible
gap. The combined focused run passed all 31 methods in 53.518 seconds.
The final serial `rtk proxy make build unit test` exited 0: all 44 native
unit executables and 331 Python methods passed, with no skips; Python
discovery took 556.775 seconds. The 407 pinned recovery-policy vectors still
pass as a foundation check. The artifact hash stayed fixed throughout Python
discovery and sandbox link checks. Dependency/import/link and credential-shaped
diff review found no new implementation dependency, binding, product helper,
Python interop, generator, real credential or paid provider traffic.
The checkpoint uses explicit staged paths and a normal Sol-owned push. Evidence:
`docs/evidence/checkpoint3-reference.json`,
`docs/evidence/checkpoint3-tests.txt`, and
`docs/evidence/checkpoint3-dependencies.txt`.

All six release qualifications, the JavaScript SDK and production recovery
remain BLOCKED/unconnected as previously recorded. No broad parity status is
promoted. The external worker worktrees remain intact. The newly completed
combo-model worker commit `bc072760c93f86d8090953b911363fab868d7052` was
inspected but is not integrated or counted in this run. The isolated Sol
checkout retains its experimental diff; the reviewed final source is on main.
Continue with independently verified request/conversation runtime slices or
owned progress-aware recovery transport, preserving the checkpoint cadence.

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
removal and sanitized oversized-body failure. Follow-up checkpoint 3 caller
tracing corrects the initial gap description:
>=400 SSE is buffered before dispatch in both products; the actual stream
gap is 3xx Responses, with larger-redirect behavior still unqualified.

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
The immediate continuation used `/tmp/modex-sol-error-sse-20261026` for
redirect SSE passthrough and stream-header validation. Its final scope,
caller-trace correction and integrated validation are recorded in checkpoint 3
above. Isolated worker boundaries and verified commit/push cadence continue.

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

Anthropic Messages web search stays in its proven request/response shape. The
adapter rejects non-string or multiple-message input, mixed tools and extra
request fields before the provider POST; it rejects unknown buffered blocks,
citations, result fields and SSE event shapes instead of completing a partial
response. Oracle controls document the release behaviors that differ, and the
local rewrite driver verifies zero upstream requests for rejected requests.
`docs/evidence/anthropic-web-search-04392.md` records those controls and the
focused checks. No parity status was promoted.

Use GPT-6 Luna agents in parallel for independent implementation, validation
and review; file ownership must stay disjoint. This user preference is also
recorded in `AGENTS.md`.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.

The active 0.165.1 streaming characterization now covers a result completing
while another search input remains open, deltas for that search across the open
result block, a new search starting during an open result, and a valid empty
result array. The parser tracks open search and result blocks independently;
result content still passes array and item validation. The real-process
comparisons match the pinned oracle, and the full focused stream suite passes
26 tests after the production build. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-stream.md`. These cases add no general
Anthropic or provider parity claim; unsupported shapes and targets remain gaps.

Image blocks that reuse an active text, function-tool, or server-search index
remain a verified stream gap. Both 0.165.1 and 0.439.2 retain subsequent
deltas, while current Modex can close the tracked block at the image stop and
fail on later content. Text, tool, search, repeated-start and result-clearing
controls are in the two provider characterization suites. The release ignores
image starts and its stop event only clears ignored result indices; index-only
stops cannot be safely attributed to overlapping blocks. No production
heuristic was retained. Fixing this requires a broader stop-state redesign that
matches the release across text, tool, search and result transitions. Other
stop orders remain unverified. Evidence: `docs/evidence/baseline-0.165.1/anthropic-stream.md`.
