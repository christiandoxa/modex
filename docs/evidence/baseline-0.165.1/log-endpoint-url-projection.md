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

The expanded process corpus reproduced additional gaps for `custom:///foo`,
`file://C:/a`, `file://c|/a`, invalid percent-encoded and IDNA-mapped hosts,
and path characters `|` and `^`. Both releases map file drive authorities to
`/C:/a`, preserve a literal pipe in file paths, reject forbidden host
characters, and omit query/fragment text from display.

`src/modex/log_operational.mojo` preserves empty-path fallback for non-special
schemes, handles empty-authority paths and Windows drive-letter authorities,
checks percent-decoded host delimiters, and preserves `|`/`^` in paths. File
backslashes normalize before dot-segment removal; query and fragment text stay
excluded from display.

## Process checks

`tests/test_log_endpoint_projection_01651_04392.py` runs isolated `log stream`
processes against both pinned release binaries and Modex for 23 synthetic URL
cases. It compares complete output and asserts each expected path, including
query/fragment omission. The 0.165.1 binary is
checksum-verified as
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`; the
0.439.2 binary uses the pinned `test_cli.ORACLE` checksum.

The interactive TUI remains guarded. Mojo 1.2.0's public standard library does
not expose raw terminal settings, terminal resize ioctls, or signal handlers;
using direct libc calls would violate the no-new-native-bindings rule. Details
are recorded in `log-terminal-fallback.md`.

The shared authority validator also serves Super URL validation and DeepSeek
beta URL checks. `test_super_cli.py` sends malformed percent hosts, including
the encoded `%40` credential separator, unescaped forbidden host characters,
invalid UTF-8, and mapped IDNA separators through real Super processes with a
synthetic API-key sentinel. Both pinned releases and Modex reject each before
launch without printing the key. Existing DeepSeek beta URL tests cover its
separately decoded configuration path.

## Verification

- `mojo --version` reports `Mojo 1.2.0 (2016d0cd)`.
- `rtk make build` passed with Mojo 1.2.0.
- `mojo run -I src tests/test_log_operational.mojo` and `mojo run -I src tests/test_super_cli.mojo` passed.
- `MODEX_BINARY=<absolute build/modex path> python3 scripts/ci/run-unittest.py test_log_endpoint_projection_01651_04392.py test_log_operational.py test_log_plain_parser_01651_04392.py` passed four tests.
- `PYTHONPATH=tests MODEX_BINARY=<absolute build/modex path> python3 -m unittest -v test_super_cli.SuperCliTests.test_invalid_percent_encoded_url_hosts_fail_before_launch test_provider_tools_04392_characterization.ProviderTool04392CharacterizationTests.test_non_strict_invalid_beta_urls_fail_before_codex_or_provider test_provider_tools_04392_characterization.ProviderTool04392CharacterizationTests.test_fullwidth_beta_hosts_reject_mapped_forbidden_host_chars` passed three tests; the synthetic API key was not printed.
- `python3 scripts/ci/check-product-dependencies.py` passed for 71 Mojo files.
- `python3 scripts/ci/check-test-census.py` found one suite owner for each of 50 native test sources and 155 Python modules.
- Python syntax checks and `git diff --check` passed.

Complete URL parser equivalence and non-host targets remain unverified; parity
statuses and the six-target denominator are unchanged.
