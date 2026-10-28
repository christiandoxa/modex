# DeepSeek SSE precommit slice

Reference: Prodex 0.439.2 commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
Linux oracle SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
The frozen `provider_precommit.rs` reads up to 8 KiB of SSE prefix while
the separate lookahead and upstream idle deadlines run. An upstream error
with an empty prefix rejects before committing; after a prefix it is delivered
through the committed stream. The prefetched bytes remain available to the
translator and an accepted request is not replayed.

The Modex production Super path now implements those selected chat-stream
boundaries, retains the original idle deadline across lookahead expiry, and
maps HTTP body-read failures to the frozen decoding diagnostic. Real-process
tests use isolated homes and synthetic loopback peers. They cover empty and
partial prefixes, text before idle, lookahead before idle, equal-deadline race
outcomes, split status/header/chunk framing, clean EOF, truncated bodies,
invalid UTF-8 in data and comment lines, and gated incremental delivery.
The covered stream attempts each send one upstream POST.

When an empty-prefix timeout rejects before commitment, the accepted binding
is not retained. A two-turn regression checks session, turn-state and
previous-response identifiers against the official oracle: the rejected first
attempt returns 502 and a later request with the same identifier returns 200,
with one upstream POST per request. Before this fix Modex rejected the second
request with 503 after recording the first request's binding too early.
A control commits a text delta first and confirms the same session is then
bound: both binaries reject the second request with 503 after only one POST.

The release can emit either `error decoding response body` or
`runtime upstream stream idle timed out` according to transport scheduling;
Modex emits the first form. Exact timeout race distributions, full precommit
retry and credential rotation, parallel prefetch admission, native Messages
and general HTTP transport are not qualified. No contract or platform status
changes on this partial evidence.
