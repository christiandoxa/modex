# Modex

Modex is a new Mojo implementation targeting the behavior of Prodex 0.439.0
(`433aad44bb249d5c25a231a6b06c2fa522a39a1f`). It is under development and does
not yet provide feature parity. Version output and development session
inspection are connected to the production CLI. Session inspection reads plain
and Zstandard rollouts and prints JSON or plain tables with supported Unicode.
Session state recovery, the interactive terminal view, resume, and baseline
startup side effects remain incomplete. Known output differences are tracked
in [verified gaps](docs/known-gaps.md).

The product uses Mojo and its official standard library only. Prodex is a
test oracle, never a production dependency. Python standard library is used
only for separate complex differential and process tests.

Build on Linux x86-64 with the pinned official Mojo toolchain:

```sh
mojo --version  # Mojo 1.2.0 (2016d0cd)
make build
build/modex --version
build/modex session list --json
make test
```

Build flags target x86-64-v3 rather than the build machine's newer CPU features.
See [baseline and toolchain](docs/baseline.json), [parity inventory](docs/parity.json),
[capability evidence](docs/capabilities.json), and [next work](docs/handoff.md).
All six baseline release targets remain in scope; only Linux x86-64 has a local
execution environment. No release artifacts have been published.

Tests require Python 3.14 or later, including its standard `compression.zstd`
module. The test suite includes native Mojo unit checks and isolated differential
checks against the official Linux release. Download that oracle and its
`SHA256SUMS` outside the repository; set `PRODEX_ORACLE` to its absolute path.
The harness checks the pinned SHA-256 before using it. `bubblewrap` is a test
prerequisite for filesystem/network isolation, never a product dependency.
Output matches do not establish full session parity: reproducible failures
are retained in [session mismatch evidence](docs/evidence/session-mismatches.json).
