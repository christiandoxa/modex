# DeepSeek Super API key environment resolution

The 0.165.1 and 0.439.2 Linux processes accept `--api-key` before
`DEEPSEEK_API_KEYS`, then `DEEPSEEK_API_KEY`. The plural value splits on comma,
semicolon, and newline; surrounding whitespace and empty entries are discarded.
A present plural variable containing only empty entries is an error and does not
fall back to the singular value. Singular and explicit values reject empty
strings and whitespace. With multiple plural keys, the releases use the first
key for the first request.

Modex resolves explicit, singular, and plural keys through the production
Super path, then passes the list only to the dedicated DeepSeek relay child.
An atomic cursor starts each request at the next key. Unknown response, turn,
or session identities keep that cursor selection and can retry across keys.
Known hard bindings retain the pinned releases' 503
`bound_continuation_unavailable` gate before provider dispatch.

There is also a security behavior difference. Both releases pass the original
DeepSeek key environment variables to Codex `--version` and `app-server --help`
probes, although their final Codex launch child has both variables removed.
Modex removes both variables from every Codex child, including probes. The
synthetic child fixture captures these environments; selected keys do not
appear in output or Codex argument vectors. Modex also avoids persisting the
environment values in the fixture capture. This is an intentional safer
difference from the releases.

The real-process methods in `tests/test_super_launch.py` compare the singular
and plural paths, all three separators, explicit-key precedence over malformed
unused environment values, empty and whitespace errors, missing keys,
provider Authorization, Codex environment/argv, key rotation and key isolation
against both pinned releases and Modex. Tests use only synthetic credentials,
isolated homes and a loopback provider. `make build` and the focused methods
passed on Linux x86-64. A one-entry plural value also reaches
`deepseek_request_headers` before any Codex probe or provider request. It
rejects internal spaces/tabs as whitespace and control, DEL, or non-ASCII
bytes as non-visible ASCII; the diagnostic does not include the value, and no
temporary overlay remains. The pinned releases send a key containing an
internal space or non-ASCII character in Authorization. For tab, control, or
DEL, they launch Codex but the synthetic provider observes no request. Modex
rejects all five cases before creating a Codex child or making a provider
request. The focused header-validation method passed across both releases and
Modex. Public network, TLS, non-Linux release targets and account-backed
credentials remain unqualified.

The combined omitted-model and environment-key launch is also checked against
both releases in `tests/test_super_shared_config_01651_04392.py`: a configured
model reaches the catalog, no model override is passed to Codex, and one
synthetic provider request carries the resolved key.

## Rotation and replay boundaries

`tests/test_deepseek_key_rotation_01651_04392.py` contains 15 real-process
methods comparing both pinned processes and Modex with synthetic keys and a
loopback provider. The matrix covers unbound round-robin selection, unknown
previous-response/session/turn IDs, known-ID 503 gates, HTTP status fallback,
the pinned structured-code set, case-sensitive JSON field names, last-value
duplicate-key handling, rejected aliases, final-error pass-through,
retryable native Anthropic first-event errors, precommit transport failures,
and a concurrent owner conflict. HTTP 429 rotates only for recognized
structured codes. The HTTP retry matrix now checks both Responses and Chat
Completions against each pinned release and Modex, including malformed 503s,
unknown 429s, duplicate code fields, and case-sensitive field names. The
native Anthropic path allows one precommit retry. When the final key also sends
a retry-classified first error frame, the prefetch consumes that frame and the
stream reader reports code `provider_stream_error`
with message `unexpected end of stream`, matching both releases. Errors after
stream progress remain terminal. Concurrent requests with the same previously
unknown identity can reach different keys; subsequent use of the conflicted
owner is rejected before provider dispatch.

Source trace: `local_rewrite_transport.rs` rotates an atomic cursor;
`local_rewrite_deepseek_send.rs` filters credential candidates against hard
bindings and retries before commitment; `provider_error.mojo` owns the exact
error-code and native-event classification. A native event with a top-level
retryable code rotates only when its type is exactly `error`; `ERROR` and
whitespace-padded names do not. An explicit `error` member is classified even
when the event type is uppercase. The four-case real-process comparison matches
both pinned releases. A three-key exhaustion case now verifies both Responses
and Chat Completions: each tries A, B, and C, returns C's raw retryable 429,
and advances the logical-request cursor once so the next request starts at B.
Both pinned releases and Modex match. A separate cursor-order comparison
verifies that malformed Chat Completions JSON is passed byte-for-byte upstream
with key A and the following request uses key B. Modex matches the tested
behavior but still has a single static endpoint and process-local binding
state. Public network/TLS, profile-backed ownership, persistence/recovery,
exhaustion beyond three keys, and the other release targets remain unqualified.
No full parity status is promoted.

Reproduce with `PYTHONPATH=tests rtk python3 -m unittest
test_deepseek_key_rotation_01651_04392 -v` using both checksum-pinned Linux
oracles. Synthetic credentials and isolated homes/loopback ports are used
throughout.

## Cursor reservation order (2026-10-30)

The pinned `local_rewrite_deepseek_send.rs` checks binding context before it
reserves the round-robin start, then reserves before Responses translation.
Three-process sequential comparisons now cover that ordering: an unsupported
route leaves the next valid request on key A; malformed Responses JSON consumes
key A before returning 502, so the next valid request uses key B; and known
response, session, and turn continuations rejected with 503 do not consume a
key. An empty-input web-search request returns 400 but consumes a key in `auto`
and `anthropic` modes, while `openai_chat` sends it and advances normally. The
valid request after each rejection uses the expected next key in both pinned
releases and Modex.

`tests/test_deepseek_continuation.py` exercises actual Super processes with
synthetic two-key credentials, a private temporary shared config, and a
loopback provider. The production build, focused cursor-order test, and 71-file
production import audit passed on Linux x86-64. Reproduce the focused test with:

```sh
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests rtk python3 -m unittest \
  test_deepseek_continuation.DeepSeekContinuationTests.test_api_key_cursor_matches_release_request_order
```

This qualifies only the selected reservation-order vectors; the
unsupported route is not malformed request-target syntax, and malformed Chat
Completions JSON plus other rejection paths remain unqualified. The other
release targets and complete provider behavior also remain unqualified.
