# Empty-store Super profile selection against 0.165.1 and 0.439.2

Prodex `0.165.1` at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and `0.439.2`
at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` resolve an explicit profile in
`crates/prodex-runtime-launch/src/profile.rs::resolve_profile_name`. When the
requested name is absent from the loaded profile map, both return
`profile '<name>' does not exist`. The Super runtime-launch preparation calls
profile selection before probing or starting Codex.

The Linux oracle SHA-256 values are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
for 0.165.1 and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
for 0.439.2. The test verifies both hashes before execution.

The real-process control uses each checksum-pinned Linux executable and Modex
with an isolated synthetic home, empty profile store, and the existing local
Codex/provider fixtures. `--profile main` and `--profile ""` produce the same
exit status and complete stderr in all three processes. None starts Codex or
sends a provider request. No real credentials, external provider traffic, or
account login is used.

The release processes create profile-lifecycle and runtime-housekeeping lock
files before returning the error. Modex deliberately leaves those side effects
untouched and only retains the fixture's pre-existing `state/update-check.json`.
This narrow fix aligns the missing-profile result; it does not implement
profile-store locking, state recovery, selection of an existing profile,
runtime-broker bootstrap, or WebSocket transport. Nonempty profile state still
fails closed. No release qualification or general Super parity claim follows.

Run the focused comparison after `make build` and `make unit-build`:

```sh
PYTHONPATH=tests python3 -m unittest \
  test_super_launch_01651.ActiveSuperLaunchTests.test_missing_explicit_profile_matches_both_releases -v
```

The test verifies the 0.165.1 and 0.439.2 oracle hashes before comparing
production process output and side effects.
