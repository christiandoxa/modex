# Mixed Anthropic function and web-search tools against 0.165.1

Reference: Prodex `0.165.1`, source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2`. The verified Linux oracle is
`~/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu`, SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.

## Trace and tested behavior

The pinned Responses adapter calls `translate_responses_request_to_chat`, then
`translate_chat_request_to_anthropic` and the Anthropic request kernel. The
request writer maps function declarations to `input_schema`, maps web search
to `web_search_20250305`, and maps `auto`, `required`, named-function, and
`none` choices to Anthropic Messages semantics. Captured oracle requests confirm
function declarations precede the web-search declaration. With `none`, the
oracle omits both tool declarations and `tool_choice`.

Modex now translates the tested mixed request through its production Super
path. Synthetic comparisons check two function declarations plus web search,
object and missing-schema defaults, all five choice cases, and rejection of a
non-object function schema before the provider receives a request. The
buffered response comparison preserves text, search, function-call, and later
text order, including two serial search/result pairs plus a function call. The
reply planner preserves text-message boundaries around search results. Each
result maps to the latest preceding search use with the same ID; later results
overwrite its sources, and a result before a matching use is ignored. This
preserves each search query and the oracle's source assignment. An ID map keeps
the association linear. The SSE comparison covers a search/result pair, a
function call with split argument
deltas, and following text; the complete normalized event sequence matches the
oracle. Buffered content arrays are capped at the oracle's 65,536 blocks before
block classification. Exact-limit function-only (with adjacent text blocks)
and mixed replies match the oracle; both oracle and Modex reject 65,537 blocks
with a 502 response. Adjacent text blocks are grouped in one pass to keep the
exact-limit case practical.

The two-search restriction on mixed buffered replies has been removed. The
production relay matches 0.165.1 for 3, 64 and 1,024 distinct search/result
pairs followed by a function call; complete normalized output and provider
request bodies are compared. The 65,536-block and provider-body limits remain.

`tests/test_anthropic_mixed_tools_01651.py` uses the checksum-pinned oracle,
the production Modex binary, synthetic keys, isolated HOME/state directories,
and a loopback provider. No paid traffic or real credentials are used.

## Validation

- `rtk make build` — pass.
- `python3 scripts/ci/run-unittest.py test_anthropic_mixed_tools_01651.py` — 14 tests pass, including exact/over-limit boundaries, text-run boundaries, duplicate-result overwrite, repeated-ID latest-use, reversed distinct-ID results, and result-before-use behavior.
- `PYTHONPATH=tests python3 -m unittest test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_repeated_server_search_results_match_release test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_buffered_search_shape_remains_release_compatible test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_function_tool_use_stream_matches_release` — 3 existing pure-search and function-stream controls pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass.
- `git diff --check` — pass.

This qualifies only the exercised Linux x86-64 shapes. Custom and namespaced
function tools, search options beyond `allowed_domains`, multiple search pairs
in streams, interleaved
search events, malformed provider responses beyond the tested schema rejection,
other release targets, and general Anthropic parity remain open. No contract or
release qualification is promoted.
