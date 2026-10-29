# Selected 0.165.1 CLI observations

The official Linux x86-64 artifact is pinned in `reference-verification.json`.
On Mojo 1.2.0 (2016d0cd), `tests/test_cli_01651.py` compared the production
Modex binary with that artifact using isolated homes, empty PATH, and no real
credentials. Leading `--version` and `-V` with six different tails produced
the respective product identities and no home mutations. Five root-help forms
and a custom executable name matched after the documented identity mapping;
the isolated homes stayed unchanged. These comparisons passed on 2026-10-29.

These observations do not cover all command-line parsing, installation,
security, startup paths, or any non-Linux target; they do not establish full
contract or release parity.

The read-only `update --help`, `update -h`, `help update`, and tested trailing
argument forms now match 0.165.1 after executable-name mapping, with no home
mutations. Update execution itself remains unimplemented.

The `update` argument parser now matches selected 0.165.1 help, invalid option,
positional, literal separator, attached value and custom-executable cases. The
isolated comparisons verify exit status, stdout, stderr and no home mutations.
Bare update still fails closed; update execution and untested combinations are
not qualified.

Gateway parser precedence now matches the pinned 0.165.1 process for both
Presidio conflict orders, valid interleaved options, duplicate flags, unknown
options and help ordering. Prodex source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` defines `--provider` as a parsed
value option; the lone value `-` therefore reaches provider validation and
reports `invalid value '-'`, while a following option still reports a missing
value. `tests/test_gateway_cli_01651.py` covers 17 isolated process-precedence
cases and seven unknown-option cases after separate and attached values,
including synthetic API keys without echoing them. The provider-dash comparison
also matches the active 0.439.2 binary.

Gateway help parsing now matches the active 0.439.2 and historical 0.165.1
processes (oracle SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
and `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`) for
short clusters beginning with `-h`, unknown short options before help, and
attached `--help=value` diagnostics. The 0.439.2 process regression also checks
Clap's generated usage after switches and attached versus split values, with a
synthetic API-key sentinel absent from both output streams.

The profileless DeepSeek startup classification now matches all three pinned
references when the shared Codex config has unrelated top-level or nested
settings in addition to `model_provider = "prodex-deepseek"`. The actual
Modex process, both checksum-pinned 0.165.1 and 0.439.2 processes, and the
available historical 0.439.1 process exit with the same no-proxy error and send
no request to the synthetic loopback peer. This selected failed-startup case
does not qualify successful Gateway startup, provider attempts, lifecycle file
deltas, or other config shapes; see
`docs/evidence/baseline-0.165.1/gateway-config-classification.md`.

On 2026-10-29, `make build`,
`make unit-compile-internal UNIT_BUILD_PROGRAMS=test_gateway_cli`,
`build/tests/test_gateway_cli`, and
`python3 scripts/ci/run-unittest.py test_gateway_cli.py test_gateway_cli_01651.py`
passed. Gateway CLI/startup suites, the native Gateway argument program, the
production import audit and test-census audit also passed for the selected
classification case. Successful Gateway startup, provider attempts, lifecycle
filesystem deltas and untested argument combinations remain unqualified.

For `help update`, three unknown subcommands containing `=` now retain the
whole argument in the diagnostic, matching the 0.165.1 executable and the
historical 0.439.2 executable. The isolated checks compare exit status, output,
and home mutations; they do not qualify other argument combinations.
