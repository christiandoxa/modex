# Native Anthropic text modalities

References: official Prodex 0.165.1 source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The checksum-pinned Linux
oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Baseline trace and behavior

Both release send paths call
`runtime_deepseek_chat_request_body_with_options` before provider dispatch in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs`.
Their `deepseek_request_translation_allows_text_only_modalities` test accepts
`modalities: ["text"]` and asserts that translation omits the field. The
adjacent `deepseek_request_translation_rejects_audio_modality` test rejects
`["text", "audio"]`.

Modex already validates modalities in the shared request mapper and emits no
provider field. Native Anthropic validation rejected the field earlier in its
top-level allowlist. The allowlist now passes it to the shared mapper, which
continues to accept only arrays containing text and rejects audio or values
that are not arrays.

`test_native_anthropic_modalities_match_modes` compares 0.165.1, 0.439.2, and
Modex real processes for missing, empty, text-only, audio-only, mixed, null,
string, number, and object values. Auto, forced Anthropic, and forced Chat
routes each run buffered and streamed requests. Missing, empty, and text-only
values return 200 and produce identical upstream bodies without
`modalities`. Audio, mixed, and wrong-type values return matching 502 bodies
without an upstream POST. Successful normalized responses match across all
three processes. Tests use synthetic credentials and loopback providers.

## Validation

- `rtk make build` — pass with Mojo 1.2.0 (`2016d0cd`); existing unused-variable warnings remain.
- `PYTHONPATH=tests rtk python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_native_anthropic_modalities_match_modes` — pass.
- `rtk python3 scripts/ci/check-product-dependencies.py` — pass; 71 Mojo files use only standard-library or internal imports.
- `rtk python3 scripts/ci/check-test-census.py` — pass; 50 native test sources and 140 Python modules.
- `git diff --check` — pass.

This qualifies the tested field and routes on Linux x86-64 only. The full suite
was not run. All six baseline release targets remain in the parity denominator;
other targets and broader provider behavior remain unqualified.
