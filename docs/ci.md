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

The reference helper obtains the frozen 0.439.2 active release and the
explicitly historical source snapshots outside the repository, verifies release and
source identities, and accepts `MODEX_REFERENCE_CACHE` for its cache location.
If a successful official tag lookup returns no refs, source acquisition may
fetch only the previously pinned commit and verifies its complete Git tree.
Moved or malformed tags and lookup errors still fail. This recovers source
only: oracle acquisition still requires the pinned release bytes, so missing
release assets keep reference-dependent CI fail-closed.
`PRODEX_ORACLE` selects the active 0.439.2 executable; its SHA-256 must match
the pinned release. CI records active 0.439.2 checks before acquiring the
0.165.1 and 0.439.5 historical oracles. Historical oracle tests use
`PRODEX_ORACLE_01651` and `PRODEX_ORACLE_04395`. Full CI retains the pinned
0.439.1 source snapshot for regression-only source checks. Missing required
reference assets fail CI. Tests use synthetic credentials and loopback peers.
Required sandbox or reference checks fail if their prerequisites are missing;
a skip is not a pass.

Native unit programs compile with bounded parallelism; set `MODEX_UNIT_JOBS`
to override the default of four. Reuse requires a fingerprint of the Mojo
sources, compiler and standard-library files, target flags, and host, plus a
matching executable checksum and mode. Symlinks anywhere under `src/` or
`tests/`, and inside the compiler packages, are rejected. Cooperating
`make build`, `make unit`, and `make test` calls serialize
on the canonical build directory; `make test` holds the lock through Python
execution. Use separate build directories for independently running CI jobs.

The strict Python runner can partition discovered tests by module with
`--shard-index N --shard-count M` (zero-based). It validates test IDs and
exactly-one ownership and rejects discovery errors, empty shards, invalid
skips, and fixture/class-wide skips. Fast CI runs its artifact, shard-runner,
census and workflow helper tests in two independent shards, so they run even
when a required historical oracle is unavailable. Local `make ci-fast` runs
the same helpers directly. A regression checks ownership in both modes.

The Fast producer verifies a clean source checkout before building and again
before packaging. The success-gated artifact consumer checks the producer's
commit, run and attempt, target, flags, compiler, runtime, standard-library
hashes, executable mode and checksums before executing the transferred Modex
binary. A rerun of the consumer uses the original producer attempt. The downloaded bundle
accepts only its two expected regular files. The producer still runs the
remaining fast tests; other test groups, native artifacts, timing-based
balancing and broader cross-job isolation remain open. The new hosted handoff
has not yet been validated by GitHub Actions. Workflow evidence is uploaded
as run artifacts.
