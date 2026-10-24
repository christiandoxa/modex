# Modex

Modex is a new Mojo implementation targeting the behavior of Prodex 0.439.0
(`433aad44bb249d5c25a231a6b06c2fa522a39a1f`). It is under development and does
not yet provide feature parity. Unimplemented commands fail explicitly.

The product uses Mojo and its official standard library only. Prodex is a
test oracle, never a production dependency. Python standard library is used
only for separate complex differential and process tests.

Build on Linux x86-64 with the pinned official Mojo toolchain:

```sh
mojo --version  # Mojo 1.2.0 (2016d0cd)
make build
build/modex --version
```

Build flags target x86-64-v3 rather than the build machine's newer CPU features.
See [baseline and toolchain](docs/baseline.json), [parity inventory](docs/parity.json),
[capability evidence](docs/capabilities.json), and [next work](docs/handoff.md).
All six baseline release targets remain in scope; only Linux x86-64 has a local
execution environment. No release artifacts have been published.
