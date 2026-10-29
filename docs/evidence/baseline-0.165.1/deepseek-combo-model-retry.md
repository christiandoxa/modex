# DeepSeek combo model fallback and retry order

This slice adds model fallback to the production DeepSeek Responses relay. The
request body's `model` selects candidates, including when Super launches Codex
with an explicit `--model`; each attempt rebuilds the provider request from the
same input and conversation history. A model-class response advances to the
next candidate under the same credential. Credential-class errors advance to
the next credential and restart at the first candidate. The shared round-robin
cursor still advances once per logical request. Native Anthropic Messages
first-event errors can make one precommit fallback attempt; committed output is
never replayed.

## Source trace

The 0.165.1 and 0.439.2 releases both nest model attempts inside credential
attempts in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs`.
The shared decision kernel in `mojo/prodex_core/deepseek_attempt_policy.mojo`
selects the next model before rotating credentials. Its provider retry policy
classifies model-not-found responses for model fallback and auth errors for
credential rotation. The native Messages first-event policy allows one retry
before commitment.

The `flash` alias differs between the compared releases. In the 0.165.1 source,
`mojo/prodex_core/deepseek.mojo` emits `deepseek-flash` for combo `flash`; the
0.439.2 source emits `deepseek-v4-flash`. The existing direct request mapper
continues to preserve its established `deepseek-v4-flash` mapping. This retry
slice follows the 0.165.1 combo alias and therefore retains a known mismatch
with the official 0.439.2 baseline for this candidate.

## Real-process comparison

`tests/test_deepseek_key_rotation_01651_04392.py` exercises Modex and both
checksum-pinned Linux release binaries with synthetic keys and a loopback
upstream. The cases cover:

- model-before-credential order: model-not-found on A/flash, auth failure on
  A/pro, then success on B/flash;
- final model error body and the next logical request's cursor after model
  exhaustion;
- unchanged translated message context for each candidate;
- a successful fallback binding a session to credential A;
- custom unknown candidate names, a 404 with an unknown error code, a single
  credential, and an empty combo preserved as a literal model;
- native Anthropic not-found first-event fallback, single-key and exhausted
  first-event behavior, and no replay after emitted text;
- request-body model selection while the harness explicitly configures
  `--model deepseek-chat`.

The first-event retry counter is shared across all model and credential
attempts. Three candidates with two consecutive not-found first events produce
only two POSTs on credential A; the third candidate is not attempted. An
auth-class first event rotates to credential B and restarts at the first model
instead of trying the next model on credential A.

The provider policy caps model fallback at 256 candidates per credential
because its precommit retry count is an unsigned 8-bit value. HTTP rate-limit
errors can then rotate to the next credential and restart from candidate 1.
Native Anthropic first-event retries apply the same model-candidate cap before
considering credential rotation. The synthetic boundary comparison is covered
by `test_combo_model_retry_budget_caps_and_resets_per_credential`.

The first-event exhaustion controls match both releases exactly: after the
final retry-classified event frame is consumed, the response contains
`response.failed` with `provider_stream_error` / `unexpected end of stream`.
After text has been emitted, all three processes preserve the text and return
the terminal Anthropic error without another provider POST.

Checks performed on Linux x86-64:

- `make build` passed;
- `tests/test_provider_request.mojo` and
  `tests/test_provider_deepseek_transport.mojo` built and passed;
- all 20 methods in `test_deepseek_key_rotation_01651_04392` passed before four
  additional focused methods were added; the four later methods and updated
  committed-stream method also passed individually;
- `test_combo_model_retry_budget_caps_and_resets_per_credential` passed against
  both pinned releases and the fixed Modex build;
- `test_provider_nonstring_model_04395` compares the unchanged direct model
  mapping with 0.439.5, 0.439.2, and Modex, and asserts the version-specific
  combo Flash alias difference;
- `make ci-dependencies` passed with 71 Mojo production files restricted to
  standard/internal imports;
- `git diff --check` passed.

This is selected runtime behavior only. The alias mismatch with 0.439.2,
other release targets, network/TLS operation, profile-backed ownership, and
full provider parity remain unqualified. Synthetic credentials and isolated
homes/ports were used throughout; no provider account or paid traffic was used.
