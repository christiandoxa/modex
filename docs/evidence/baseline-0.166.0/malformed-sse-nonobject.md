# Malformed SSE non-object chunk

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

For a synthetic `/v1/responses` stream whose provider sends `data: []`, the
reference sends HTTP 200 chunked response headers but emits no body and does not
close the socket within the 1.5-second observation window. Modex instead emits
a terminal `response.failed` event with `chat stream chunk is not an object`.
The oracle timeout is recorded as a mismatch, not a completed response or
parity pass. Modex retains its explicit failure behavior.

The active passthrough process test uses a bounded raw socket and synthetic
credentials in a private loopback-only network namespace. It verifies the
reference timeout, Modex's failure and terminal chunk, and both products'
completed empty-choice and invalid-JSON controls. The worker ran the full
active passthrough module successfully; other malformed inputs, longer waits,
and non-Linux targets remain unqualified.
