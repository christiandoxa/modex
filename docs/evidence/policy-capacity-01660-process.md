# Prodex 0.166.0 policy-capacity process comparison

Reference: official Prodex 0.166.0, source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`.

`tests/test_policy_capacity_01660.py` exercises the connected
`super --provider deepseek` route against the pinned release binary and Modex,
using only a loopback HTTP fixture and synthetic API keys. In an isolated user,
mount, and network namespace, the focused test file passed all three tests:

- With two keys, a top-level `policy_capacity_unavailable` HTTP 503 retries to
  the second key and returns its successful response in both binaries.
- With one key, the 503 status and response body pass through unchanged in both
  binaries.
- A `policy_capacity_unavailable` value under unrelated `metadata` does not
  suppress the overload retry in either binary.

The pinned source's `crates/prodex-runtime-proxy/tests/src/error_policy.rs`
generic runtime-proxy policy tests separately classify
`policy_capacity_unavailable` as `Other` / `PassThrough`. That profile policy
is not the same path as Modex's DeepSeek API-key fallback; the process-level
oracle confirms status-based key retry on the connected route. Changing that
route to suppress retries would break observed 0.166.0 CLI behavior. This
comparison establishes only the DeepSeek CLI path; it does not qualify
profile-level account selection or quota handling.
