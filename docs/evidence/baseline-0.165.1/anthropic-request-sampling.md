# Anthropic web-search request parameters against both pinned releases

References: official Prodex 0.165.1 at
`81c1a01933bc33f536a24452c3fd72c3f8d0b1f3` and Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The Linux x86-64 oracle
SHA-256 values are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

Both releases accept `temperature`, `top_p`, and `stop` controls on the
Responses request before translating the request to Anthropic Messages. In
the 0.439.2 source, `local_rewrite_deepseek_send.rs` calls
`translate_openai_chat_request_to_anthropic_messages`; the shared
`AnthropicRequestKernelInput` exposes `temperature`, `top_p`, and
`stop_sequences`. The same request-kernel fields exist at the pinned 0.165.1
source commit. Modex already validated and normalized these controls in
`provider_request_params.mojo`, and its Anthropic body builder already emitted
them. Two request allowlists rejected them before that mapping ran.

The production request allowlists now admit `temperature`, `top_p`, `stop`,
`stop_sequences`, and `stopSequences`. Existing validation still requires
numeric sampling values and a string or string-array stop value; the mapper
normalizes all three stop spellings to Anthropic `stop_sequences`.

`tests/test_anthropic_request_sampling_01651_04392.py` sends synthetic
Responses requests through the real Modex Super process and both checksum-
verified release processes. It compares the parsed Anthropic request bodies,
the response payload after removing only `created_at`, and isolated-workspace
cleanup. Cases cover both sampling values together, string and array stop
values, both stop aliases, alias precedence, and malformed values. Malformed
values return 502 before any provider POST in all three processes.

Validation on Linux x86-64: `make build` and both methods under
`scripts/ci/run-unittest.py` passed. The adjacent token-limit and stop-field
real-process controls passed seven methods. The production import audit passed
for 71 Mojo files; the test census covered 50 native sources and 133 Python
modules, with one suite owner each. `git diff --check` passed. The checks use
synthetic provider keys and loopback responses. Other request fields and rich
message content remain guarded; this slice does not qualify other release
targets or full DeepSeek request parity.
