# DeepSeek JSON-mode fallback with web search

References: official Prodex 0.165.1 at
`81c1a01933bc33f536a24452c3fd72c3f8d0b1f3` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The Linux x86-64 oracle
SHA-256 values are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

When a Responses request combines a `web_search_preview` tool with JSON-object
or JSON-schema output, both releases use Chat Completions in the default
`auto` mode. The DeepSeek route prepares the ordinary chat request, including
the JSON-only system instruction and `response_format: json_object`, while
omitting the web-search tool that Anthropic Messages cannot represent. JSON
schema requests also retain the tested `degraded_response_format` metadata.
In explicit `anthropic` mode, both releases return the same 400 invalid-request
body without a provider POST.

The 0.439.2 source traces through
`local_rewrite_deepseek_send.rs::runtime_deepseek_prepare_model_request`, which
calls `translate_openai_chat_request_to_anthropic_messages`, then passes the
translation result to `runtime_deepseek_local_rewrite_route`. The pinned
`local_rewrite_deepseek_send_tests.rs` records the `response_format` rejection
from the Anthropic translator; the route planner permits the automatic Chat
fallback. The same translator and route policy exist in the 0.165.1 source.

Modex now detects a non-text `request_format` before provider I/O. In `auto`
mode it selects Chat Completions and uses the existing web-search fallback
that removes only the unsupported search tool. Explicit `anthropic` mode uses
the existing 400 incompatibility response.

`tests/test_anthropic_websearch_json_mode_01651_04392.py` exercises the real
Modex Super process and both checksum-verified release binaries with synthetic
loopback providers. It covers top-level and nested JSON-object/JSON-schema
forms, the generated chat request and response, and explicit `anthropic` mode.

Validation on Linux x86-64: `make build` and both methods under
`scripts/ci/run-unittest.py` passed. The cases compare parsed request JSON,
response JSON after removing only `created_at`, status and isolated-workspace
cleanup. A combined nine-method rerun including the preceding sampling slice
and active web-search mode controls passed. The production import audit passed
for 71 Mojo files; the test census covered 50 native sources and 134 Python
modules, each with one suite owner. `git diff --check` passed. The tests use
synthetic credentials and make no real provider requests.
Other incompatible Anthropic request shapes, non-Linux targets and full
provider parity remain unqualified.
