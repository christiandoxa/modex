# Current work: Prodex 0.166.0 parity and CI

Doctor missing-requirement and conflict diagnostics match 54 tested two- and
three-option 0.166.0 cases. The release accepts `--runtime --json --redacted`,
which Modex still rejects; doctor runtime remains unimplemented. See
`docs/evidence/baseline-0.166.0/doctor-missing-requirement-order.md`.

Buffered provider metadata matches the active 0.166.0 process for selected
empty and whitespace fields, first-choice selection, and request metadata
collisions. The historical 0.439.2 source has a different whitespace
expectation; see `docs/evidence/baseline-0.166.0/provider-metadata.md`.

For a non-object upstream SSE chunk, a bounded active-oracle probe records
headers without a body or socket closure within the observation window; Modex
instead emits a terminal `response.failed` event. Missing-choices and invalid
JSON controls match. This fail-closed difference remains a parity gap; see
`docs/evidence/baseline-0.166.0/malformed-sse-nonobject.md`.

The production CLI supports `doctor --install`, including one optional valid
`--tail-bytes` value, with bounded local prerequisite probes and a plain Install
Checks panel. Active 0.166.0 process tests cover accepted argument orderings,
invalid and duplicate flags, synthetic present/missing tools, probe limits, and
no state creation. Selected invalid boolean diagnostics also match. Probe
environments exclude provider secrets; output and paths are redacted and
terminal controls escaped. TTY rendering, Caveman integrity
validation, descendant cleanup and other doctor modes remain incomplete or
different; see `docs/evidence/baseline-0.166.0/doctor-install.md`.

Hosted Fast CI run `41137805159` on `187e7f46e7d52aaa3aa2c6fb721a369b72947406`
failed while compiling the native Gateway test: its `_response_headers` call
omitted the new duplicate-content-type argument. The test call is corrected
and now checks both buffered and streaming duplicate handling. Its focused
native build and execution passed; the failed hosted run is not a CI pass.

The Responses relay now emits the tested 0.166.0 204 event-stream failure
instead of closing before headers. This exceptional 204 stream is explicitly
restricted to the translated event-stream path and closes after its terminal
chunk; the oracle kept the tested keep-alive socket open. Generic 204/304
stream starts remain rejected, and a pipelined request is not forwarded after
the Modex 204. See `docs/evidence/baseline-0.166.0/responses-204-stream.md`.

Buffered DeepSeek passthrough now retains the last valid duplicate
`Content-Type` at its first position, matching tested active-release responses.
Streaming responses retain their observed duplicate headers; first-value SSE
classification and unrelated duplicate headers are unchanged. See
`docs/evidence/baseline-0.166.0/duplicate-content-type.md`.

Mixed Anthropic tool history now requires function arguments to decode to a
JSON object, matching the active release's pre-provider HTTP 400 for arrays,
scalars and null. The separate OpenAI Chat route retains its observed behavior.
Active process comparisons cover both Anthropic modes and Chat controls; see
`docs/evidence/baseline-0.166.0/anthropic-tool-argument-object.md`.
Valid function-history blocks also match tested wire bytes, including original
argument whitespace and key order. Duplicate decoded keys remain normalized in
Modex while the reference forwards them; that is a documented parity gap.

Bodyless 204 and 304 DeepSeek SSE passthrough responses now advertise
`Connection: close` along with chunked framing, matching the active release.
The focused raw-socket comparison also verifies that both implementations
accept a second request on the same connection in the tested case; the header
does not establish physical closure. JSON 204/304 and SSE 205 controls pass.
See `docs/evidence/baseline-0.166.0/bodyless-sse-connection.md`.

Quota now exposes the active release's static short and expanded help, including
selected argument diagnostics, without entering quota execution. Isolated
0.166.0 process comparisons cover the help routes and a no-state runtime guard;
quota execution and other targets remain unimplemented or unverified. See
`docs/evidence/baseline-0.166.0/quota-help.md`.

The DeepSeek Anthropic route now emits function-tool fields and stop sequences
in the same order as the active release for six tested mixed-tool requests.
Before the change their JSON values matched but raw provider-request bytes
differed. The production build, eight active provider-shape and Anthropic
stream tests, and the dependency audit passed; see
`docs/evidence/baseline-0.166.0/anthropic-request-wire-order.md`. Other request
shapes, provider behavior and release targets remain unqualified.

Profile parsing now matches selected 0.166.0 diagnostics when `--` appears
before a subcommand, including multiple suggestions for direct typos and no
suggestions for help aliases. Sixteen isolated process cases and the 21-test
active baseline module passed after the follow-up fix. Profile operations
remain guarded and unimplemented.

The active compact regression now covers the JSON nesting boundary: 123
nested payload arrays retain context, while 124 yield the matching parse-failure
summary. All four compact tests passed with synthetic requests in a private
loopback-only namespace; wider compact and profile-runtime parity remain open.

The DeepSeek loopback boundary now accepts selected equivalent IPv6 `::1`
spellings and emits the canonical Host authority. The native Gateway test and
five active-oracle authority tests passed, including non-loopback rejection, in
a private loopback-only network namespace with isolated temporary state. The
production build and dependency audit also passed. This does not qualify other
IPv6 forms, providers, release targets, or full parity; see
`docs/evidence/baseline-0.166.0/provider-ipv6-loopback.md`.

On `bc3a6c69966ac3ce143e2722cf408fe935bac45f`, eight active-oracle
policy-capacity and Guardian API-key tests passed in a private loopback-only
namespace with isolated temporary state. With one API key, the tested 503 is
forwarded unchanged; with multiple keys, this distinct API-key route follows
the release's status-based retry behavior. These tests do not implement or
qualify profile-backed 503 handling, Guardian affinity, or socket reuse.
The isolated active WebSocket fallback framing comparison also passed on the
same build; it does not cover reviewer routing-pin socket reuse.

The DeepSeek URL boundary now accepts selected percent-encoded numeric
loopback hosts such as `127%2e1`, matching 0.166.0 in Chat and Anthropic
process comparisons. Decoded values still pass the numeric `127/8` check;
encoded separators, controls, malformed escapes, hostnames and non-loopback
destinations remain rejected. Other host spellings and release targets remain
unqualified; see `docs/evidence/baseline-0.166.0/provider-percent-encoded-host.md`.
Full native `make unit` passed on `89d1dc406ca2a8325e23e2889cedd43340542abf`;
this is not full CI or release qualification.

The DeepSeek numeric-loopback HTTP relay now uses port 80 for omitted and empty
ports and omits the default port from the Host header. A manual, isolated
0.166.0 process comparison covers IPv4 and IPv6 loopback forms; native Gateway
checks cover authority selection and formatting. The port-80 comparison is not
automated in CI because the existing bubblewrap launcher cannot bind that port.
Other providers, URL forms, and release targets remain unqualified; see
`docs/evidence/baseline-0.166.0/provider-default-port.md`.
Full `make unit` passed on `7834b9284531833cd16a1349c80bd64062ffa89b` after
the default-port change; this does not establish complete CI or parity.

The DeepSeek loopback transport now canonicalizes tested numeric IPv4 aliases
such as `127.1` and integer, octal, hexadecimal, and trailing-dot forms, while
requiring a numeric `127/8` destination. Active 0.166.0 comparisons cover Chat
and Anthropic routes, canonical Host headers, padded ports, and rejection of
selected malformed and non-loopback authorities. Hostname and non-loopback
guards remain in place. Other numeric spellings and targets remain unverified; see
`docs/evidence/baseline-0.166.0/provider-base-url-authority.md`.
Full `make unit` passed on `29d7bae37098574974fcdeac753cff64efd9ab99`, after
the numeric-loopback change. This is native unit evidence, not full CI or
other-platform qualification.

The DeepSeek Super conversation cache now scopes tool-history lookup by an
explicit session ID. A synthetic active-oracle comparison shows that requests
with different session IDs or only one session ID no longer import the other
request's prompt in Modex, while 0.166.0 does. Missing IDs still share history
within the same credential, and client-supplied session IDs do not authenticate
an owner. Both products reject the tested same-session follow-up with 503. This is a limited
security-preserving difference, not full ownership or continuation parity; see
`docs/evidence/baseline-0.166.0/deepseek-session-tool-history.md`.

Stored tool-call history is now also scoped by a process-local credential
identity. Active 0.166.0 process tests cover buffered and streamed histories,
duplicate keys, cross-key rejection, concurrent lookups, and suppression of a
cross-key retry after cached history is selected. The active release forwards
the tested history across keys. Cached-history retry on the native Anthropic
route, eviction, restart, and adversarial session identifiers remain unverified;
see `docs/evidence/baseline-0.166.0/deepseek-credential-history.md`.

Doctor's `--json` and `--bundle` conflict diagnostics now follow the tested
0.166.0 argument order. Ten isolated process comparisons and the native
inspection check passed; doctor execution remains unqualified. See
`docs/evidence/baseline-0.166.0/inspection-cli-conflict-order.md`.

Logout help and selected parser precedence now match the active 0.166.0
release in isolated process comparisons. Valid non-help logout requests still
reach the unimplemented guard; logout execution and profile behavior remain
open. The production build and dependency audit passed, and the focused
root-help module covers the comparison and no-execution controls. See
`docs/evidence/baseline-0.166.0/logout-help.md`.

Hosted Fast CI run `41128005328` on `ce6c75654af2b5546d112ac74a16dffb5f863fe6`
passed the native build and units, three WebSocket sandbox tests, 124 active
0.166.0 tests, 52 independent relay tests, 121 historical 0.165.1 tests, eight
width-memory tests, and both helper shards. It failed closed for missing
historical 0.439.2 and 0.439.5 oracles; it does not validate the later default
port change or establish full CI.

Earlier hosted Fast CI run `41124656633` on `627d555552af519794fd6099fd269861d575e68a`
passed the native build and units, three WebSocket sandbox tests, 121 active
0.166.0 tests, 52 independent relay tests, 121 historical 0.165.1 tests, eight
width-memory tests, and both helper shards. The overall run failed closed
because required historical 0.439.2 and 0.439.5 oracles were unavailable. It
does not validate the later numeric-loopback change or establish full CI.

Earlier hosted Fast CI run `41120572378` on `37c78129280c4c5666a5a1562b2f28201e9e127c`
passed the three WebSocket sandbox tests, 115 active 0.166.0 tests, 52
independent relay tests, 121 historical 0.165.1 tests, eight width-memory
tests, and both helper shards. It failed closed because required historical
0.439.2 and 0.439.5 oracles were unavailable. This does not qualify full CI,
the missing historical lanes, or later commits.

Hosted Fast CI run `41123086672` on `17e0eab1a227e16e443eb6f90ed29c0de1884861`
failed during `focused-build make unit`: the Gateway native test still called
`_history` with its old three-argument signature and expected a string, while
the helper now requires a credential index and returns history ownership flags.
`tests/test_gateway_cli.mojo` now checks explicit credential scopes, same-key
history, cross-key rejection and namespace isolation. The targeted Gateway and
ProviderConversation native tests compile and pass. Full `make unit` also
passes all native targets at `e37a256b87cb92720fd8ccede27124d186c40f03` with
Mojo 1.2.0. The hosted compile failure was a stale test callsite; this does not
clear the missing historical-oracle lanes or establish hosted CI success.

Earlier hosted Fast CI run `41103940113` on `3fbf27876a53c45ffb544eb33b82d520a9571970`
passed its build and native checks, 102 active 0.166.0 Python tests, 52
independent relay tests, 121 historical 0.165.1 tests, eight width-memory tests,
and both helper shards. The product dependency audit passed for 73 Mojo files.
The run failed closed because the required historical 0.439.2 and 0.439.5
oracles were unavailable; their dependent lanes were blocked and the 0.439.2
source lane was skipped. Neither historical lane is counted as passed. This is
evidence for the recorded commit, not full CI or parity qualification.

The active 0.166.0 local-rewrite WebSocket fallback comparison is now
scheduled by Fast and Full CI in a required bubblewrap network namespace. The
wrapper keeps a private tmpfs `/tmp`, clears the child environment, assigns private
HOME/XDG paths, and mounts workspace, binary, oracle, Python runtime and Mojo
toolchain inputs read-only. Inputs below host `/tmp` are rebound explicitly;
the manual preflight rejects writable `/tmp` search paths and scratch-path
overlap. Its dedicated CI tests cover the real checksum-verified oracle
comparison plus synthetic `/tmp` and normal host-path layouts. Local build,
three focused tests, shell/workflow validation and the test census passed;
hosted Fast CI run `41120572378` passed the sandbox module. Details are in
`docs/evidence/baseline-0.166.0/websocket-fallback-ci-sandbox.md`.

DeepSeek Super now percent-encodes ASCII spaces in numeric-loopback upstream
path segments, matching the verified 0.166.0 process for synthetic paths.
Authority whitespace, C0/DEL controls, credentials and non-loopback destinations
remain rejected. The active process and native URL checks are described in
`docs/evidence/baseline-0.166.0/provider-base-url-scheme.md`.

The DeepSeek loopback provider now accepts case-insensitive `http` URL schemes,
matching the verified 0.166.0 release for a synthetic `HTTP://` request. Its
existing numeric-loopback and credential-free restrictions remain in place.
The production build, active provider process comparisons, and native URL
rejection checks passed; see
`docs/evidence/baseline-0.166.0/provider-base-url-scheme.md`. HTTPS and other
provider transports remain unqualified.

The DeepSeek local compact formatter now trims a model's full whitespace
suffix before applying the bounded summary limit. This preserves input counts
and synthetic conversation context when an otherwise short model is followed
by more than 24 KiB of whitespace. Active release comparisons include Unicode
whitespace, an all-whitespace model, and a long internal gap with a nonblank
suffix. Broader compact input shapes remain unqualified; see
`docs/evidence/baseline-0.166.0/local-compact-fallback.md`.

The DeepSeek local relay now handles `POST /v1/responses/compact` with the
0.166.0 local fallback summary, response body and `x-prodex-compact-*` headers.
`tests/test_local_compact_gap_01660.py` compares ten compact requests against
the verified oracle, covering generic and tool content, whitespace, non-object
items, 24-item retention, UTF-8 snippet/summary caps, an 8 MiB model, 20,000
items, nested input, invalid JSON, query and method routing, and a neighboring
unsupported path. The synthetic fixtures observe no upstream request. These
checks run in isolated user, mount and network namespaces and do not qualify
all input shapes or full parity. The 0.166.0 oracle accepts an invalid
`Authorization` value for compact and returns 200; Modex rejects the same
request with 401 in its shared request parser before `_serve`. Keep this
client-token guard; record the difference as a security-preserving baseline
mismatch rather than weakening authentication. This local fallback is
separate from the unimplemented profile-backed remote compact 503 behavior.

Active 0.166.0 process comparisons now cover unknown short options after valid
`info` and `status` options. Modex preserves the full `[OPTIONS]` usage for
these errors, matching the release; focused process cases also confirm current
errors and long-option typo suggestions remain unchanged. See
`docs/evidence/baseline-0.166.0/inspection-cli-unknown-short-usage.md`.
The active parser also matches 0.166.0 interval-error precedence: attached
values fail immediately, while separated values can be superseded by a later
unknown option or literal operand. Recognized-option controls preserve the
earlier interval error. These isolated comparisons are documented in
`docs/evidence/baseline-0.166.0/inspection-cli-interval-precedence.md`; they do
not establish broader CLI or status parity.

The 19 active-release process modules listed in `scripts/ci/run-fast.sh`
passed 78 tests in 106.422 seconds against the verified 0.166.0 oracle on
`a9d4ff15ea0eb714a3159185e3c327f22727cb2b`. The Modex executable SHA-256 was
`9d67f75019604993452e5198fc4ce89a73efdb9a67fa94eb19bfc78d3dd62b17`;
its production sources match that commit. The run used a private user, mount,
and loopback-only network namespace, read-only worktree and oracle, synthetic
fixtures, and isolated temporary storage. It retained no log file. The three
CI helper modules on the same script line were not part of this process run.
Some tests characterize known gaps or exercise Modex alone, so this result is
not a full parity or full CI verdict.

The local relay keeps an HTTP/1.x connection reusable after a 426 WebSocket
fallback only when the request was fully captured with unambiguous fixed-length
framing and no duplicate Connection or Upgrade fields. An active 0.166.0
process comparison covers contiguous and fragmented bodies, explicit
zero-length bodies, a first request with `Connection: keep-alive`, an
unauthorized follow-up, conflicting framing, and a truncated body. Modex
separately rejects an unauthorized second request with 401 and closes on
ambiguous framing; the oracle accepts those follow-ups, so those controls
remain security-preserving differences. The 2026-10-30 manual run was outside
automatic discovery and Fast/Full CI. Its preflight required private tmpfs and
loopback-only networking, and it could not preserve Python or oracle inputs
below host `/tmp`; direct host invocation failed before comparison. That setup
is historical. Fast and Full CI now schedule the real-oracle comparison through
the bubblewrap runner, which supports host `/tmp` inputs with explicit
read-only binds. CI does not exclude the regression. Local checks and the
hosted sandbox module passed on the recorded commit. This does not implement WebSocket
transport or qualify other targets. See
`docs/evidence/baseline-0.166.0/local-relay-websocket-fallback.md` and
`docs/evidence/baseline-0.166.0/websocket-fallback-ci-sandbox.md`.

Selected DeepSeek and Anthropic stream ordering cases now have active 0.166.0
process comparisons, including partial errors and search-mode configuration.
Two provider request bodies differ in object member order but match as
duplicate-free JSON structures. These synthetic cases do not qualify broader
stream parity; see `docs/evidence/baseline-0.166.0/provider-stream-edge-ordering.md`.

Fast and full CI now attempt independent historical checks after recording a
missing required 0.439.2 reference; dependent lanes remain blocked and the
overall result still fails closed. Synthetic routing tests cover missing oracle,
missing source, and all references available. Actual hosted CI still requires
the verified historical assets; this change does not establish a CI pass.
Hosted Fast CI run `41097956030` on
`c63b708b17270152dbe17e1f194680c1f0124091` verified the active 0.166.0 oracle,
passed the production build and native units, the 94-test active lane, 52
independent relay tests, 121 historical 0.165.1 tests, and eight independent
width-memory tests. Both helper shards passed. The run failed closed because
the required historical 0.439.2 and 0.439.5 oracles were unavailable; their
comparisons were reported blocked. It did not validate a complete CI run,
historical parity, or later commits.
Missing 0.439.5 acquisition now receives the same fail-closed treatment: both
scripts mark its oracle-dependent lanes blocked, continue independent checks,
and return failure; Full CI skips the complete suite while that required
reference is unavailable. Synthetic routing coverage exercises both scripts;
all 21 `test_ci_oracle_routing.py` tests passed with fake reference tools, and
both CI scripts passed `bash -n`. This verifies routing only, not hosted CI or
the missing historical comparisons.
Hosted Fast CI run `41087191880` on `8f458fa6f1a047db726b4808f031abc6fb14e0df`
was superseded and cancelled after its `Run fast CI` step failed in the bundled
width-memory module: `SessionTextMemoryParityTests.setUpClass` still required
the unavailable historical 0.439.2 oracle. The native width measurement and
the two oracle comparisons now live in separate modules. Fast CI continues the
independent width checks and reports the missing session comparison as
`width-memory-session-parity: BLOCKED`; Full CI does the same before marking
the complete suite blocked. If 0.439.2 is available but another required
reference blocks the full suite, Full CI runs the parity lane independently;
with all references available, `make test` discovers it once. Synthetic
routing and strict-discovery checks passed locally with missing and available
references, along with the seven
memory-metric tests and both shell syntax checks. Hosted validation of this
change is pending; no 0.439.2 comparison or full-suite pass is claimed.
Hosted Fast CI run `41074130130` also exposed a historical 0.165.1 live-log
fixture that retained a separate 0.439.2 holder binary. Its helper now receives
and restores the same 0.165.1 oracle as the rest of that suite. The originally
failing test passed with 0.439.2 absent in a private loopback-only namespace.
An initial broader local log run failed because four native test drivers had
not been built; after building them, the complete 40-test log suite passed.
The seven other independent 0.165.1 modules passed 81 tests separately in the
same isolation. The official 0.439.5 tag and release were unavailable on a
subsequent lookup, so the later historical lane also remains blocked. These
checks do not qualify the missing historical lanes or the complete CI run.
In a clean checkout of `d16dd4855498517924f4fa1cb8a657352afec9d5`,
`make build unit` passed, and the exact active Fast CI Python lane passed 56
tests under a private user, mount and network namespace with only loopback and
no default routes. The runner retained no log file. This is evidence for that
checkout and active lane only, not a full-suite or hosted CI result.

`tests/capture_cli.py` now verifies the pinned 0.166.0 baseline, release
identity and oracle checksum before capturing. It writes
`docs/cli-inventory-0.166.0.json` and
`docs/evidence/baseline-0.166.0/help/`, preserving the historical 0.439.1
inventory and fixtures. Four focused tests passed; a real capture recorded 35
routes and 326 option mentions with no stderr or state mutations. A fresh
0.439.1 capture remains unavailable because no checksum-verified matching
oracle was available for this run. This is an unavailable historical input,
not a failure of the fixed active capture script. Help captures are discovery
evidence only and do not establish parity.

Unknown top-level `help` operands now match isolated 0.166.0 process
comparisons, including the exit code, diagnostic, custom executable name, and
no-state behavior. The production dispatcher leaves all declared visible and
hidden root commands on their existing paths. Evidence and the focused command
are in `docs/evidence/baseline-0.166.0/root-help-unknown-command.md` and
`tests/test_root_help_errors_01660.py`; this does not qualify valid but
unimplemented help targets or broader CLI parity.
The same isolated test covers flag-shaped operands and the `help help` route,
including the release's different nested-error usage.

Set `TASK_SCRATCH` to a private temporary directory when reproducing commands.
Paths under `$TASK_SCRATCH` are generalized per-run locations; no host-specific
scratch path is part of the handoff.

The active target is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its Linux x86-64 release and
SHA256SUMS have been verified; see
`docs/evidence/baseline-0.166.0/reference-verification.json`. An installed
`prodex` is separate from the pinned test oracle. Versions 0.165.1 and 0.439.x
are historical controls only. Codex is also a separate installation; the
isolated comparison uses the verified Codex 0.166.0 executable.
Existing 0.439.2 acceptance routing
was caused by the README and baseline pin, `test_cli.py` defaulting
`PRODEX_ORACLE` to 0.439.2, and CI aliasing the active oracle/source to 0.439.2
variables. Historical tests and CI routing now use explicit versioned
overrides. These observations cannot establish 0.166.0
parity. All six release targets, Guardian routing and cookie affinity,
WebSocket pin reuse, policy-capacity responses, offline replay and loopback
TLS remain open. The previously running 0.439.2-based ownership suite was
interrupted after the target change; its result is not a 0.166.0 qualification.

An isolated Super launch showed that 0.166.0 sends `prodex-hook-trust` client
version `0.166.0` to the synthetic Codex app server while the prior Modex
build sent `0.439.2`. The production hook initializer now uses the active
version. `test_active_baseline_01660.py` compares real 0.166.0 and Modex
processes and retains isolated synthetic provider and Codex fixtures; the
older 0.165.1 and 0.439.2 expectations remain explicitly historical. This
qualifies only the tested initialize request, not Guardian, TLS, or overall
Codex 0.166.0 compatibility.
Isolated 0.166.0 process comparisons also match Super help and selected parser
diagnostics without creating state. For `super exec --model --help`, the
release instead proceeds to a no-profile error and creates housekeeping
files, while Modex stops at its unimplemented startup guard; this is a
recorded difference, not a parity pass.
Super now rejects unknown optional-tool IDs and reports invalid sub-agent URLs
as typed argument errors before help, matching selected 0.166.0 process cases.
It also validates `--sub-agent-provider` against the active release's provider
IDs and aliases before later help flags. The process test covers each alias,
invalid separated/attached values and help precedence. A native test covers
`LOCAL_OPENAI` normalization before the local URL requirement; delegated
execution remains unimplemented.
For `--cli agy`, selected missing or non-Gemini providers now receive the
0.166.0 provider guard after existing option validation. Isolated comparisons
cover four launch forms and selected error-precedence controls. Shared Super
parsing now also matches selected 0.166.0 conflict and required-option
diagnostics before and after `exec`. A further isolated matrix covers 45
constraint/option-order combinations without state mutations. Other
combinations remain unqualified,
and the valid Gemini launcher remains unimplemented; see
`tests/test_super_cli_01660.py`.
Plain provider URL validation runs after help parsing but still before startup;
see `docs/evidence/baseline-0.166.0/super-cli-validation.md` for the parser
scope and test commands.
The 0.166.0 `--sub-agent-url` parser accepts leading/trailing ASCII spaces and
retains the raw value downstream. Modex validates a space-trimmed view but
preserves those spaces. It continues to reject C0/DEL controls, credentials,
query, fragment, invalid authorities and non-ASCII whitespace. Other URL forms
that the reference rewrites remain documented conservative mismatches. A
sanitized process probe confirms accepted input still reaches the Super startup
guard; the local sub-agent runtime remains unimplemented.
Selected `doctor` help and invalid argument diagnostics also match isolated
0.166.0 comparisons; valid execution still reaches the unimplemented guard.
Other argument combinations remain unqualified.
Gateway without an explicit provider now reaches the existing fail-closed
profile preflight. Selected empty-home and profileless-config diagnostics
match 0.166.0; a synthetic selected profile still stops at Modex's existing
state guard without modifying state or auth. The release starts its Gateway
for that fixture in an isolated network namespace. This covers preflight
only, not profile lifecycle, broker or Gateway runtime parity; see
`tests/test_gateway_default_01660.py`.
Gateway now matches selected 0.166.0 diagnostics for unknown hyphen-prefixed
arguments, missing values and help order. Isolated controls also verify that
synthetic API keys are not echoed. Successful Gateway startup and broader
parser combinations remain unqualified; see
`docs/evidence/baseline-0.166.0/gateway-cli-argument-errors.md`.
For DeepSeek `custom_tool_call`, both production request paths now encode the
input as a string inside the function arguments, using compact JSON text for
non-string values and an empty string for a missing input. The active 0.166.0
process comparison covers both paths, nested object key ordering, Unicode,
escaping and argument precedence; ordinary function calls retain their tested
precedence. Broader tool conversion remains unverified.
Anthropic namespace tools also reach the shared Responses mapper: selected
automatic and forced-mode requests match the active release, and four malformed
child controls return matching errors before provider dispatch. See
`docs/evidence/baseline-0.166.0/anthropic-namespace-tools.md`.
Custom tool calls and outputs now also reach that validated mapper in the
Anthropic Messages path. Synthetic 0.166.0 process comparisons cover automatic
and forced mode, an ordinary function-call control, and malformed inputs that
remain rejected before provider I/O; see
`docs/evidence/baseline-0.166.0/anthropic-custom-tool-calls.md`.
The DeepSeek Super launch catalog matches the active 0.166.0 process for
selected known models, retired aliases, priority gaps, reasoning choices and
escaped custom IDs. This qualifies only the tested Linux x86-64 launch cases,
not provider traffic or broader Super parity; see
`docs/evidence/baseline-0.166.0/deepseek-model-catalog.md`.

Codex 0.166.0's direct help documents `--json` as JSONL output, and its
duplicate-option diagnostic confirms `--experimental-json` is a hidden alias.
The active Prodex oracle forwards the alias to the synthetic Codex client;
Modex stops before launching it, while the existing `--json` control reaches
the client. Keep this argument guarded while the launcher injects
`--dangerously-bypass-approvals-and-sandbox`. No real Codex Super run or JSONL
model output was used; see
`docs/evidence/baseline-0.166.0/super-experimental-json-guard.md`.

One synthetic `log last --json` transcript, upstream payload and token-usage
snapshot matches the active release, including bearer-token redaction and
unchanged session bytes. This does not establish live logging or broader
redaction parity; see `docs/evidence/baseline-0.166.0/log-last-synthetic.md`.
For one ambiguous Unicode-separated synthetic credential, the release emits
the suffix while Modex masks it. Modex retains that safer behavior. An empty
home session-list comparison also records missing startup locks and
housekeeping in Modex. These are characterized gaps, not parity passes; see
`docs/evidence/baseline-0.166.0/session-log-process-gaps.md`.
An additional active-release comparison covers selected session output,
filtering, timestamps and timezones; it does not qualify startup side effects
or profile recovery. See `docs/evidence/baseline-0.166.0/session-output-matrix.md`.
Session inspection now falls back to epoch zero for a file mtime before the Unix
epoch, matching the active release when no record timestamp overrides it.
The isolated comparison covers 18 combinations of file formats, boundary
timestamps, and record timestamp precedence; remaining limits are in
`docs/evidence/baseline-0.166.0/session-pre-epoch-mtime.md`.
Invalid UTF-8 in `.json` sessions now reports the active release's path and
byte-offset diagnostic after rejecting the input. Isolated comparisons cover
malformed sequences, JSONL controls, and valid Unicode; no file contents are
echoed. Modex escapes terminal controls in the error path where the release
emits them raw; this is a retained safety difference. See
`docs/evidence/baseline-0.166.0/session-json-invalid-utf8.md`.

DeepSeek `low` reasoning effort now remains `low` in both request paths,
matching 0.166.0 rather than the 0.439.2 mapping to `high`. Isolated process
comparisons cover flat and nested effort, tool choice, continuation, and other
effort controls. The historical comparison records the 0.439.2 divergence.
These cases do not establish broader DeepSeek parity.

Buffered Chat Completions and Responses passthrough also match the active
0.166.0 oracle for ASCII/HTAB turn-state headers, non-ASCII omission, binary
bodies, hop-header filtering and one upstream POST per request. The earlier
non-ASCII mismatch capture remains historical; this focused comparison does
not qualify streaming metadata or broader provider parity. See
`docs/evidence/baseline-0.166.0/provider-buffered-metadata.md`.
The passthrough path now also lowercases validated forwarded header names,
matching a synthetic 0.166.0 503 response on the wire. Header names are
case-insensitive; status, body, values and generated framing remain covered
separately. This does not implement profile-backed policy handling; see
`docs/evidence/baseline-0.166.0/local-relay-response-header-casing.md`.
All active
0.166.0 callers of the shared process fixture now set its temporary update
metadata to 0.166.0 explicitly; the historical default remains unchanged. The
25-method active subset, including the manual fragmented-tool-stream case,
passed inside a private namespace.

In the Anthropic Messages route, untyped input items without text no longer
fail preflight solely because `content` is absent. Pinned 0.166.0 process
comparisons cover selected missing, empty, null and scalar content, mixed
function calls and outputs, and typed invalid-item rejection before provider
dispatch. Other input shapes and broader Anthropic parity remain open; see
`docs/evidence/baseline-0.166.0/anthropic-missing-content.md`.

Active-oracle Anthropic search streams now match in the tested empty-start,
fragmented and first-object cases. The comparison includes malformed suffixes
ending in `}` and the release's first-object query behavior; incomplete suffixes
and outer whitespace yield an empty query list. Multi-object protocol validity
and broader Anthropic parity remain unqualified. The manual test requires an
isolated network and private temporary storage; see
`docs/evidence/baseline-0.166.0/anthropic-stream-query-fragments.md`.

Anthropic tool streams now defer validation when `message_delta` has an absent,
null, or non-string `stop_reason`, matching Prodex 0.166.0 until
`message_stop`. The active process comparison also covers a string-reason
control and malformed arguments rejected at `message_stop`; trailing frames
are ignored after that final failure. Other Anthropic stream orders and broader
provider parity remain open; see
`docs/evidence/baseline-0.166.0/anthropic-stream-stop-reason.md`.

DeepSeek streamed text-item IDs now use the 0.166.0 hash mapping for UUIDv7
entropy and sequence, checked against fixed pinned-Rust vectors. The process
comparison covers the ID shape and selected event consistency. Modex still
lacks the release's per-instance sequence seed: audited public Mojo 1.2
`std.os.process` and `std.runtime` interfaces expose no PID or current-thread-ID
getter, while the shipped `std.sys._libc` exports neither POSIX `getpid` nor
`pthread_self`; project rules prohibit adding native bindings. The counter now
uses `fetch_add` return-before-wrap semantics under its existing lock; an
active-release concurrent process comparison checks distinct local sequence
values. Generated prefixes can collide, and full generator parity and global
uniqueness remain unqualified. See
`docs/evidence/baseline-0.166.0/deepseek-stream-item-ids.md`.
An additional isolated 0.166.0 matrix compares eight translated provider
request bodies and seven streamed response shapes through both real processes;
the translated bodies match exactly and event JSON matches after normalizing
only the generated text-item ID. The focused test is
`tests/test_provider_shapes_01660.py`; evidence is in
`docs/evidence/baseline-0.166.0/provider-shape-matrix.md`. These cases found no
new production mismatch and do not establish broader provider parity. The
active process matrix now also checks a synthetic local metadata tag colliding
with provider `finish_reason`; both processes preserve the local tag object.
This qualifies only that response merge case. The separate release-metadata
local-Git-tag contract remains unverified because Modex has no release-sync
runtime path.
The same active test now pins direct `flash`, explicit current and compatibility
IDs, `combo:flash,pro` retries after structured 404/429 errors, and malformed
empty combo inputs. Modex and the active oracle produce matching provider
request bodies and tested statuses. Historical 0.439.2 expectations remain
version-specific; this is not cross-release parity evidence.
One synthetic streamed function call split over two argument deltas, followed
by a usage-only chunk, also matches the 0.166.0 process. This manual isolated
check is scoped to that case; see
`docs/evidence/baseline-0.166.0/deepseek-tool-stream.md`.

The official historical 0.439.2 tag currently resolves to no ref and its
SHA256SUMS URL returned 404 on 2026-10-30. Previously verified local bytes
are not present in the current oracle cache, and fresh hosted runners cannot
acquire that historical oracle until its official asset or a verified cache is
provisioned. The
historical lane must fail closed rather than count a missing oracle as a pass.

The 0.166.0 policy-capacity change is in the profile-backed Responses and
standard/compact HTTP runtime. Modex does not yet implement those account
profile paths, so their 503 passthrough and no-quota-rotation behavior remain
unverified gaps. The separate DeepSeek API-key path behaves differently: real
0.166.0 and Modex processes both retry a synthetic 503 with key B after key A;
with one key both forward its body unchanged. The active-release tests in
`test_policy_capacity_01660.py` retain that distinction and include an overload
control. They do not establish profile-runtime policy parity.
The five active identity and API-key tests also passed with both historical
oracle overrides set to nonexistent paths, confirming those tests do not
require a 0.165.1 or 0.439.2 binary.
A separate isolated three-case DeepSeek 503 differential also passes; generic
profile-runtime policy remains unimplemented. See
`docs/evidence/policy-capacity-01660-process.md`.
An additional isolated Super launch uses a synthetic Codex HTTP client and
one synthetic provider key to compare the 503 body through both real launchers.
It checks one upstream request and overlay cleanup, not the real Codex binary
or profile-backed policy; see
`docs/evidence/baseline-0.166.0/policy-capacity-synthetic-codex.md`.
Guardian reviewer metadata does not pin the DeepSeek API-key path in two
isolated comparisons, including quota retry; this does not implement the
profile-backed Guardian broker or cookie routing. See
`docs/evidence/baseline-0.166.0/guardian-api-key-scope.md`.

The official Codex 0.166.0 Linux binary passed the real local-auth test against
Modex through a synthetic loopback provider inside a network namespace with
no default routes. Its release archive and executable hashes, isolation and
reproduction command are in `docs/evidence/baseline-0.166.0/codex-offline.md`.
This is one local-auth case, not general Codex or Guardian parity.
Both focused real-Codex tests also passed on the `c7cb160` production sources
in a private user, mount, and loopback-only network namespace. Normalized
request bodies matched in the synthetic 401 comparison, while Modex retained
overlay state that the release removed; that lifecycle gap remains open.
The existing Modex Super launcher passed Codex's
`--dangerously-bypass-approvals-and-sandbox` flag in that isolated test. This
does not qualify Codex's own safeguards; do not extend or exercise that bypass
in future migration checks under the current user instruction.
An earlier isolated real-Codex 401 comparison observed Prodex routing to
Anthropic Messages and Modex to Chat Completions with the same normalized
client arguments. After the catalog and namespace fixes, a fresh isolated
real-Codex comparison reaches Anthropic Messages for both products; a synthetic
success case and a 401 case pass. With a Node-only tool directory, the 401
request bodies match after normalizing temporary paths and ports; earlier
uncontrolled `PATH` exposure enabled optional tools and changed the request.
Behavior with optional tools and Modex's retention of Codex-created state and
`auth.json` remain gaps; see the same evidence file for scope and reproduction.

`test_runtime_broker_startup_01660_oracle.py` records the broker gap with a
synthetic profile: the 0.166.0 process publishes a private capability and
loopback registry, while Modex exits with its unimplemented-command error and
publishes neither. This is a characterization, not parity. The test passed
with isolated state and a loopback upstream, including under a network and
mount namespace with a private user-owned `/tmp`. A plain `unshare -Urn`
attempt failed Prodex's secret-location validation because host `/tmp`'s owner
was unmapped; the passing setup retains that validation.

For the tested absent app root under a writable home, Modex and 0.166.0
`profile list` render the same empty panel. Modex creates no state, while the
release acquires lifecycle and update locks and may create housekeeping files
asynchronously. Existing roots
remain guarded; populated listing and lock side effects are incomplete. The
owner/mode guard cannot detect ACL or read-only-mount denials. See
`docs/evidence/baseline-0.166.0/profile-list-empty-store.md`.
The release uses `flock` for the Linux lifecycle lock. A synthetic local-file
test shows that POSIX record locks do not contend with it, and the pinned Mojo
standard library exposes no compatible whole-file lock interface. This is a
lock-interface characterization, not lifecycle parity; see
`docs/evidence/baseline-0.166.0/lifecycle-lock-stdlib-gap.md`.
The top-level `use` help and selected argument diagnostics now match the
active release without state changes; profile selection remains guarded. See
`docs/evidence/baseline-0.166.0/profile-use-help.md`.

A full isolated `make test` finished against exact Modex commit
`94b514c2fe3992a9f2219b035746820f8fe17161`, with the verified 0.166.0 oracle
as `PRODEX_ORACLE` and separate versioned historical oracles. It ran 1,182
Python tests in 3,416.417 seconds and failed with one error and one failure.
Its temporary log has SHA-256
`e62110a7ce5174463bf0c24a6321fc1bbb8c9a14a7ce9160d805d27e9e527c26`.
The failures were a CI-cleanliness test error and a historical
private-temp fixture failure. The first expected an old CI command spelling;
the second passed a generic oracle variable into a sanitized HOME even though
its historical fixture now requires a version-specific oracle. Both tests have
been corrected, and their five focused cases pass; the running older snapshot
cannot validate those corrections. The installed Prodex and Codex executables
are not replaced.

A second full run used exact commit
`418afa07d24d6c89abdc508f55ef287258302dab`, including the fixture corrections
and custom-tool change, in an isolated temporary worktree. Its log reports
1,186 Python tests passed in 3,443.472 seconds and the native checks completed;
the original shell exit status was not retained. The temporary log has
SHA-256
`0ac6167a1ef120853367905442819d02cd91b58905fb08ece16455ee9430fff7`.
This is evidence for that snapshot, not a full-suite result for later commits.

A third full run used exact commit
`b04873c96f55db20151e2c284144824ec470c3aa` in
an isolated temporary worktree, with a cleared environment, private HOME and
temporary directory, and explicit active and historical oracle paths. Its
temporary log has SHA-256
`b9b4342a09a5ca931cb5d4380fc6c3f9b9a4a2d32a53d70bf1c0a7374e625a18`.
It exited 2 after 1,195 tests in 3,343.608 seconds: four failures and one
required-reference skip. For the Anthropic parent-EOF test, Modex's parent had
already exited before the test could send SIGTERM, so the test did not prove
cancellation. The same test passed alone with the same isolated HOME and
oracle paths and ten further repetitions passed in a loopback-only namespace;
the early exit remains unresolved. The run omitted the historical 0.439.1
source override, so the strict runner correctly rejected its skipped recovery
policy comparison. That comparison passed on rerun with the explicit pinned
0.439.1 source path. This snapshot does not validate later changes.
The parent-EOF fixture now separately characterizes the original invalid-UTF-8
pipeline case and tests cancellation with the upstream held open. The latter
requires a live parent before SIGTERM, upstream closure and no surviving direct
children; active 0.166.0 and historical controls are independently runnable.
A single delayed 0.166.0 reference observation left a child alive at two seconds
and remains unresolved. See
`docs/evidence/baseline-0.166.0/anthropic-parent-eof-cancellation.md`.
The same run also reported three historical optional-tool fixture failures.
All three reproduce with an isolated `TMPDIR` because their output normalizer
assumed `/tmp` directly. The fixture now uses Python's actual temporary
directory prefix and preserves its path-disclosure checks. All three pass under
a nested temporary directory, and the two managed-tool cases also pass with the default.
The completed snapshot cannot validate this later correction.

A fourth full run used exact commit
`8993f0d2e74ffb1d82e57f847ad68937faed4324` in
an isolated temporary worktree. It uses a cleared environment, a private
user-owned `/tmp` and HOME, loopback-only networking with no default routes,
and explicit active and historical binary and source paths, including the
previously omitted 0.439.1 source. It exited 2 after 1,205 tests in 3,204.329
seconds, with two failures and no reported skips. Its temporary log has SHA-256
`5b0fa9d26b533e6cb73eba84f59dc1ba207dedf157203408a6b7446a6b221ca8`.
It reported a CLI regression fixture failure: the omitted-provider
Gateway now reaches its no-profile preflight, so that fixture's expected
unimplemented-provider error was stale. The fixture now explicitly selects an
unsupported provider and still checks that a synthetic key is not echoed; its
two focused CLI tests pass. The tested snapshot predates this correction.
It also reported a historical dry-run assertion that assumed which of two
existing-state guards would be encountered first. The test now accepts either
fail-closed diagnostic while still requiring unchanged state; the valid and
invalid state controls pass. This snapshot predates that correction too.

A fifth isolated `make test` was launched against exact commit
`e2be12831aa97e16770f91429293a64ede15c2aa`. It uses a private
user/mount/network namespace, private HOME and `/tmp`, loopback only, no default
routes, and explicit active and historical oracle and source paths. Its process
and temporary log are no longer available, so the outcome is unknown. It is
not counted as a pass or failure.

In an isolated checkout of the pinned 0.166.0 source, its Guardian loopback
TLS/CONNECT smoke passed and observed the reviewer using its parent's routing
cookie; six additional offline Guardian broker tests passed. Its local-only
release-tag preservation test also passed with a
temporary Git remote. These are upstream reference tests, not Modex parity:
Modex currently lacks the profile broker, Guardian routing, WebSocket client,
cookie store and release metadata synchronization path. An existing Modex
local-rewrite process test returns 426 for the tested WebSocket upgrades and
makes no upstream request. Commands and scope are in
`docs/evidence/baseline-0.166.0/guardian-and-release.md`.
The pinned upstream Codex compatibility-baseline guard and five offline
capture/replay fixture checks also passed. They do not exercise Modex or
establish compatibility with the installed Codex 0.165.0.

# Historical work: Prodex 0.439.2 parity and CI

The supported DeepSeek Super launch now translates rollout-budget token and
reminder options before or after `exec` into Codex configuration. Synthetic
child-process comparisons against both pinned releases cover defaults,
filtering, repeated options, limits 0, 1, 2 and the largest unsigned values,
and normalized argument order. Raw `-c` before `--` is still guarded by Modex,
although both releases accept it; broader Super option combinations and the
other release targets remain unverified.

Historically, a same-key tool result with a different session ID imported the
first session's prompt in Modex and the tested release processes. Modex now
scopes explicit session IDs as described in the current-work section above;
absent IDs and untrusted client-supplied identifiers remain limitations.
Full-cache tool-call lookup also scans stored histories under the shared lock;
its load impact has not been measured.

The historical note below about nonempty Anthropic text block starts is stale:
current Modex ignores their initial contents, matching both pinned releases in
real-process tests. The 0.165.1 cases also cover empty, missing and numeric
start payloads. Both focused test modules passed (31 tests); broader stream
behavior remains unverified. See `test_anthropic_text_stream_04392.py` and
`test_provider_stream_01651_characterization.py`.
The historical note about missing or non-string stop fields is also stale:
the tracked single-search tests compare these fields against both releases and
pass. The exercised cases include missing or non-string stop reasons,
non-string stop sequences and a missing message delta; other stream shapes
remain unverified. See `test_provider_stream_01651_characterization.py` and
`test_provider_tools_04392_characterization.py`.
The historical message-array note is also outdated for metadata: tested
message IDs, statuses and extra fields are accepted and ignored like both
releases. For the tested mixed text-and-image input, Modex and both releases
instead return 502 without a provider POST. Five existing message-array tests
passed against each release; other rich inputs remain unverified. See
`test_anthropic_message_arrays_04392.py`.

At the historical checkpoint, Modex had a cross-key tool-history ownership gap.
With two synthetic provider keys, a buffered response under key A containing a tool
call can be followed by a tool output without `previous_response_id`; the
next provider request uses key B and includes key A's prior synthetic
conversation. Both pinned release processes do the same. The per-launch
client token does not separate provider-key ownership. A candidate in
`$TASK_SCRATCH/ownership-final-1030` rejects this with 503 and one provider POST.
That older candidate remained unpublished pending a full suite: 76 continuation,
key-rotation and session-history tests passed, and an independent source review found no new
ownership race. Its first full `make test` stopped during native compilation:
`test_gateway_cli.mojo` still expected the old history return type. The test
callers have been updated in the candidate and the suite must be rerun; the
failed log is `$TASK_SCRATCH/ownership-full-1030.log` (SHA-256
`5dfbc49f127a4321f9b09a77d1b5eff2577b6833bb5e285c40d9299da1ecf42f`).
The corrected gateway test compiles and passes. A subsequent full run was
interrupted to include the corrected child-environment fixture; its partial
log is `$TASK_SCRATCH/ownership-rerun-1030.log` (SHA-256
`18ac529e7b774e21379a48bc22127e46b3fe262a3f6f8e8400bfcde65a27dedc`)
and it is not a pass. Its tracked diff SHA-256 was
`2283d6eb5bc8b57df0a54a272fd3560dba62cf1ef9ead53ed0d49538d4450e54`.
After integrating the corrected fixture and rollout-budget launch slice, the
full run at `$TASK_SCRATCH/ownership-combined-1030.log` was interrupted when the
target changed to 0.166.0. Its partial log SHA-256 is
`d0fae4b398fb4bdd99bfe170f38d1957a26aac99d3407c1bb478e342efb98fb9`;
it is not a full pass or 0.166.0 evidence.
The untracked native binding test SHA-256 is
`62be13c2d1a34a648d9ded15b74c31657fd093ea2091c048d4878fdeb29431b3`.
An earlier candidate incorrectly allowed a buffered `previous_response_id`;
that regression was fixed and the original assertion retained. A separate
`realpath` failure occurred while a concurrent build replaced the test binary;
an isolated rerun passed, but the cause has not been proven. The real-process test
`test_deepseek_key_rotation_01651_04392.DeepSeekKeyRotationTests.test_published_cross_key_tool_history_gap_is_fixed_in_modex`
now distinguishes the earlier releases from Modex, but has not been rerun
against the unavailable 0.439.2 oracle. The later 0.166.0 checks and their
remaining limits are described in the current-work section above.

The 0.165.1 runtime-broker path was traced through bootstrap, profile auth,
registry lifecycle and WebSocket transport. Mojo 1.2.0 compiler probes again
confirmed the listed standard-library networking, DNS, crypto and file-lock
APIs are unavailable; the seven pinned-process WebSocket observations passed.
This identifies implementation work, not an impossibility proof or Modex
parity. See `docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

DeepSeek Super now gives its local relay a fresh per-launch bearer token and
scrubs the pinned provider-secret environment variables from Codex children.
The relay rejects missing, empty, wrong, duplicate and stale tokens before
waiting for a declared body or contacting the provider; header capture can
already buffer bytes sent with the head. A real Codex 0.165.0
loopback-only test passed with synthetic credentials. Both releases accept
the tested unauthenticated client, so the 401 is an intentional security
non-parity; single-key prefetched continuations still return 503. Same-user
token access, incomplete-header starvation, multi-key ownership and all six
release targets remain open. See
`docs/evidence/baseline-0.165.1/super-local-client-auth.md`.

The 426 local WebSocket fallback now sends a write-side shutdown before close
on selected rejection paths. Focused Linux tests cover fragmented/coalesced
pipelines, client half-close, and adjacent auth/framing controls. The 0.439.2
and 0.165.1 processes can reuse one HTTP/1.1 fallback connection that Modex
closes; that existing difference remains. The separate runtime-broker
WebSocket path is still unimplemented.

After repairing direct-relay authentication fixtures, slow-body probes,
probe-environment expectations and exact on-wire header sizing, an isolated
full `make test` in `$TASK_SCRATCH/auth-full-repaired-1030` finished with six
failures in 1,172 tests. All six binary-selection subtests compare the child
environment and encounter the intentional provider-secret scrub: the release
supplies a synthetic `OPENAI_API_KEY` and Modex removes it. The fixture is
now corrected with explicit assertions for both behaviors; the six 0.165.1
path modes, eight 0.439.2 path modes, and secret-scrub test passed separately.
The full suite has not yet passed with that correction. Its log
`$TASK_SCRATCH/auth-full-repaired-1030.log` has SHA-256
`c13d48e8f63c605280d59b44f5020830cd2de87bbf8037b63cf913864d17e745`.
The snapshot base is `af5344e`,
with tracked patch SHA-256
`b4ba84dfa49774df9dc9805a2815ec19e3be5295f9e4cec0142b5e86dbbeaa55`
and `src/modex/auth_token.mojo` SHA-256
`4bfc5234c572703350fb459d6cc494e2db92d07a7895bff085838f772dc05eea`.
It predates the later 426 correction and continuation work, and is not a full
pass or validation of those later changes.

The authentication-snapshot full suite finished with 28 failures and one error
in 1,167 tests. Failures include large relay headers, WebSocket body handling,
direct relay startup, slow partial requests and Super probe environments. The
snapshot predates later fixture repairs; their causes and any production
regressions are under investigation. No full pass is claimed. The log
`$TASK_SCRATCH/auth-full-1030.log` has SHA-256
`ad35399915ac6e5d2bbb91abcae676db75e977b8ad8c28808ac16dd4d55fa60f`.
An earlier status update overlooked indented failure lines.

Two pinned runtime-broker WebSocket processes now have separate synthetic
interrupt characterizations. In the tested 0.165.1 case a foreign-session
interrupt closes the submitting connection without reaching the owner; a
same-session interrupt and its real acknowledgement are forwarded on the
owning socket. In the 0.439.2 case, the tested foreign interrupt waits for
the submitter's response to finish and is then forwarded on its existing
socket. The seven oracle-only tests passed; each new case also passed three
fresh-process repeats. Neither test exercises Modex, whose profile-backed
runtime WebSocket path remains unimplemented. See
`docs/evidence/runtime-websocket-interrupt-oracle-01651-04392.md`.

The broader, unpublished continuation-and-ownership draft remains in
`$TASK_SCRATCH/auth-integrate-1030`, based on `c386b71`; the earlier draft remains
preserved in `$TASK_SCRATCH/integration-20261030`. A write-side shutdown before
closing on non-ASCII headers passed the six-test header suite, including
coalesced and fragmented pipeline controls against both releases. The worker
also tested delayed input, queued bodies, a write flood and peer reset on Linux;
other operating systems remain unqualified. The draft now scrubs the pinned
12 provider-key environment variables from child processes. The installed
Codex CLI 0.165.0 successfully used the launch credential with a synthetic
provider in a loopback-only network namespace, including a conflicting synthetic
parent `OPENAI_API_KEY`. The relay still cannot authenticate partial headers:
132 unauthenticated partial connections delayed a valid request until the
connections were closed. Same-user access and broader security remain open.

The isolated full `make test` in `$TASK_SCRATCH/auth-full-1030` used `c386b71`,
plus tracked draft patch SHA-256
`69211338b7c3e6f4e4879059bfbf7ffc200def806b865671407152d99630dae2`
and `src/modex/auth_token.mojo` SHA-256
`4bfc5234c572703350fb459d6cc494e2db92d07a7895bff085838f772dc05eea`.
It predates the later environment-scrub and continuation work and is not a
pass for those changes. Its failure is recorded above.

Invalid post-`exec` `--rollout-budget-reminders` values now report the same
comma-separated-integer error as both release processes. The focused test
also retains the release/Modex startup-lock side-effect difference and checks
a valid reminder list; Modex's valid launch path remains guarded. See
`docs/evidence/baseline-0.165.1/super-rollout-reminder-element-errors.md`.

For pre-command `--rollout-budget-reminders` lists, invalid comma-separated
elements now appear individually in the diagnostic, matching both 0.165.1
and 0.439.2. Four malformed lists were compared through real isolated CLI
processes; the full eight-test Super CLI module passed on the combined build.
See `docs/evidence/baseline-0.165.1/super-rollout-reminder-element-errors.md`.
Other Super parsing and post-`exec` behavior remain incomplete.

Untyped null, boolean and numeric Responses message content now reaches the
native Anthropic web-search route as JSON text, as in both the 0.165.1 and
0.439.2 release processes. The earlier Modex binary returned 502 for all twelve
buffered and streamed controls; explicitly typed scalar messages remain 502
with no provider POST. Three focused scalar methods, three existing array and
role controls, the combined production build, 71-source dependency audit and test
census passed on Linux x86-64 with isolated synthetic peers. Forced Anthropic
mode also matched for selected assistant, system and developer scalar content.
See `docs/evidence/baseline-0.165.1/anthropic-untyped-scalar-input.md`.
Broader provider semantics, security and all six release targets remain open.

An unpublished per-launch client-token prototype is in the dirty worktree
`$TASK_SCRATCH/integration-20261030`; it is not part of the pushed product. It
generates a random token in the private overlay, passes it to the relay and
checks the header before reading a body or sending 100 Continue. Synthetic
launch tests passed for valid, missing, wrong and duplicate credentials,
stale launch tokens, stalled bodies and `Expect`. The existing streamed continuation restriction
is unchanged. The production build, native relay driver and 72-source
dependency audit passed for this draft. Same-user process compromise, partial
header exhaustion and cross-platform randomness are not qualified.

The draft is not ready to integrate: the non-ASCII-header-after-valid-pipeline
test receives a TCP reset instead of the release's clean disconnect. The
previous build passed the same focused test; with the prototype, whole-packet
probes reset in three of three trials and delayed splits varied. A bounded
nonblocking drain did not fix it and was removed. After fixture adaptation,
the full focused raw HTTP production-path comparison passed on the rebuilt
draft. Do not count this as
provider ownership or continuation parity, and do not stage the draft until
the regression and affected tests are resolved.

The new malformed-trailer raw-wire regression initially failed locally on
Modex because the probe discarded already received bytes when the peer reset
the connection. The probe now retains those bytes and records the reset as a
closed connection. Both new raw-wire comparisons and all five focused local
admission tests passed after that repair. The isolated `777cd3a` full run
finished with one failure in 1,157 Python tests: its 0.439.2 chunked
invalid-target connection-close assertion observed a close where it expected
an open socket. The later `b6dd839` test records the release's bounded second
400 using raw bytes instead of relying on HTTPResponse buffering; its focused
rerun passed. The historical full run does not qualify the later revision.
The log is `$TASK_SCRATCH/full-777cd3a-20261030.log` (SHA-256
`b85a538bb1db382c72b640daabe9ce8fc48deeec74b7a06c22024489c2ef6a00`).

Single-key streamed DeepSeek continuations expose an unfinished prefetch
binding gap: both releases accept selected follow-ups while Modex returns 503.
A candidate change reproduced the release behavior but also let a different
unauthenticated synthetic loopback client replay stored history. It was not
integrated. Both releases also replayed synthetic prior history with a different
synthetic configured key; Modex retains 503. See
`docs/evidence/baseline-0.165.1/streamed-continuation-prefetch.md`. Verified
client authentication and history ownership, runtime WebSocket ownership,
broader timing, and security behavior remain open.

The isolated `fa01212` full suite finished with seven failures and seven
errors in 1,146 Python tests after native checks. Six gated precommit failures
and seven fragmented-fixture errors predate the response-list fixture repairs;
the remaining failure is the truncated WebSocket body fixed in `79ff1b6`.
Focused reruns of the repaired fixtures and the three-process WebSocket case
passed. The log is `$TASK_SCRATCH/full-fa01212-20261030.log` (SHA-256
`34c0d50e8c7ebf147e15104c1e76340bef29b059d833bb59a598e235ca867bf7`).
This historical failed run does not qualify the current revision.

The isolated `2cf20df` full suite finished with one failure in 1,136 Python
tests after the native checks. Its only failure was the truncated WebSocket
body mismatch fixed and rerun in `79ff1b6` and the combined checks below.
The log is `$TASK_SCRATCH/full-2cf20df-20261030.log` (SHA-256
`0addeb36b9049ff040a10944d389cf90b2e21a55d3cb7b5a14074148c549c62e`).
This historical failed run does not establish a full pass for current code.

The combined build at `777cd3a` passed. Its native buffered-provider unit,
six buffered response process checks, five relay upgrade/framing process
checks, and five Super dry-run/launch/key-isolation checks passed. A direct
three-process rerun of the previously failing truncated WebSocket body also
closed without a response for both releases and Modex. Dependency audit,
test census, oracle routing, workflow validation and parity JSON validation
passed. Independent reviews covered relay framing and the Super option guard.

The isolated `7bad09f` full run finished with nine failures in 1,151 Python
tests: six gated precommit subtests, two 0.165.1 raw HTTP cases, and the
0.439.2 chunked connection-close assertion described above. It predates the
gated-fixture, WebSocket and raw-wire follow-ups; the malformed-trailer raw
case remains a separately observed mismatch. Its log is
`$TASK_SCRATCH/full-7bad09f-20261030.log` (SHA-256
`007b11cb07fa91c70340dfdc4cd2e8076ec561b719d9374e24227da2f654bb47`).
The earlier `2cf20df` and `fa01212` runs finished with the failures recorded
above. Runtime-proxy WebSocket/WSS, ambiguous-header and connection-reuse
differences, security qualification, and all six release targets remain open.

The `fa01212` full run has reported failures in fragmented and gated
precommit fixtures. The integrated fragmented fixture already gained the
response list required by redirect handling; the gated fixture lacked it as
well, causing its synthetic peer never to reach the gate. A focused gated
invalid-comment test reproduced that failure on `b20dbba`; after supplying
the response list, all seven tests in the precommit-boundaries and invalid
UTF-8 modules passed. The running `7bad09f` full suite predates this fixture
correction and cannot establish a pass for it.

The older `2cf20df` full run also reports a truncated WebSocket-upgrade
failure. A focused three-process probe on `b20dbba` confirmed both releases
close without a response on a half-closed, incomplete declared body without
`Connection: Upgrade`, while Modex sends 426. This production mismatch is
under investigation; no parity is claimed for it.

The combined production build at `636d01c` passed; later commits through
`7bad09f` add tests and evidence only. Focused RTK/Playwright, live-log,
provider idle/partial/truncation/cancellation and relay version/head controls
passed on the combined worktree. The native transport unit, dependency audit,
test census, oracle routing and workflow validation also passed. Independent
review checked the RTK scanner against Unicode separators and SemVer
boundaries, and led to the prefetched partial-frame investigation below.
An isolated full `make test` on `7bad09f` is running in
`$TASK_SCRATCH/full-7bad09f-20261030`, logging to
`$TASK_SCRATCH/full-7bad09f-20261030.log`; no full-suite pass is claimed yet.
All six release targets, broader behavior and security qualification remain
open.

## Super Codex reasoning effort (2026-10-30)

The guarded DeepSeek `super ... exec` launch and dry-run now preserve Codex
`--reasoning-effort` in separate and attached forms. Both pinned releases
consume their known Super tail overrides and pass this unrecognized Codex
option through unchanged. Captured app-server argv and generated settings
match Prodex 0.165.1 and 0.439.2 for normal, malformed, missing,
option-looking and delimiter-separated values. Synthetic provider-key controls
confirm that `--api-key` remains a Super override and is absent from Codex
argv, config, environment, auth and runtime config; the local synthetic peer
receives no request.

A follow-up guard regression now rejects an unverified option-looking token
after `--reasoning-effort` instead of treating it as that option's value. The
guard consumes only a nonempty non-option value or lone `-`; `--` still ends
validation. The synthetic blocked case confirms no Codex child or upstream
request starts.

The production build and native Codex fixture build passed. The focused
three-release dry-run report, launch argument matrix and API-key scrub check
passed on Linux x86-64. Invalid and missing values are only verified as
pass-through; no real Codex parser was used for those controls. Other Codex
arguments, five release targets, and full Super parity remain open. See
`docs/evidence/baseline-0.165.1/super-exec-reasoning-effort.md`.

RTK dry-run version selection now uses the shared semantic-version token
scanner: selected punctuation, Unicode whitespace, invalid candidates, and
first-valid precedence match both pinned releases. The production build,
three-process RTK and Playwright version checks, dependency audit and census
passed. An initial test command included a nonexistent method; its corrected
rerun passed. See `docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.
Broader optional-tool behavior, all six target qualifications and security
behavior remain open.

The shared synthetic upstream fixture polls for shutdown every 50 ms instead
of the Python default 500 ms. Eight empty fixture lifetimes took 4.012 seconds
before and 0.408 seconds after on this host. The three-process redirect status
matrix and buffered/streaming invalid-UTF-8 comparisons passed with the new
interval; this test-only change does not establish additional product parity.
The two older full-suite runs remain in progress on their original revisions.

## Live broker log source gap (2026-10-30)

Added a focused real-process characterization against the frozen Prodex 0.439.2
binary (commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`, SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`). With a
synthetic registry, matching capability and loopback snapshot server, Prodex
requests cursors 0 and 1, emits the synthetic token event and bounded-buffer
gap, and remains alive. Modex exits with `live runtime log sources are not
implemented` before connecting. All eight direct/broker, cursor-reset and
invalid-identity comparisons remain FAIL in
`docs/evidence/log-live-mismatch.json`; the new regression deliberately
verifies this known gap and does not count as parity.

The production gap remains blocked on the frozen registry store's lock,
recovery and legacy-artifact contract plus source executable identity checks.
The pinned Mojo standard library does not provide compatible locking and
durable replacement primitives, and invoking Prodex for identity discovery is
prohibited. The implementation remains fail-closed. Linux x86-64 checks:
isolated `make build BUILD_DIR=$TASK_SCRATCH/session-profile-build`; the focused
`test_log_runtime.LogRuntimeTests.test_live_broker_log_gap_is_reproduced_against_frozen_release`;
the eight-case `tests/capture_log_live.py` capture; and `git diff --check`.
The fixtures use a temporary HOME/cwd and synthetic capability, with only an
ephemeral 127.0.0.1 listener.

The combined production build at `fa01212` passed, as did eight focused
three-process redirect tests, five native deadline/cancellation and passthrough
tests, and the native transport units. The dependency audit, 50-native/155-
Python census, oracle routing and workflow validation passed. A full `make
test` is running in `$TASK_SCRATCH/full-fa01212-20261030`, with log
`$TASK_SCRATCH/full-fa01212-20261030.log`; no full-suite result is claimed yet.
Cross-origin redirects, HTTPS and general URL behavior remain unqualified.

## Local relay request versions and large heads (2026-10-30)

Three-process production tests cover supported HTTP/0.9, HTTP/1.0, and
HTTP/1.1, malformed HTTP/1.2, and unsupported HTTP/2.0 and HTTP/3.0 tokens.
For HTTP/2.0 and HTTP/3.0, both pinned releases return no bytes and keep the
connection open during a 1.2-second raw capture plus a 0.5-second close check;
Modex sends HTTP/1.1 400 with an empty body and closes. The frozen TinyHTTP
source suggests its 505 response is buffered while it waits for another
request; that explanation is an inference. Modex keeps its bounded close
behavior and records this release mismatch. The supported HTTP/0.9 reuse and
pipeline control passes.

An exact 4 MiB request head reaches the synthetic provider through both
releases; Modex returns 502 without dispatch at its current 2 MiB cap. Raising
the cap to 4 MiB would permit up to 152 live head slots (128 parked, 12
overflow, and 12 active/queued), or an estimated 608 MiB of raw head bytes
before copies. This is a worst-case byte estimate, not an RSS measurement, so
the 2 MiB cap remains. Focused tests pass; details and reproduction are in
`docs/evidence/baseline-0.439.2/local-relay-version-and-head-bounds.md`.

The isolated `dd82b3b` full suite finished with two failures in 1,127 Python
tests after native checks. Both are the stale passthrough header assertions
corrected and rerun below. Its log is `$TASK_SCRATCH/full-dd82b3b-20261030.log`
(SHA-256 `c6c4c395492e00588cbbd626680079b3683b95cddf9e96cc8a6f841b55aaae31`).
This failed historical run does not qualify the current revision.

The combined production build at `46600f4` passed. Focused Node and `npx`
precedence, session diagnostics, WebSocket pipeline, endpoint projection,
Super URL validation, and DeepSeek beta URL controls passed on the preceding
combined builds. Both native operational-log and Super parser checks passed
on `46600f4`; the dependency audit, 50-native/155-Python test census, oracle
routing and workflow validation passed. Full runs on `2e7dcc8` and `dd82b3b`
predate these changes and do not qualify this revision.

The isolated full `make test` on `2e7dcc8` finished with two failures in
1,117 Python tests after native checks. Both failures were stale expectations
for duplicate passthrough `Content-Type` headers; their corrected fixtures and
focused reruns are recorded below. The log is
`$TASK_SCRATCH/full-2e7dcc8-20261030.log` (SHA-256
`c14d7a4a26abb9c6dbe95922a54ccbf8004a62b3d812f71b93584ca51b42d1ad`).
This failed historical run does not qualify the current revision.

The `2e7dcc8` full run also reported a stale Super passthrough assertion: the
synthetic upstream converted duplicate headers to a dictionary and expected
only the caller's `Content-Type`. It now records all values and asserts the
default and forwarded fields in release order. The focused buffered/binary
passthrough and ordinary streamed-launch controls pass. One initial rerun
used a nonexistent unittest method name and failed at test discovery; the
corrected two-method rerun passed. The full run predates this test fix.

Node and `npx` dry-run discovery now selects the first regular file on `PATH`,
including a non-executable file that shadows later candidates. Synthetic
three-process controls match both releases' readiness outcomes for both
commands; Modex keeps a path-free Node spawn error where the releases print the
path. Focused Node and Playwright probe regressions passed on Linux x86-64.
Other path cases, process descendants and non-host targets remain unqualified.
See `docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.

The running `2e7dcc8` full suite reported a passthrough-driver failure because
its synthetic peer still expected the single `Content-Type` from before the
relay header-parity change. The fixture now asserts both release-matching
`Content-Type` fields, the default `Accept`, and the absence of `Connection`;
all three passthrough tests pass after rebuilding the native driver. This
focused correction does not establish a full-suite pass.

The combined production build at `d536403` passed. Its focused Node readiness,
WebSocket framing-precedence, and DeepSeek metadata-stream process checks
passed; the combined Node/session regression passed eight methods, and the
full dry-run module passed 27. The dependency audit, 50-native/155-Python
census, oracle routing, and workflow validation passed. Full runs on `2e7dcc8`
and `dd82b3b` were still active when this was recorded and predate these
changes; no current full-suite pass is claimed.

The isolated `b405bc2` full run finished with 40 failures and one error in
1,100 Python tests after native checks, reproducing the update-cache fixture
failures documented below. Its log is `$TASK_SCRATCH/full-b405bc2-20261030.log`
(SHA-256 `df3972864371c99bfd1031d1ebedd7530da1bfe2ecb052c11d0db4cd1f1e3177`).
The focused corrected-fixture reruns pass; this older run does not establish
full-suite success on the current revision.

## Ponytail Node readiness probe (2026-10-30)

Super dry-run now reports the Node health probe's exit status in the Ponytail
row, accepts any successful output as both pinned releases do, and uses the
five-second bound and filtered probe environment. Three-process checks cover
malformed, empty, stderr-only and invalid UTF-8 successful outputs, nonzero
exit, with and without an available synthetic `npx`, plus timeout. Modex omits
the timeout path printed by the releases. Managed Ponytail installation,
descendant cleanup and non-host targets remain unqualified. See
`docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.

## Session CLI edge diagnostics (2026-10-30)

Session CLI parsing now matches both pinned releases for two edge cases found
by a three-process sweep: a malformed boolean switch immediately after a
split invalid `--limit` value takes precedence as in Clap, and invalid nested
`session help help` subcommands omit the generic help footer. Six numeric-value
sequences and three nested-help cases run against 0.165.1, frozen 0.439.2, and
Modex with synthetic temporary homes and no fixture mutation. The full seeded
608-sequence three-release sweep had zero mismatches after the fix. All seven
focused `test_session_cli.py` methods, the production import audit, and test
census passed on Linux x86-64. This qualifies only selected diagnostics; state
locking/recovery, broader CLI behavior, security behavior, and the other five
release targets remain open. Evidence:
`docs/evidence/baseline-0.165.1/session-cli-precedence.md`.

## DeepSeek metadata-only Chat stream chunk (2026-10-30)

A synthetic loopback Chat Completions stream begins with a `choices: []` chunk
containing ID, model, creation time, fingerprint, and usage, then sends text,
`stop`, and `[DONE]`. A focused real-process comparison passed against pinned
Prodex 0.165.1, Prodex 0.439.2, and Modex; event order and the final response
metadata match. This qualifies only that stream shape on Linux x86-64 and does
not reduce the six-release denominator. Details and reproduction:
`docs/evidence/baseline-0.165.1/provider-chat-stream-shared-releases.md`.

The combined production build at `dd82b3b` passed. Focused real-process
redaction, numerically equal relay-length and duplicate web-search checks
passed on that build; the dependency audit, 50-native/155-Python test census,
oracle routing and workflow validation passed. A full `make test` is running
in `$TASK_SCRATCH/full-dd82b3b-20261030` with log
`$TASK_SCRATCH/full-dd82b3b-20261030.log`; it is not yet a completed result.

The isolated `c5609d0` full suite finished with 40 failures and one error in
1,096 Python tests after the native checks. The log is
`$TASK_SCRATCH/full-c5609d0-20261030.log` (SHA-256
`8da2310bbef4635e5ecbb2307ae1a47df73e6d57f6246b3b8138af0df37f7350`). Its
failing Super, app-server, Gateway, and terminal-width tests use fixtures that
did not seed the 0.165.1 update-cache filename. After correcting those
fixtures, focused reruns of all 19 Super/terminal methods, six app-server
methods, and six Gateway classification methods pass. The full run predates
those corrections and cannot qualify the current revision.

Playwright dry-run readiness now rejects invalid UTF-8 on either captured probe
stream, matching both pinned releases even when the other stream contains a
valid version. A synthetic three-process regression and the 25-test dry-run
module passed. The production build, dependency audit, test census, and
workflow validation passed on Linux x86-64. Other optional-tool paths and
security behavior remain unqualified; all six targets remain in scope.

The integrated production build at `2e7dcc8` and native Super parser test
passed. Focused three-process float and Anthropic result-ID tests passed;
both large-header release comparisons passed on the preceding combined relay
revision. The 25-test dry-run module and Gateway fixture checks passed after
their changes. The dependency audit, test census, oracle routing and workflow
validation also passed. A fresh full `make test` is running from an isolated
`2e7dcc8` worktree; its log is `$TASK_SCRATCH/full-2e7dcc8-20261030.log` and no
full-suite result is claimed yet. The older runs retain the fixture failures
documented below.

The older full-suite runs also reported Gateway classification failures from
the same release-specific update-cache mismatch. The Gateway fixture now seeds
the aligned 0.165.1 cache filename for that oracle and a non-newer synthetic
version for each release. All six historical Gateway classification tests and
five active Gateway tests pass in focused reruns. The two in-flight full runs
predate this fix and remain failed; a later full run is still required.

## Playwright dry-run readiness (2026-10-30)

Super dry-run now probes a locally resolved `npx --no-install @playwright/mcp
--version` with the filtered environment and a five-second bound, as both
pinned releases do. Synthetic three-process comparisons cover version
selection, failure, timeout, report ordering and environment isolation; no
network or real package is used by these tests. Malformed Node probes still
fail closed and the Mojo process wrapper cannot terminate descendants. This
qualifies selected Linux x86-64 behavior, not all six targets or security.
See `docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.

The combined production build at `64e37c1` passed. Its focused three-process
Anthropic alias checks passed, and the preceding combined relay build passed
six header, framing, and large-field process tests. The integrated managed
tool dry-run module passed all 23 tests; app-server checks passed after the
fixture correction below. The 71-file dependency audit, 154-module test census,
oracle routing, and workflow validation passed. Full runs on `c5609d0` and
`b405bc2` were still active when this entry was written and predate these
changes; they cannot qualify the combined revision.

## Translated Responses large-header follow-up (2026-10-30)

The production `/v1/responses` route now forwards a 1 MiB + 1-byte
`User-Agent` through both pinned releases and Modex, including the two copied
outbound values. A large field in an exact 2 MiB request head also reaches the
synthetic upstream with both copies. Modex retains a 2 MiB inbound request-head
cap and returns 502 without dispatch at 2 MiB + 1 byte; both releases dispatch
that control. Its outbound serialized-header bound is now 4 MiB + 2,048 bytes,
derived from the 2 MiB inbound bound plus one copied `User-Agent` and generated
headers. These are wire bounds; peak heap from parser/serialization copies was
not measured. Direct stream defaults remain 65,536 bytes. The two focused
real-process methods passed against checksum-pinned 0.165.1 and 0.439.2.
See `docs/evidence/baseline-0.165.1/local-relay-http.md`. Larger unbounded
release heads, other outbound field distributions that reach the fixed cap,
and non-host behavior remain open.

The full run on `c5609d0` reported six failures in historical app-server
checks because its shared Super fixture seeded only the 0.439.2 update-cache
filename. The 0.165.1 oracle instead uses `update-check-codex-aligned-v1.json`
and printed a real update notice, changing stderr. The fixture now seeds the
release-specific cache with a synthetic current version; all six 0.165.1 and
0.439.2 app-server test methods pass in a focused rerun. Both full runs started
before this fixture correction, so neither can qualify the corrected revision.

## Super missing Codex values (2026-10-30)

Missing `--add-dir`, `--enable`, and `--disable` values now reach the Codex
child, including when a recognized option follows. Three-process checks match
both pinned releases' child arguments and exit status; a network-isolated local
Codex 0.165.0 check returned its missing-value diagnostic. Empty values and
unknown options remain guarded, and other Codex versions and release targets
remain unqualified. See `docs/evidence/baseline-0.165.1/super-exec-value-options.md`.

The combined production build at `b405bc2` passed, as did the focused
three-process Codebase Memory, endpoint projection, and Anthropic empty-field
tests, plus the large-header relay comparisons against each pinned release.
The production import audit, 154-module test census, oracle-routing tests, and
workflow validation passed. A full `make test` is running in the isolated
`$TASK_SCRATCH/full-b405bc2-20261030` worktree; its log is
`$TASK_SCRATCH/full-b405bc2-20261030.log`. An earlier full run on `c5609d0` is
also still running. Neither run is a completed full-suite result yet.

## Codebase Memory dry-run discovery (2026-10-30)

Super dry-run follows both pinned releases' managed-root and candidate order:
`PRODEX_OPTIMIZERS_HOME`, `XDG_DATA_HOME/prodex-optimizers`, then
`HOME/.local/share/prodex-optimizers`; within each root it checks the root
command, checkout command, `build/c`, and `bin` command before `PATH`. The
missing and non-regular candidates are skipped; the first regular file
shadows later candidates even if it is not executable.
Synthetic real-process tests compare all four candidate positions and all
three roots across 0.165.1, 0.439.2, and Modex. Internal managed symlinks are
accepted; symlinked roots report `skipped (managed Codebase Memory root is not
a real directory)`. Prodex executes an escaping command symlink before checking
containment, while Modex returns `skipped (managed codebase-memory-mcp command
escapes its root)` before execution. For a non-executable first candidate,
Modex returns `skipped (codebase-memory-mcp health check failed)` without the
temporary path printed by the releases.

The complete 23-test dry-run module passed against both pinned Linux binaries
and Modex. The production import audit passed for 71 Mojo files, the test
census passed for 50 native sources and 154 Python modules, and `git diff --check`
passed. The probe still cannot terminate descendant process groups,
and its timeout message omits the executable path printed by the releases.
This evidence qualifies tested Linux x86-64 cases only; all six release
targets and unverified security behavior remain in the parity denominator.
See `docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.

The isolated `make test` run on `751639602fd13c24c216606f086de558e942be88`
stopped in the native `test_provider_chat_reader` unit before Python tests:
its direct-reader assertion expected no usage after `message_start`. The
release reader records the start's usage, and the corrected whole native unit
passes on the later combined revision. The failed log is
`$TASK_SCRATCH/full-7516396-20261030.log` (SHA-256
`fcdb8f4c39e4aedb03d51563d3c3d712a07a3a0fa88599e908ff29f21805af18`).
This focused rerun is not a full-suite pass; rerun the full suite on the
current combined revision.

The isolated full `make test` run on `89e8c04e7fcd3fb93d52bcafc400d19e5704dfc7`
finished with three failures in 1,076 Python tests after the production and
native checks. The local log is `$TASK_SCRATCH/full-89e8c04-20261030.log`
(SHA-256 `f292b8829be8ee968e03df844df76a4088b35d3feb0ec28e37d42977a229e14a`).
The session PTY comparison had a timing race and was subsequently synchronized;
its focused rerun passes. The Anthropic search-edge comparison passes on the
later integrated revision, after its prefetch changes. The test census had an
outdated exact method list; it now requires the five relevant methods and checks
that discovered IDs are unique, and the census/routing tests pass. These
focused reruns do not qualify the current revision as a full-suite pass.

## Log follower terminal fallback (2026-10-30)

`log stream` and `log upstream` now follow the release's plain-output path when
their stdin/stdout TUI condition is false. Real-process tests compare both
release binaries and Modex for stderr-only, stdout-only, and stdin-only TTYs
without `NO_COLOR`, plus stdin/stdout TTYs with `NO_COLOR`. With both TTYs and
`NO_COLOR` absent, the release TUI accepts `q` and restores its terminal;
Modex keeps its explicit unsupported-TUI error. Live runtime registries also
remain fail-closed. This is Linux x86-64 behavior evidence only; parity statuses
and the six-target denominator are unchanged. See
`docs/evidence/baseline-0.165.1/log-terminal-fallback.md`.

## Operational endpoint URL projection (2026-10-30)

The operational stream now renders empty paths on non-special custom URLs as
`upstream`, handles empty-authority custom paths and file drive-letter
authorities, preserves path `|`/`^`, and rejects percent-decoded host
separators such as encoded `%40`, as well as IDNA-mapped separators. The
23-case real-process URL matrix matches Prodex 0.165.1, frozen 0.439.2, and
Modex, including query/fragment omission and a synthetic
query-secret check. The shared authority validator also serves Super URL and
DeepSeek beta URL validation; process controls reject malformed hosts before
launch and keep a synthetic API-key sentinel private. Focused operational,
plain-log, Super, and DeepSeek tests pass. Full UTS #46 URL parsing, live log
registries, TUI rendering, and the other release targets remain open. See
`docs/evidence/baseline-0.165.1/log-endpoint-url-projection.md`.

The isolated full `make test` run on `0023b4669e547e27bc4d660786f791c33546d79c`
completed successfully: production and native checks passed and 1,050 Python
tests passed in 3,356.477 seconds. The local log is
`$TASK_SCRATCH/full-0023b46-20261030.log` (SHA-256
`441ad6b5926568c88ab3331b0adc996696818bbcde4747b84a986ce701bc623a`). This
run predates later dry-run, provider, and log changes; it does not qualify the
current revision, non-host targets, or security behavior.

## Generated stateless session matrix (2026-10-30)

Generated real-process fixtures compare session metadata aliases and
precedence, duplicate keys, record order and type classes, timestamps, and
stateless query fields across Prodex 0.165.1, frozen Prodex 0.439.2, and Modex.
All five matrix tests passed; every generated output matched after replacing
only fixture-root paths. No substantial stateless report or query mismatch
appeared in the covered Linux x86-64 cases. Managed state and profile filtering
were excluded; other release targets and overall parity remain open, and all
six baseline targets stay in the denominator. Evidence:
`docs/evidence/session-stateless-generated-matrix-04392.md`.

## Super effort diagnostics with escaped input (2026-10-30)

Reasoning-effort errors now format C0/C1 codepoints, quotes, backslashes, and
tested ANSI CSI values like both pinned releases. Printable Unicode also
matches. Full Rust Debug printability remains open for non-ASCII nonprintables
such as U+0301, U+200B, and unassigned U+0378. Selected OSC and other terminal
control strings now match both releases in the outer diagnostic; broader
terminal protocol behavior remains unverified. Evidence records the remaining
mismatches and verified boundary cases in
`docs/evidence/baseline-0.165.1/super-sub-agent-reasoning-escaping.md`.

## Super reasoning-effort CLI values (2026-10-30)

Super now trims and ASCII-lowercases `--sub-agent-model-reasoning-effort` before
validation, and invalid values return the matching Clap diagnostic and exit 2.
Real-process tests compare 0.165.1, frozen 0.439.2, and Modex for accepted
mixed-case input, whitespace, attached values, and Unicode case-folding
controls. No filesystem state is created. This is parser parity on Linux
x86-64; sub-agent execution and the other five release targets remain outside
this result. Evidence: `docs/evidence/baseline-0.165.1/super-sub-agent-reasoning-effort.md`.

## Anthropic stream message-delta ordering (2026-10-30)

Modex now ignores a standalone `message_delta` before `message_start`, while
translating selected text and function-argument deltas that arrive before
`message_start`. The cross-release process matrix matches both releases for
those cases, the standalone delta case, and its function-name error path.
Late and repeated `message_start` metadata now matches both release binaries.
The source trace resolved the earlier contradiction: native prefetch drops its
consumed prefix before the Anthropic reader sees it. The regression matrix also
covers first text/error/ping events, mismatched `event:` labels, fragmented and
incomplete first frames, timeout, EOF, and the 8 KiB prefix boundary. All tested
Linux x86-64 cases match both releases. The production Modex path has no
equivalent to Prodex's prefetch-slot semaphore, so saturated-slot behavior
remains unqualified; the other five baseline release targets remain gaps.
Build, focused process tests, production import audit, test census, and the
full source trace are recorded in
`docs/evidence/baseline-0.165.1/anthropic-stream-message-delta-order.md`.

## Buffered first-choice history shaping (2026-10-30)

The buffered DeepSeek history shaper now rejects a present non-object first
choice. The production relay returns the same empty HTTP 500 response as
checksum-verified Prodex 0.439.2. Missing or empty `choices` and malformed
later choices still match the selected release cases. One synthetic real-process
test compares both releases and Modex, and runs in fast and full cross-release
CI. It resolves 0.439.2 through `PRODEX_ORACLE_04392` or its pinned cache
fallback. The native buffered unit, focused process comparison, production
dependency audit, and `git diff --check` pass. Evidence:
`docs/evidence/baseline-0.439.2/provider-buffered-choice-history.md`.

The completed `23bb0b1` local full run had 1 failure in 1,036 tests: an old
combo-model assertion expected 0.439.2's Flash alias despite the 0.165.1 combo
mapping. Three-process follow-up also found direct `flash` still used 0.439.2's
alias. Both request preparation paths now use 0.165.1's `deepseek-flash`;
0.439.2's `deepseek-v4-flash` remains a documented difference. The focused
simple/non-simple matrix and native request checks pass; the full suite has not
been rerun on this change. See
`docs/evidence/baseline-0.165.1/deepseek-flash-alias.md`.

Detached log streaming now checks for the literal raw `stream_payload` text
before projecting an event, like both pinned releases. Escaped event names
without that raw substring are ignored; a literal occurrence elsewhere on the
line still admits the event. Real-process JSON and plain comparisons cover
initial snapshots and appended records. Redaction remains unchanged. See
`docs/evidence/baseline-0.165.1/log-stream-escaped-event.md`.

Token usage selection now requires the parsed event name `token_usage` in the
shared projection. Both pinned releases accept an escaped JSON event name even
when the raw line has no `token_usage` substring, so this event family does not
use the upstream payload raw-substring filter. Cross-release process tests
cover `log last`, stream snapshots, and followed records in JSON and plain
modes. Other runtime records can still appear as generic stream events; the
check prevents them from also being emitted as token usage. See
`docs/evidence/baseline-0.165.1/log-token-selection.md`.

## Local relay Expect/framing precedence (2026-10-30)

The production relay now matches both pinned releases when `Expect: 100-wait`
arrives with conflicting or malformed framing: it returns 417 before reading a
body, sending interim 100, or dispatching upstream. Real-process tests also
cover fragmented headers, client half-close, a pipelined valid request behind
the rejection, and the unchanged single valid `100-continue` control. The
shared parser remains strict by default. Valid ambiguous chunk framing stays
fail-closed in Modex: both releases dispatch it, while Modex returns 502 with
no upstream request. Do not count that security difference as parity. The
0.439.2 test path now uses only `PRODEX_ORACLE_04392` or its pinned cache path;
a focused test passed with generic `PRODEX_ORACLE` deliberately set to 0.165.1.
See `docs/evidence/baseline-0.439.2/local-relay-expect-framing.md` and
`docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md`.

## Identical local relay Expect duplicates (2026-10-30)

The TinyHTTP-compatible production path now accepts repeated identical
`Expect: 100-continue` values and sends one interim 100. The shared parser's
default remains strict. Synthetic process comparisons cover both pinned
releases, a valid-first mixed expectation, the reversed mixed order, invalid
targets, and ambiguous framing. Modex keeps mixed values fail-closed: a valid
`100-continue` followed by `100-wait` returns 417 without dispatch, while both
releases use the first field and dispatch. A valid chunked body with both
`Content-Length` and `Transfer-Encoding` remains rejected by Modex before body
read or provider I/O, although both releases dispatch it. Invalid-target
requests with unread nonzero bodies still close the Modex client socket after
400. These differences remain visible. Only Linux x86-64 is qualified; all six
release targets stay in the denominator. Evidence:
`docs/evidence/baseline-0.165.1/local-relay-identical-expect.md`.

## Anthropic web-search ID handling (2026-10-30)

Native Anthropic streaming now uses the releases' `web_search_<index>` fallback
for absent or non-string search IDs, preserves empty string IDs, and ignores
unmatched results before parsing their source content. Buffered responses still
require string IDs while accepting empty strings, matching both releases.
Three-process loopback tests cover fallback and result association, default and
reused indices, duplicate and colliding IDs, interleaving, and buffered error
controls. The full shared stream module, focused buffered ID checks, buffered
content-block boundaries, no-replay-after-commit control, production import
audit, and diff check pass on Linux x86-64. See
`docs/evidence/baseline-0.165.1/anthropic-search-id-handling.md`. This qualifies
only these tested cases; complete provider parity and all six release targets
remain open.

## DeepSeek Super dry-run (2026-10-30)

The guarded DeepSeek `super --dry-run ... exec` path now shares its Codex
argument builder with live launch, honors `PRODEX_CODEX_BIN` and PATH selection,
and performs no Codex launch, relay startup, or provider traffic. Synthetic
three-process controls cover read-only config/history, model selection,
secret and path redaction, absent Codex, Node without npx, and the bounded RTK
version probe. The RTK probe uses a filtered environment, selects managed roots
before PATH, and matches both pinned reports for stable, old, prerelease,
malformed, stderr-only, empty, failed, and timeout status cases. Modex redacts
the executable path in timeout diagnostics; both releases include it. The probe
uses the standard library's direct-child timeout, so descendant process-group
cleanup remains unverified. A native Mojo Node and RTK fixture make these
probes runnable inside bwrap.

The earlier combined dry-run and live-launch run passed 56 tests against the
pinned 0.165.1 and 0.439.2 Linux binaries. The final dry-run rerun passed all 16
tests after the managed-root symlink control was added. Production import audit
passed for 71 Mojo files; test census passed for 50 native sources and 145
Python modules. Full repository tests and Fast/Full CI were not run. Evidence:
`docs/evidence/baseline-0.165.1/super-dry-run-01651.md`.

The releases leak a synthetic value in the chained `--api-key --password`
control; Modex redacts it. Record this stricter behavior as security
non-parity. When Node and npx are both present, Modex remains fail-closed
because the release probes Playwright by executing locally resolved package
code. Installed-tool readiness, populated profile state, recovery locks,
shared-history launch, all six baseline targets, and complete Super parity
remain open.

## Relay worker concurrency (2026-10-30)

The exact `36ab8ca` Linux build admitted at most eight synthetic provider
requests at once, even when `PRODEX_RUNTIME_PROXY_WORKER_COUNT=12`. A candidate
cap of twelve reached twelve synchronized upstream requests through the real
Super CLI and returned all twelve responses successfully. Both pinned Prodex
0.439.2 and the historical 0.165.1 control also reached twelve. This qualifies
only the loopback request path under a 250 ms synthetic upstream hold; it does
not establish full parity. See
`docs/evidence/worker-concurrency-04392.json` and its raw samples.

An exploratory configured-64 probe observed both pinned releases reaching 64
concurrent upstream requests while the candidate stayed at twelve. Its
temporary harness is not committed, so treat the result as a non-reproducible
measurement, not an automated parity gate; raw samples are retained. In one
0.439.2 sample, the 64-request process tree peaked at 86 threads, 139 file
descriptors, and 35,188 KiB RSS; the Modex candidate stayed at 26 threads, 86
file descriptors, and 25,636 KiB RSS while serving all 64 requests in bounded
waves. Keep this gap visible; do not raise the cap to 64 without a separate
resource qualification.

The default count is `min(12, max(4, parallelism_level()))`, and execution
still depends on scheduler capacity. On hosts with fewer than four scheduler
lanes, the configured floor can exceed effective concurrent execution. The
automated barrier test queries Mojo parallelism and qualifies active capacity
as `min(configured workers, parallelism)`; it claims twelve lanes only where
the scheduler supports them. This evidence covers Linux x86_64 only and does
not remove any target or security gap from the parity denominator.

## Local relay polling and keep-alive throughput (2026-10-30)

The full-overflow no-progress scan now waits 5 ms; the no-work wait with parked
sockets is 10 ms. Three matched process runs cut Modex's 71-request
keep-alive/churn wall median from 3.685 s to 1.804 s and partial-head flood CPU
from 0.33 to 0.13 CPU seconds per second. With 128 parked idle sockets, CPU
rose 0.01 seconds per second at the median; descriptor count stayed 127. The
normal response and fragmented-head samples showed no added latency.

Admission, eviction, framing, and the starvation boundary did not change.
Both releases still serve a healthy client before releasing seven body
blockers and 136 partial heads; Modex still waits until release. Modex also
remains slower in the keep-alive/churn control than both releases. The
120-second request-head expiry, non-Linux targets, and full admission parity
remain unverified. Focused process tests, production dependency audit, and
`git diff --check` pass. Details, sample ranges, and reproduction commands:
`docs/evidence/baseline-0.165.1/local-relay-polling-20261030.md`.

Two sequential DeepSeek Super launches expose a core shared-home gap: the
first Modex launch creates session and history paths, then the second rejects
them before starting Codex. Both pinned releases launch twice and preserve the
synthetic session and history. The three-process test records this mismatch;
it is not a parity pass. The release coordinates the child and session
maintenance with shared and exclusive advisory locks. Mojo 1.2.0 supports
append-mode history opens, but exposes no compatible lock API; its internal
`fcntl` wrapper does not provide a supported lock protocol. Removing the guard
and changing only the history open mode would leave concurrent maintenance
uncoordinated. Keep the guard until compatible shared/exclusive locking is
available. Concurrent Modex child behavior remains untested because the
guard prevents reaching the shared-storage path. See
`docs/evidence/baseline-0.165.1/super-repeat-launch.md`.

The profile-state follow-up confirms the lock boundary against the verified
0.165.1 and 0.439.2 Linux releases. Populated `profile list` reads and may
repair state under persistent `flock` files; both releases create lifecycle,
state, housekeeping, and update locks. Modex remains fail-closed and leaves
synthetic state and auth unchanged. The stateless profile help/parser controls
pass against 0.165.1. Mojo 1.2.0 lacks compatible flock, atomic replace,
fsync, and permission APIs, so no safe profile-state implementation was
available. The new historical-lane tests route 0.439.2 through
`PRODEX_ORACLE_04392` while `PRODEX_ORACLE` is unset, and the 0.165.1-only
controls run without a cached 0.439.2 binary. See
`docs/evidence/baseline-0.165.1/profile-state-locks.md`.

The local full suite on `b9b52d5` finished 1,006 tests with 53 failures and
one error. Most failures exposed a single-key provider-panel punctuation
regression and a stale probe-environment assertion; the combined Super and
app-server recheck passes all 53 tests after their fixes. Two Expect/framing
expectations were also stale; both release-specific matrices pass after
checking the actual 417 wire responses. The JSON log-follow rotation marker
timed out once in the full run but passed five focused reruns; its cause is
not proven. Both releases and Modex skip the initial replacement record when
a followed path is absent during a poll; the rotation fixture now replaces
the path atomically to avoid that race. A subsequent local `make test` run on
`13d4db21df6b325fac5fbfd1b9698564d5ed3e38` passed 1,019 Python tests after
the production and native test builds; it predates the removal of a separate
sleep-dependent gap assertion and all newer commits. It does not qualify the
current revision or other release targets. The full log is retained locally at
`$TASK_SCRATCH/full-13d4db2-20261030.log` (SHA-256
`dbd3ed9d59ea42b7664fb6868f9e897a938fc6d5251f904c3a17d6abc663c971`). See
`docs/evidence/log-follow-rotation-recheck-20261030.md`.

Native Anthropic request handling now ignores unknown top-level Responses
fields and unknown `web_search_preview` properties, matching both pinned
releases in auto and forced-Anthropic loopback comparisons. The provider bodies
and normalized responses match; unknown extension values are not forwarded.
Malformed `temperature`, unsupported `service_tier`, duplicate known fields,
duplicate unknown keys, and requests over 4 MiB retain release behavior. The
three-process tests, fallback and duplicate-key regressions, dependency audit,
test census, active-oracle routing checks, and diff check pass. Fast and full CI
run the module in their active cross-release phases. This qualifies selected
Linux x86-64 request behavior only; full provider translation and all six
release targets remain open. See
`docs/evidence/baseline-0.165.1/anthropic-request-unknown-fields.md`.

DeepSeek Responses now retries combo model candidates before credentials on
retryable model-class errors. HTTP auth failures rotate credentials and restart
at the first candidate; a successful candidate retains request context and
credential binding. Native Anthropic not-found first events can use the same
one-retry model budget before commitment, while text already emitted is not
replayed. Three-candidate, one-key, exhausted-stream, auth-precedence and
committed-output comparisons match both pinned Linux processes. The provider's
8-bit retry counter limits model fallback to 256 candidates per credential;
transient retries can rotate keys and restart at the first candidate. Combo
parsing accepts large chains and deduplicates names without pairwise scans.
Modex follows the 0.165.1 `combo:flash` alias (`deepseek-flash`); 0.439.2 sends
`deepseek-v4-flash`, so this slice remains a recorded mismatch against the
official baseline. See
`docs/evidence/baseline-0.165.1/deepseek-combo-model-retry.md`.

Native Anthropic Responses requests now accept missing, empty, and text-only
`modalities` values and omit them from provider requests. Audio-only, mixed,
and wrong-type values still return matching 502 errors without provider I/O.
The three-process matrix covers auto, forced Anthropic, and forced Chat routes
with buffered and streamed requests against both pinned releases and Modex.
The production build, focused matrix, 71-file dependency audit, 50-native/140-
Python test census, and diff check pass. This qualifies Linux x86-64 only; all
six baseline release targets remain in the denominator. See
`docs/evidence/baseline-0.165.1/anthropic-text-modalities.md`.

The Super single-key provider panel now matches both pinned releases:
“API-key rotation is skipped and quota preflight stays disabled.” Multi-key
panel text remains unchanged. A real-process control compares both messages
across 0.165.1, 0.439.2, and Modex using synthetic credentials and a forced
Codex capability-probe failure before provider I/O. The probe environment
regression now records the 0.165.1 behavior of forwarding provider-key
variables and verifies Modex scrubs them. The production build, three focused
process tests, dependency audit, test census, and diff check pass. The full
suite was not run; all six release targets remain in the denominator. See
`docs/evidence/baseline-0.165.1/super-codex-probes.md`.

The production relay trims ASCII boundary whitespace around request header
lines and values only in TinyHTTP compatibility mode. Real-process controls
match checksum-pinned 0.165.1 and 0.439.2 for boundary whitespace, CRLF field
separation, and rejection of embedded value controls before upstream I/O.
Identical and numerically equal duplicate `Content-Length` values are now
accepted as described below; conflicting values remain rejected by Modex. With
valid chunked bodies, both releases dispatch conflicting
`Content-Length`/`Transfer-Encoding` and duplicate `Transfer-Encoding`; Modex
returns 502 without upstream dispatch.
This is a recorded fail-closed security difference, not parity. An earlier
fixture used a decimal rather than hexadecimal chunk size and did not establish
release behavior for valid framing. Both releases and Modex now close without
a response for raw UTF-8 header bytes. Embedded-control and mismatched-length
cases also avoid upstream dispatch in Modex. These are selected Linux x86-64
controls; all six baseline targets stay in the denominator. Evidence:
`docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md`.

## Relay numeric Content-Length duplicates (2026-10-30)

Both pinned TinyHTTP sources select the first `Content-Length` and parse it as
decimal when no transfer encoding is present. Modex's production compatibility
parser now accepts later values only when they parse to the same first length.
It still rejects conflicting numeric lengths, `Content-Length` with
`Transfer-Encoding`, and duplicate `Transfer-Encoding` before provider I/O.
Tests compare both pinned real processes with the production Modex relay for
leading-zero variants in either order, fragmented and pipelined requests, and
truncated body half-close. The shared parser defaults and request/body caps did
not change. The full focused parser and real-process pair passed 36 tests on
Linux x86-64. Ambiguous transfer framing remains a documented fail-closed
security difference. See
`docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md`.

The raw requests `Expect: 100-continue\x00bad` with `Content-Length: 0` and
`Expect: 100-wait` with duplicate zero `Content-Length` fields return 417 with
no interim response, an empty body, a closed client socket, and no upstream
request on 0.165.1, 0.439.2, and Modex. Raw response heads have the same status
line and stable headers; only the dynamic `Date` value varies. The stale Modex
400 and 502 assertions are corrected and the exact stable wire is checked in
both release comparisons. These are selected Linux x86-64 controls.

Full-suite validation at `b9b52d5` also recorded an intermittent
`test_truncation_and_rotation_reopen_followed_file` failure in JSON mode: the
follower emitted no output for the `after-rotation` marker within the test's
five-second wait. On clean `2d1217d`, the focused test passed once and then
three consecutive repeats under quiet conditions. The full-suite failure was
not reproduced or fixed; retain it as an unqualified intermittent log-follow
gap until it is reproduced and addressed. Run details are recorded in
`docs/evidence/log-follow-rotation-recheck-20261030.md`.

Native Anthropic Responses requests now accept `background: false` and
`truncation: "disabled"`, validating and omitting both through the shared
request mapper like Prodex 0.165.1 and 0.439.2. Both releases and Modex agree on
missing/default controls, invalid `background: true` and `truncation: "auto"`,
upstream bodies, and normalized responses across auto, forced Anthropic, and
forced Chat routes with buffered and streamed requests. The focused
three-process matrix, production build, 71-file dependency audit, and diff
check pass. This qualifies only these controls on Linux x86-64; all six
baseline targets remain in the parity denominator. See
`docs/evidence/baseline-0.165.1/anthropic-background-truncation-controls.md`.

Anthropic streamed `tool_use` blocks with missing, null, non-string, empty, or
whitespace-only names now follow both pinned releases' deferred validation
path. Three-way real-process comparisons match the complete normalized event
sequence and request for five malformed cases plus a valid-name control. The
nine selected function index/stop cases also match after UUIDv7 fallback IDs
are validated and narrowly normalized. See
`docs/evidence/baseline-0.165.1/anthropic-stream.md`; broader provider parity
remains unqualified.

Session ordering now rejects signs inside fixed-width date, time and timezone
components, matching both pinned releases; standalone signed integer
timestamps remain accepted. Eight invalid strings and a valid control were
compared through production session reports with fixed file times. The shared
timestamp parser also serves logs and rate-limit projection; their focused
checks are recorded in `docs/evidence/baseline-0.165.1/session-signed-date-components.md`.

Anthropic Messages translation now accepts Responses function-call history
for shared adjacency repair. Malformed JSON arguments on a matched call return
the pinned releases' local 400 in native modes; explicit Chat mode forwards the
raw arguments. Buffered and streamed synthetic process controls match both
releases. Other function-call shapes and provider behavior remain unqualified.
See `docs/evidence/baseline-0.165.1/anthropic-mixed-tools.md`.

Log CLI suggested-option usage now matches checksum-pinned 0.439.2 when an
unknown option resembling `--json` follows a positional value. Three real
process regressions cover valid, invalid and dash positionals. The production
build and focused log CLI suite passed with isolated temporary homes. This
qualifies only these selected parser diagnostics; log output, other argument
combinations, security behavior, the remaining five release targets and full
parity remain open. Evidence:
`docs/evidence/baseline-0.439.2/log-cli-unknown-option-usage.md`.

The full 87-case log CLI argument matrix now also runs against the checksum-
verified Prodex 0.165.1 process. It compares the shared Modex parser with both
the historical 0.439.2 and 0.165.1 releases using isolated synthetic
homes. The selected parser cases match both; this does not cover successful
live log sources, output parity, or other release targets. Evidence:
`docs/evidence/baseline-0.165.1/log-01651-tests.md`.

The production relay now accepts TinyHTTP's ASCII nonstandard method syntax
such as `G@T`, retaining the parsed HTTP version. Checksum-verified 0.165.1,
0.439.2 and Modex processes agree on a selected unsupported-route 404 and on a
supported Chat Completions request that returns 502 before any synthetic
upstream request. The outbound method validator remains in place. Evidence and
the focused real-process comparison are in
`docs/evidence/baseline-0.439.2/local-relay-http-1.0.md`.

Multi-key DeepSeek rotation now runs through the production Super relay.
Unbound requests and requests with unknown response, session or turn IDs start
from an atomic round-robin cursor and can retry on another key before
commitment. The classifier matches the pinned code set, structured 429 rule,
and selected non-429 status/text fallbacks. Retryable native Anthropic
first-event errors and pre-event transport failures allow one credential
retry. Combo model candidates run before credential rotation. The first-event
retry budget is global across the model and credential attempts; auth-class
first events rotate and restart at the first model. The exhausted first
retry-classified error frame is consumed before the stream reader, matching
the pinned `provider_stream_error` code and `unexpected end of stream`
message; an error after stream progress remains terminal. Non-2xx SSE stays on
the raw pass-through path. Known hard bindings keep the pinned 503 gate.

Native Anthropic first-event classification also preserves the pinned
case-sensitive event gate: a top-level retryable code rotates only when
`type` is exactly `error`; an explicit `error` member is classified regardless
of event type. Four synthetic process cases match both releases, including
uppercase and whitespace-padded event types.

Real-process comparisons against both checksum-pinned Linux releases pass for
the tested rotation, error-code, continuation and concurrent-conflict cases.
Concurrent requests with the same unknown identity may use different keys;
the later conflicting owner is rejected before provider dispatch. The focused
production build, relay comparisons and 71-file dependency audit pass. This
does not establish the six-target denominator, public network/TLS, persistent
or profile-backed ownership, or complete provider parity. See
`docs/evidence/baseline-0.165.1/super-api-key-env.md`.

A three-key exhaustion control now covers both Responses and Chat Completions:
each retries A, B, and C on retryable 429s, returns C's raw error, then starts
the next logical request at B. The 0.165.1, 0.439.2 and Modex processes match.
This verifies one three-key sequence on each route; larger pools and other
exhaustion sequences remain unqualified.

The round-robin cursor now matches the pinned request ordering for selected
sequential cases. An unsupported `/v1/unknown` route and known response, session,
and turn continuation 503 rejections do not advance it. Raw malformed Responses
JSON (`{`) consumes once before its 502; empty-input web-search 400s consume in
`auto`/`anthropic`. `openai_chat` sends the empty-input search and rotates from
A to B as usual. Malformed Chat Completions JSON is passed byte-for-byte to
the upstream and consumes key A, so the following request uses B. The 0.165.1,
0.439.2 and Modex process comparisons pass for these vectors. The
unsupported-route case does not test malformed request-target syntax. Other
invalid-body, target, or translation-time rejection orderings remain
unqualified; no full parity status is promoted. See
`docs/evidence/baseline-0.165.1/super-api-key-env.md`.

The recorded combined rotation and shared Anthropic stream run passed all 38
tests before the three-key exhaustion method was added; it included the prior
14 rotation methods, error-event compatibility, and pipeline/half-close
shutdown controls. The focused three-key route comparison and two-route
structured-error matrix pass separately.
The synthetic client now edits only the sequential request loop, so the
generated Codex probe and stream requests run as intended.

The Anthropic Messages request path now accepts Responses `metadata` objects
and `include` arrays, then drops them from the provider request like both
pinned releases. It checks the same top-level types; both releases accept
arbitrary nested values and array entries. Synthetic process comparisons cover
buffered auto, forced-Anthropic and Chat routes, plus streamed auto and
forced-Anthropic requests. Invalid top-level types return the same pre-POST
502 response. The focused process test and production dependency audit pass;
no provider parity status is promoted. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-request-metadata-include.md`.

The Anthropic adapter now labels unsupported translated Chat fields with the
same safe-reason prefix as Prodex. This restores auto-mode Chat fallback for
valid `logprobs` and supported reasoning effort, while explicit Anthropic mode
returns 400 before POST. Malformed values and unsupported `service_tier` still
fail before provider I/O. Buffered/streaming process comparisons pass across
both releases and Modex. No relay routing changes or parity statuses were
needed. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-chat-fallback-fields.md`.

Further admission profiling compared both pinned processes, the current relay,
and the unmerged aggregate-budget prototype under 246 incomplete heads. With
six 200 KiB heads held in active workers, the prototype served two healthy
keep-alive requests but used 0.97 CPU seconds over about two seconds versus
0.01–0.02 seconds for the releases; the current relay returned neither during
the sample. The prototype's padded-head RSS increase was about 4.7 MiB above
its no-padding control, while its accounting charged those six active heads
only 96 KiB. It remains unmerged: active retained bytes, fairness and CPU need
correct accounting and measurement before the timing/shutdown matrix can
qualify it. These are local observations, not full parity evidence.

DeepSeek Super now starts without an explicit `--model` on its supported
synthetic loopback path. It leaves the child model override absent and uses the
shared config's string model, or `deepseek-v4-pro`, for the generated catalog.
Real-process controls against both pinned releases cover missing, blank,
non-string, whitespace and escaped model values, with one matching synthetic
provider request. This does not establish general provider, profile or model
selection parity. Evidence:
`docs/evidence/baseline-0.165.1/super-shared-config.md`.

DeepSeek Super now resolves API keys through `--api-key`, `DEEPSEEK_API_KEY`,
or a plural `DEEPSEEK_API_KEYS` list. Explicit keys take precedence; plural
entries accept comma, semicolon, and newline separators. The list reaches only
the dedicated relay child; both provider key variables remain scrubbed from
all Codex children. The releases expose the key variables to Codex
version/help probes before scrubbing them from the final launch; this remains
a deliberate security behavior difference. Synthetic process tests cover
precedence, validation, Authorization, key rotation and Codex environment
isolation against both releases and Modex. Unsafe header bytes are rejected by
Modex before child creation or provider I/O. No real credentials or provider
traffic were used. See
`docs/evidence/baseline-0.165.1/super-api-key-env.md`.

The next aggregate-budget relay admission prototype remains unmerged. In an
isolated 246-partial-head load with eight blocked workers, the current relay
used 0.55 CPU seconds over two seconds with 146 accepted client descriptors;
the prototype used 0.82 seconds with 256 descriptors. A separate reserve and
keep-alive stress case used 1.20 CPU seconds over two seconds and failed its
1.0-second CPU bound even after reducing repeated scans. The candidate's final
backoff changes were not revalidated against the release timing or shutdown
matrix. Its accounting and reserve transitions need further review, including
active workers retaining large parsed heads. The current bounded queue and
its documented saturation gap remain in production; these observations are
not parity evidence.

The 2026-10-30 three-process admission follow-up traced both pinned releases
to TinyHTTP's uncapped `TaskPool`: each accepted socket becomes a task, and a
new thread starts whenever none is waiting. Synthetic production comparisons
confirm that 0.165.1 and 0.439.2 preserve a preconnected idle socket during
136-client floods; Modex closes it. With seven incomplete-body blocker
requests and 136 partial headers, both releases serve two healthy keep-alive
requests before release while Modex waits until held clients close. The bounded Modex listener
also deliberately evicts the oldest completed idle socket from a full pool,
while retaining an oldest partial request. A one-socket carveout would shift
eviction to later idle clients and does not match the uncapped release policy,
so no production policy change was made. Evidence and one-sample process-tree
metrics are in `docs/evidence/baseline-0.165.1/local-relay-admission.md` and
`docs/evidence/baseline-0.165.1/local-relay-admission-tests.txt`. The
process-tree probe excludes fake Codex and counts the supervisor plus relay
child; the earlier prototype probe's `/proc/<ppid>` numbers target Modex's
supervisor only and remain invalid.
These tests do not combine the backlog with parent EOF, large request heads,
or header timers. A fresh worktree based on `origin/main` commit `6210413`
reran the three-scenario admission test (18.344 seconds), both release framing
guards, and the retained-overflow parent-EOF test. The guard tests passed;
admission mismatch remains, and these checks do not qualify parity. This
investigation found no bounded production policy that avoids raising resource
limits or moving the eviction boundary. Keep the admission
gap and fail-closed ambiguous-framing behavior visible; no platform status is
promoted. See
`docs/evidence/baseline-0.165.1/local-relay-admission.md`.

A final test-only recheck on `origin/main` (`1274046`) kept the production
eviction policy unchanged. Real-process coverage offered 132 idle clients and
confirmed that Modex closes old idle sockets to keep a new healthy request
available. A two-worker parent-EOF case filled 132 client descriptors with two
body-blocked requests, 128 partial headers, and two overflow requests, then
verified shutdown cleanup. At the 12-worker ceiling, 128 parked, 12 overflow,
and 12 worker-owned slots with a 2 MiB head limit yield a derived 304 MiB
request-head estimate; this is not an aggregate RSS bound. The seven-blocker
release comparison still shows Modex waiting about 3,003 ms for held clients
while both releases serve healthy requests before release.

The release fixture now checks raw wire output for the malformed-trailer
invalid-target case and the bodyless chunked invalid-target case. The 0.439.2
chunked case sends two bounded 400 responses before EOF; Python's normal
`HTTPResponse` close sample can observe bytes from that second response instead
of EOF, so only that observational assertion was removed. Status, first body,
interim responses, and the zero-upstream assertion remain exact. Test output and
limits are recorded in
`docs/evidence/baseline-0.165.1/local-relay-admission.md` and
`docs/evidence/baseline-0.165.1/local-relay-admission-tests.txt`.

DeepSeek Super now preserves a safely checked shared `config.toml` in the
isolated child home. The three DeepSeek runtime settings take precedence over
environment values, and string-valued catalog context/compaction settings
affect the generated catalog as in the pinned releases. Real-process controls
cover selected ordinary config, invalid catalog values and missing-profile
ordering. Unsafe permissions, symlinks, exposed hard links and existing home
data remain guarded. General config behavior, profile lifecycle and transport
parity remain unfinished. Evidence:
`docs/evidence/baseline-0.165.1/super-shared-config.md` and
`docs/evidence/deepseek-strict-tools-04392.md`.

Anthropic streamed function calls now ignore non-string or missing
`input_json_delta.partial_json` fragments like both pinned releases. The
function call completes with its existing empty argument string; a focused
synthetic process comparison covers number, null, missing, boolean, and object
values against 0.165.1, 0.439.2, and Modex. The earlier 54-test mixed-tools
process suite passed. Other Anthropic content and event shapes,
continuation, transport security, and non-Linux targets remain unqualified.
Evidence: `docs/evidence/baseline-0.165.1/anthropic-response-shapes.md`.

Anthropic stream `error` events now match both pinned releases when the error
object or either field is missing, null, or non-string. Valid strings,
including empty strings, are preserved independently; unknown extension fields
are ignored. An 11-case synthetic real-process comparison also sends one valid
error event in three-byte HTTP chunks and confirms terminal `response.failed`
ordering. The production build, two neighboring three-process error/terminal
checks, focused native stream reader, dependency audit, and test census pass.
Existing SSE and HTTP body limits remain unchanged. See
`docs/evidence/anthropic-stream-optional-metadata-shared.md`.

Session CLI errors for malformed attached values on boolean switches now match
both pinned Linux releases across split/attached prior values, switches,
conflicts, missing split values and top-level/resume help errors. The
356-case-per-release matrix leaves synthetic homes unchanged;
the full five-method session CLI suite and native parser program passed.
Session data and lock handling are unchanged. See
`docs/evidence/baseline-0.165.1/cli-observations.md`.

Buffered Anthropic response envelopes now ignore unrecognized top-level and
usage fields, fall back for invalid or missing IDs/models, default invalid
usage counters to zero, omit missing/non-object usage, and project valid
`server_tool_use.web_search_requests` into Responses `tool_usage`. Both pinned
Linux releases match these cases through production Super process comparisons.
The content array and 65,536-block bound remain enforced; other malformed
content and full provider behavior remain open. The 50-test mixed-tools suite,
focused native buffered test, production build/import audit, test census, and
diff check passed. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-buffered.md`.

Gateway CLI parsing now treats a literal `--` as the option terminator and
reports the first following token as unexpected, matching checksum-pinned
0.165.1 and 0.439.2 processes. The production build, native Gateway argument
program, six real-process test methods, production import audit, test census
and diff check passed. This selected parser behavior does not qualify Gateway
startup; its operational path and remaining argument combinations are
unfinished. Evidence: `docs/evidence/baseline-0.165.1/cli-observations.md`.

`session list` now prints its existing plain report on an ordinary TTY instead
of failing with `session terminal rendering is not implemented`. Both pinned
release processes still launch the interactive `Prodex Sessions` screen, so
this is a safe output fallback and does not claim TUI parity. Fallback output
continues to match both releases under the tested CI/strict controls, and the
state-file guard still runs first. The 17-test session-text suite and 71-file
production import audit passed on Linux x86-64. TUI interaction and the other
five release targets remain open. See
`docs/evidence/baseline-0.165.1/session-terminal-fallback.md`.

Human-readable session output now escapes C0/C1 controls in session fields and
`session current --cwd`, preventing terminal control injection from synthetic
rollout metadata and arguments. Both pinned releases emit these bytes raw, so
this is a deliberate safe difference, not parity. JSON and selector behavior
stay unchanged. The 68 focused report/profile/state/text/CLI tests and 13
query/resume checks passed against the pinned Linux releases; the import audit
covered 71 Mojo files. See
`docs/evidence/baseline-0.165.1/session-display-controls.md`.

The Anthropic web-search route now maps Responses `instructions` strings into
the leading Anthropic `system` field, then joins input system/developer messages
with `\n\n`, matching 0.165.1 and 0.439.2. Unicode whitespace-only values are
omitted, surrounding Unicode whitespace is preserved for nonblank values, and
non-string values fail before provider I/O. The production build and two
focused three-process comparisons passed. See
`docs/evidence/baseline-0.165.1/anthropic-instructions.md`.

The Anthropic Messages adapter now maps untyped `role: "tool"` input items
with missing or unusable IDs to `call_prodex` and groups results before text,
matching the checksum-pinned 0.165.1 and 0.439.2 processes. Selected function
output IDs remain intact in grouped history. Five focused real-process methods
passed on Linux x86-64, including buffered and streaming comparisons. The
71-file import audit, 50-native/135-Python test census, and `git diff --check`
passed. The previous production build covered the unchanged Mojo source.
Broader tool-result round-trips remain incomplete. See
`docs/evidence/baseline-0.165.1/anthropic-buffered.md`.

Profileless Gateway startup now classifies root-level
`model_provider = "prodex-deepseek"` as the missing OpenAI-proxy case even when
the Codex config has unrelated top-level or nested settings. Real-process checks
match checksum-pinned 0.165.1 and 0.439.2; the locally available 0.439.1 oracle
matches too. Duplicate and malformed TOML still fail before classification,
and no-config startup matches the releases' no-profile error. A project-only
`model_provider` now matches the releases' no-profile diagnostic because it is
not a root profileless-provider setting. The real-process test checks exact
exit/output, no loopback request, and no Modex filesystem mutation. Group-
writable configs retain Modex's stricter guard. A synthetic `state.json` also
hits the existing-state fail-closed guard; release parity for populated profile
state remains unverified. All tested cases exit before loopback provider I/O.
Full Gateway startup, provider exchange, and lifecycle/housekeeping filesystem
parity remain incomplete. Evidence:
`docs/evidence/baseline-0.165.1/gateway-config-classification.md`.

A pinned 0.165.1 broker process control holds 16 idle local WebSockets and an
incomplete text-frame header on one, then receives matching pongs on two other
connections without upstream I/O. This adds a reproducible requirement for the
release's idle parking and partial-frame isolation; it is reference-only, not
Modex parity. The bounded idle-cache limit, message admission and interruption
remain unverified in Modex. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

The DeepSeek Anthropic web-search route now forwards `temperature`, `top_p`,
and the `stop`, `stop_sequences`, and `stopSequences` aliases, matching the
normalized request bodies from checksum-pinned 0.165.1 and 0.439.2. Invalid
types still fail before provider I/O. The production build and two real-process
comparison methods passed. The import audit covered 71 Mojo files; the census
covered 50 native sources and 133 Python modules. Other request fields remain
guarded. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-request-sampling.md`.

DeepSeek requests that combine web search with JSON-object or JSON-schema
output now follow both pinned releases: `auto` mode falls back to Chat
Completions, preserving the JSON request and dropping the unsupported search
tool; explicit `anthropic` mode returns 400 before provider I/O. The production
build and two real-process methods passed against both checksum-pinned Linux
oracles. The combined nine-method neighboring run passed; the import audit
covered 71 Mojo files and the census covered 50 native sources and 134 Python
modules. Evidence: `docs/evidence/baseline-0.165.1/anthropic-websearch-json-mode.md`.

The Mojo 1.2.0 (`2016d0cd`) source audit found no production standard-library
WSS/TLS or DNS path. `std.net` exposes only internal POSIX socket building
blocks; `std.hash` provides AHash/FNV-1a, and `std.random` is explicitly not
cryptographically secure. Public TCP/TLS, DNS, SHA-256, and CSPRNG compile
probes fail. A private IPv4 UDP socket probe runs locally; LLVM address-layout
probes compile for four Linux/macOS release targets and fail for both Windows
targets because `SockaddrIn` is unsupported. This is compiler/API evidence,
not target runtime validation or parity; all six release qualifications stay
BLOCKED. See `docs/evidence/mojo-1.2.0-network-tls-dns.md`.

Buffered Anthropic response validation now ignores a structurally valid orphan
`web_search_tool_result`, after text or as the only content block, matching
both pinned releases through the production Super path. Four cross-release
process methods, the focused native buffered test, production build, import
audit, test census and diff check passed. Unsupported blocks and broader
provider behavior remain unqualified. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-orphan-result.md`.

Hosted Fast run `40840411893` on `479cd57136ddc9c52b8952d48d095eecf02eef9c`
failed after focused build and native checks passed because the required
0.439.2 tag was unavailable. Oracle-dependent checks did not run.

The guarded DeepSeek Super path now accepts explicit `--no-proxy` before or
after `exec`. Both pinned releases and Modex complete a synthetic loopback
provider request with unreachable proxy settings and matching normalized child
arguments and request bodies. The production build, three process tests,
dependency audit and test census passed. Public proxy, DNS and TLS behavior
remain open. See `docs/evidence/baseline-0.165.1/super-no-proxy.md`.

Super now passes explicit `--profile` through its production launch path. With
an empty profile store, Modex returns the same missing-profile error as 0.165.1
and 0.439.2 before starting Codex or contacting a provider. Their
lifecycle/housekeeping lock files remain absent in Modex; existing profile
state, safe locking/recovery, broker bootstrap, and WebSocket
lifecycle/interruption are still open. Evidence and the isolated real-process
command are in `docs/evidence/baseline-0.165.1/super-missing-profile.md`.
The production build and native unit build passed; the new comparison plus the
no-proxy and supported-exec launch controls passed against both releases and
Modex. The native Super parser, production import audit, test census, and diff
check also passed.

The guarded DeepSeek Super path now forwards tested Codex `exec --cd` and `-C`
arguments, including attached values, matching checksum-pinned 0.165.1 and
0.439.2 child argv. Missing or option-looking separate values remain guarded.
The production build, three process methods, dependency audit and test census
passed. The synthetic Codex child records arguments but does not verify actual
working-directory changes. See
`docs/evidence/baseline-0.165.1/super-exec-working-directory.md`.

The guarded DeepSeek exec path now forwards repeatable Codex `--add-dir`,
`--enable`, and `--disable` options, including attached values, after prompts,
and across `--` literal boundaries. Tests against both pinned release
processes confirm identical child argv and unchanged Modex-generated config.
The effective precedence of `--enable` over generated disabled feature settings
has not been verified with a real Codex child.
Modex's synthetic process tests reject missing, option-looking, and empty
`--add-dir` values before overlay or child launch. A one-time local Codex CLI
0.165.0 characterization observed that the releases defer the error to Codex;
this external-binary check is not in the automated suite. See
`docs/evidence/baseline-0.165.1/super-exec-value-options.md`.

The same guarded path forwards `--strict-config`, `--worktree`, and a nonempty
`--thread-source` value. Synthetic child comparisons cover both pinned Linux
releases, including separated and attached values and a literal `--` boundary.
The child fixture does not exercise real Codex configuration or worktree
behavior; malformed thread-source values remain guarded before launch. See
`docs/evidence/baseline-0.165.1/super-exec-worktree-options.md`.

Buffered Anthropic thinking blocks now produce reasoning items in tested
search and mixed-tool responses. Session text reports include bound profile
details; C0/C1 control characters are escaped, unlike the releases' raw output.
The local relay's bounded request-head cap is now 2 MiB; both releases accept
larger heads and some smaller layouts still hit outbound limits. Real
`super exec` controls for an 80 KiB head, fragmented exact-limit head, and the
2 MiB + 1-byte mismatch are in `docs/evidence/runtime-slow-partial.md`. The
combined production build, 54 provider/session process tests, two large-head
oracle controls, two Super launch controls, dependency audit and test census
passed.
Worker suites additionally passed 16 historical relay and 48 local relay/shared
parser tests. The reasoning continuation control returns the same 503 before a
second provider POST in both releases and Modex, leaving retained-history
behavior unqualified. See `docs/evidence/baseline-0.165.1/anthropic-buffered.md`,
`docs/evidence/baseline-0.165.1/session-profile-text.md` and
`docs/evidence/baseline-0.165.1/local-relay-http.md`.

At the initial one-slot checkpoint, local-rewrite admission retained and
scanned one overflow client while worker or parked-slot capacity was
unavailable. A direct production-relay regression
fills all 128 parked slots with partial headers, holds each worker on an
incomplete body, and queues two complete clients; neither responds before a
worker is released, and both then receive 200. Parent-channel EOF also closes
the retained overflow client. The full historical 0.165.1 relay suite passed
19 tests, the 0.439.2 suite passed 11, and the slow-partial suite passed 11.
In a separate 128-partial-header test with free workers, a healthy request
returned 200 in 4.1 ms before the partial clients were released.
That checkpoint's cap was 128 parked sockets plus one accepted overflow and a
128-entry kernel listen backlog. The bounded queue follow-up below supersedes
this limit. Prodex 0.439.2 can add TinyHTTP parser threads and has no hard
queue cap, so full admission flood and wait-time parity remain open. See
`docs/evidence/runtime-overflow-admission.md`.

Hosted Fast run `40837992499` on `3ef8a2b58a5ab63c8fa6422079d09207b06a7937`
failed after the focused build and native checks passed: the required 0.439.2
tag was unavailable. Oracle-dependent tests did not run.

Hosted Fast run `40837362548` on `736098a5c599ed797e27879db2a56f306c1d6ab5`
failed after its focused build and native checks passed because the required
0.439.2 tag was unavailable. Oracle-dependent tests did not run.

The guarded DeepSeek Super launch now accepts explicit `--full-access` before
or after `exec`, matching the already-enabled default in both pinned releases.
Two real-process comparisons cover normalized child argv and the synthetic
loopback provider request, and an unverified-argument guard regression passes.
The production build, native Super parser, import audit and test census pass.
See `docs/evidence/baseline-0.165.1/super-explicit-full-access.md`.

Anthropic Messages now forwards validated output-token limits and tested alias
precedence instead of rejecting nondefault values. Terminal session output now
falls back to plain text under tested `CODEX_CI` and `PRODEX_TUI_STRICT`
controls without changing the state lock guard. The local relay now emits the
terminal chunk for tested HEAD event streams, including pipelined follow-up
requests. Each behavior is compared to checksum-pinned 0.165.1 and 0.439.2
Linux releases. The combined production build, native session/Super checks,
19 provider/session process tests, five framing controls, three Super launch
tests, six CI-routing
tests, 71-file import audit and 130-module test census passed. The initial
framing invocation also had two test-class-name errors; a corrected five-test
rerun passed. See `docs/evidence/baseline-0.165.1/anthropic-output-token-limits.md`,
`docs/evidence/baseline-0.165.1/session-terminal-fallback.md` and
`docs/evidence/baseline-0.165.1/local-relay-http.md`.

Hosted Fast run `40835269269` on `e760cf6805bac76e6535737a4c466905eaa55250`
failed after the focused build and native checks because the required 0.439.2
tag is unavailable. Both helper shards passed; oracle-dependent tests and
the artifact consumer did not run.

The guarded DeepSeek Super path now forwards explicit Codex `--ephemeral`
and `--image`/`-i` arguments. Synthetic child argv matches the pinned 0.165.1
and 0.439.2 releases for separate, attached and repeated image arguments;
missing values and separate option-looking values remain guarded. The
production build, native parser, three launch tests, dependency audit and test
census passed. The child fixture does not establish actual Codex image decoding,
provider image support or session-persistence behavior. See
`docs/evidence/baseline-0.165.1/super-exec-output-flags.md`.

Anthropic web-search source projection now matches selected 0.165.1 and
0.439.2 buffered and streamed responses: entries with string URLs are kept,
string titles are included, and other entries and fields are ignored. Invalid
UTF-8 retains the tested release failures. Session parsing also matches twelve
two-release controls for split `--limit` errors and later arguments. After
integration with the Super and Gateway changes, the production build, native
session parser, 26 provider/session/Gateway process tests, three Super process
tests, five CI-routing tests, dependency audit and test census passed.
The final combined build also passed four provider process controls covering
missing, empty and non-array source content and malformed UTF-8, and two
session/Gateway parser controls. The worker's full mixed-tool and 0.439.2
provider suites passed 20 and 22 tests respectively after the final guard fix.
The two newly cross-release-dependent modules run after both oracles in Fast
and Full CI. Evidence: `docs/evidence/baseline-0.165.1/anthropic-mixed-tools.md`
and `docs/evidence/session-limit-error-precedence-01651-04392.md`. Gateway
startup, managed session launch and full provider behavior remain incomplete.

Gateway option parsing now treats a lone `-` as a value. The invalid-provider
diagnostic and the missing-value control match the checksum-pinned 0.165.1 and
0.439.2 releases. The combined production build, native Gateway check, four
focused process tests, dependency audit and test census passed. Gateway startup
and provider exchange remain incomplete; see
`docs/evidence/baseline-0.165.1/cli-observations.md`.

Hosted Fast run `40832483695` on `e3e47e58453fc05a68a76476a617fb4e263e5dbc`
failed at the unavailable 0.439.2 tag after its focused build and native
checks passed. Its oracle-dependent tests and artifact consumers did not run.

The guarded DeepSeek Super launch now forwards selected Codex output-file and
output-schema arguments. Synthetic child argv matches the pinned 0.165.1 and
0.439.2 releases for separated and attached values, short `-o`, and `-`.
Missing values or a separate option-looking value remain guarded. Production
build and the three focused real-process tests passed; the synthetic child does
not verify Codex file or schema behavior. See
`docs/evidence/baseline-0.165.1/super-exec-output-flags.md`.

Hosted Fast run `40829783630` on `fe86a659ea920755f5c5ebf477a93b0de172f1e9`
failed at the unavailable 0.439.2 tag after the focused build and native
checks passed. Oracle-dependent tests and artifact consumers did not run.

Hosted Fast run `40829002499` on `8f4752da279879eff7de1574e905539dbe3cfd94`
also failed at the unavailable 0.439.2 tag after the focused build and native
checks passed. Oracle-dependent tests and artifact consumers did not run.

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

At that historical checkpoint, the reference was Prodex 0.439.2 at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Prodex 0.165.1 and 0.439.1
observations retain historical provenance; 0.439.1 was regression-only. CI
then routed oracle checks to 0.439.2 and kept all six release targets in the
parity denominator. At that checkpoint the inventory had 76 contracts and
complete production parity was unfinished, with all six qualifications blocked.

The read-only session listing now treats a dangling `state.json` symlink as
absent, matching the checksum-pinned 0.165.1 and 0.439.2 Linux binaries.
Synthetic external targets remain unchanged; live symlinks are rejected by the
private state reader, and adjacent lock or last-good markers remain fail-closed.
The focused process comparisons, production build, production import audit and
test census passed. This does not establish race freedom or state-lock and
recovery parity. Evidence: `docs/evidence/session-profile-state-04392.md`.

Gateway help parsing matched tested historical 0.439.2 and 0.165.1
short-cluster and attached-value cases, including Clap's usage variation after
switches and attached versus split values. Synthetic API-key text stays out of
output. The production build, native parser program and focused process checks
pass; this covers CLI parsing only. Evidence:
`docs/evidence/baseline-0.165.1/cli-observations.md`.

Session resume now resolves IDs on the production CLI path using the existing
session reader. Five synthetic real-process tests against the checksum-pinned
0.165.1 and 0.439.2 Linux binaries cover missing/ambiguous errors, exact-ID
precedence over longer prefixes, ASCII case, ASCII/Unicode surrounding
whitespace and blank whitespace selectors, duplicate exact IDs, and state
failure ordering. Missing and ambiguous outputs match both releases. Valid
selections stop before direct Codex launch because Modex still lacks the
managed profile authorization and runtime path. The stricter lock-only and malformed-state refusals remain
fail-closed differences; metadata repair and state database-only candidates
remain open. The native session test, 28 listing/report tests, production
dependency audit, production build, strict-runner test, and test census passed.
The census found 50 native test sources and 129 Python modules. See
`docs/evidence/session-resume-selection-01651-04392.md`.

Anthropic stream stop handling now matches both pinned releases for tested
text, tool, search, and result index reuse. Stops only clear ignored result
indexes; they no longer close text, tool, or search state. Three-way synthetic
process controls cover image collisions, duplicate search/result starts,
post-stop deltas, malformed events, and missing starts. `make build`, the two
native stream checks, and 66 tests across four stream suites passed on Linux
x86-64. An initial broad run exposed four assertion failures and one stale
test-helper reference; the corrected rerun passed. Remaining stream gaps and
limits are recorded in `docs/evidence/baseline-0.165.1/anthropic-stream.md`.
After integrating the Gateway and session changes and narrowing fallback call-ID
normalization to one fixture, the combined production build, two native stream
checks, 67 provider process tests, dependency audit and test census passed.

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

Session listing now reads valid owner-owned state without repair, attaches
profile bindings, and applies profile filters. A single-linked, world-readable
`state.json` inside the verified mode-0700 app root now matches both releases;
group/other-writable state and group/other-readable state with hard-link
aliases remain fail-closed. Five focused session-state process methods passed
against both release binaries; the app-root guard passed with the 0.439.2
oracle. Indexed binding processing matches last-key and 2,048-entry retention
behavior; a 16,384-entry response-map stress case and
2,048-session report case match both 0.165.1 and 0.439.2. Modex still does not
lock or recover state: an invalid primary with a valid `.last-good` remains
fail-closed, dangling symlinks are treated as absent, and live symlinks are
rejected. The existing mode-0755 app-root control also remains fail-closed
because Mojo 1.2.0's allowed stdlib has no chmod operation. Descriptor checks
are not interprocess exclusion. Details and exact artifacts are in
`docs/evidence/session-profile-state-04392.md`.

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

Hosted Fast CI run `40796304229` passed both helper shards, the then-active 0.165.1
and focused relay checks, then failed on the unavailable required historical
0.439.2 tag; the artifact consumer was skipped. An isolated local `make test`
run completed 728 Python tests and the native checks successfully. The checkout
changed during that run, so it is not evidence for an exact final commit.

Hosted Fast CI run `40794762417` passed both helper shards, the build, active
0.165.1 checks and relay checks, then failed because the mandatory historical
0.439.2 tag was unavailable. Its artifact consumer was skipped. No hosted CI
success is claimed for that run.

At an earlier checkpoint, the local relay supported tested sequential and
pipelined HTTP/1.1 keep-alive
requests, honors `Connection: close`, and parks up to 128 idle sockets so a
second client can run. Pipelined requests are parsed and dispatched in order;
responses remain serial. The parked queue is FIFO; when full, admission closes
the oldest idle socket to make room, after ready sockets are dispatched. If no
socket is safe to evict, one accepted overflow connection was retained until
admission was safe. The current bounded overflow queue is described in the
later local-relay status below. Parked sockets have no idle expiry.
Parent EOF is checked between requests and does not interrupt an in-progress
body read. The separate runtime-proxy WebSocket transport remains
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

The bootstrap trace is now tied to the 0.165.1 and frozen 0.439.2 source pins:
runtime launch selects the profile, sends a bounded versioned private-pipe
bootstrap to `__runtime-broker`, and the broker loads application state before
starting the profile-backed listener. The WebSocket message path later reloads
the selected profile's `auth.json` and adds its bearer token/account ID to the
upstream handshake. A connected slice still cannot be built safely here:
Modex Super rejects persisted profile state and has no broker entry point, and
the pinned Mojo standard library lacks TCP/TLS streams, DNS, and WSS transport.
A bootstrap parser or 101-only listener would leave upgraded clients without a
message path. The exact first connected milestone and validation boundary are
recorded in the prerequisite evidence; the capability remains unimplemented
and no parity is claimed.

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
admission, and HEAD event-stream terminal chunks remained an explicit gap at
that checkpoint. SSE
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

The existing bounded logging suite now also runs in an isolated historical 0.165.1
lane. All 36 selected log snapshot, payload, redaction, runtime parsing,
transcript, text and timestamp checks passed against the verified Linux
binary; historical 0.439.2 comparisons remain separate. This does not verify
live-source registry locking/recovery, terminal rendering or non-host targets.
See `docs/evidence/baseline-0.165.1/log-01651-tests.md`.

The production Super Codex version and app-server help probes now run with
`CODEX_HOME` and the five `TEST_CODEX_*` logging variables removed. A synthetic
peer comparison against the historical 0.165.1 Linux oracle verifies both probe
arguments, the selected capability-failure diagnostic, no RPC/provider start,
and overlay cleanup. The version check now enforces the frozen `0.153.2`
minimum: a synthetic `0.153.1` stops before app-server help, while exact-minimum
`0.153.2` from stderr and components with leading `+` are accepted. A version
probe exit 7 also preserves the oracle's path/status/guidance diagnostic. The
tests use a private nested temp directory; oversized version/help capture
errors still match. Modex now matches the selected fallback progress lines,
provider panel, and child-start line on complete redirected stdout/stderr
comparisons against 0.165.1 and historical 0.439.2, with synthetic child and
no provider requests. Historical 0.165.1 also matched redirected provider-panel
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
large-header gaps remained at that checkpoint. See
`docs/evidence/baseline-0.165.1/local-relay-status-reasons.md`.

The local relay now forwards tested HTTP methods on both supported routes,
including extension methods. GET JSON and SSE responses and selected HEAD
framing match 0.165.1, including the terminal chunk for HEAD 204/304 event
streams. Modex still suppressed the release's terminal chunk for HEAD 200
event streams at that checkpoint. Large request heads now match
selected 65,535/65,536/65,537-byte boundaries, 128 KiB fields, and 1 MiB
aggregate/token cases against 0.165.1 and 0.439.2. At that checkpoint the relay
was bounded at 1 MiB; its current 2 MiB limit and remaining mismatch are noted
above. Other
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
on `483bcf1` passed helper shards, build, native units and then-target tests,
then failed on the unavailable required 0.439.2 oracle. Artifact consumption was
skipped; see `docs/ci-lessons.md`.

Fast run [40751613083](https://github.com/christiandoxa/modex/actions/runs/40751613083)
on `12b7392` passed both helper shards, production build, native units and
then-target tests, then failed at the unavailable mandatory 0.439.2 oracle.
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
oracle before acquisition. The stream checks at that checkpoint used only 0.165.1 and Modex;
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
selected 0.165.1 process cases. An additional aggregate production query now
compares all 1,488 UnicodeData lowercase mappings across 0.165.1, 0.439.2, and
Modex; no mapping mismatch appeared. See
`docs/evidence/baseline-0.165.1/session-query-unicode.md`.

Update help and selected parser diagnostics now match 0.165.1 in isolated
process tests; update execution remains unimplemented. The session-query selector now uses the complete Unicode 17 Cased and
Case_Ignorable properties for contextual sigma. Exhaustive scalar tests and
eight real 0.165.1 process comparisons pass; other lowercase behavior and
session state remain unverified. Selected unknown Anthropic event types are now
ignored as in the 0.165.1 release. No contract status is promoted. Profile list
still fails closed because the release acquires interprocess locks and repairs
state; omitting those steps would race concurrent profile operations.

At that historical checkpoint, the next step was to recapture 0.165.1 behavior.
The active target is now 0.166.0. WebSocket transport work
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
`$TASK_SCRATCH/ci-40631003222/`.
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

The reference at that historical checkpoint was Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The tag, Linux oracle SHA-256,
and an isolated full source checkout were verified. Earlier 0.439.5 material
below is historical and retains its original reference; it does not establish
0.439.2 parity. All 76 contracts, 456 platform obligations, six blocked
release qualifications and incomplete inventory remain unchanged.

A combined isolated build restores the 0.439.2 hook version, DeepSeek model
catalog, flash aliases and low-reasoning mapping. Real synthetic launch and
request comparisons covered the then-targeted release and selected separately pinned
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

The historical mission designated Prodex 0.439.5 at
`ac9aad08f25d6dc8cda96463ce2045b40f35f510` as the frozen reference,
superseding the earlier 0.439.2 session instruction. At that checkpoint, the baseline,
CI oracle, and hook client version matched that target. The remote tag
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

The historical reference at that checkpoint was Prodex 0.439.5 at
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
The historical checkpoint target was Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.

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

The historical checkpoint target was Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
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

Sol continued immediately in `$TASK_SCRATCH/sol-error-sse-20261026`, then
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
The immediate continuation used `$TASK_SCRATCH/sol-error-sse-20261026` for
redirect SSE passthrough and stream-header validation. Its final scope,
caller-trace correction and integrated validation are recorded in checkpoint 3
above. Isolated worker boundaries and verified commit/push cadence continue.

# Previous checkpoint: native Super

Historical target: Prodex 0.439.1 at `81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`.
The reference repository remains unchanged. Sixteen relevant snapshot files were
compared byte-for-byte with pinned Git objects; the 0.439.0-to-0.439.1 delta
is 463 files, 8,026 additions and 26,066 deletions. Worker-lane isolation,
nonblocking bounded admission, separate compaction capacity, targeted affinity
release, progress-aware recovery/backoff, tunnel-client 0.0.18 and Kiro CLI
2.34.0 were source-traced. Evidence: `docs/evidence/native-super-reference.json`.

The existing tracked and untracked work was preserved and backed up outside
the repository in `$TASK_SCRATCH/parity-20261026-initial`. This checkpoint integrates
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
`$TASK_SCRATCH/worker-{a,b}-20261026.{stdout,stderr}`; raw logs stay outside the
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

The historical checkpoint target was Prodex 0.439.1 at
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

The historical 0.439.1 help inventory contains 35 routes and 326 option
mentions, including four hidden commands and both Super exposure/short aliases.
Its checked-in fixtures remain historical evidence; a fresh capture is
unavailable without the checksum-verified matching 0.439.1 oracle. The active
capture command, `python3 tests/capture_cli.py`, now writes versioned 0.166.0
inventory and fixtures without touching the historical files. Help mentions
still require source validation for registered flags, hidden flags, defaults,
precedence and passthrough.
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
combinations need further verification. Three quoted Unicode-whitespace inputs
still expose synthetic credentials in the frozen release while Modex masks
them. The earlier unquoted whitespace-only case now matches both 0.165.1 and
frozen 0.439.2 as `password=<redacted>`; additional multi-space, tab, quote,
and control-boundary tests keep malformed values fail-closed. The current
capture retains three unapproved safe differences and three matching outputs
in `docs/evidence/log-mismatches.json`; focused cross-release evidence is in
`docs/evidence/baseline-0.165.1/log-redaction-whitespace-01651-04392.md`.
These observations do not qualify full log parity or any non-host target.

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

The historical 0.165.1 streaming characterization now covers a result completing
while another search input remains open, deltas for that search across the open
result block, a new search starting during an open result, and a valid empty
result array. The parser tracks open search and result blocks independently;
result content still passes array and item validation. The real-process
comparisons match the pinned oracle, and the full focused stream suite passes
26 tests after the production build. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-stream.md`. These cases add no general
Anthropic or provider parity claim; unsupported shapes and targets remain gaps.

The earlier image/index collision gap was fixed in `e3e47e5`: the release and
Modex retain later text, tool and search deltas, and stop events clear ignored
result indices. The selected collision and stop controls are documented in
`docs/evidence/baseline-0.165.1/anthropic-stream.md`; other event orders remain
unverified.

The local relay now supplies the release's default Server and Date headers for
buffered responses, preserving forwarded values and the existing head-size
limit. Its streamed and shared loopback paths retain their existing behavior.
Anthropic web-search translation now projects blocked domains, user location,
and max uses; search context is validated but omitted from the native request.
Conflicting allow/block filters fall back to Chat Completions only in auto mode.
The selected real-process comparisons and remaining limits are recorded in
`docs/evidence/baseline-0.165.1/local-relay-http.md`,
`docs/evidence/baseline-0.439.2/local-relay-http-1.0.md`, and
`docs/evidence/baseline-0.165.1/anthropic-mixed-tools.md`.
The combined production and native driver builds, native unit suite, 48
shared loopback/local-rewrite tests, 30 mixed-tool process tests, both release
raw-header controls, and both `super --no-proxy` controls passed. The production import audit and test
census also passed. The first raw-control command included a mistyped 0.165.1
test class and reported a loader error; the corrected no-proxy test passed.

Hosted Fast run 40841282229 on `a2e341af21236444d64bd56d3efac712f783e387`
passed both helper shards and its focused native build and unit checks, then
failed then-active oracle acquisition because the required 0.439.2 tag was absent.
Oracle-dependent suites and executable handoff/consumer did not run. This is
not a Fast pass. An interrupted build in the primary checkout may have touched
its ignored `build/modex`; its previous hash was not captured and the artifact
was not restored. Tracked source edits in that checkout were left untouched.
Fast run 40844909607 on `f842b8b6f23473cba994c0594096e54c60ca03bd` likewise
passed its helper shards and focused build/native checks, then failed because
the required 0.439.2 tag was unavailable. Its oracle-backed tests did not run;
this is not a Fast pass.
Fast run 40845949112 on `08098b666be8c5ecd09cea693fd09832a00d48f6` likewise
passed the dependency audit and focused build/native checks, then stopped at
the missing 0.439.2 tag before oracle-backed tests. It is not a Fast pass.
Fast run 40847657930 on `dc4ea1ff04f9dc64e9070a2a446ed1f5581838a0` also
passed the dependency audit and focused build/native checks, then failed at the
missing 0.439.2 tag. Oracle-backed tests did not run; this is not a Fast pass.
Fast run 40849847056 on `31ce00a932350b606e11e8c72e90bf03541e1ecc` likewise
passed the dependency audit and focused build/native checks, then failed at
the missing 0.439.2 tag before the oracle-backed tests. It is not a Fast pass.

Full 0.165.1 parity remains incomplete: profile-backed WebSocket capacity and
interruption, managed session launch and recovery, interactive TUI, DNS, TLS,
proxies, security behavior and non-Linux targets remain open. All six release
targets remain in the denominator.

Anthropic web-search requests now discard blank message-array entries through
the existing Responses mapper and return the release's 400 error when no
conversation block remains. Real-process controls compare both releases on
empty, whitespace, system-only, mixed and role-transition cases, and the four
web-search modes. The build, native request-message test, dependency audit and
test census passed. Unsupported input shapes and broader continuation remain
open; see `docs/evidence/anthropic-web-search-04392.md`.

An independent four-module provider run had one failure in an obsolete
assertion that expected a buffered thinking block to fail. After correction,
the four-module characterization run passed all 68 tests. A separate two-release
stream check confirms the invalid-UTF-8-after-failure body-close
behavior remains different; see `docs/evidence/baseline-0.165.1/anthropic-stream.md`.

Buffered Anthropic responses with empty content or text/thinking-only blocks
now match the selected 0.165.1 and 0.439.2 process controls; missing or
non-string text and unknown blocks still reject. The combined production and
two native provider tests built and passed, as did six focused process tests
covering the response change, blank inputs, continuation, thinking and
citations. Dependency and test-census audits passed. Broader response shapes
and continuation behavior remain unqualified.

For a resolved session with no application state or shared Codex config,
resume now matches the two tested releases' no-profile diagnostic. State and
config still preserve the managed-launch refusal; default, absolute and
relative shared-home config paths have process controls. The releases also
create repair, maintenance and housekeeping files that Modex does not; bound
profile launch and state mutation remain unfinished. Evidence:
`docs/evidence/baseline-0.165.1/session-managed-resume.md`.
After integration, the production build and four provider/session native
programs passed, as did all eight resume tests and five focused provider
process tests against the pinned releases. The 71-file import audit and test
census passed; these checks do not establish a complete contract or platform.

Anthropic web-search input now admits selected text-part arrays and object
content through the existing Responses mapper, ignores tested message metadata,
and maps untyped unknown roles as the pinned releases do. Typed invalid roles,
prefix overrides, malformed text and typed images still reject. Both releases
also omit untyped image parts in arrays; a standalone untyped image object is
forwarded as serialized text in both releases and Modex. Production process
comparisons cover both releases, buffered
and streaming requests, and blank/mixed inputs. The five-method 0.439.2 array
suite, focused 0.165.1 controls, 25 transport tests, production build, import
audit and test census passed. Other request shapes remain unqualified; see
`docs/evidence/anthropic-web-search-04392.md`.
Session-resume process controls also confirm that both releases and Modex
ignore a symlinked rollout and reject symlinked state without altering its
target. The releases create four lock files before the state error; Modex
creates none, and the diagnostics differ. All 10 resume tests pass; state
transactions, recovery, and launch remain unfinished.

Buffered Anthropic text blocks now ignore citations and other text metadata,
as both pinned releases do, while retaining the string-text requirement and
tool/search validation. The worker's 37-test mixed-tool process suite passed;
after integration, five focused request/response comparisons, 10 resume
tests, the production build, native provider checks, import audit and census
passed. Broader provider behavior remains unqualified. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-text-metadata.md`.

At the earlier eight-worker checkpoint, the local relay used a bounded worker
pool and canceled tested in-flight
upstream requests on parent EOF. The accept loop now captures request heads
incrementally before handler admission; incomplete headers do not occupy
provider workers. Each pass reads/scans at most 512 bytes per parked socket,
and the existing 2 MiB request-header limit and 128 parked-socket cap bound
capture. `PRODEX_RUNTIME_PROXY_WORKER_COUNT` now controls relay lanes when set:
the existing Modex default remains `min(8, Mojo parallelism)`, positive values
can reduce the pool, and empty, whitespace-only, malformed, or zero values
fail before Codex probes with the same diagnostics as both pinned releases.
Counts cannot increase the pool above its default or the eight-worker cap.
The policy-file `runtime_proxy.worker_count` is not wired to this pool, and
the releases accept counts through 64. The default also differs when the
release's documented CPU-parallelism clamp of 4–12 does not equal Modex's
default; the default controls below were checked only on this Linux x86-64
host. The round-robin overflow list is capped at `max(2, worker_count)`;
completed keep-alive connections enter it when the parked set is full and
capacity remains. Admitted workers still parse headers and read request bodies,
so slow or incomplete bodies can occupy every lane. The 129- and 132-client
flood controls returned 200 before release in 2–3 ms for both releases and
Modex. At 136 partial clients, both releases answered in 2 ms; Modex waited
through the 1,000 ms hold and returned 200 after release. Its test requires
eventual success and records the observed finite-cap mismatch without making
the timing gap an assertion. A 130-client control also verifies promoted
overflow completion, same-socket keep-alive reuse, and a later healthy request
against both releases. Parent EOF with 137 held clients exits and closes peers.
The 15-test `test_runtime_slow_partial.py` suite passed against the pinned
releases and rebuilt candidate; the three-test local admission harness passed
against the candidate. Configured worker counts one and two match the releases
for incomplete-body admission and
synthetic provider overlap; default incomplete-body and provider-overlap
controls also pass. The invalid-value process matrix matches the exact release
diagnostics and confirms no Codex probe or upstream request occurs. Larger
worker counts, policy-file tuning, other release targets, and full admission
fairness remain unqualified. Evidence and commands are in
`docs/evidence/runtime-slow-partial.md` and
`docs/evidence/runtime-overflow-admission.md`.
Fixed-length bodies of 1,024 bytes or less remain in parser capture;
EOF there closes without a response as both releases do. Deferred-body EOF now
returns the baseline 502 and `upstream request failed` body for tested large
fixed-length bodies, chunk-data EOF, and `Expect: 100-continue`. Large
invalid-target and WebSocket heads now return the baseline 400 or 426 before
waiting for body completion. A failed Anthropic stream with an unfinished
downstream body returns its connection for subsequent request handling.
A separate eight-client failure probe now matches in selected timed runs.
Full concurrency, signal, platform, and security behavior remain unqualified;
all six release targets stay in the
parity denominator. See
`docs/evidence/baseline-0.165.1/local-relay-concurrency.md` and
`docs/evidence/runtime-slow-partial.md`.

The local relay now matches selected TinyHTTP request-line handling: it accepts
HTTP/0.9 on the production relay, uses the first three space-separated fields,
and preserves HTTP/0.9 response and `100 Continue` lines. HTTP/1.2 is rejected
with an empty 400 before provider I/O, as both pinned processes do. HTTP/2.0
and HTTP/3.0 remain unqualified: TinyHTTP recognizes their tokens while Modex
returns 400, and the isolated release probe did not obtain a stable response
within five seconds; checksum-verified probes against both pinned binaries
again timed out without a response for either token. Leading request-line
spaces and tabs now match TinyHTTP's trim behavior. The shared parser continues
to reject HTTP/0.9 unless a caller opts in. Both pinned release matrices, the
0.9 pipelined keep-alive control, the focused three-process leading-whitespace
control, and all 27 shared parser tests pass. See
`docs/evidence/baseline-0.165.1/local-relay-http.md`.
Modex now matches a complete, already-buffered pipelined request after an
Anthropic stream fails: the first SSE reply carries `Connection: close`, stays
chunk-incomplete, and a queued request receives the raw second 502 on the same
socket. FIN and RST controls also verify worker release. No-pipeline open-body,
request half-close, complete and truncated pipeline heads, truncated pipeline
bodies, and parent EOF controls pass against both releases. A separate eight
client probe with 32 KiB padded request heads previously exposed a timing gap.
The listener now polls worker completion at 5 ms while work is pending; in two
subsequent FIN/RST runs both releases and Modex emitted the raw 502 on 8/8
connections. The 512-byte fair capture quantum remains; 5 ms polling adds
full parked-socket scans while workers are active, on top of the accept loop's
existing 1 ms retries. General pipeline and saturation parity remain
unfinished. The complete 1 MiB parent-EOF control can finish naturally after
the raw 502, so explicit shutdown is checked separately with a truncated body
and a truncated head. See `docs/evidence/baseline-0.165.1/local-relay-concurrency.md`
and `docs/evidence/anthropic-stream-optional-metadata-shared.md`.

Top-level `web_search_options` without a `tools` declaration now reaches the
native Anthropic search mapping like pinned releases 0.165.1 and 0.439.2.
Unknown options fall back to Chat Completions only in auto mode, while forced
Anthropic mode rejects before dispatch. `parallel_tool_calls=true` is accepted
and omitted from the provider request. Stale 0.439.2 assertions for untyped
roles and typed text content then compared the historical 0.439.2 process and Modex;
the CI lane at that checkpoint did not depend on 0.165.1 before acquisition.
The focused 75-process-test and 35-request/transport-test runs passed after the
production build; the 71-file dependency audit and 50-native/135-Python test
census passed. Broader Anthropic parity and the other release targets remain
open; all six targets stay in the denominator. Evidence:
`docs/evidence/baseline-0.165.1/anthropic-mixed-tools.md`.

Anthropic buffered and streamed responses now ignore unknown metadata on the
tested content blocks and events. Search results use `query` first, then
`queries`; buffered arrays keep strings, streamed arrays retain all values, as
both pinned releases do. Missing streamed function-call IDs use the existing
`call_deepseek_...` fallback; buffered calls without IDs still fail. Earlier
evidence documented that a numeric `input_json_delta.partial_json` failed the
Modex stream although both releases completed with empty arguments. The shared
parser now ignores that fragment, and the updated 54-test mixed-tools suite
passes across synthetic process comparisons. Continuation, unsupported content
blocks, other stream event orders, transport security, and other release
targets remain unqualified. See
`docs/evidence/baseline-0.165.1/anthropic-response-shapes.md`.

The local relay now matches both checksum-pinned releases when an invalid-target
`Expect: 100-continue` request has no body framing or `Content-Length: 0`: it
returns 400 without an interim 100, then accepts a valid request on the same
socket. Sequential and pipelined controls pass through the production relay
against 0.165.1, 0.439.2 and Modex. Invalid-target requests with a nonzero
declared body or chunked framing still close in Modex, while both releases leave
those connections open after 400; Modex keeps the safer behavior because those
request bodies remain unread. No full transport parity is claimed. Evidence:
`docs/evidence/baseline-0.165.1/local-relay-http.md`. The full 16-test
0.439.2 relay module, 27 shared loopback tests, production import audit and
test census passed; no dependency was added.

DeepSeek Anthropic request validation now delegates `function_call_output`
items to the shared Responses mapper, which handles the tested ID and output
aliases and ignores unknown fields. The buffered three-process matrix covers
matched and orphan history in auto, forced Anthropic, and forced Chat modes.
Valid outputs retain their matched IDs; orphan and non-string-primary outputs
are dropped. A whitespace-only primary `call_id` still rejects before
provider I/O, matching both pinned releases. The matrix checks routed result
IDs rather than full request-body equality; broader request serialization and
all other Anthropic shapes remain unqualified. The focused matrix, production
build, 71-file import audit, and `git diff --check` pass. See
`docs/evidence/baseline-0.165.1/anthropic-function-call-output-aliases.md`.
All six baseline release targets remain in the parity denominator.

Native Anthropic Responses requests now accept the boolean `store` control and
omit it from provider requests, matching Prodex. Both pinned releases also
reject null and non-boolean values before provider I/O. The real-process
matrix covers missing/false/true/null/string values, auto, forced Anthropic,
and forced Chat routes, with buffered and streamed requests. The production
build, focused matrix, 71-file import audit, and `git diff --check` pass. This
qualifies only the tested request control on Linux x86-64; all six release
targets remain in the parity denominator. See
`docs/evidence/baseline-0.165.1/anthropic-request-store-control.md`.

The production TinyHTTP-compatible request parser now accepts and collapses
only duplicate `Content-Length` values with identical trimmed digit text. The
shared parser still rejects duplicates. Both pinned releases and Modex return
404 for duplicate zero lengths on an unsupported route, and dispatch equal
duplicate lengths with one normalized upstream length, including both
pipelined request orders. Numeric variants such as `N`/`0N` and `N`/`N+1`
remain intentionally fail-closed in Modex while both releases dispatch using
the first value. With valid chunk bodies, both releases dispatch duplicate
transfer encoding and content-length plus transfer encoding, while Modex
returns 502 without upstream dispatch. The earlier no-response observation
used an invalid decimal chunk size. These remain documented security
differences, not parity passes. The four-test real-process relay suite, 29-test
loopback suite, production build, 71-file dependency audit, and diff check
passed. Only selected Linux x86-64 behavior is qualified; the six-target
denominator and broader transport/security gaps remain unchanged. See
`docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md`.

An uncommitted relay admission-budget experiment remains isolated in
`$TASK_SCRATCH/relay-gap-23c5a22-20261030` with code based on `23c5a22`, five
commits behind `origin/main` `63bb015`. Its 136-partial-head production probe
passed only when the healthy keep-alive client connected after the flood: both
pinned releases and Modex returned two 200 responses. When that client
connected before the flood and sent after the settle period, the candidate
closed it with `RemoteDisconnected` and sent no upstream request, while both
releases served it. The 4 MiB candidate has no qualified resource comparison
because its `/proc/<ppid>` sample targets the Modex supervisor, not the relay.
Current-main three-way results and process-tree measurements are recorded in
`docs/evidence/baseline-0.165.1/local-relay-admission.md`; earlier candidate
measurements and reproduction commands remain in
`docs/evidence/runtime-overflow-admission.md`. The candidate remains
unqualified and untouched.

Buffered Anthropic response validation now admits multiple web-search blocks
and selected interleavings of text, thinking, orphan results, and pending
searches. A three-process production comparison matches checksum-pinned 0.165.1
and 0.439.2 for both tested sequences. The focused mixed-tools module passed 63
tests; the production build, native buffered-provider test, 71-file import
audit, and 50-native/140-Python test census passed. This qualifies selected
buffered shapes on Linux x86-64 only; streaming, other response shapes, all six
release targets, and broader provider parity remain open. See
`docs/evidence/baseline-0.165.1/anthropic-buffered.md`.

Gateway unknown-option diagnostics now suggest the nearest declared option and
show the matching generated usage, including the visible `--url` alias, like
both pinned releases. Real-process comparisons cover nine typo/prior-option
cases with synthetic homes and an API-key sentinel; no contract or release
status is promoted. The production build, Gateway process tests, native parser
checks, dependency audit and test-census audit passed. Evidence and source
traces are in `docs/evidence/baseline-0.165.1/cli-observations.md`.

The local relay now matches both pinned TinyHTTP releases for non-ASCII bytes
in request header names and values. Before the fix, Modex returned an empty
400; Prodex 0.165.1 and 0.439.2 return no response when ASCII line conversion
fails. The production path now closes on that parser error before dispatch.
Real-process controls cover complete and fragmented headers, client half-close,
and an invalid pipelined request after a valid request. The six-test
`test_loopback_header_whitespace` suite, production build, dependency audit,
Python syntax check, and `git diff --check` passed. Probe results record empty
response heads and `RemoteDisconnected`; they do not rely on the helper's
secondary socket-state sample after EOF. Numeric duplicate lengths and
conflicting framing remain fail-closed differences. See
`docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md` and
`docs/evidence/baseline-0.165.1/local-relay-http.md`.

The file-backed upstream log parser now checks both the raw
`upstream_payload` substring and the parsed event name across `log last`,
`log stream`, and `log upstream`. Both pinned release processes reject escaped
event names without the literal substring and unrelated events with payload
fields; they accept escaped names when another field supplies the substring.
The prior Modex behavior and selected process comparisons are recorded in
`docs/evidence/baseline-0.165.1/log-upstream-selection.md`. This does not verify
live log sources, security behavior, or non-host release targets.

Plain runtime log parsing now recognizes the first non-field event after
leading fields and keeps quoted values intact, matching selected file-backed
upstream, token, and stream cases in both pinned releases. Empty and duplicate
fields and malformed quotes are covered by synthetic three-process comparisons.
See `docs/evidence/baseline-0.165.1/log-plain-parser.md`. Live-source, security,
and non-host target parity remain open.

## Session PTY test synchronization (2026-10-30)

The session TUI process test now answers the cursor-position query and waits
for the initial cursor-hide marker before sending `q`. Its earlier title-only
trigger raced the frame writes: the echoed key appeared before or after cursor
restoration, with both orders reproduced in 0.439.2. Six synchronized captures
per pinned release consistently showed cursor-hide before cursor-show. The
test now checks each release's TUI lifecycle independently and keeps Modex's
plain TTY fallback gap visible. This corrects the harness; it adds no TUI
parity. See `docs/evidence/baseline-0.165.1/session-terminal-fallback.md`.

The local rewrite now rejects a valid `Connection: Upgrade` plus
`Upgrade: websocket` after request headers, before reading a declared body.
Real-process controls using checksum-pinned 0.165.1 and 0.439.2 binaries confirm
the existing 426 response, no body bytes, and no upstream request. Invalid-
target 400 and unsupported-`Expect` 417 precedence stay intact. The check
compares complete status, normalized non-Date headers, and body; it does not
claim a socket-close timing contract.
Conflicting content lengths remain fail-closed in Modex with 502; both releases
return 426 for that malformed WebSocket request, so this is a visible behavior
difference. The pinned WebSocket characterization passed 5 tests, the focused
three-process controls passed, the loopback parser passed 30 tests, and the
HTTP/1.1 sequential and HTTP/1.1/0.9 pipeline checks passed. The full
profile-backed WebSocket/WSS route remains unimplemented. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

Super's `--cli`, `--web-search`, and `--current-time-clock-source` invalid
pre-command values now use the release's Clap diagnostics, including tested
suggestions and empty-value handling. Invalid post-command values use the
release's runtime error, and supported case variants reach the existing guarded
startup. Both pinned release processes and Modex pass selected synthetic
argument comparisons; missing launch/state behavior and non-host targets remain
gaps. See `docs/evidence/baseline-0.165.1/super-enum-values.md`.

## Buffered provider response JSON shapes (2026-10-30)

The buffered DeepSeek path now returns the pinned releases' bodyless HTTP 500
for JSON roots that are not objects, matching its existing handling for a
non-object first choice. Buffered Anthropic null, scalar, array, and malformed
roots continue to return 502. Synthetic three-process tests also cover valid
Buffered Anthropic tool calls also preserve string-valued empty IDs and names,
as both pinned releases do; missing and non-string fields still fail.
Synthetic three-process tests also cover valid response translation and
retryable 503 key rotation on DeepSeek and Anthropic. The five focused
response-shape methods and ten CI oracle-routing methods passed on Linux
x86-64. This qualifies only the listed buffered cases;
it does not establish full provider parity or reduce the six-release
denominator. See
`docs/evidence/baseline-0.165.1/provider-buffered-response-shapes.md`.

## Relay large-field dispatch and readiness follow-up (2026-10-30)

The earlier 1 MiB translated-field and 2 MiB + 2 KiB outbound limits in this
historical section were superseded by the current bounds recorded above.

At that checkpoint, the chat-completions passthrough admitted the tested
1,048,577-byte `User-Agent` with a 2 MiB field limit and 2 MiB + 2 KiB outbound
aggregate cap. Both releases and Modex dispatched it, but their captured
headers differed. The later header-parity follow-up below resolves the tested
duplicate `User-Agent`, default `Accept`, and `Connection` differences. The
translated Responses path still retains its 1 MiB field limit; both releases
dispatch 1 MiB + 1-byte values there while Modex returns 502 before dispatch.

The focused large-header production-path tests passed against 0.165.1 and
0.439.2 after recording the chat-route duplicate count by product. The relay
fairness mismatch for seven incomplete-body blockers and 136 partial heads is
unchanged. Mojo 1.2.0 documents no public socket-readiness API: `std.net` has
no public networking types, and runtime async primitives remain private and
unstable. No readiness scheduling change was made. The supported API finding,
test commands and captured request-header details are in
`docs/evidence/baseline-0.165.1/local-relay-concurrency.md` and
`docs/evidence/baseline-0.165.1/local-relay-http.md`. This does not establish
complete HTTP, fairness, security or six-target parity.

## Relay chat passthrough header parity follow-up (2026-10-30)

The later translated-route large-field change supersedes the limits and
remaining 1 MiB + 1-byte mismatch described in this historical section.

Modex `/v1/chat/completions` now matches the tested 0.165.1 and 0.439.2
upstream request-header behavior: it emits the default `Accept` and
`Content-Type`, duplicates the first inbound `User-Agent` before forwarding
the inbound fields, and omits `Connection: close` on this path. Other HTTP
stream callers retain the default close header. The production relay test
captures ordinary, duplicate, and missing `User-Agent`/`Accept` inputs, also
checking duplicate `Content-Type`, against each pinned release and Modex. The
1 MiB + 1 byte `User-Agent` reaches all three with two outbound copies.

Fixed-length and chunked upstream responses with `Connection: keep-alive`
complete while the synthetic upstream holds the socket open; close-delimited
responses complete at EOF. Request and response framing checks, the 2 MiB +
2 KiB outbound aggregate cap, field/body limits, and timeout limits remain in
place. The translated `/v1/responses` route still rejects the 1 MiB + 1 byte
`User-Agent` accepted by the releases. Larger duplicated fields, other HTTP
cases, non-host targets, and complete security behavior remain unverified.
Validation passed on Linux x86-64: production build, focused Mojo header
driver, four selected-header/framing tests, and both pinned-release large-head
tests. The test peers, credentials, homes, and ports are synthetic and
isolated. See `docs/evidence/baseline-0.165.1/local-relay-http.md`.
## DeepSeek Anthropic web-search tool aliases (2026-10-30)

The official 0.439.2 bridge and historical 0.165.1 bridge both classify
`web_search`, exact `web_search_preview`, and `web_search_preview_`-prefixed
types as web search. Modex's request mapper had the same accepted set, but the
Anthropic validator rejected the aliases before dispatch; the conflict
fallback classifier also missed versioned aliases. Both Modex checks now use
the shared accepted set while preserving existing option validation.

Synthetic three-process comparisons cover those aliases, several version
suffix shapes, two invalid near-prefix types, normalized provider request and
response bodies, and conflicting domain filters on a versioned alias.
Focused process methods, the production build, the 71-file dependency audit,
the 50-native/154-Python test census, and `git diff --check` passed on Linux
x86-64. This qualifies only the tested request shapes and leaves the six-release
denominator unchanged. Details:
`docs/evidence/baseline-0.165.1/anthropic-web-search-aliases.md`.

## Buffered Anthropic search result identifiers (2026-10-30)

Buffered `web_search_tool_result` blocks with missing, null, or non-string
`tool_use_id` values are now ignored like Prodex 0.165.1 and 0.439.2. Before
the fix, Modex returned 502 for a numeric result ID after a valid search, while
both releases returned the still-pending search without sources. The production
mapper now checks the identifier's JSON type before matching it, so missing or
null values cannot attach to a search with the valid empty-string ID. A
three-process loopback test covers numeric, missing and null IDs, the empty-ID
negative control, and a matching string-ID positive control. The focused
identifier, result-source, result-content, and orphan suites passed; the
production build, 71-file dependency audit, 50-native/154-Python census, and
`git diff --check` passed on Linux x86-64. This qualifies only these buffered
response shapes; all six release targets and broader Anthropic parity remain
unqualified. See
`docs/evidence/baseline-0.165.1/anthropic-orphan-result.md`.

## Super rollout float diagnostics (2026-10-30)

The Super parser now matches 0.165.1 and frozen 0.439.2 diagnostics for the two
rollout weight options. It preserves Rust `f64` spellings and rejects malformed
exponents, whitespace, Unicode digits, suffixes, hex floats, and trailing
bytes. A 54-value-per-option differential matrix had no mismatch. The focused
synthetic three-process tests confirm invalid post-tail values stop before any
Codex child or provider request, with the key redacted. Only Linux x86-64 CLI
diagnostics are qualified; rollout weight launch effects and other targets
remain open. See
`docs/evidence/baseline-0.165.1/super-rollout-float-diagnostics.md`.

## Anthropic duplicate web-search tool selection (2026-10-30)

Anthropic request translation now matches both pinned releases when a Responses
request contains multiple web-search tools: the first recognized tool supplies
the single provider search tool and later recognized duplicates are ignored.
The validator still checks the first tool's options and rejects unrecognized
tool types; invalid `max_uses` on the first tool fails before POST, while
invalid options on later duplicates are ignored and are never forwarded.
Conflicting-domain fallback uses the first tool too: an invalid first tool
falls back to Chat in auto mode and returns 400 in explicit Anthropic mode,
while a conflict on a later duplicate has no effect.

Synthetic three-process comparisons cover auto, forced Anthropic, and forced
Chat routes, function tools alongside duplicates, malformed input and unknown
tool controls. The production build, seven focused provider test methods, the
71-file dependency audit, 50-native/154-Python test census, and diff check
passed on Linux x86-64. This qualifies only the listed request shapes; other
Anthropic behavior, targets, and the six-release parity denominator remain
unchanged. See
`docs/evidence/baseline-0.165.1/anthropic-web-search-duplicate-selection.md`.

## Local relay WebSocket framing precedence (2026-10-30)

The relay now returns the 426 fallback before body parsing when a request with
both `Connection: Upgrade` and `Upgrade: websocket` has conflicting
Content-Length fields. This matches both pinned Linux releases and closes the
connection, so an appended pipeline request is not reused or dispatched. A
synthetic Authorization header
is not reflected. Invalid target and unsupported `Expect` precedence remain
400 and 417; non-WebSocket `h2c` framing remains fail-closed with no upstream
dispatch. For a WebSocket header without `Connection: Upgrade`, the releases
leave the connection open after 426, while Modex returns 502 and closes it to
protect the ambiguous framing boundary.

The check used the production Super relay with checksum-pinned 0.165.1 and
0.439.2 processes, isolated homes and loopback peers. The focused real-process
tests and production build pass on Linux x86-64. The distinct admission
fairness mismatch under a saturated bounded pool remains open; no idle or
partial client eviction rule changed. Other malformed framing and all six
release targets remain unqualified. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md` and
`docs/evidence/baseline-0.439.2/local-relay-websocket-framing.md`.

## Local relay WebSocket fallback classification (2026-10-30)

The local relay now returns the 426 WebSocket fallback whenever it sees the
exact `Upgrade: websocket` field, matching both pinned releases even without
`Connection: Upgrade`. Modex follows TinyHTTP's body-capture order for a
no-Connection request with a first `Content-Length` from 1 through 1,024, no
`Expect`, and no transfer encoding: complete bodies then get 426, while
truncated bodies ending at EOF get no response. Empty bodies,
`Connection: Upgrade`, chunked framing, `Expect`, and lengths over 1,024 reach
the fallback before body capture. Three-process tests cover complete and
truncated lengths 0, 1, 1,024, and 1,025, plus the framing and `Connection`
controls.

One deliberate ambiguous-framing gap remains: a positive first
`Content-Length` followed by a smaller duplicate makes both releases close on
an incomplete body, while Modex returns 426 before reading it. The tested
zero-first conflict returns 426 in all three products. For fragmented valid
non-ambiguous requests followed by a valid pipeline request, the releases
return 426 then process the second request with 200 and one synthetic upstream
dispatch; Modex returns 426, closes, and makes no upstream request. A separate
low-load production control holds a partial one-byte WebSocket body while a
preconnected idle client receives 200, then completes the partial body for
426; neither client is evicted. It does not establish saturated-pool fairness,
which remains open. Invalid-target 400, unsupported `Expect` 417 and
non-WebSocket `h2c` 502 precedence remain covered. Focused process tests and
`make build` pass on Linux x86-64. Runtime-proxy WebSocket/WSS and all six
release targets remain unqualified. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md` and
`docs/evidence/baseline-0.439.2/local-relay-websocket-framing.md`.

## DeepSeek same-origin redirect following (2026-10-30)

DeepSeek's production transport now follows tested same-origin numeric-loopback
HTTP redirects. Process comparisons against 0.165.1, frozen 0.439.2 and Modex
cover 301/302/303 POST-to-GET conversion, 307/308 method and body preservation,
relative and absolute locations, query resolution, the redirect limit, and
selection of only the final streamed response. Missing Location and other 3xx
statuses remain unchanged. A real child launch verifies the rebuilt binary.

Modex refuses cross-origin redirects and returns their original response;
Prodex follows them while stripping authorization. Modex also cannot follow
HTTPS, DNS, or other non-numeric-loopback destinations. Keep these limits
visible; this does not establish full provider transport or redirect security
parity. See `docs/evidence/deepseek-redirect-following-04392.md`.

Linux x86-64 validation: production build; 35 continuation process tests;
two native redirect deadline/cancellation tests and native transport header
checks; three passthrough tests; one Super binary-passthrough comparison;
product dependency audit; Python syntax check; and `git diff --check` all
passed. Tests used synthetic loopback peers and credentials only.

## DeepSeek stream idle-timeout diagnostics (2026-10-30)

The provider event reader now preserves the frozen continuation reader's
`runtime upstream stream idle timed out` diagnostic when its loopback reader
reports that exact idle timeout. Framing and other body-read errors retain
`error decoding response body`. Both pinned source releases use the timeout
diagnostic, though a three-process probe showed the 0.165.1 process can emit
either message depending on which timeout/read path wins. One controlled capture
reported generic on 0.165.1 and timeout-specific on 0.439.2 and Modex; a repeat
reported timeout-specific on 0.165.1 too. Keep this observed run difference
visible without treating it as a stable cross-release mismatch.

Pre-commit empty-body, post-commit text-idle, and truncated length/chunked-body
controls pass across 0.165.1, 0.439.2 and Modex. The direct native transport
idle regression checks the new Modex message. The focused production build,
provider unit and process comparisons passed on Linux x86-64. See
`docs/evidence/provider-stream-idle-04392.md`.

The prefetch boolean latch does discard read-error text, but repeated chat and
Anthropic-native partial-frame fixtures returned the same generic decoding
diagnostic from both frozen releases and Modex. The focused three-process
regression now locks this observed behavior; no production change was justified.

## Buffered DeepSeek first-choice type (2026-10-30)

The real 0.165.1 and frozen 0.439.2 processes return an empty HTTP 500 when the
first Chat Completions `choices` entry is null, numeric, or an array, even if a
later entry is valid. Modex previously returned HTTP 200 with an empty output
for scalar and array entries. The buffered response mapper now rejects any
present first choice that is not an object using the existing transport error
mapping. Empty choices still return HTTP 200, and a valid first choice still
wins over later entries.

At both commits, the buffered response path calls the assistant-history
extractor after translation. Its native `deepseek_chat_assistant_messages`
operation rejects a present first choice that is not an object. The
three-process comparison confirms this reaches the client as HTTP 500. Focused
production build, native buffered-provider test, real-process comparison,
71-file dependency audit, 50-native/155-Python test census, and diff check pass
on Linux x86-64. Other response shapes, all six release targets, and broader
provider parity remain unqualified. See
`docs/evidence/baseline-0.439.2/provider-buffered-choice-history.md`.
