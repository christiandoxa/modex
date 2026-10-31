# Repeated Super launch characterization

`tests/test_super_repeat_launch_01661.py` runs a real Super launch against the
checksum-pinned Prodex 0.166.1 Linux binary and Modex. Both use an isolated
temporary home, a synthetic Codex child, a synthetic provider key, and a
loopback-only upstream fixture. The child exits 7 before making a provider
request. The harness adds a synthetic history record between launches.
Reproduce with `python3 scripts/ci/run-unittest.py test_super_repeat_launch_01661.py`
after building Modex.

Prodex starts the child on both launches and returns 7 both times. Modex returns
7 on the first launch, then returns 1 before starting the child again because
the existing shared session and history paths are not yet reconciled. The
synthetic session and history record remain present, no provider request is
sent, and both runs leave no temporary overlay. This test records an active
0.166.1 mismatch; it does not count as parity.

The frozen release holds a shared session-maintenance lock while the child is
running and uses an exclusive lock for maintenance. Mojo 1.2.0 supports
append-mode file opens but exposes no compatible advisory locking API. Opening
history in append mode without matching session coordination would leave
concurrent launches and maintenance unsafe, so Modex keeps the current guard.
The test covers sequential launches only and does not establish concurrent
behavior, broader session storage, or parity on other release targets.
