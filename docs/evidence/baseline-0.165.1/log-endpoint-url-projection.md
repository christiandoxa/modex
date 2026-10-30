# Operational endpoint URL projection (2026-10-30)

## Release trace

At 0.165.1 source commit `10ae15b5d1806302b60f051e4e6fec788044f4c2` and
frozen 0.439.2 commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`, operational
`log stream` projection uses `Url::parse(url)`, takes a nonempty URL path, and
falls back to `upstream` when parsing fails or the path is empty. The relevant
`log_stream.rs` files are identical at both commits.

Differential URL probes found two concrete projection differences:

- `custom://example.test` and `custom://example.test?token=/hidden` have empty
  paths in both releases and display `path=upstream`; Modex previously displayed
  `path=/`.
- `file://localhost/a\b` and `file://localhost/a\..\b` use backslashes as
  file-URL path separators in both releases and display `path=/a/b` and
  `path=/b`; Modex previously percent-encoded the backslashes.

`src/modex/log_operational.mojo` now preserves the empty-path fallback for
non-special schemes and normalizes file-scheme backslashes before path
normalization. Query strings remain excluded from the displayed endpoint.

## Process checks

`tests/test_log_endpoint_projection_01651_04392.py` runs isolated `log stream`
processes against both pinned release binaries and Modex. It compares complete
output and asserts the expected path for each case. The 0.165.1 binary is
checksum-verified as
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`; the
0.439.2 binary uses the pinned `test_cli.ORACLE` checksum.

The interactive TUI remains guarded. Mojo 1.2.0's public standard library does
not expose raw terminal settings, terminal resize ioctls, or signal handlers;
using direct libc calls would violate the no-new-native-bindings rule. Details
are recorded in `log-terminal-fallback.md`.

## Verification

- `mojo --version` reports `Mojo 1.2.0 (2016d0cd)`.
- `make build` passed after the projection change.
- `python scripts/ci/run-unittest.py test_log_endpoint_projection_01651_04392.py` passed one three-process test.
- `python scripts/ci/run-unittest.py test_log_operational.py test_log_endpoint_projection_01651_04392.py test_log_plain_parser_01651_04392.py` passed four tests.
- `python scripts/ci/run-unittest.py test_ci_oracle_routing.py` passed 9 tests.
- `python scripts/ci/check-product-dependencies.py` passed for 71 Mojo files.
- `python scripts/ci/check-test-census.py` found one suite owner for each of 50 native test sources and 152 Python modules.
- `bash -n scripts/ci/run-fast.sh scripts/ci/run-full.sh` passed.
- `git diff --check` passed.

Complete URL parser equivalence and non-host targets remain unverified; parity
statuses and the six-target denominator are unchanged.
