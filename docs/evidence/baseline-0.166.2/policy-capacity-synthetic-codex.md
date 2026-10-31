# Policy-capacity response through synthetic Codex

`tests/test_provider_policy_codex_01662.py` compares the checksum-verified
Prodex 0.166.2 Linux executable and production Modex through their existing
Super launch path. A synthetic Codex child sends one request to a synthetic
loopback provider, which returns HTTP 503 with `policy_capacity_unavailable`.
Both clients receive the exact status, JSON content type, and body; each run
makes one upstream POST, uses the 0.166.2 hook identity, cleans its overlay,
and does not print the synthetic provider key.

The local comparison passed in private user, filesystem, and network
namespaces with loopback only. No real account or provider traffic was used.
This covers one process path and does not establish general quota, profile
rotation, session-affinity, or other-platform parity.
