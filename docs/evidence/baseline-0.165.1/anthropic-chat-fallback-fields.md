# Anthropic web-search fallback for Chat-only fields

References: official Prodex 0.165.1 source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Linux oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Trace and behavior

For native Anthropic search, 0.165.1's
`runtime_deepseek_prepare_model_request` runs the Anthropic Messages translator
before provider I/O, then passes its result to
`runtime_deepseek_local_rewrite_route`. That planner chooses Chat fallback only
in `auto` mode and only when the rejection reason matches the pinned safe
prefixes. `mojo/prodex_core/deepseek.mojo::deepseek_native_fallback_safe_plan`
recognizes `Anthropic Messages does not translate chat field `, web-search
option incompatibilities, and `Anthropic web search ` failures. The
`AutoChatFallback` branch sends a Chat request with the native search tool
removed. Explicit Anthropic mode returns the invalid-request response before
upstream I/O.

Responses `logprobs: true` and supported `reasoning.effort` values become valid
Chat request fields. The native Messages translator rejects these Chat-only
fields, so both pinned releases use the safe automatic Chat fallback. Modex's
Anthropic adapter previously rejected the same translated request with a
different error label, preventing its existing fallback classifier from
selecting Chat. The adapter now uses the source-derived `chat field` rejection
label for unknown fields on the translated Chat request. Input and field type
validation still runs before routing; malformed `logprobs` and `reasoning`
values remain pre-POST errors. Unsupported `service_tier` also remains a
pre-POST error rather than being treated as safe for fallback.

`test_native_anthropic_unsupported_chat_fields_fallback_safely` compares the
0.165.1, 0.439.2, and Modex processes with synthetic credentials, isolated
homes, and loopback providers. Buffered tests cover `logprobs` and reasoning in
automatic and explicit Chat modes, plus the forced-Anthropic 400 response. A
streamed Chat request combines both fields. Malformed field shapes and an
unsupported service tier verify that neither automatic nor forced modes send
an upstream request.

## Validation

- `rtk make build` — pass with Mojo 1.2.0 (`2016d0cd`).
- `PYTHONPATH=tests python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_native_anthropic_unsupported_chat_fields_fallback_safely` — pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; no dependency or import changes.
- `git diff --check` — pass.

This covers only selected Chat-only fields and route modes on Linux x86-64.
Anthropic request translation, broader fallback classification, other compiler
targets, and all release qualifications remain open.
