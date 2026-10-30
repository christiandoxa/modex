# Anthropic duplicate web-search tool selection

Prodex 0.165.1 (`10ae15b5d`) and frozen 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) select the first recognized web
search tool in a Responses `tools` array. In `mojo/prodex_core/chat_tools.mojo`,
`chat_tools` omits web-search entries from function tools, while
`chat_web_options` scans until the first match and reads its options. Later
web-search tools do not affect the provider request.

Modex previously rejected more than one web-search tool before provider I/O.
The request validator now validates the first recognized search tool and
ignores later recognized search tools; the conflicting-domain fallback check
uses the same first-tool rule. Function tool validation, unknown tool rejection,
input validation, and validation of the first search tool remain in place.

Synthetic three-process loopback comparisons cover automatic, forced Anthropic,
and forced Chat routing. Valid duplicates preserve the first tool's options and
emit only one Anthropic search tool; the function tool remains available on
both routes. A later duplicate with invalid `max_uses`, a non-object
`user_location`, or conflicting domain filters is ignored and never appears in
the provider request. An invalid first `max_uses` still fails before POST. A
conflicting first tool still falls back to Chat in automatic mode and returns
400 in explicit Anthropic mode. Unknown near-prefix tools and a typed unknown
input role remain rejected before POST in each tested mode.

Validation on Linux x86-64:

- `make build` — passed.
- Focused process comparisons — 7 methods passed against the pinned 0.165.1
  and 0.439.2 processes and Modex:

  ```sh
  PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" rtk python3 -m unittest \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_duplicate_web_search_tools_use_first_tool_across_modes \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_duplicate_web_search_ignores_later_invalid_options_and_validates_first \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_duplicate_web_search_keeps_first_conflict_and_other_validation \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_web_search_tool_type_aliases_match_both_releases \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_conflicting_search_filters_fall_back_only_in_auto_mode

  PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" rtk python3 -m unittest \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_invalid_web_search_options_fail_before_provider_post \
    test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_malformed_tools_and_top_level_web_search_options_fail_before_post
  ```
- `rtk python3 scripts/ci/check-product-dependencies.py` — passed; all 71 Mojo
  production files use only standard-library or internal imports.
- `rtk python3 scripts/ci/check-test-census.py` — passed; all 50 native test
  sources and 154 Python modules have one suite owner.
- `git diff --check` — passed.

The tests use synthetic keys, isolated homes, and loopback providers. This
qualifies only the tested duplicate-tool behavior on Linux x86-64; it does not
establish Anthropic parity generally or change the six-release denominator.
