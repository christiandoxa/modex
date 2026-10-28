# Continuation ownership against Prodex 0.439.2

`tests/test_continuation_binding_04392.py` checks the checksum-pinned Linux
0.439.2 binary and the production Modex Super path with isolated synthetic
Codex and loopback provider processes. The 11 cases cover previously owned
and unknown response IDs, matching and changed session and turn identities,
upstream failure, an accepted invalid body, and both route directions between
Responses and chat completions. Each compares expected response statuses and
POST counts for both binaries; blocked continuations also compare the complete
error JSON.

The previously recorded protected two-turn mismatch is resolved in the
current source: both binaries return 200 then 503 with one upstream POST. The
focused regression passed all 11 cases on Linux x86-64. The relay still uses a
single static endpoint and a process-local table; multi-profile ownership,
persistence and general security or resource equivalence remain unverified.
No parity status is promoted.
