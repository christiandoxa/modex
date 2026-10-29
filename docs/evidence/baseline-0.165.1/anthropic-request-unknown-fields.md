# Anthropic request unknown fields

References: official Prodex 0.165.1 source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The checksum-pinned Linux
oracle hashes are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Trace and behavior

Prodex 0.165.1 prepares the translated Chat request before routing it to native
Anthropic Messages. `runtime_deepseek_prepare_model_request` calls
`runtime_deepseek_chat_request_body_with_options`, then passes the translated
body to the Anthropic translator when the selected route requires it
(`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs:481-517`).
The Anthropic kernel validates and serializes that translated Chat request
(`mojo/prodex_core/anthropic_request.mojo:252-316`).

Prodex 0.439.2 follows the same two-stage shape: its Anthropic Responses
translator first calls `translate_responses_request_to_chat`, then passes the
result to `mojo_request::transform`
(`crates/prodex-provider-core/src/translators/anthropic/messages.rs:51-87`;
`crates/prodex-provider-core/src/translators/anthropic/messages/mojo_request.rs:6-19`).
The release processes show that the native provider request contains only
selected fields: an unknown top-level Responses field and an unknown
`web_search_preview` property are dropped before the Anthropic POST.

Modex previously validated the raw Responses request with `_only_fields` before
the shared translator could drop unknown members. Both pinned releases and
Modex now match on the production Super route for these cases: auto and forced
Anthropic each return 200, send one request to `/anthropic/v1/messages`, and
produce the same normalized Responses body and provider body. Synthetic
extension values are absent from the provider request.

Known boundaries remain active. Across auto, forced Anthropic and forced Chat,
malformed `temperature` and unsupported `service_tier` return the same 502
without provider I/O. Duplicate unknown keys are ignored; duplicate known
`temperature` keys use the final value, and a malformed final value still
fails before POST. A request larger than 4 MiB remains rejected before POST.
An existing three-process control also confirms conflicting duplicate domain
filters fall back in auto mode and return 400 in forced Anthropic mode.

The synthetic process harness uses checksum-verified release binaries,
synthetic keys, isolated homes and loopback providers. No real credential,
account login or paid provider request is used.

## Validation

- `rtk make build` — pass with Mojo 1.2.0 (`2016d0cd`).
- `PYTHONPATH=tests MODEX_BINARY=build/modex python3 -m unittest test_anthropic_request_unknown_fields_01651_04392` — 3 tests passed.
- `PYTHONPATH=tests MODEX_BINARY=build/modex python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_native_anthropic_unsupported_chat_fields_fallback_safely test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_auto_conflict_duplicate_keys_fall_back_and_malformed_json_stops` — 2 tests passed.
- `PRODEX_ORACLE=/synthetic/wrong-generic-oracle PRODEX_ORACLE_04392="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" PRODEX_ORACLE_01651="$HOME/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu" PYTHONPATH=tests MODEX_BINARY=build/modex python3 -m unittest test_anthropic_request_unknown_fields_01651_04392` — 3 tests passed with conflicting generic and explicit release variables.
- `PYTHONPATH=tests MODEX_BINARY=build/modex python3 -m unittest test_ci_oracle_routing` — 7 tests passed; both fast and full CI include the module in the active cross-release phase.
- `python3 scripts/ci/check-test-census.py` — 50 native test sources and 141 Python modules each have one suite owner.
- `python3 scripts/ci/check-product-dependencies.py` — 71 Mojo files use only standard-library or internal imports.
- `git diff --check` — pass.

This qualifies selected Linux x86-64 request behavior only. Other request
fields, other provider routes and the remaining five release targets remain
unverified. Complete provider parity and all six release qualifications remain
open.
