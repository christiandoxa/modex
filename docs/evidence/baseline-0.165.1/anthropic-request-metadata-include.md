# Anthropic Messages request metadata and include

References: official Prodex 0.165.1 source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Linux oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Trace and behavior

The 0.165.1 runtime calls
`runtime_deepseek_chat_request_body_with_options` before provider dispatch in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs`.
That stage extracts Responses `metadata` into response metadata and validates
its top-level object shape. The adapter then calls
`translate_responses_request_to_anthropic`, which translates Responses to Chat
and passes the resulting body through `mojo_request::transform` and the
Anthropic request kernel. The kernel emits only Anthropic Messages fields, so
top-level `metadata` and `include` do not appear in the provider request.
The pinned `deepseek_bridge/request_params/metadata.rs` requires `metadata` to
be an object; the release's request path requires `include` to be an array.

Before the Modex change, the Anthropic request allowlist rejected valid
`metadata` objects and `include` arrays with HTTP 502 before provider dispatch.
Modex now accepts and omits these fields on the Messages route, and checks the
same top-level types as both releases. The releases also accept arbitrary
metadata values and include array entries, then omit them from the provider
request; Modex preserves that observed behavior.

`test_responses_metadata_and_include_match_routes` compares complete normalized
responses and parsed provider requests from checksum-verified 0.165.1,
0.439.2, and Modex processes. Buffered controls cover automatic Anthropic,
forced Anthropic, and explicit Chat Completions routing. Streamed controls
cover automatic and forced Anthropic routing. Invalid null/scalar metadata and
include values return the same pre-POST 502 response on each route. All
requests use synthetic credentials, isolated homes, and loopback peers.

## Validation

- `rtk make build` — pass with Mojo 1.2.0 (`2016d0cd`).
- `PYTHONPATH=tests python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_responses_metadata_and_include_match_routes` — pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; no dependency or import changes.
- `git diff --check` — pass.

This qualifies only the tested request fields and route shapes on Linux x86-64.
Complete Anthropic provider behavior, other compiler targets, and all release
qualifications remain open. The separate Chat-only-field fallback slice is
documented in `anthropic-chat-fallback-fields.md`.
