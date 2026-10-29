# Native Anthropic background and truncation controls

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official baseline 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Process comparisons use the
checksum-pinned Linux x86-64 binaries and the production Modex binary.

## Baseline trace

Both pinned `local_rewrite_deepseek_send.rs` implementations call
`runtime_deepseek_chat_request_body_with_options` at line 481, then select the
native Messages translation at line 517. The shared chat-compatible request
builder constructs a new provider request body. Both releases also contain
`deepseek_request_translation_tolerates_default_response_controls` at line
1436 of `local_rewrite_tests/deepseek.rs`; it supplies `store: false`,
`background: false`, and `truncation: "disabled"`, then verifies all three are
omitted from the translated body.

Real-process comparisons confirm that missing controls, either default alone,
and both defaults are accepted. `background: true` and `truncation: "auto"`
return 502 before provider I/O. These results hold in auto, forced Anthropic,
and forced Chat modes for buffered and streamed requests. Successful responses
match after normalization, and provider request bodies omit both controls.

Before the fix, Modex rejected the defaults on auto and forced Anthropic paths
before dispatch; forced Chat already matched both releases. The native
Anthropic allowlist in `provider_anthropic_messages.mojo` now passes the fields
to the shared request mapper. That mapper validates only `false` and
`"disabled"` and does not forward either value.

`test_native_anthropic_default_response_controls_match_modes` compares six
requests per process and mode/stream combination. It checks response statuses,
upstream paths and bodies, normalized successful responses, and matching
pre-POST errors. The four accepted requests produce four upstream posts; the
two invalid requests produce none.

## Validation

- `rtk make build` — pass; existing unused-variable warnings remain.
- `cd tests && rtk python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_native_anthropic_default_response_controls_match_modes` — pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; all 71 production Mojo files use only standard-library or internal imports.
- `git diff --check` — pass.

The harness uses synthetic credentials, isolated temporary state, and loopback
providers. This qualifies only the tested controls on Linux x86-64. Other
provider behavior and the remaining baseline targets remain unqualified.
