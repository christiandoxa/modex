# Anthropic function-call output aliases and extra fields

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official baseline 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The process test uses the
checksum-pinned Linux x86-64 oracles and the production Modex binary.

The shared Responses request mapper accepts function-call outputs with the
tested `call_id`, `tool_call_id`, or `id` identifiers and `output`, `content`,
`result`, or `error` values. The DeepSeek Anthropic validator had rejected
aliases, extra fields, and nested values before this mapper ran. It now leaves
`function_call_output` validation to the shared mapper.

`test_function_output_aliases_and_extra_fields_match_modes` exercises matched
and orphaned history in `auto`, forced `anthropic`, and forced `openai_chat`
modes. It checks that the first matching `call_id` wins over a conflicting
`tool_call_id`, that the other identifier aliases preserve matched result IDs,
and that nested values and unknown fields do not prevent dispatch. The orphan
is dropped. A whitespace-only `call_id` remains invalid even when a later ID
alias is nonblank; all three processes return 502 before provider I/O. A
non-string primary output ID with a secondary alias remains unmatched and is
dropped in all three processes.

The assertions verify each process's route and projected tool-result IDs.
They do not claim byte-for-byte request parity: the captured provider bodies
also contain message and tool-declaration serialization that differs across
the releases and Modex. This evidence covers buffered history only and does
not qualify other Anthropic request shapes or the remaining baseline targets.

Validation on Linux x86-64:

- `rtk make build` — pass.
- `PYTHONPATH=tests rtk python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_function_output_aliases_and_extra_fields_match_modes` — pass.
- `rtk python3 scripts/ci/check-product-dependencies.py` — pass; 71 Mojo files use only standard-library or internal imports.
- `git diff --check` — pass.

The test uses synthetic credentials, isolated state, and a loopback provider.
It makes no paid provider requests.
