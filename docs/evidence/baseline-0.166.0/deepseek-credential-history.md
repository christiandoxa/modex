# DeepSeek tool history and credential ownership

This change closes the local relay's cross-key tool-history exposure. The cache
key now includes the session namespace and a process-local credential index;
equal API-key entries resolve to the same index. Cache identifiers and logs do
not contain API-key text. Missing and explicitly empty namespaces use distinct
keys.

The 0.166.0 control confirms the exposed behavior: a tool call stored after a
request using key A is included in a later request using key B. Modex returns
`503 bound_continuation_unavailable` before sending that foreign tool output
upstream. The same scope rule applies to buffered and streamed Responses. A
cached tool history also prevents retrying a failed request under another API
key; the 0.166.0 control retries and sends the cached history to the other key.
Duplicate identical key entries retain history because they authenticate as the
same credential. Concurrent follow-ups against one cached call produce one
same-key provider request and reject the other key while both lookups share the
cache lock.

The explicit-session guard still rejects the existing unsupported continuation
before it reaches the cache. Native Anthropic first-event retry remains covered
for requests without cached history: both 0.166.0 and Modex retry from key A to
key B. A synthetic cached-history continuation through the native Anthropic
route was rejected with HTTP 400 during request preparation by both binaries,
before either reached the upstream peer. Cached-history suppression on that
native route therefore remains unverified.

## Checks

- `make build` — passed with the pinned Mojo 1.2.0 toolchain.
- `mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_provider_conversations.mojo -o /tmp/test_provider_conversations_runtime_policy` — passed.
- `/tmp/test_provider_conversations_runtime_policy` — passed, including per-key same-session lookup and absent-versus-empty namespace isolation.
- `python3 scripts/ci/run-unittest.py test_deepseek_session_history_01660.py` — passed, 6 tests. The active oracle checksum was verified by the test fixture.
- `python3 -m py_compile tests/test_deepseek_continuation.py tests/test_deepseek_key_rotation_01651_04392.py tests/test_deepseek_session_history_01660.py` and `git diff --check` — passed.

The modified historical 0.165.1/0.439.2 characterization was not run because
the 0.439.2 oracle binary is absent from this environment. No parity claim is
made for the unverified native cached-history retry case.
