# Local relay client authentication

The previously published Modex Super relay accepted any loopback client and
wrote a fixed `prodex-runtime-provider` token into the private Codex overlay.
Both pinned Prodex releases accept the tested synthetic foreign client; that
client can replay selected prefetched conversation history in those releases.
An earlier candidate that enabled that history behavior in Modex therefore
exposed synthetic prior history to an unauthenticated local client and was not
integrated. See `streamed-continuation-prefetch.md`.

The supported DeepSeek Super launch now generates 32 bytes from `/dev/urandom`
and encodes them as a per-launch 64-character token. It writes that token into
the owner-only overlay's `auth.json`, sends it to the relay through its private
child environment, and removes it and the twelve provider API-key environment
names from Codex version probes, hook preflight and the launched child. The
relay requires exactly one matching bearer header after request-head validation
and before sending 100 Continue, waiting for the declared body or dispatching
to the provider. Header capture can already buffer body bytes sent with the
head. Missing, empty, incorrect, duplicate and prior-launch tokens return
401 with no upstream request. The provider receives only its synthetic provider
key, not the local token. These rules intentionally differ from the pinned
releases; they do not implement the prefetched-continuation parity gap.

The token protects against a client without access to the private overlay or
relay environment. A same-UID process able to read either can obtain it. Partial
headers are admitted before authentication; a focused process test shows 132
such sockets can delay an authorized request until released. This is an open
availability gap. The 426 fallback still closes a connection that the releases
may reuse. A write-side shutdown preserves a clean close in selected Linux
fragmented and coalesced WebSocket fallback controls; other OS semantics and
broader TCP behavior are unqualified. No complete security or platform parity
is claimed.

Linux x86-64 validation used Mojo 1.2.0 (2016d0cd), real Modex processes,
checksum-pinned 0.165.1 and 0.439.2 executables, private temporary homes,
synthetic credentials and loopback providers. Focused checks covered Super
client authentication and inherited-environment scrubbing; all 28 local relay
and admission tests; six whitespace/pipelining tests; the two streamed history
gap tests; exact 2 MiB request-head boundaries; and selected 426/method/body
controls. The installed Codex CLI 0.165.0 was also launched under `unshare -Urn`
with only loopback enabled, isolated homes, a synthetic provider and a conflicting
synthetic parent `OPENAI_API_KEY`. It completed one provider request through
the authenticated relay. `tests/manual_real_codex_local_auth.py` contains that
manual test; it does not require account login or external traffic.

One combined focused command initially used a nonexistent test method name;
the corrected four-test run passed. A later command lacked the native Codex
fixture required by the 0.165.1 environment test; that test passed after
building `codex_argv_child`. The 15 slow-partial tests in that command passed.

The previous whole-suite snapshot failed 28 subtests and one error before
fixture repairs. A later full-suite snapshot is still running and predates the
last 426 close change; neither result qualifies this final candidate. All six
release targets and the WebSocket runtime-broker work remain open.
