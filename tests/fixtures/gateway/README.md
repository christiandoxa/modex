# Frozen gateway CLI observations

`cases.json` records Prodex 0.439.0 at
`433aad44bb249d5c25a231a6b06c2fa522a39a1f`, using the checksum-pinned Linux
oracle `2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a`.
Reproduce with `python3 tests/capture_gateway.py`.

The thirteen cases contain help, ten parse errors and two DeepSeek startup
failures. Inputs use synthetic credentials, temporary HOME/config/state,
ephemeral loopback endpoints and a private synthetic current-version update
cache. The cache prevents a live update notice from affecting captured output.
Each case retains exit status, exact stdout/stderr, upstream observations and
filesystem snapshots/deltas. File modes are observations of the captured
environment; other umasks and non-host platforms remain unverified.

The forced gateway path excludes local rewrite. Empty synthetic state reports
no available profile; a profileless `model_provider = "prodex-deepseek"`
configuration reports no compatible proxy. Neither sends an upstream request.
These fixtures do not prove an operational DeepSeek gateway.

`tests/test_gateway.py` checks output compatibility and the separately retained
filesystem failure. `python3 tests/capture_gateway_mismatches.py` writes
`docs/evidence/gateway-mismatch.json` and exits 1 for that mismatch. The report
keeps baseline/current deltas and explicitly marks overall parity FAIL.
Modex omits real runtime/profile locks and housekeeping artifacts; tests do
not replace them with placeholder files or count matching error text as full
startup parity. Product code never loads these fixtures.

The `0600` config cases do not cover shared-write permissions. Run
`python3 tests/capture_gateway_permissions.py` for a separate `0664` probe.
The release proceeds to its factory error while Modex rejects the file; the
report retains this unapproved safe difference as FAIL.

Operational provider socket tests use the internal native driver in
`tests/test_local_rewrite.py`. The real Super process/preflight path remains
unfinished; it is not replaced by a new public command.
