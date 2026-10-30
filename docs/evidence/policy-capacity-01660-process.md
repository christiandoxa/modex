# Prodex 0.166.0 policy-capacity process comparison

Reference: official Prodex 0.166.0, source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`.

`tests/test_policy_capacity_01660.py` exercises the connected DeepSeek
API-key route against the pinned release binary and Modex, using only loopback
HTTP fixtures and synthetic API keys. Its six tests passed in an isolated
user, mount, and network namespace:

- On both Chat Completions and Anthropic Messages, a top-level
  `policy_capacity_unavailable` HTTP 503 retries with key B after key A; the
  synthetic success is returned in both binaries.
- With one key, each route forwards the 503 status and body unchanged.
- An unrelated `metadata.policy_capacity_unavailable` value does not suppress
  the Chat Completions overload retry in either binary.
- A `combo:flash,pro` request falls back from `deepseek-flash` to
  `deepseek-v4-pro` on the 503 while retaining key A in both binaries.

The pinned source's `crates/prodex-runtime-proxy/tests/src/error_policy.rs`
generic runtime-proxy policy tests separately classify
`policy_capacity_unavailable` as `Other` / `PassThrough`. That profile policy
is not the same path as Modex's DeepSeek API-key fallback; the process-level
oracle confirms status-based key retry on the connected API-key routes.
Changing those routes to suppress retries would break observed 0.166.0 CLI
behavior. This comparison does not qualify profile-level account selection,
Guardian affinity, or quota handling; API keys are not profiles.
