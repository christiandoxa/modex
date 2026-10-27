# CI and local reproduction

GitHub Actions runs the fast checks on pushes to `main`, pull requests, and
manual dispatch. Full validation runs weekly or on manual dispatch; a full
40-character `source_sha` selects an exact commit and its run is not cancelled
by later pushes. A separate manually dispatched parity-completeness workflow
fails while any contract, required platform, or release qualification is open.
Engineering CI passing is not a parity verdict.

The initial supported CI host is Linux x86-64. The bootstrap installs the
SHA-256-pinned official Mojo 1.2.0 compiler and libraries, verifies Python
3.14 with `compression.zstd`, checks util-linux `flock --close`, and exercises
the required bubblewrap namespaces.
GitHub workflows pin Python 3.14.10. Other release targets remain in the
inventory as unverified or blocked until their actual builds and tests run.

From a clean checkout, run:

```sh
make ci-bootstrap
make ci-fast
make ci-full
make ci-parity
```

`make ci-fast` builds production and native units and runs focused Python
checks. `make ci-full` runs the complete suite and probes; it currently requires
the checkout's `build/` directory because some historical test harnesses still
address that path. `make ci-parity` is expected to fail until parity is complete.
The original `make build`, `make unit`, and `make test` entrypoints remain
available. Set `PYTHON` when the required interpreter is not `python3`.

The reference helper obtains the frozen active release and the explicitly
historical source snapshots outside the repository, verifies release and
source identities, and accepts `MODEX_REFERENCE_CACHE` for its cache location.
`PRODEX_ORACLE` can select an existing active-release executable; its SHA-256
must match the pinned release. Tests use synthetic credentials and loopback
peers. Required sandbox or reference checks fail if their prerequisites are
missing; a skip is not a pass.

Native unit programs compile with bounded parallelism; set `MODEX_UNIT_JOBS`
to override the default of four. Reuse requires a fingerprint of the Mojo
sources, compiler and standard-library files, target flags, and host, plus a
matching executable checksum and mode. Symlinks anywhere under `src/` or
`tests/`, and inside the compiler packages, are rejected. Cooperating
`make build`, `make unit`, and `make test` calls serialize
on the canonical build directory; `make test` holds the lock through Python
execution. Use separate build directories for independently running CI jobs.

Workflow evidence is uploaded as run artifacts. Test sharding, verified
immutable cross-job artifacts, and timing-based balancing remain unfinished.
