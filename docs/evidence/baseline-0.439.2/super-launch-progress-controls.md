# Super launch progress controls against Prodex 0.439.2

The frozen reference is Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. The test runs its verified Linux
oracle and Modex with a synthetic Codex script, private storage roots, and a
loopback provider. No provider request is made.

The below-minimum version, app-server capability failure, and child-start
controls match for exit status, stdout, normalized stderr, probe arguments,
process trace, and upstream request count. Both runs remove the temporary
profile overlay. The child-start runs retain the same synthetic session data.

Prodex creates additional state in all three controls: `state/profile-lifecycle.json.lock`,
`state/runtime-housekeeping.lock`, `state/runtime-housekeeping.last-run`, and
one `state/runtime-broker-live-runtime-*.json.lock`. The child-start control
also leaves `state/runtime-local-proxy-leases` and
`shared/sessions/.prodex-maintenance.lock`. Modex creates none of these paths.
The test asserts this inventory separately from output parity; runtime
housekeeping, broker ownership, session locks, and lease persistence remain
unfinished.

Reproduce after `make build` with:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
PYTHONPATH=tests python3 -m unittest \
  test_super_launch.SuperLaunchTests.test_launch_progress_and_probe_errors_match_historical_release
```

This checks three Linux x86-64 launch controls only. It does not establish
Codex path-selection parity or full Super parity.
