# Verified gaps

Complete parity remains unfinished against officially released Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The incomplete inventory retains
76 contracts and 456 platform obligations. All six complete release
qualifications are explicitly BLOCKED; focused host tests do not establish a
release PASS. The 0.439.5 and 0.439.1 observations below retain their original
provenance and do not by themselves establish 0.439.2 behavior.

The profile group and selected subcommand help now match the 0.439.2 release.
Profile listing and all state-changing operations remain unimplemented: the
release creates persistent locks that Modex cannot yet coordinate with safely.
Selected help prefixes and parser errors now match; other argument combinations
remain unverified. See `docs/evidence/profile-help-04392.md`.

The 0.439.2 oversized SSE continuation case now binds the response ID: both
products return 200/503 with one upstream POST. The incremental observer has
native parser comparisons and selected production controls for malformed JSON,
duplicate keys, chunk boundaries, UTF-8 and depth. Its numeric-position counters
saturate at one billion; complete streaming/resource/security equivalence remains
unverified. Persistent bindings, multi-account ownership, affinity release,
account/profile lifecycle, credential finalization and login/quota concurrency
remain incomplete.

Selected 0.439.2 DeepSeek web-search requests now reach Anthropic Messages on
the production Super path. Synthetic release comparisons cover supported URL
suffixes and prefixes, dot-segment normalization, request body/auth conversion,
buffered text and search outputs, search sources, SSE ordering and stream
truncation. It now rejects requests before upstream unless they use string
input or selected arrays of plain messages, one `web_search_preview` tool,
optional `allowed_domains`, the default token limit and no other request
fields. Rich message content, metadata and mixed function/web tools are
fail-closed. Oracle controls record that the release coerces untyped roles,
accepts mixed tools and drops some metadata and blank items; these differences
remain explicit gaps. Empty and system-only arrays also return different errors.

Buffered and SSE response conversion rejects unsupported content, citations,
result fields and event shapes rather than returning successful partial output.
Oracle controls record citation omission, reasoning conversion from a
`thinking` block and completion after an image block without retaining its data.
Successful handling remains limited to one tested search call/result with
text. Broader request/message shapes, tool-result/history round trips, complete
metadata/citation behavior, TLS/DNS/proxies, resource behavior and full
stream/error equivalence remain open. The tested ordered search/result/text
shape and text-only or empty streams with a final `message_stop` are supported;
other Anthropic event orders remain unverified. Nonempty initial text blocks
are rejected while the release drops that text. The exact empty-string request is rejected with the observed 400
before POST, while whitespace-only input is accepted. See
`docs/evidence/anthropic-web-search-04392.md`.
Selected string/null stop reasons and streams without `message_delta` now match
the release's full normalized events. Missing or non-string stop reasons and
non-string stop sequences remain fail-closed differences: the release completes
them while Modex fails. Other stream metadata and stop variants remain unverified.

Strict-tool environment settings select the beta route and normalize supported
runtime-path schemas for numeric-loopback HTTP. The baseline simple-request
pass can preserve nested tools unchanged; config-only settings still fail
closed, public beta TLS/DNS remains unsupported, and an invalid unused beta
environment URL is ignored when strict mode is off while Prodex rejects it.
`tests/test_provider_tools_04392_characterization.py` reproduces these gaps.
The separate web-search mode environment setting now controls selected
production routes; TOML mode precedence remains unimplemented. See
`docs/evidence/deepseek-web-search-mode-04392.md`.

DeepSeek requests with a missing, null, non-string or blank model match the
tested 0.439.2 default. Selected combo aliases match the active release; its
flash alias differs from the historical 0.439.5 behavior. Broader provider
model selection and fallback remain unverified. The
read-only profile-list prototype cannot safely interoperate with the release's
persistent `flock` files using the available Mojo standard-library APIs, so
it is not connected to production.
The tested session metadata admission cases match 0.439.5. For a non-object
first JSONL record, that release panics while Modex omits the session. Session
listing now ignores selected unrelated state-like filenames in the same way as
0.439.2 and the historical 0.439.5 control. Actual state, last-good snapshots,
locks, atomic temporary files and profile journals remain fail-closed because
state recovery and locking are not implemented.
Selected dotted-I expansion and contextual Greek sigma queries now match both
the active 0.439.2 oracle and the separately pinned 0.439.5 oracle. The sigma
context covers common combining marks and apostrophes, not the complete
Unicode Case_Ignorable property. Broader session behavior, state locking,
recovery and security remain unqualified.

Checkpoint 15 matches the official 0.439.2 bodyless SSE chunked header
and final raw wire chunk `0\r\n\r\n` on 204/304, and corrects the buffered
oversized 2xx/3xx versus >=400 error classification. The fixed-length reader
now enforces its bound when configured after the upstream header, and admitted
3xx SSE remains streamed beyond 4 MiB, including chunked unknown-length
302/307 responses. Two older native-only cap assertions conflicted with the
current source oracle and were replaced with eight release/native checks.
This is verified through real Super synthetic peers, selected route/status
controls and isolated raw socket probes;
it is not broad streaming, cancellation, timeout, HTTP binary metadata,
security or SDK parity. At that checkpoint the protected two-turn binding
case returned 200/503 with one POST in Prodex and 200/200 with two in Modex.
The current source now matches that case; broader ownership remains unverified.
All release targets remain blocked. Earlier mismatch paragraphs are historical.
See `checkpoint15-reference.json` and `checkpoint15-protected-probes.json`.

Checkpoint 14 fixes buffered bodyless Content-Length: 0 and the hook initialize
version through actual native dispatch. Fourteen hook scenarios are freshly
captured from 0.439.2; the original 0.439.1 fixture remains intact. Bodyless
SSE omits Content-Length in both products, but release emits chunked transfer
encoding while native omits it; that framing mismatch remains visible.
Binding ownership, oversized-302 diagnostics and broad transport/security
qualification remain unfinished. See checkpoint14-reference.json.

Checkpoint 13 targets 0.439.2. Earlier 0.439.1 and 0.439.0 evidence below
retains historical provenance and is not automatically current-target evidence.
Known five-hour or weekly exhaustion, pre-I/O hard-owner HTTP/WebSocket recovery
and busy/cooling recoverable alternatives are new explicit obligations. Modex
still has no real account pool, WebSocket transport or connected native recovery
owner; production quota handoff and all six release qualifications remain BLOCKED.
No opaque continuation-delta transfer or POST replay is permitted. Optional RTK
1.1.0 and Presidio 2.2.365 qualification is also unfinished.

Checkpoint 13 fixes only inspection help/error usage for empty argv0, with
four live regressions through actual native CLI dispatch. Standalone quota
signal policy has 1,600 current-source comparisons but remains unconnected.
New live 0.439.2 checks reject proposed earlier-slot tool replacement and a
4 MiB merged-metadata cap. Oversized hook trust still differs in panic/exit
behavior; changing its diagnostic alone is excluded. Fresh binding and
bodyless/oversized-redirect probes retain the documented runtime gaps.
At checkpoint 13 hook initialization still advertised historical 0.439.1;
checkpoint 14 corrects it after fresh release capture.
See `docs/evidence/checkpoint13-reference.json`.

Checkpoint 12 closes whole-dot normalization for admitted numeric-loopback
HTTP upstream paths, including literal/encoded dots, repeated separators,
root clamp and suffix assembly. Forty-six real Super/release route vectors
match exact paths and retain authoritative synthetic auth and one POST each.
Checkpoint 11 failed 20 of 23 base-path cases. The historical checkpoint 10
backslash-dot refusal below is resolved for this subset; general schemes,
authorities, transport/security/resources and non-host behavior remain gaps.
See `docs/evidence/checkpoint12-reference.json`. Final binding and adjacent
transport probes retain the known mismatches; this path fix does not implement
credential/profile ownership, recovery or actual goal progress.

Checkpoint 11 corrects bodyless effective length in the shared native HTTP
reader. Six live 304 route/framing vectors match status/empty body, with one
POST each; raw header/constructor equivalence remains incomplete. The release
emits Content-Length: 0 for 304 while native omits it. Oversized 302 returns
502 in both but different error bodies; exact worker observations are retained
in `docs/evidence/checkpoint11-worker-bodyless.json`. Reproduce with a synthetic
Chat Completions POST and 302 application/json upstream body of 4,194,305 `x`
bytes with the same Content-Length through observe_turns. No POST replay is used.
Corrected RPC pre-receive timing and source-equivalent estimator saturation are
narrow changes; full lifecycle/progress and physical memory parity remain gaps.
The SSE constructor override proposal is excluded because production defaults
already match and the frozen private constructor has no matching restriction.
See `docs/evidence/checkpoint11-reference.json` for all four worker decisions.

Checkpoint 10 fixes ordinary HTTP upstream path backslash separators in the
shared native resolver. Twelve live path/route vectors preserve repeated
separators, literal trailing-slash trim order, percent-encoded backslashes,
queries, mixed UTF-8 and authoritative synthetic auth, with one POST per
accepted request. At checkpoint 10, literal/encoded dots and broader URL
behavior were unqualified; its stricter backslash-dot refusal was not a parity
PASS. Checkpoint 12 closes the admitted whole-dot subset. Full binding,
timeouts, aggregate retention and all six release qualifications remain blocked.
See `docs/evidence/checkpoint10-reference.json`.
The checkpoint 10 probe observed `/v1\..\other`: release normalized to
`/other/chat/completions` and returned 200/one POST, while that native artifact
exited 1 without a POST. Checkpoint 12 now matches the admitted path.
The original two-turn binding mismatch is also reproduced in that evidence.

Checkpoint 9 extends native upstream base-path encoding to quotes, angle
brackets, backticks and braces. Ten live path/route vectors preserve existing
percent escapes, ordinary punctuation, mixed UTF-8, queries, authoritative
synthetic auth and one POST per request. Backslash separators were a reproduced mismatch at that
checkpoint; checkpoints 10/12 cover admitted separators and whole-dot segments.
Broader URL behavior remains unqualified. See `docs/evidence/checkpoint9-reference.json`.

Exactly two completed worker proposals were reviewed and excluded. `9d05840`
changed only a timeout message and did not implement precommit behavior; its
historical 0.439.1 mismatch capture remains unchanged. The current 0.439.2
production path now distinguishes lookahead and idle deadlines for selected
DeepSeek chat streams: an idle error with an empty precommit prefix returns
502, while a nonempty prefix or elapsed lookahead commits the stream. Tests
cover timeout, EOF, truncation, invalid UTF-8, incremental output and no
replay. The release can expose either of two idle diagnostics; Modex emits the
decoding form. Complete retry/rotation, parallel admission and transport
behavior remain open.

`d127513` introduces an incompatible partial 16 MiB state counter. Both real
products complete 500,000 null annotations that its allowances would charge
at 18,000,000 bytes; the existing worker binary fails that input. Metadata and
snapshots also escape its counter. The frozen per-operation kernel limits
must be traced separately: a 17.5 MB refusal probe times out in the release's
synthetic client while Modex completes. No large-refusal PASS or whole-response
memory ceiling is claimed. See `docs/evidence/checkpoint9-worker-review.txt`
and `checkpoint9-state-review.json` in that directory. Full binding and recovery
remain protected gaps, and accepted control RPCs are not actual goal progress.

Checkpoint 8 corrects blank explicit session-header alias fallback in the
shared native resolver. Six live independent production vectors confirm later
alias priority over turn metadata/body, rejection of oversized resolved aliases
before any provider POST, and retained valid fallback behavior. This corrects an
older native assertion; it does not establish full affinity ownership or recovery.
See `docs/evidence/checkpoint8-reference.json`.

Checkpoint 7 extends the existing native header filter to buffered passthrough,
matching the frozen TinyHTTP ASCII constructor. Ten live production metadata
vectors cover successful Chat Completions and Responses errors, unchanged binary
bodies, isolated metadata and one POST per request. Lower-client header storage
is still lossy; arbitrary binary metadata and other transport/platform behavior
remain unqualified. See `docs/evidence/checkpoint7-reference.json`.

Checkpoint 6 connects Super's source-traced unscoped history context while
retaining scoped internal relays. Buffered and streamed tool follow-ups across
different sessions/turn states match the real release on its history-aware path.
Equal comma-list Content-Length and first-present call-ID mapping are integrated;
reader, raw usage scanner and malformed-format fallback worker changes are
rejected. The production boundary decodes usage keys before mapping and rejects
missing/non-string format types before fallback. Native and live regressions
retain those distinctions. See `docs/evidence/checkpoint6-reference.json`.

Non-object SSE remains a reproduced mismatch: null, array, and text-then-null
within one event time out in the pinned release's synthetic client; Modex emits
`response.failed`. The source metadata kernel rejects non-objects and its Rust
wrapper panics. No empty-chunk or graceful-failure parity is claimed. The full
binding mismatch below is also reproduced unchanged. Checkpoint 7 fixes the
buffered non-ASCII metadata mismatch described in that checkpoint; it does not
implement general lower-client binary header retention.

Checkpoint 5 fixes non-ASCII upstream base-path bytes: native dispatch now
matches the release's UTF-8 percent encoding. Existing percent escapes and
combining sequences are preserved; eight production path/route comparisons
cover Responses and Chat Completions, including query forwarding. ASCII
punctuation, separators and whole-dot segments were unqualified there;
checkpoints 9/10/12 now cover the admitted path subset. Full URL behavior,
redirects and non-host qualification remain unfinished. The model `default`
probe matched the release, so no alias change was made. See
`docs/evidence/checkpoint5-reference.json`.

Checkpoint 4 connects the pinned Responses continuation-identifier boundary:
resolved previous-response, session and header turn-state values reject C0/C1
controls and values above 1,024 UTF-8 bytes before provider dispatch. Twelve
invalid vectors, five valid boundary/precedence vectors, eight simple combo
selectors and buffered timestamp fallback have live 0.439.1 comparisons.
This guard does not implement hard-binding ownership or recovery. In an isolated
two-turn buffered probe using the same synthetic key and model, the release
returns 200 then 503 `bound_continuation_unavailable` with one upstream POST;
Modex returns two 200 responses and sends two POSTs. Full binding identity
resolution, including the release's profile/credential identity interaction,
remains a reproducible gap. See `docs/evidence/checkpoint4-reference.json`.

Worker J's `27cd318` is rejected: replacing decoded-value cache weights with
the larger serialized size evicts escaped histories earlier than the frozen
store. Its production test asserts earlier eviction without an oracle
comparison. The existing logical retention rule is unchanged; physical memory
accounting for Modex's serialized history representation remains unqualified.
The separate `bf80ee8` header-count cap is also still excluded. Worker-owned
reader/usage files and the experimental Sol worktree remain untouched.

Checkpoint 2 connects explicit context/compaction limits and their visible
aliases to the guarded native DeepSeek Super path. Nine live 0.439.1
comparisons cover fallback/clamping and UInt64 boundaries. Codex receives the
normalized numeric overrides, while model-catalog rows retain default budgets:
the pinned exact-value scanner reads only TOML strings. Other configuration
precedence and real Codex interpretation remain unverified.

The proposed early-error quota projection is not a pinned-reference gap.
The reference dispatches non-2xx responses through passthrough without derived
quota headers, including auth errors; a 200 SSE provider error retains the
projection sent in its successful HTTP headers. Native tests preserve that
distinction and verify no replay. Invalid non-ASCII quota values are rejected
before parsing. Follow-up caller tracing corrects the original checkpoint 2
gap note:
DeepSeek statuses >=400 are buffered before dispatch in both products, with
a 4 MiB cap. Checkpoint 3 connects 3xx Responses SSE to native passthrough and
filters non-ASCII stream headers as the release does. Redirect streams retain
an extra 4 MiB guard; larger-redirect behavior remains unqualified. See
`docs/evidence/checkpoint3-reference.json`.

Super has a guarded production clean-home DeepSeek exec path with explicit
loopback URL/model/key, `--no-presidio`, `--no-sub-agent` and absolute
`PRODEX_CODEX_BIN`. It reaches real native HTTP/SSE/JSON and binary Chat
Completions passthrough through the actual Modex CLI. Tests use isolated fake
credentials and synthetic external Codex/provider peers and compare selected
observations with the checksum-verified 0.439.1 release. Real Codex
distributions and complete Super output/configuration/lifecycle are unverified.

Existing shared Codex contents/account state are rejected. The supported
launch now emits a source-traced model catalog and default
context/compaction/provider settings; additional config/argv combinations,
provider preset routing, Smart Context tokenization, optional tools, native
frontend companions and durable shared storage locks are unfinished. Temporary
directories are private (0700), but exact private file modes and repair/atomic durability are not implemented.
Unknown Codex-created overlay state is retained rather than deleted; that is
data protection, not evidence of baseline cleanup/storage parity. Repeated
launch after shared state is created still requires existing-state integration.
Launch notices/side effects also differ from the baseline.

Hook-trust request writes now survive closed peer stdin without SIGPIPE and
reap the direct child. Normal exit/error, relay death and idle parent-channel
closure are covered. Parent stdio swaps still require no concurrent parent I/O.
Process-tree cleanup, signal forwarding, crash cleanup of overlays and
cancellation during in-flight relay work remain incomplete. The parent EOF
check runs between requests; the serial relay has bounded network deadlines,
not a complete cross-process cancellation protocol.

Passthrough preserves POST query/body/content type and authoritative credentials,
filters hop-by-hop headers and removes the aggregate cap only for successful
SSE. Buffered/error bodies stay bounded. API keys are currently limited to
visible ASCII. Numeric loopback HTTP is supported; TLS/DNS/proxy traversal,
WebSockets, general backpressure and account rotation remain unimplemented.
Response/conversation memory can still grow with provider output. Worker-lane
isolation, nonblocking bounded admission and reserved compaction capacity are
source-traced obligations, not implemented behavior.

Native recovery retry/wire policy has deterministic assertions and 407 actual
pinned-source differential vectors. Accepted control RPCs are not progress.
The event monitor/revision owner, owned control socket, targeted session/compact
affinity release, mutation dispatch, ambiguity/no-replay handling and diagnostics
are not connected to production. The module is a tested foundation only.
Tunnel-client 0.0.18 and Kiro CLI 2.34.0 were verified in the pinned source;
neither integration is qualified in Modex. Evidence:
`docs/evidence/native-super-reference.json`,
`docs/evidence/native-super-data-plane.json`,
`docs/evidence/native-super-tests.txt` and
`docs/evidence/native-super-dependencies.txt`.

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
regressions, not observations against the official release. The guarded Super
path now calls these modules; complete translation/error, HTTP/TLS/proxy,
backpressure and cancellation equivalence remain unfinished. Evidence:
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

These modules now reach the guarded clean-home Super CLI path. The older
test-only synthetic Codex client replaced the external integration target;
its historical outer Super process exited 1 without app-server support.
The new production launch tests provide that peer protocol and exit 0.
Adapter response comparisons still do not establish Super command parity. Full provider
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

DeepSeek request preparation is implemented as a native
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

The guarded production Super path now calls this exchange. Only numeric IPv4 127/8 and
compressed IPv6 `::1` are admitted. Buffered/error bodies are capped at
4 MiB; SSE reads are incremental and retain per-frame/accumulation limits.
Final response and conversation memory remain proportional to output. Route selection and
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
Missing call IDs use UUIDv7; explicit empty IDs remain present. The production
relay supplies response-ID fallbacks. Missing/invalid buffered creation times
now use translation time; supplied unsigned timestamps remain unchanged.

The exchange exposes pending plus normalized assistant messages only for
nonfailed translated responses with a nonblank response ID. No persistent
conversation store has been connected. Exact buffered captures and real
socket regressions are in `tests/fixtures/provider-buffered/cases.json`,
`docs/evidence/provider-buffered-tests.txt` and
`docs/evidence/provider-buffered-link.txt`. Large-output conformance fallback, complete parser/resource/error
equivalence, complete provider route selection and all
previously listed transport/CLI/platform gaps remain unfinished.

The native listener and internal local-rewrite relay now serve real synthetic
HTTP requests through the existing provider exchange. The guarded Super launch
now invokes the relay. The frozen gateway forces a different proxy path;
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
graceful signals and limits above the incoming 64 MiB cap remain gaps.
Fallback ID/time generation timing is also unverified.

The real Super path requires Smart Context, overlays and Codex app-server
hook trust (`initialize`, `hooks/list`, optional `config/batchWrite`, then
`hooks/list`, with a 12-second RPC deadline). Native stdio transport now
completes the preflight against synthetic peers in a real process harness.
Secure overlays, Smart Context and production launcher integration remain
unfinished. Descendant cleanup and other recorded capability gaps remain.
See `docs/evidence/checkpoint-04391-tests.txt`, `docs/evidence/runtime-local-tests.txt`
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
