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

`tests/test_deepseek_key_rotation_01651_04392.py` contains 13 real-process
methods comparing both pinned processes and Modex with two synthetic keys and
a loopback provider. The matrix covers unbound round-robin selection, unknown
previous-response/session/turn IDs, known-ID 503 gates, HTTP status fallback,
the pinned structured-code set, case-sensitive JSON field names, last-value
duplicate-key handling, rejected aliases, final-error pass-through,
retryable native Anthropic first-event errors, precommit transport failures,
and a concurrent owner conflict. HTTP 429 rotates only for recognized
structured codes. The native Anthropic path allows one precommit retry. When
the final key also sends a retry-classified first error frame, the prefetch
consumes that frame and the stream reader reports code `provider_stream_error`
with message `unexpected end of stream`, matching both releases. Errors after
stream progress remain terminal. Concurrent requests with the same previously
unknown identity can reach different keys; subsequent use of the conflicted
owner is rejected before provider dispatch.

Source trace: `local_rewrite_transport.rs` rotates an atomic cursor;
`local_rewrite_deepseek_send.rs` filters credential candidates against hard
bindings and retries before commitment; `provider_error.mojo` owns the exact
error-code and native-event classification. Modex matches the tested behavior
but still has a single static endpoint and process-local binding state. Public
network/TLS, profile-backed ownership, persistence/recovery, key exhaustion
beyond the tested counts, and the other release targets remain unqualified.
No full parity status is promoted.

Reproduce with `PYTHONPATH=tests rtk python3 -m unittest
test_deepseek_key_rotation_01651_04392 -v` using both checksum-pinned Linux
oracles. Synthetic credentials and isolated homes/loopback ports are used
throughout.
