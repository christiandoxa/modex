# Hook initialization identity

The checksum-verified official Prodex 0.166.2 Linux x86-64 release and the
Modex production executable were exercised through their Super launch paths
with a synthetic Codex child and loopback provider. Both sent
`prodex-hook-trust` version `0.166.2` in the initialization request, made one
synthetic upstream request, and cleaned the temporary overlay. The test ran
with isolated home and storage in private user, network, and filesystem
namespaces; no provider credentials or external traffic were used.

This covers one Linux launch and its initialization identity, not native
session resume or overall parity. `tests/test_hook_identity_01662.py` retains
the oracle digest and the process comparison.
