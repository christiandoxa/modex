# Untyped scalar content on the Anthropic web-search route

Prodex 0.165.1 commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`
validates explicitly typed `message` inputs in
`mojo/prodex_core/deepseek.mojo:deepseek_input_item_validation`, while an
input item without `type` returns before typed content validation. The runtime
then prepares the Chat request and translates it to Anthropic Messages in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_deepseek_send.rs:runtime_deepseek_prepare_model_request`.
The Modex shared Responses mapper already serializes untyped scalar content as
text, but its additional Anthropic raw-request check rejected it before the
provider POST. The check now leaves present untyped scalar values to the shared
mapper. Explicitly typed scalar content is still rejected.

Synthetic Super launches compare the checksum-pinned 0.165.1 and 0.439.2
Linux release executables with Modex. Null, booleans, integer and decimal
content become their JSON text and reach one loopback Anthropic Messages POST
in both buffered and streamed requests. Typed controls for null, false, zero
and decimal remain HTTP 502 with no upstream POST. The earlier Modex binary
failed all twelve untyped buffered/streaming controls with HTTP 502. Tests use
isolated temporary homes and synthetic provider credentials.

The focused tests in `tests/test_anthropic_mixed_tools_01651.py` compare
upstream request bodies and response behavior; timestamps and generated stream
IDs alone are normalized. Selected assistant, system and developer scalars
also match in forced Anthropic mode. On Linux x86-64, three scalar methods and
three existing array/role controls passed after the production build; the
71-source dependency audit and test census passed. This is a selected input-shape slice, not complete
Anthropic request, continuation, security or platform parity. All six release
targets remain in scope.
