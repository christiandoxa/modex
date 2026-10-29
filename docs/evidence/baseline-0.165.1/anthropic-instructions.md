# Responses instructions in Anthropic Messages requests

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Their frozen
`crates/prodex-provider-core/src/deepseek_bridge/request_messages.rs` files
are byte-identical (SHA-256
`682613aa238bd3aa57b35fa6a3858717bd4b036de6eb9740e09dbfa861576ebb`).

Both request mappers insert a nonblank string `instructions` as the leading
system message. They preserve its original text, omit it when it contains only
Unicode whitespace, then place input `system` and `developer` messages after it
using `\n\n` separators. The shared request validator rejects non-string
instructions before provider dispatch.

Modex already built system messages from `instructions` in its shared request
preparation path, but the Anthropic adapter's top-level allowlist rejected the
field before preparation. The adapter now allows string instructions and
rejects other types before provider I/O.

`tests/test_anthropic_mixed_tools_01651.py` runs synthetic production Super
requests through both checksum-pinned releases and Modex. It compares the
Anthropic route, raw request body, translated system text, response status and
workspace cleanup. Cases cover ordinary instructions, ordering with input
system/developer messages, ASCII and Unicode whitespace-only values, and a
nonblank value surrounded by NBSP and IDEOGRAPHIC SPACE that contains a
zero-width space. Null, numeric, and array instructions return 502 without an
upstream POST in all three processes.

Validation on Linux x86-64: `make build` passed. The two focused real-process
methods passed against all three processes; the production dependency audit and
`git diff --check` passed. All provider traffic and credentials are synthetic
and loopback-only. This qualifies the tested Anthropic web-search route and
input shapes, not complete request translation, other routes, targets or
release parity.
