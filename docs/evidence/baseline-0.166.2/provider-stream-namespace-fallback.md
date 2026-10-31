# DeepSeek streamed tool namespace fallback

The 0.166.2 Linux x86-64 oracle and Modex were compared through the real
DeepSeek Super relay with synthetic Chat Completions JSON and SSE from a
loopback-only provider. Frozen Prodex uses
`provider_core_split_flat_namespace_tool_name`, backed by
`mojo/prodex_core/chat_tool_names.mojo::tool_name_split_namespace_bounds`. That
decoder considers only the final `--` pair, and when that pair is invalid it
tries the `mcp__...__tool` fallback. The regression verifies the oracle SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

The prior Modex `_split_name` kept scanning backward after an invalid final
pair and accepted an earlier valid `--`. This made the streamed item for
`a--b--` become namespace `a`, name `b--`, while Prodex preserved the complete
name. For `mcp__srv__foo--bar--`, Prodex fell back to namespace `mcp__srv`,
name `foo--bar--`; Modex incorrectly chose namespace `mcp__srv__foo`, name
`bar--`. The shared Modex splitter now validates only the final pair before
the existing MCP fallback.

The active regression checks last-valid and invalid-final pairs, empty left
and right sides, the MCP fallback, buffered controls, and both streamed
`response.output_item.added` and `response.output_item.done` items. It asserts
the synthetic authorization header and upstream path for both processes.
The active suite also compares the Anthropic Messages `tool_use` caller using
`a--b--`, `mcp__srv__foo--bar--`, a valid final split, and valid and invalid
whitespace cases. Each reaches `/anthropic/v1/messages` with the synthetic
`x-api-key`; all output items match the oracle.

All eleven methods in `test_provider_shapes_01662.py` passed on 2026-10-31 in
a Bubblewrap user/mount/network namespace with private `/tmp`, isolated 0700
HOME/TMPDIR/XDG/state roots, read-only workspace/oracle/Modex mounts, only
loopback up, and no default route. The native `test_provider_chat_items`
checks, production build, Python syntax check, 74-file production import audit,
and staged `git diff --check` also passed.

This qualifies the selected DeepSeek stream and Anthropic buffered name
mappings on Linux x86-64. It does not establish full Anthropic, provider,
security, or six-target parity.
