# DeepSeek tool history and credential ownership

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

This change closes the tested local relay leak where stored function-call
history was included in a later tool-output request handled by another API key.
The cache key now includes the session namespace and a process-local credential
index; equal API-key entries resolve to the same index. Cache identifiers do
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
native route therefore remains unverified. These checks use synthetic session
identifiers; they do not characterize adversarial session identifiers,
credential-specific eviction interactions, or process-restart behavior.

## Checks

- `make build` — passed with the pinned Mojo 1.2.0 toolchain.
- `mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_provider_conversations.mojo -o /tmp/test_provider_conversations_runtime_policy` — passed.
- `/tmp/test_provider_conversations_runtime_policy` — passed, including per-key same-session lookup and absent-versus-empty namespace isolation.
- The same active suite passed in `unshare -Urnm`: the checkout was bind-mounted read-only at `/mnt`, `/tmp` was a private mode-0700 tmpfs, `lo` was the only interface, and IPv4 and IPv6 default routes were absent. The test process used `HOME=/tmp/home`, `TMPDIR=/tmp/work`, `MODEX_BINARY=/mnt/build/modex`, and the checksum-pinned `PRODEX_ORACLE`; `python3 scripts/ci/run-unittest.py test_deepseek_session_history_01660.py` passed all 6 tests. Its provider peer binds loopback and its API keys are synthetic.
- `python3 -m py_compile tests/test_deepseek_continuation.py tests/test_deepseek_key_rotation_01651_04392.py tests/test_deepseek_session_history_01660.py` and `git diff --check` — passed.

The modified historical 0.165.1/0.439.2 characterization was not run because
the 0.439.2 oracle binary is absent from this environment. No parity claim is
made for the unverified native cached-history retry case.
