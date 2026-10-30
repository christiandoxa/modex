# DeepSeek Anthropic web-search tool aliases

The official 0.439.2 source at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` recognizes `web_search`, exact
`web_search_preview`, and every `web_search_preview_` prefix in
`mojo/prodex_core/chat_tools.mojo::chat_web_search_tool`. The 0.165.1 source
has the same classifier, and its DeepSeek bridge test at
`crates/prodex-provider-core/src/deepseek_bridge/tests.rs:901` exercises
`web_search_preview_2025_03_11`.

Modex's request mapper already recognized these three forms in
`provider_request_tools.mojo::_is_web`, but the Anthropic transport validator
accepted only exact `web_search_preview` before provider dispatch. Its
conflicting-domain fallback classifier also matched only that exact value.
The validator and conflict classifier now share the accepted alias set;
existing domain, location, use-count, and context validation is unchanged.

`test_web_search_tool_type_aliases_match_both_releases` launches the checksum-
pinned 0.165.1 and 0.439.2 processes and Modex for `web_search`, the exact
preview form, and version strings with underscore, compact-date, hyphenated,
and future suffixes. All return 200, issue one POST to
`/anthropic/v1/messages`, send the same normalized provider body containing
`web_search_20250305`, and produce equivalent normalized responses.
`test_near_prefix_web_search_types_are_rejected_by_both_releases` checks
`web_search_previewX2025_03_11` and `web_search_preview-2025_03_11`; all three
processes return 502 without a provider POST and with identical response
bodies. The existing mode matrix now also covers conflicting domain filters
on a versioned alias, including automatic Chat fallback and forced-mode
behavior.

Validation on Linux x86-64:

- `rtk make build` — passed.
- `PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_web_search_tool_type_aliases_match_both_releases test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_near_prefix_web_search_types_are_rejected_by_both_releases test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_conflicting_search_filters_fall_back_only_in_auto_mode`
  — 3 methods passed against both pinned release processes and Modex.
- `rtk python3 scripts/ci/check-product-dependencies.py` — passed for 71 Mojo
  files.
- `rtk python3 scripts/ci/check-test-census.py` — passed for 50 native test
  sources and 154 Python modules.
- `git diff --check` — passed.

The fixtures use synthetic keys, isolated homes, and loopback providers. This
qualifies only the tested request shapes on Linux x86-64; it does not establish
general provider parity or change the six-release denominator.
