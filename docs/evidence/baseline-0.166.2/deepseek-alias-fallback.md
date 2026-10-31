# DeepSeek alias fallback and retry policy

`tests/test_deepseek_alias_fallback_01662.py` compares real Prodex 0.166.2 and
Modex processes through synthetic loopback peers. The test runner requires a
Bubblewrap user, filesystem, and network namespace with only loopback enabled;
HOME, TMPDIR, config, cache, state, credentials, and ports are isolated.

The active process retries the `flash` chain as
`deepseek-flash` → `deepseek-v4-pro`, and `auto` and `pro` as
`deepseek-v4-pro` → `deepseek-flash`. It sends `default` literally; an empty
model resolves to `deepseek-v4-pro` with no further candidate. Concrete model
IDs also remain single-candidate. The comparison covers structured and generic
404 fallback, a generic 400 no-retry control, generic and
`policy_capacity_unavailable` 503 model-first fallback followed by credential
rotation, and buffered and streamed requests. Native Anthropic
SSE tests cover one retryable first-event fallback and `overloaded_error` with
two synthetic keys: both processes retry the next model once on key A, then
stop without trying key B. A successful fallback is not replayed.

All eight process tests passed against the checksum-verified Linux x86-64
oracle. `rtk make build`, `rtk make unit`, and the isolated active test wrapper
passed. This qualifies only the listed cases on Linux x86-64; full DeepSeek
parity, other provider paths, and the other five release targets remain open.
