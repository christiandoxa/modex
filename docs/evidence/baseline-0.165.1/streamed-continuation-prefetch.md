# Streamed continuation and prefetch ownership

Both pinned releases accept a single-key DeepSeek follow-up when the preceding
stream's ID occurs only in the prefetched prefix, or when the stream uses a
generated fallback ID. The loopback provider receives the first user message,
assistant text, and follow-up. Published Modex returns 503 before a second
provider request. The selected native Anthropic message-start fixture has the
same difference. When a later raw event repeats the ID, or the request carries
a bound session ID, all three processes return 503 on the follow-up.

The frozen precommit reader stores the prefix separately and wraps only the
remaining raw stream with its SSE binding observer. A local candidate made
Modex follow that boundary for a single key and passed the selected history
controls. It was not integrated: the then-current Super relay did not authenticate
inbound loopback clients, used an unscoped conversation store, and wrote a fixed
`prodex-runtime-provider` token. With a synthetic different Authorization
header and a known response ID, the candidate sent the first client's stored
history to the provider. Published Modex rejected the same follow-up with 503
and one provider POST. Both releases accepted the different synthetic client.
The relay now requires a per-launch bearer token before provider dispatch;
the different synthetic client receives 401 and no second POST. Same-UID
processes able to read the private overlay or relay environment can obtain
the token, and full history/provider-key ownership remains unverified. A
caller-supplied session ID or fixed token is not proof of ownership.

With two synthetic keys, both releases sent the follow-up and prior synthetic
conversation history using the second key after the first key produced the
stream. Modex retains 503 and sends no second request. This is a conservative
security difference, not parity. The candidate observer work remains on its
isolated worker branch and is not part of published Modex.

The pinned source commits are 0.165.1
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and frozen 0.439.2
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Their Git objects for
`local_rewrite_pipeline_dispatch/provider_precommit.rs` share SHA-256
`7b48d032641a5d1007fee0aaf9af324c9465a1e7aa0f9d579728071958330b5f`;
`local_rewrite_response_dispatch.rs` shares SHA-256
`fd74afb623fde8b52595ee49d5714bd994e1214dd4f7d5da62789a8bde7fb224`.

The three-process regression in `tests/test_deepseek_continuation.py` uses
isolated synthetic homes and loopback peers. It characterizes prefix and
fallback IDs, delayed later IDs, session binding, a different synthetic client,
multiple synthetic keys, and the native Anthropic path. It records a gap and
does not establish parity. Real credentials, external provider traffic, account
login, runtime WebSocket interruption, all six targets, and security
qualification remain untested or unfinished.
