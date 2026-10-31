# Anthropic mixed-tool request byte ordering

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

Before this change, the connected DeepSeek Super route sent semantically equal
JSON with different raw bytes for mixed web-search/function requests. Function
tool fields were ordered differently, including the generated default schema;
`stop_sequences` also followed `stream` and `system` instead of preceding them.
The production translator now emits those fields in the observed order. The
web-search tool order and field validation are unchanged.

The active runtime invokes `transform_anthropic_chat_request` through the
Anthropic Chat-to-Messages translator. The corresponding pinned source,
`mojo/prodex_core/anthropic_chat_tools.mojo`, writes description, schema and
name in the observed order. A separate `anthropic_request.mojo` tool writer
uses a different order; it is not the Chat-to-Messages writer exercised here.

`test_anthropic_mixed_tool_request_bytes_match_active_release` compares the
actual provider request bytes and successful client status from both real
processes for six synthetic cases: optional description and schema, a default
schema, web-search filters, required tool choice, and combined system, stop and
sampling fields. Both use isolated temporary state, synthetic credentials and
a private loopback-only network namespace. The production build, this test,
the rest of the active provider-shape and Anthropic-stream modules (eight tests
total), and the production import audit passed on Linux x86-64. This is focused
wire evidence; it does not qualify every request shape or other release targets.
