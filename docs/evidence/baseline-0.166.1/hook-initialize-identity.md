# Super hook initialization identity

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.1 as active describe the original capture.

Prodex 0.166.1 at `4951b813ca308fb0ba7148dbc6d6aeb74b93cd32` identifies
its hook-trust app-server client with the release package version in
`crates/prodex-app/src/runtime_tools/hook_trust.rs`. Modex previously sent
`0.166.0`, the preceding reference version.

The connected Super preflight now sends `0.166.1`. The active-release
process test checks the initialize request against the checksum-verified
Linux oracle and Modex using a synthetic child and loopback peer. The
historical 0.166.0 comparison retains its original expected identity and
explicitly expects the updated Modex identity.

The comparison covers this initialization identity on Linux x86-64; it does
not establish full hook, app-server, or cross-platform parity.
