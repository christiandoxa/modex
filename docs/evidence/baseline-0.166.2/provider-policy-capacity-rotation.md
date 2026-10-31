# DeepSeek policy-capacity retry and API-key rotation

`tests/test_provider_policy_capacity_01662.py` reuses the existing synthetic
policy-capacity cases and binds them to the checksum-pinned Prodex 0.166.2
Linux x86-64 binary. It compares Modex and Prodex through their real Super
launch and loopback relay processes. The cases cover a two-key 503 retry,
single-key 503 passthrough, combo-model retry before credential rotation,
structured overload rotation despite unrelated metadata, and the same
two-key/single-key controls on the native Anthropic Messages route.

The matrix passed in isolated user and filesystem namespaces with loopback
network access only. Requests, responses and API keys are synthetic. These
checks qualify the selected 0.166.2 API-key retry path; they do not cover
profile-backed rotation, session affinity, other response classes, other
release targets, or overall provider parity.

To reproduce with a private loopback-only network and isolated filesystem,
use the namespace driver in
`docs/evidence/baseline-0.166.2/provider-relay-routes-bodyless.md`, replacing
its test module with `test_provider_policy_capacity_01662.py`.
