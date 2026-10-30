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

The reference helper obtains the frozen 0.166.0 active release and the
explicitly historical source snapshots outside the repository, verifies release and
source identities, and accepts `MODEX_REFERENCE_CACHE` for its cache location.
If a successful official tag lookup returns no refs, source acquisition may
fetch only the previously pinned commit and verifies its complete Git tree.
Moved or malformed tags and lookup errors still fail. This recovers source
only: oracle acquisition still requires the pinned release bytes, so missing
release assets keep reference-dependent CI fail-closed.
`PRODEX_ORACLE` selects the active 0.166.0 executable; its SHA-256 must match
the pinned release. Historical oracle tests use `PRODEX_ORACLE_01651`,
`PRODEX_ORACLE_04392`, and `PRODEX_ORACLE_04395`; their results are not
0.166.0 acceptance evidence. Full CI retains the pinned 0.439.1 source
snapshot for regression-only source checks. Missing required
reference assets fail CI. Tests use synthetic credentials and loopback peers.
Required sandbox or reference checks fail if their prerequisites are missing;
a skip is not a pass.

`python3 tests/capture_cli.py` uses the checksum-pinned active `PRODEX_ORACLE`
and writes `docs/cli-inventory-0.166.0.json` with help fixtures under
`docs/evidence/baseline-0.166.0/help/`. It leaves the historical
`docs/cli-inventory.json` and `docs/evidence/baseline/help/` untouched. Help
output is discovery evidence only; source tracing and behavior comparisons are
still required.

On 2026-10-30 the historical 0.439.2 tag lookup returned no ref and its
official SHA256SUMS URL returned HTTP 404. A clean hosted runner without the
previously verified historical bytes therefore cannot run that regression
lane; acquisition fails closed. Active 0.166.0 tests run first, and the
historical failure is reported separately as blocked. This does not make
0.439.2 the active target or count the missing regression lane as passed.
When the 0.439.2 oracle or source is unavailable, CI attempts independent
checks whose references are available and marks dependent lanes blocked. Full
CI does not run or claim a complete suite in that case. Either script still
returns a failing result; another missing reference or a failed independent
check can stop the run before all independent checks complete.
Hosted Fast CI run [41097956030](https://github.com/christiandoxa/modex/actions/runs/41097956030)
passed the active 0.166.0 lane and the available independent checks on its
recorded commit, then failed closed for the missing required historical
0.439.2 and 0.439.5 oracles. This is not a complete CI or parity pass.
The width-RSS measurements and metric fixtures run independently; their
0.439.2 session comparisons are a separate historical lane. If that oracle or
source is missing, CI reports the comparisons as blocked and makes no parity
claim. If 0.439.2 is available but another required reference is missing, Full
CI runs the independent width checks and 0.439.2 comparisons before blocking
its complete suite.

The historical 0.439.5 oracle is also required for its regression lane. If it
is unavailable, Fast CI marks the 0.439.5-only and cross-release lanes blocked,
then runs its independent helper and width-memory checks before failing. Full
CI marks those comparisons and the complete suite blocked, then runs available
source checks, native units, width-memory checks, platform probes, and
capability probes before failing. Missing historical bytes never count as a
pass or change the active 0.166.0 target.

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
