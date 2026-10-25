# Frozen buffered DeepSeek observations

`cases.json` records real application/json request/response interactions with
Prodex 0.439.0 at `433aad44bb249d5c25a231a6b06c2fa522a39a1f`.
The Linux oracle SHA-256 is
`2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a`.

Reproduce with `python3 tests/capture_provider_buffered.py`. The harness uses
synthetic credentials, a temporary HOME/config/state/environment and an
ephemeral numeric-loopback upstream. A synthetic Codex integration client
captures the release's local response; it supplies no Modex behavior.
The incomplete client leaves Super exit 1 with the recorded hook-trust
preflight error. Captured adapter responses are evidence for this component,
not Super/CLI parity or a clean runtime.

Every request/upstream/response body includes a SHA-256. Expected bodies come
from the checksum-pinned release, never from Modex. Rich text, tools, usage,
metadata, trimming, cmd-only rewriting, wrong-type fields and malformed
arguments exercise the active provider-core conformance/fallback path.
The two missing-call-ID samples demonstrate fresh `call_deepseek_` UUIDv7
values. Comparers validate canonical UUIDv7 and occurrence counts before
normalizing only that field; all other bytes remain compared exactly in the
socket suite. Structural fragment acceptance for ordinary function-call
arguments can preserve malformed literal/escape spellings; raw tool-search
arguments additionally require valid output JSON. The fixtures retain that
observable boundary.

`tests/test_provider_chat_buffered.py` exercises the native mapper. The real
POST and restricted-filesystem runtime checks are in
`tests/test_provider_deepseek_transport.py`. Product code does not load these
files. Conversation persistence, CLI wiring, complete parser/error/resource
equivalence, general HTTP/TLS/proxies and non-host targets remain unfinished.
