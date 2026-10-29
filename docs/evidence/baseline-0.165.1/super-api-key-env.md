# DeepSeek Super API key environment resolution

The 0.165.1 and 0.439.2 Linux processes accept `--api-key` before
`DEEPSEEK_API_KEYS`, then `DEEPSEEK_API_KEY`. The plural value splits on comma,
semicolon, and newline; surrounding whitespace and empty entries are discarded.
A present plural variable containing only empty entries is an error and does not
fall back to the singular value. Singular and explicit values reject empty
strings and whitespace. With multiple plural keys, the releases use the first
key for the first request.

Modex now resolves explicit, singular, and one-entry plural keys through its
production Super path. It rejects a multi-entry plural value before creating a
Codex child or contacting the provider because per-request rotation is not
implemented. This is a retained functional mismatch, not rotation parity.

There is also a security behavior difference. Both releases pass the original
DeepSeek key environment variables to Codex `--version` and `app-server --help`
probes, although their final Codex launch child has both variables removed.
Modex removes both variables from every Codex child, including probes. The
synthetic child fixture captures these environments; selected keys do not
appear in output or Codex argument vectors. Modex also avoids persisting the
environment values in the fixture capture. This is an intentional safer
difference from the releases.

The four real-process methods in `tests/test_super_launch.py` compare the
singular and plural paths, all three separators, explicit-key precedence over
malformed unused environment values, empty and whitespace errors, missing
keys, provider Authorization, Codex environment/argv, and the multi-key gap
against both pinned releases and Modex. Tests use only synthetic credentials,
isolated homes and a loopback provider. `make build` and all four focused
methods passed on Linux x86-64. A one-entry plural value also reaches
`deepseek_request_headers` before any Codex probe or provider request. It
rejects internal spaces/tabs as whitespace and control, DEL, or non-ASCII
bytes as non-visible ASCII; the diagnostic does not include the value, and no
temporary overlay remains. The pinned releases send a key containing an
internal space or non-ASCII character in Authorization. For tab, control, or
DEL, they launch Codex but the synthetic provider observes no request. Modex
rejects all five cases before creating a Codex child or making a provider
request. The focused header-validation method passed across both releases and
Modex. Public network, TLS, other release targets, and multi-key rotation remain
unqualified.

The combined omitted-model and environment-key launch is also checked against
both releases in `tests/test_super_shared_config_01651_04392.py`: a configured
model reaches the catalog, no model override is passed to Codex, and one
synthetic provider request carries the resolved key.

## Rotation and replay boundaries

`tests/test_deepseek_key_rotation_01651_04392.py` exercises the actual pinned
processes using two synthetic keys and a loopback provider. Two unbound
buffered Responses requests use the keys in order. If the first response is
accepted and the second request references its response ID, both releases
return 503 `bound_continuation_unavailable` without a second provider POST in
the tested fixture. This is an observed ownership boundary, not evidence of
general profile or binding parity.

For a single unbound request with a synthetic JSON error body, both releases
retry with the second key after HTTP 401, 403, 500, 502, or 503; they return
HTTP 400, 404, 408, 409, 422, or 429 without trying the second key. These are
selected response/error-class controls; body-dependent classification,
streaming commitment, retries, concurrency, exhaustion and recovery remain
unqualified. Source trace: `local_rewrite_transport.rs` rotates an atomic
cursor, while `local_rewrite_deepseek_send.rs` filters candidate credentials by
binding identity and permits only precommit retries. Modex still rejects the
multi-key list before any child or provider request. The release-only
observations are not Modex parity and no rotation status is promoted.

Reproduce with `python3 scripts/ci/run-unittest.py test_deepseek_key_rotation_01651_04392.py`
using both checksum-pinned Linux oracles. Synthetic credentials and isolated
homes/loopback ports are used throughout.
