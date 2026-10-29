# Responses `store` control on DeepSeek Anthropic requests

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official baseline 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The process comparisons use the
checksum-pinned Linux x86-64 release binaries and the production Modex binary.

## Baseline trace and behavior

At both release commits, `local_rewrite_deepseek_send.rs` passes Responses
requests through `runtime_deepseek_chat_request_body_with_options` before
selecting the native Anthropic Messages route. The chat-compatible request
builder projects fields into a new provider body, so the Responses-only
`store` flag is omitted. The release test
`deepseek_request_translation_tolerates_default_response_controls` in
`local_rewrite_tests/deepseek.rs` supplies `store: false` and asserts that the
translated body has no `store` field. The request-policy diagnostics also
require a boolean `store` value.

Real-process probes confirm that missing, `false`, and `true` are accepted by
both releases and omitted from their upstream bodies. `null` and the string
`"false"` return 502 before provider I/O. This behavior holds in auto, forced
Anthropic, and forced Chat modes, for buffered and streamed requests.

Modex's shared request mapper already validates `store` as a boolean and omits
it from provider requests, but the native Anthropic request allowlist rejected
the field before that mapper ran. The allowlist now admits `store`; the shared
mapper retains type validation and omission.

`test_store_defaults_are_ignored_on_anthropic_provider_requests` sends five
requests (missing, false, true, null, and string) through each of the three
processes for every route mode and stream setting. It compares statuses,
invalid-request bodies, upstream paths and exact provider request bodies, plus
normalized successful responses. Boolean values match the omitted-field
baseline; invalid values produce no upstream request.

## Validation

- `rtk make build` — pass.
- `PYTHONPATH=tests rtk python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_store_defaults_are_ignored_on_anthropic_provider_requests` — pass.
- `rtk python3 scripts/ci/check-product-dependencies.py` — pass; 71 Mojo files use only standard-library or internal imports.
- `git diff --check` — pass.

The checks use synthetic credentials, isolated temporary state, and loopback
providers. They qualify this control only on Linux x86-64; broader request
parity and the remaining baseline release targets stay open.
