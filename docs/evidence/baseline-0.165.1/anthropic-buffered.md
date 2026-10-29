# Buffered Anthropic tool-use observations

The production Super path was compared with the checksum-pinned Linux 0.165.1
executable using synthetic Codex and loopback peers. Buffered Anthropic
responses with function tool calls now preserve tool order and adjacent text
parts, including mixed text and multiple calls. The tested input variants
include missing, scalar and array tool inputs and namespaced names. Missing,
null and numeric stop reasons retain the observed metadata behavior.

A synthetic two-turn comparison also checks the second upstream request: the
saved assistant tool call and its function result are translated into Anthropic
history. Additional production comparisons cover unmatched call IDs, mixed
text/tool history and representative array outputs. Historical 0.439.2
Anthropic checks are retained separately. These
cases do not qualify mixed web-search/function blocks, arbitrary malformed
input, real providers, concurrency or any non-Linux release target.

A synthetic buffered response with an Anthropic `image` block in the tested
web-search shape returns 502 in both Prodex 0.165.1 and Modex after one local
upstream response; neither client response exposes the image data. Responses
`input_image` requests are also rejected before the provider POST by both
processes. The streaming image block has a different release behavior and is
covered in `anthropic-stream.md`; this buffered rejection does not imply that
image request or response support is implemented.
