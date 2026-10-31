# DeepSeek Super session tool-history scope

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its verified Linux x86-64 oracle
SHA-256 is `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The connected Super relay previously searched its unscoped conversation store
for tool-call IDs even when a request supplied a session ID. With synthetic
sessions A and B and the same provider key, both Prodex 0.166.0 and the prior
Modex build sent A's prompt to the provider in B's tool-result request. Modex
now uses the existing session namespace when a session ID is present. The
real-process comparison in `tests/test_deepseek_session_history_01660.py`
confirms that the tested cross-session and session-to-absent transitions no
longer import the other request's prompt in Modex. The active oracle still
does so; this is a security-preserving compatibility difference, not parity.

The test also covers an absent-to-session transition and two absent session
IDs. When both requests lack a session ID, the shared history behavior remains;
the session value is client supplied and is not an authentication boundary.
Both products return 503 before a second provider request for the tested
same-session follow-up because their existing continuation binding rejects it.
This change does not establish successful same-session continuation or prevent
cross-key reuse in the absence of a trustworthy owner.

The focused comparison passed in a private user, mount, and network namespace
with private HOME and `/tmp`, no default routes, and a synthetic loopback
provider and key. The existing historical comparison controls also passed
locally with the verified 0.165.1 and 0.166.0 oracles and Modex; the missing
0.439.2 oracle was not tested. Mojo 1.2.0 production build passed. The test is
included in the active Fast and Full CI lanes; other targets remain unverified.
