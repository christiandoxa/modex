# Anthropic Messages output token limits

The pinned Prodex `0.165.1` source is commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2`. Its DeepSeek request path routes
web-search requests to Anthropic Messages. `mojo/prodex_core/deepseek_request_diagnostics.mojo`
validates `max_output_tokens`, `max_tokens`, and `max_completion_tokens` as
positive integers. `mojo/prodex_core/anthropic_chat_request.mojo` writes the
translated `max_tokens`, defaulting to `4096` when the request omits a limit.
The same behavior is present in the pinned `0.439.2` binary.

Before this change, Modex's native Messages request validator rejected these
token fields, and its translated body validator accepted only the default
`4096`. The two pinned release binaries instead accepted
`max_output_tokens: 128` and posted `max_tokens: 128` to
`/anthropic/v1/messages`. This was reproduced through the synthetic Codex
client and loopback provider in `tests/test_anthropic_request_max_output_tokens_01651.py`.

Modex now accepts the three token-limit aliases on this route. The shared
request translator validates each as a positive integer and resolves conflicts
in alias order, so later supplied `max_tokens` or `max_completion_tokens`
values take precedence. The default remains `4096`.

The real-process characterization compares Modex with checksum-pinned Linux
`0.165.1` and `0.439.2` binaries. It verifies the default and each alias,
`max_output_tokens: 128` conflicting with `max_tokens: 64`, the
`max_completion_tokens` precedence case, and invalid zero, negative, decimal,
string, null, and `2^64` values. Both releases and Modex reject invalid limits
before the provider POST. Invalid alias values are also rejected before the
POST. A non-Anthropic control confirms that `max_output_tokens: 128` still
reaches `/v1/chat/completions` as `max_tokens: 128`.

Validation on Linux x86-64: `make build` passed;
`python3 scripts/ci/run-unittest.py test_anthropic_request_max_output_tokens_01651.py`
passed all three process tests against both pinned releases and Modex. Tests
use isolated homes, synthetic credentials, and loopback-only traffic. No paid
provider requests or real credentials are used. The existing 22-test
`test_provider_tools_04392_characterization.py` suite passed, the production
import audit passed for 71 Mojo files, the test census passed for 50 native
sources and 130 Python modules, and `git diff --check` passed.

This qualifies only the exercised Linux x86-64 request shapes. Other provider
fields, release targets, and general provider parity remain unverified.
